"""
Begona (tanilmagan) odamlarni qayd qilish.

Kirish kamerasi har bir odamni qayd qilishi kerak — xodim bo'lmasa ham.
Har safar yangi yozuv yaratmaslik uchun tanilmagan yuz avval mavjud
mehmonlar bilan solishtiriladi: o'xshashi topilsa, o'sha mehmonning
"oxirgi ko'rilgan" vaqti yangilanadi.
"""
import json
import threading
import time
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from sqlalchemy import func, select

from app import timeutil
from app.config.settings import CONFIG
from app.db.models import PresenceEvent, Visitor

# Mehmonlarni birlashtirish chegarasi. Xodimni tanish chegarasidan PASTROQ:
# bir odamning turli burchakdagi kadrlari "Mehmon #1, #2, #3" bo'lib
# ko'payib ketmasligi uchun birlashtirish kengroq bo'lishi kerak.
VISITOR_MATCH_THRESHOLD = 0.32

# Bitta mehmon uchun ketma-ket yozuvlar orasidagi minimal vaqt (soniya)
VISITOR_DEBOUNCE_SECONDS = 300

# Mehmon embeddinglari keshini to'liq qayta yuklash oralig'i (soniya).
# Bitta jarayon ichida qo'shilgan mehmon keshga darhol qo'shiladi (_cache_add);
# bu faqat boshqa manba (masalan ikkinchi worker) qo'shgan mehmonlarni ko'rish uchun.
RELOAD_INTERVAL = 20.0

# Yangi mehmon yaratish shartlari — "xodim, lekin noqulay burchak" holatini
# begona deb yozib yubormaslik uchun.
# Xodimga o'xshashlik shu qiymatdan past bo'lsagina begona hisoblanadi
# (tanish chegarasi 0.40 bo'lsa, 0.30–0.40 oralig'i "shubhali" — hech narsa yozilmaydi).
UNKNOWN_MAX_EMPLOYEE_SIMILARITY = 0.30
# Sifatsiz (kichik yoki noaniq) yuzdan mehmon yaratilmaydi
MIN_DETECTION_SCORE = 0.65
MIN_FACE_HEIGHT_PX = 60


def is_confident_stranger(best_employee_similarity: float, det_score: float, bbox) -> bool:
    """Yangi mehmon yozuvini yaratish o'rinlimi?"""
    if best_employee_similarity >= UNKNOWN_MAX_EMPLOYEE_SIMILARITY:
        return False  # xodimga yetarlicha o'xshaydi — shubhali, yozmaymiz
    if det_score < MIN_DETECTION_SCORE:
        return False
    x1, y1, x2, y2 = bbox
    return (y2 - y1) >= MIN_FACE_HEIGHT_PX


class VisitorRegistry:
    """Tanilmagan yuzlarni mehmon sifatida saqlaydi va takrorlarni birlashtiradi."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._lock = threading.Lock()
        self._last_seen: dict[int, float] = {}
        self._snapshot_dir = Path(CONFIG["paths"]["enrolled_faces_dir"]).parent / "visitors"
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Mehmon embeddinglari keshi. Avval har begona yuz uchun BARCHA
        # mehmonlarni bazadan qayta o'qirdik (O(V) so'rov har kadrda) — mehmon
        # soni ortgani sari sekinlashardi. Endi matritsa xotirada saqlanadi va
        # yangi mehmon qo'shilganda joyida yangilanadi (bazaga qayta murojaat
        # qilinmaydi); vaqti-vaqti bilan (RELOAD_INTERVAL) to'liq yangilanadi —
        # boshqa jarayon/ip tomonidan qo'shilgan mehmonlarni ham ko'rish uchun.
        self._cache_ids: list[int] = []
        self._cache_matrix = np.empty((0, 512), dtype=np.float32)
        self._cache_loaded_at = 0.0

    def _ensure_cache(self, session) -> None:
        now = time.monotonic()
        if self._cache_ids and (now - self._cache_loaded_at) < RELOAD_INTERVAL:
            return
        rows = session.execute(select(Visitor.id, Visitor.embedding_json)).all()
        self._cache_ids = [vid for vid, _ in rows]
        self._cache_matrix = (
            np.stack([np.array(json.loads(emb), dtype=np.float32) for _, emb in rows])
            if rows
            else np.empty((0, 512), dtype=np.float32)
        )
        self._cache_loaded_at = now

    def _match_existing_id(self, session, embedding: np.ndarray) -> int | None:
        """Eng o'xshash mehmonning id'sini qaytaradi (keshdan, DB so'rovsiz)."""
        self._ensure_cache(session)
        if not self._cache_ids:
            return None
        sims = self._cache_matrix @ embedding.astype(np.float32)
        best_idx = int(np.argmax(sims))
        if float(sims[best_idx]) >= VISITOR_MATCH_THRESHOLD:
            return self._cache_ids[best_idx]
        return None

    def _cache_add(self, visitor_id: int, embedding: np.ndarray) -> None:
        """Yangi mehmonni keshga qo'shadi — keyingi kadrda darhol tanilishi uchun."""
        self._cache_ids.append(visitor_id)
        row = embedding.astype(np.float32).reshape(1, -1)
        self._cache_matrix = (
            row if self._cache_matrix.shape[0] == 0 else np.vstack([self._cache_matrix, row])
        )

    def _save_snapshot(self, frame, bbox) -> str | None:
        """Yuz atrofidan kesib olib saqlaydi (mehmonni keyin tanib olish uchun)."""
        if frame is None:
            return None
        x1, y1, x2, y2 = bbox
        pad_x = int((x2 - x1) * 0.25)
        pad_y = int((y2 - y1) * 0.25)
        h, w = frame.shape[:2]
        crop = frame[
            max(0, y1 - pad_y): min(h, y2 + pad_y),
            max(0, x1 - pad_x): min(w, x2 + pad_x),
        ]
        if crop.size == 0:
            return None

        dest = self._snapshot_dir / f"{uuid4().hex}.jpg"
        cv2.imwrite(str(dest), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return str(dest)

    def record(
        self,
        embedding: np.ndarray,
        camera_id: str,
        zone: str | None = None,
        frame=None,
        bbox=None,
    ) -> dict | None:
        """
        Tanilmagan yuzni qayd qiladi. Qaytaradi: {"visitor_id", "label", "is_new"}
        yoki debounce ichida bo'lsa None.
        """
        session = self.session_factory()
        try:
            with self._lock:
                visitor_id = self._match_existing_id(session, embedding)

                if visitor_id is not None:
                    last = self._last_seen.get(visitor_id)
                    if last is not None and (time.monotonic() - last) < VISITOR_DEBOUNCE_SECONDS:
                        return None
                    self._last_seen[visitor_id] = time.monotonic()

                    visitor = session.get(Visitor, visitor_id)
                    visitor.last_seen = timeutil.now()
                    visitor.seen_count += 1
                    is_new = False
                else:
                    count = session.execute(select(func.count(Visitor.id))).scalar_one()
                    visitor = Visitor(
                        label=f"Mehmon #{count + 1}",
                        embedding_json=json.dumps(embedding.tolist()),
                        photo_path=self._save_snapshot(frame, bbox) if bbox is not None else None,
                        first_seen=timeutil.now(),
                        last_seen=timeutil.now(),
                        seen_count=1,
                    )
                    session.add(visitor)
                    session.flush()  # visitor.id kerak
                    self._last_seen[visitor.id] = time.monotonic()
                    self._cache_add(visitor.id, embedding)
                    is_new = True

                session.add(
                    PresenceEvent(
                        visitor_id=visitor.id,
                        camera_id=camera_id,
                        zone=zone,
                        similarity=0.0,
                        timestamp=timeutil.now(),
                    )
                )
                session.commit()
                return {"visitor_id": visitor.id, "label": visitor.label, "is_new": is_new}
        finally:
            session.close()
