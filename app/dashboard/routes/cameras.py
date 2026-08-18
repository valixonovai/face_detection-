from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import select

from app.cameras.camera_stream import webcam_backend_options
from app.cameras.probe import list_local_cameras, local_subnet, scan_network, test_connection
from app.cameras.registry import unique_camera_id
from app.cameras.rtsp import (
    BRAND_PRESETS,
    CUSTOM_BRAND,
    DEFAULT_BRAND,
    DEFAULT_RTSP_PORT,
    DEFAULT_STREAM,
    STREAM_KINDS,
    brand_choices,
    build_rtsp_url,
    normalize_path,
    stream_path_for,
)
from app.db.database import SessionLocal
from app.db.models import (
    DIRECTION_AUTO,
    DIRECTION_IN,
    DIRECTION_OUT,
    ROLE_ENTRANCE,
    ROLE_MONITORING,
    Camera,
)
from app.workers.camera_worker import current_service

bp = Blueprint("cameras", __name__, url_prefix="/cameras")

VALID_ROLES = {ROLE_ENTRANCE, ROLE_MONITORING}
VALID_DIRECTIONS = {DIRECTION_IN, DIRECTION_OUT, DIRECTION_AUTO}
VALID_BACKENDS = {name for name, _ in webcam_backend_options()}


BLANK_CONNECTION = {
    "device_index": None,
    "backend": None,
    "host": None,
    "port": None,
    "username": None,
    "password": None,
    "brand": None,
    "stream_kind": None,
    "stream_path": None,
    "rtsp_url": None,
}


def _form_connection() -> dict:
    """
    Formadagi ulanish maydonlarini Camera ustunlariga aylantiradi.

    RTSP uchun manzil yig'ilmaydi — IP, port, login, parol va oqim yo'li
    alohida saqlanadi; to'liq manzil kerak bo'lganda `resolved_rtsp_url()`
    ularni kodlab qo'shadi.
    """
    fields = dict(BLANK_CONNECTION)
    source_type = request.form.get("source_type", "rtsp")

    if source_type == "webcam":
        backend = request.form.get("backend", "").strip()
        fields["source_type"] = "webcam"
        fields["device_index"] = request.form.get("device_index", type=int) or 0
        fields["backend"] = backend if backend in VALID_BACKENDS else None
        return fields

    brand = request.form.get("brand", DEFAULT_BRAND)
    if brand not in dict(brand_choices()):
        brand = DEFAULT_BRAND
    stream_kind = request.form.get("stream_kind", DEFAULT_STREAM)
    if stream_kind not in STREAM_KINDS:
        stream_kind = DEFAULT_STREAM

    if brand == CUSTOM_BRAND:
        stream_path = normalize_path(request.form.get("stream_path", ""))
    else:
        stream_path = stream_path_for(brand, stream_kind)

    fields.update(
        source_type="rtsp",
        host=request.form.get("host", "").strip() or None,
        port=request.form.get("port", type=int) or DEFAULT_RTSP_PORT,
        username=request.form.get("username", "").strip() or None,
        password=request.form.get("password", ""),
        brand=brand,
        stream_kind=stream_kind,
        stream_path=stream_path,
    )
    return fields


@bp.route("")
def index():
    session = SessionLocal()
    try:
        cameras = list(session.execute(select(Camera).order_by(Camera.role, Camera.name)).scalars())
        session.expunge_all()
    finally:
        session.close()

    service = current_service()
    live = {c["id"]: c for c in service.metrics()["cameras"]} if service else {}

    return render_template(
        "cameras.html",
        active_page="cameras",
        cameras=cameras,
        live=live,
        subnet=local_subnet(),
        brands=brand_choices(),
        brand_paths={
            key: {"main": preset["main"], "sub": preset["sub"]}
            for key, preset in BRAND_PRESETS.items()
        },
        backends_local=[name for name, _ in webcam_backend_options() if name != "any"],
        custom_brand=CUSTOM_BRAND,
        default_brand=DEFAULT_BRAND,
        default_stream=DEFAULT_STREAM,
        default_port=DEFAULT_RTSP_PORT,
    )


@bp.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Kamera nomini kiriting.", "error")
        return redirect(url_for("cameras.index"))

    connection = _form_connection()
    if connection["source_type"] == "rtsp" and not connection["host"]:
        flash("Kameraning IP manzilini kiriting.", "error")
        return redirect(url_for("cameras.index"))

    role = request.form.get("role", ROLE_MONITORING)
    direction = request.form.get("direction", DIRECTION_AUTO)
    if role not in VALID_ROLES or direction not in VALID_DIRECTIONS:
        flash("Rol yoki yo'nalish noto'g'ri.", "error")
        return redirect(url_for("cameras.index"))

    session = SessionLocal()
    try:
        camera = Camera(
            id=unique_camera_id(session, name),
            name=name,
            role=role,
            direction=direction if role == ROLE_ENTRANCE else DIRECTION_AUTO,
            zone=request.form.get("zone", "").strip() or None,
            enabled=True,
            **connection,
        )
        session.add(camera)
        session.commit()
        flash(f"'{name}' kamerasi qo'shildi. Kuzatuv xizmati uni bir necha soniyada ulaydi.", "success")
    finally:
        session.close()
    return redirect(url_for("cameras.index"))


@bp.route("/<camera_id>/update", methods=["POST"])
def update(camera_id: str):
    session = SessionLocal()
    try:
        camera = session.get(Camera, camera_id)
        if camera is None:
            flash("Kamera topilmadi.", "error")
            return redirect(url_for("cameras.index"))

        camera.name = request.form.get("name", camera.name).strip() or camera.name
        role = request.form.get("role", camera.role)
        direction = request.form.get("direction", camera.direction)
        if role in VALID_ROLES:
            camera.role = role
        if direction in VALID_DIRECTIONS:
            camera.direction = direction if camera.role == ROLE_ENTRANCE else DIRECTION_AUTO
        camera.zone = request.form.get("zone", "").strip() or None

        connection = _form_connection()
        # Parol maydoni bo'sh qoldirilsa — saqlangani o'zgarmaydi. Aks holda
        # har bir tahrirda (nom yoki zonani o'zgartirganda ham) parol o'chib
        # ketardi, chunki forma uni hech qachon ochiq ko'rsatmaydi.
        if connection["source_type"] == "rtsp" and not connection["password"]:
            connection["password"] = camera.password

        for field, value in connection.items():
            setattr(camera, field, value)

        session.commit()
        flash("Kamera yangilandi.", "success")
    finally:
        session.close()
    return redirect(url_for("cameras.index"))


@bp.route("/<camera_id>/toggle", methods=["POST"])
def toggle(camera_id: str):
    session = SessionLocal()
    try:
        camera = session.get(Camera, camera_id)
        if camera:
            camera.enabled = not camera.enabled
            session.commit()
            flash(
                f"'{camera.name}' {'yoqildi' if camera.enabled else 'o‘chirildi'}.",
                "success",
            )
    finally:
        session.close()
    return redirect(url_for("cameras.index"))


@bp.route("/<camera_id>/delete", methods=["POST"])
def delete(camera_id: str):
    session = SessionLocal()
    try:
        camera = session.get(Camera, camera_id)
        if camera:
            session.delete(camera)
            session.commit()
            flash("Kamera tarmoqdan chiqarildi.", "success")
    finally:
        session.close()
    return redirect(url_for("cameras.index"))


def _webcam_owner(device_index: int, backend: str | None) -> str | None:
    """Shu (backend, indeks) qurilmasini hozir ishlatayotgan kamera nomi."""
    service = current_service()
    if service is None or not service.running:
        return None

    default_backend = webcam_backend_options()[0][0]
    wanted = backend or default_backend

    session = SessionLocal()
    try:
        cameras = session.execute(
            select(Camera).where(
                Camera.source_type == "webcam",
                Camera.device_index == device_index,
                Camera.enabled.is_(True),
            )
        ).scalars().all()
        for camera in cameras:
            if (camera.backend or default_backend) == wanted:
                return camera.name
        return None
    finally:
        session.close()


@bp.route("/test", methods=["POST"])
def test():
    """
    Saqlashdan oldin ulanishni sinash (AJAX).

    Manzil brauzerda emas, shu yerda yig'iladi — parol kodlanishi bir joyda
    bo'lishi uchun, va sinov aynan haqiqiy ulanishdagi manzilni tekshiradi.
    """
    data = request.get_json(silent=True) or {}
    source_type = data.get("source_type", "rtsp")

    if source_type == "webcam":
        device_index = data.get("device_index") or 0
        backend = data.get("backend") or None
        if backend not in VALID_BACKENDS:
            backend = None
        owner = _webcam_owner(device_index, backend)
        if owner:
            # Windows'da bir kamerani ikki marta ochib bo'lmaydi: sinasak,
            # kuzatuv xizmatining ulanishi uziladi va u qayta ulanolmay qoladi.
            return jsonify(
                {
                    "ok": False,
                    "state": "busy",
                    "message": f"№{device_index} qurilmani '{owner}' kamerasi ishlatyapti "
                    f"— u allaqachon ulangan. Sinash uchun avval o'sha kamerani vaqtincha o'chiring.",
                }
            )
        ok, message = test_connection("webcam", None, device_index, backend=backend)
        return jsonify({"ok": ok, "message": message})

    password = data.get("password") or ""
    if not password and data.get("camera_id"):
        # Tahrirlashda parol maydoni bo'sh — saqlangan parol bilan sinaymiz
        session = SessionLocal()
        try:
            existing = session.get(Camera, data["camera_id"])
            password = (existing.password if existing else "") or ""
        finally:
            session.close()

    brand = data.get("brand", DEFAULT_BRAND)
    stream_kind = data.get("stream_kind", DEFAULT_STREAM)
    stream_path = (
        normalize_path(data.get("stream_path", ""))
        if brand == CUSTOM_BRAND
        else stream_path_for(brand, stream_kind)
    )

    rtsp_url = build_rtsp_url(
        data.get("host"),
        data.get("port") or DEFAULT_RTSP_PORT,
        data.get("username"),
        password,
        stream_path,
    )
    ok, message = test_connection("rtsp", rtsp_url, None)
    return jsonify({"ok": ok, "message": message})


@bp.route("/scan", methods=["POST"])
def scan():
    """Lokal tarmoqni skanerlab, kameraga o'xshash qurilmalarni qaytaradi."""
    data = request.get_json(silent=True) or {}
    devices = scan_network(data.get("subnet") or None)
    return jsonify({"devices": devices, "subnet": data.get("subnet") or local_subnet()})


@bp.route("/local", methods=["POST"])
def local():
    """Kompyuterga ulangan kameralarni (backend, indeks) bo'yicha topadi."""
    all_backends = [name for name, _ in webcam_backend_options() if name != "any"]

    session = SessionLocal()
    try:
        configured = session.execute(
            select(Camera.backend, Camera.device_index).where(
                Camera.source_type == "webcam", Camera.device_index.is_not(None)
            )
        ).all()
    finally:
        session.close()

    # Backendi "avtomatik" bo'lgan kamera ochilishda hammasini navbat bilan
    # sinaydi — demak o'sha indeksni har bir backendda band qiladi.
    in_use: set[tuple[str, int]] = set()
    for backend, index in configured:
        for name in ([backend] if backend else all_backends):
            in_use.add((name, index))

    return jsonify(
        {
            "devices": list_local_cameras(skip=in_use),
            "in_use": [{"backend": b, "index": i} for b, i in sorted(in_use)],
        }
    )
