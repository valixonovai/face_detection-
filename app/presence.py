"""
Zona (xona/koridor) harakat yozuvlari.

Kuzatuv rolidagi kameralar davomatga ta'sir qilmaydi — ular faqat
"kim, qayerda, qachon" degan yozuvni yuritadi: "Aziz Karimov 14:20 da
2-qavat koridorida ko'rindi".
"""
import threading
import time

from app import timeutil
from app.db.models import PresenceEvent

# Bir xodim bitta kamerada shu vaqt ichida qayta yozilmaydi (soniya).
# Davomatdagi debounce'dan qisqaroq: harakat yozuvi tez-tez bo'lishi tabiiy,
# lekin har kadrda yozib bazani to'ldirmaslik kerak.
PRESENCE_DEBOUNCE_SECONDS = 120


class PresenceTracker:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._lock = threading.Lock()
        # kalit: (employee_id, camera_id)
        self._last_seen: dict[tuple[int, str], float] = {}

    def record(
        self,
        employee_id: int,
        camera_id: str,
        similarity: float,
        zone: str | None = None,
    ) -> dict | None:
        key = (employee_id, camera_id)
        now_monotonic = time.monotonic()

        with self._lock:
            last = self._last_seen.get(key)
            if last is not None and (now_monotonic - last) < PRESENCE_DEBOUNCE_SECONDS:
                return None
            self._last_seen[key] = now_monotonic

        session = self.session_factory()
        try:
            event = PresenceEvent(
                employee_id=employee_id,
                camera_id=camera_id,
                zone=zone,
                similarity=similarity,
                timestamp=timeutil.now(),
            )
            session.add(event)
            session.commit()
            return {"employee_id": employee_id, "zone": zone, "timestamp": event.timestamp}
        finally:
            session.close()
