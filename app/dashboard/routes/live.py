import time

import cv2
from flask import Blueprint, Response, abort, jsonify, render_template, request
from sqlalchemy import select

from app.dashboard.services import get_engine
from app.db.database import SessionLocal
from app.db.models import Camera
from app.workers.camera_worker import get_service

bp = Blueprint("live", __name__, url_prefix="/live")

RECOGNIZED_BGR = (74, 164, 22)   # tanilgan xodim — yashil
VISITOR_BGR = (52, 104, 235)     # begona — to'q sariq/qizil
UNKNOWN_BGR = (150, 150, 150)


def _service():
    service = get_service(get_engine)
    service.start()
    return service


@bp.route("")
def page():
    session = SessionLocal()
    try:
        cameras = list(
            session.execute(
                select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.role, Camera.name)
            ).scalars()
        )
        session.expunge_all()
    finally:
        session.close()

    _service()  # xizmatni ishga tushiramiz
    selected = request.args.get("camera") or (cameras[0].id if cameras else None)

    return render_template(
        "live.html",
        active_page="live",
        cameras=cameras,
        selected=selected,
    )


@bp.route("/feed/<camera_id>")
def feed(camera_id: str):
    service = _service()
    engine = get_engine()

    session = SessionLocal()
    try:
        camera = session.get(Camera, camera_id)
        if camera is None:
            abort(404)
        session.expunge_all()
    finally:
        session.close()

    def generate():
        last_seq = 0
        while True:
            # Bir xil kadrni qayta yubormaymiz — aks holda har bir ochiq
            # brauzer oynasi o'zgarmagan tasvirni tinimsiz qayta tahlil qilib
            # GPU'ni bekorga band qilardi.
            new_frame = service.get_frame_if_new(camera_id, last_seq)
            if new_frame is None:
                time.sleep(0.03)
                continue
            last_seq, frame = new_frame

            # Ko'rsatish uchun qayta aniqlaymiz: worker allaqachon hodisalarni
            # yozgan, bu yerda faqat ramka chizamiz.
            matcher = service.matchers.get()
            for face in engine.detect(frame):
                x1, y1, x2, y2 = face["bbox"]
                match, best_sim = matcher.best(face["embedding"])
                if match:
                    color, label = RECOGNIZED_BGR, f"{match['name']} {match['similarity']:.2f}"
                elif camera.role == "entrance":
                    color, label = VISITOR_BGR, "Begona"
                else:
                    color, label = UNKNOWN_BGR, "Noma'lum"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, max(y1 - 10, 18)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/events.json")
def events():
    service = _service()
    return jsonify(service.metrics())
