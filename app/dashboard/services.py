import threading

from app.recognition.face_engine import FaceEngine

_engine = None
_engine_lock = threading.Lock()


def get_engine() -> FaceEngine:
    """Butun dashboard uchun bitta umumiy FaceEngine (GPU xotirasini tejash uchun)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = FaceEngine()
    return _engine


def loaded_engine() -> FaceEngine | None:
    """Model allaqachon yuklangan bo'lsa qaytaradi, aks holda None (yuklamaydi)."""
    return _engine
