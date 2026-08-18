import threading
import time

from sqlalchemy import select

from app import timeutil
from app.config.settings import CONFIG
from app.db.models import DIRECTION_IN, DIRECTION_OUT, AttendanceLog


class AttendanceTracker:
    """
    Tanilgan xodim uchun keldi/ketdi hodisasini aniqlaydi va bazaga yozadi.

    - debounce: bir xodim uchun ketma-ket yozuvlar orasida minimal interval
      (bir necha kamera ketma-ket ko'rsa ham takror yozilmasin).
    - Hodisa turi kameraning yo'nalishidan olinadi: kirish eshigi -> "in",
      chiqish eshigi -> "out". Yo'nalish "auto" bo'lsa (eshik bitta yoki
      yo'nalishni ajratib bo'lmasa) — oxirgi hodisaga qarab almashadi.

    Bir nechta kamera ipi (thread) bir vaqtda chaqirishi mumkin, shuning uchun
    holat lock bilan himoyalangan.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.debounce_seconds = CONFIG["attendance"]["debounce_seconds"]
        self._lock = threading.Lock()
        self._last_seen: dict[int, float] = {}
        self._last_event_type: dict[int, str] = {}
        self._load_last_events()

    def _load_last_events(self) -> None:
        session = self.session_factory()
        try:
            rows = session.execute(
                select(AttendanceLog.employee_id, AttendanceLog.event_type)
                .order_by(AttendanceLog.timestamp.asc())
            ).all()
            for employee_id, event_type in rows:
                self._last_event_type[employee_id] = event_type
        finally:
            session.close()

    def record(
        self,
        employee_id: int,
        camera_id: str,
        similarity: float,
        direction: str = "auto",
    ) -> dict | None:
        now_monotonic = time.monotonic()

        with self._lock:
            last_seen = self._last_seen.get(employee_id)
            if last_seen is not None and (now_monotonic - last_seen) < self.debounce_seconds:
                return None  # debounce ichida — yozuv yaratilmaydi
            self._last_seen[employee_id] = now_monotonic

            if direction in (DIRECTION_IN, DIRECTION_OUT):
                event_type = direction
            else:
                prev_type = self._last_event_type.get(employee_id)
                event_type = "out" if prev_type == "in" else "in"
            self._last_event_type[employee_id] = event_type

        session = self.session_factory()
        try:
            log = AttendanceLog(
                employee_id=employee_id,
                camera_id=camera_id,
                event_type=event_type,
                similarity=similarity,
                timestamp=timeutil.now(),
            )
            session.add(log)
            session.commit()
            return {"employee_id": employee_id, "event_type": event_type, "timestamp": log.timestamp}
        finally:
            session.close()
