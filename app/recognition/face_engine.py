import app.gpu_bootstrap  # noqa: F401 — CUDA/cuDNN DLL yo'llarini import'dan oldin ro'yxatdan o'tkazadi

import numpy as np
from insightface.app import FaceAnalysis

from app.config.settings import CONFIG


class FaceEngine:
    """InsightFace bilan yuzni aniqlash va embedding chiqarish (GPU)."""

    def __init__(self):
        rec_cfg = CONFIG["recognition"]
        self.app = FaceAnalysis(
            name=rec_cfg["model_name"],
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=rec_cfg["gpu_id"], det_size=tuple(rec_cfg["det_size"]))

    def detect(self, frame_bgr: np.ndarray):
        """Kadrdagi barcha yuzlarni qaytaradi: [{bbox, embedding, det_score}, ...]"""
        faces = self.app.get(frame_bgr)
        results = []
        for face in faces:
            embedding = face.normed_embedding  # allaqachon L2-normalized
            results.append(
                {
                    "bbox": face.bbox.astype(int).tolist(),
                    "embedding": embedding,
                    "det_score": float(face.det_score),
                }
            )
        return results


class FaceMatcher:
    """Bazadagi xodim embeddinglari bilan cosine similarity orqali solishtirish."""

    def __init__(self, employees: list):
        # employees: [(employee_id, full_name, embedding: list[float]), ...]
        self.ids = [e[0] for e in employees]
        self.names = [e[1] for e in employees]
        if employees:
            self.matrix = np.stack([np.array(e[2], dtype=np.float32) for e in employees])
        else:
            self.matrix = np.empty((0, 512), dtype=np.float32)
        self.threshold = CONFIG["recognition"]["similarity_threshold"]

    def best(self, embedding: np.ndarray) -> tuple[dict | None, float]:
        """
        Eng mos xodim va uning o'xshashligini qaytaradi.

        Ikkinchi qiymat (best_sim) chegaradan past bo'lsa ham qaytariladi —
        chaqiruvchi "bu umuman begona" (juda past) va "tanish, lekin noqulay
        burchak" (chegaraga yaqin) holatlarini ajrata olishi uchun.
        """
        if self.matrix.shape[0] == 0:
            return None, 0.0
        sims = self.matrix @ embedding.astype(np.float32)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])
        if best_sim >= self.threshold:
            return (
                {"employee_id": self.ids[best_idx], "name": self.names[best_idx], "similarity": best_sim},
                best_sim,
            )
        return None, best_sim

    def match(self, embedding: np.ndarray):
        return self.best(embedding)[0]
