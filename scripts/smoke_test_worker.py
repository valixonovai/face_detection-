"""Ko'p kamerali xizmatni qisqa sinash: kameralarni ochadi, bir necha soniya
ishlaydi va ko'rsatkichlarni chiqaradi."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import init_db
from app.recognition.face_engine import FaceEngine
from app.workers.camera_worker import get_service

init_db()

service = get_service(FaceEngine)
service.start()
print("xizmat ishga tushdi, 20 soniya kuzatiladi...")

for _ in range(4):
    time.sleep(5)
    m = service.metrics()
    print(
        f"  kameralar: {m['connected_count']}/{m['camera_count']} ulangan | "
        f"umumiy FPS: {m['total_fps']}"
    )
    for cam in m["cameras"]:
        print(
            f"    - {cam['name']} [{cam['role']}] ulangan={cam['connected']} "
            f"fps={cam['fps']} yuz={cam['faces_detected']} tanildi={cam['faces_recognized']}"
            + (f" XATO={cam['last_error']}" if cam["last_error"] else "")
        )

print("--- oxirgi hodisalar ---")
for event in service.metrics()["recent_events"]:
    print(f"  {event['time']} {event['camera_name']}: {event['name']} ({event['kind']})")

service.stop()
print("xizmat to'xtatildi")
