"""
Asosiy runner: barcha kameralarni ishga tushiradi, har birida yuzlarni aniqlab
tanib, keldi/ketdi hodisalarini bazaga yozadi.

Ishlatish:
    python -m app.main
"""
import json
import time

from sqlalchemy import select

from app.attendance import AttendanceTracker
from app.cameras.camera_stream import CameraStream
from app.config.settings import CONFIG
from app.db.database import SessionLocal, init_db
from app.db.models import Employee
from app.recognition.face_engine import FaceEngine, FaceMatcher

EMPLOYEE_RELOAD_INTERVAL = 60.0  # soniya


def load_employees() -> list[tuple[int, str, list[float]]]:
    session = SessionLocal()
    try:
        rows = session.execute(select(Employee.id, Employee.full_name, Employee.embedding_json)).all()
        return [(eid, name, json.loads(emb)) for eid, name, emb in rows]
    finally:
        session.close()


def main() -> None:
    init_db()

    employees = load_employees()
    if not employees:
        print("Ogohlantirish: bazada birorta ham xodim yo'q. Avval `python -m app.recognition.enroll` bilan qo'shing.")
    matcher = FaceMatcher(employees)
    last_reload = time.monotonic()

    engine = FaceEngine()
    tracker = AttendanceTracker(SessionLocal)

    streams = [
        CameraStream.from_config(cam).start()
        for cam in CONFIG["cameras"]
    ]
    frame_skip = CONFIG["recognition"]["frame_skip"]
    skip_counters = {s.camera_id: 0 for s in streams}

    print(f"{len(streams)} ta kamera ishga tushirildi. Chiqish uchun Ctrl+C.")

    try:
        while True:
            now = time.monotonic()
            if now - last_reload > EMPLOYEE_RELOAD_INTERVAL:
                matcher = FaceMatcher(load_employees())
                last_reload = now

            for stream in streams:
                if skip_counters[stream.camera_id] > 0:
                    skip_counters[stream.camera_id] -= 1
                    continue
                skip_counters[stream.camera_id] = frame_skip

                frame = stream.get_frame()
                if frame is None:
                    continue

                faces = engine.detect(frame)
                for face in faces:
                    result = matcher.match(face["embedding"])
                    if result is None:
                        continue
                    event = tracker.record(result["employee_id"], stream.camera_id, result["similarity"])
                    if event:
                        ts = event["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        label = "KELDI" if event["event_type"] == "in" else "KETDI"
                        print(f"[{ts}] {stream.camera_id}: {result['name']} — {label} (sim={result['similarity']:.2f})")

            time.sleep(0.03)
    except KeyboardInterrupt:
        print("\nTo'xtatilmoqda...")
    finally:
        for stream in streams:
            stream.stop()


if __name__ == "__main__":
    main()
