"""
Xodim embeddinglarini keshlash.

Har bir kadr uchun bazadan o'qish qimmat — ayniqsa 10+ kamera bo'lganda.
Kesh davriy ravishda yangilanadi, shuning uchun yangi qo'shilgan xodim bir
necha soniyadan keyin tanila boshlaydi.
"""
import json
import threading
import time

from sqlalchemy import select

from app.db.models import Employee
from app.recognition.face_engine import FaceMatcher

RELOAD_INTERVAL = 20.0  # soniya


class MatcherCache:
    def __init__(self, session_factory, reload_interval: float = RELOAD_INTERVAL):
        self.session_factory = session_factory
        self.reload_interval = reload_interval
        self._lock = threading.Lock()
        self._matcher: FaceMatcher | None = None
        self._loaded_at = 0.0

    def _load(self) -> FaceMatcher:
        session = self.session_factory()
        try:
            rows = session.execute(
                select(Employee.id, Employee.full_name, Employee.embedding_json)
                .where(Employee.status == "active")
            ).all()
        finally:
            session.close()
        return FaceMatcher([(eid, name, json.loads(emb)) for eid, name, emb in rows])

    def get(self) -> FaceMatcher:
        now = time.monotonic()
        with self._lock:
            if self._matcher is None or (now - self._loaded_at) > self.reload_interval:
                self._matcher = self._load()
                self._loaded_at = now
            return self._matcher

    def invalidate(self) -> None:
        """Xodim qo'shilgan/o'chirilgan bo'lsa — keshni darhol eskirtiradi."""
        with self._lock:
            self._loaded_at = 0.0
