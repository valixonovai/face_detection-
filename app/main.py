"""
Asosiy runner: barcha kameralarni fon xizmati sifatida ishga tushiradi
(dashboard'siz). Kameralar, rollar va davomat qoidalari bazadan olinadi —
xuddi dashboard ishlatadigan xizmatning o'zi.

Ishlatish:
    python -m app.main

Eslatma: dashboard'ning "Jonli kamera" sahifasi ham shu xizmatni ishga
tushiradi. Ikkalasini bir vaqtda emas, faqat bittasini ishlating (lokal
webcam qurilmasi bir vaqtda bitta jarayon tomonidan ochiladi).
"""
import time

from app.db.database import init_db
from app.recognition.face_engine import FaceEngine
from app.workers.camera_worker import get_service

STATUS_INTERVAL = 10.0  # soniya — holatni ekranga chiqarish oralig'i


def main() -> None:
    init_db()

    service = get_service(FaceEngine)
    service.start()
    print("Kuzatuv xizmati ishga tushdi. Chiqish uchun Ctrl+C.")

    last_event_key = None
    try:
        while True:
            time.sleep(STATUS_INTERVAL)
            metrics = service.metrics()
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"kamera: {metrics['connected_count']}/{metrics['camera_count']} ulangan · "
                f"FPS: {metrics['total_fps']}"
            )
            # Oxirgi hodisani (agar yangi bo'lsa) ko'rsatamiz
            events = metrics.get("recent_events", [])
            if events:
                top = events[0]
                key = (top["time"], top["name"], top["kind"])
                if key != last_event_key:
                    last_event_key = key
                    print(f"    -> {top['time']} {top['name']} — {top['kind']} ({top['camera_name']})")
    except KeyboardInterrupt:
        print("\nTo'xtatilmoqda...")
        service.stop()


if __name__ == "__main__":
    main()
