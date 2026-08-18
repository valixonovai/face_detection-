"""
Ko'p kamerali kuzatuv xizmati.

Bitta GPU modeli (FaceEngine) barcha kameralar uchun umumiy — 10+ kamerada ham
model xotiraga bir marta yuklanadi. Har bir kamera uchun alohida oqim ipi
(CameraStream) ishlaydi, tanish esa markazlashgan holda navbatma-navbat
bajariladi: GPU bitta bo'lgani uchun kadrlarni parallel emas, ketma-ket
qayta ishlash to'g'riroq (aks holda ular baribir GPU navbatida kutadi).

Kamera qo'shilsa yoki o'chirilsa xizmatni qayta ishga tushirish shart emas —
u davriy ravishda bazadagi kameralar ro'yxatini qayta o'qiydi.
"""
import threading
import time
from collections import deque

import numpy as np

from app.attendance import AttendanceTracker
from app.cameras.camera_stream import CameraStream
from app.cameras.registry import active_cameras
from app.config.settings import CONFIG
from app.db.database import SessionLocal
from app.db.models import ROLE_ENTRANCE
from app.presence import PresenceTracker
from app.recognition.matcher_cache import MatcherCache
from app.recognition.visitors import VisitorRegistry, is_confident_stranger

CAMERA_RELOAD_INTERVAL = 15.0  # soniya — kameralar ro'yxatini qayta o'qish
IDLE_SLEEP = 0.02


class CameraRuntime:
    """Bitta kameraning ishlash holati."""

    def __init__(self, camera):
        self.camera = camera
        self.stream = CameraStream.from_config(camera.as_stream_config()).start()
        self.frame_times: deque[float] = deque(maxlen=30)
        self.faces_detected = 0
        self.faces_recognized = 0
        self.last_error: str | None = None
        self.last_frame = None
        self.last_seq = 0  # oxirgi qayta ishlangan kadr raqami

    @property
    def fps(self) -> float:
        times = list(self.frame_times)
        if len(times) < 2:
            return 0.0
        span = times[-1] - times[0]
        return (len(times) - 1) / span if span > 0 else 0.0

    def stop(self) -> None:
        self.stream.stop()


class MultiCameraService:
    """Barcha yoqilgan kameralarni kuzatadi va hodisalarni bazaga yozadi."""

    def __init__(self, engine_factory):
        self.engine_factory = engine_factory
        self._engine = None
        self._runtimes: dict[str, CameraRuntime] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_reload = 0.0

        self.attendance = AttendanceTracker(SessionLocal)
        self.presence = PresenceTracker(SessionLocal)
        self.visitors = VisitorRegistry(SessionLocal)
        self.matchers = MatcherCache(SessionLocal)

        self.recent_events: deque[dict] = deque(maxlen=50)
        self.started_at: float | None = None

    # ---- hayotiy sikl -------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True, name="camera-service")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        with self._lock:
            for runtime in self._runtimes.values():
                runtime.stop()
            self._runtimes.clear()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- kameralar ro'yxatini sinxronlash ------------------------------

    def _sync_cameras(self) -> None:
        session = SessionLocal()
        try:
            cameras = active_cameras(session)
            # Obyektlarni sessiondan uzamiz — ular boshqa ipda ishlatiladi
            session.expunge_all()
        finally:
            session.close()

        wanted = {c.id: c for c in cameras}

        with self._lock:
            for camera_id in list(self._runtimes):
                if camera_id not in wanted:
                    self._runtimes.pop(camera_id).stop()

            for camera_id, camera in wanted.items():
                existing = self._runtimes.get(camera_id)
                if existing is None:
                    self._runtimes[camera_id] = CameraRuntime(camera)
                else:
                    # Sozlamalar o'zgargan bo'lsa oqimni qayta ochamiz
                    old, new = existing.camera, camera
                    if (old.source_type, old.rtsp_url, old.device_index) != (
                        new.source_type, new.rtsp_url, new.device_index
                    ):
                        existing.stop()
                        self._runtimes[camera_id] = CameraRuntime(camera)
                    else:
                        existing.camera = camera  # rol/zona/nom yangilanishi yetarli

    # ---- asosiy sikl ---------------------------------------------------

    def _run(self) -> None:
        self._engine = self.engine_factory()

        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - self._last_reload > CAMERA_RELOAD_INTERVAL:
                try:
                    self._sync_cameras()
                except Exception as exc:  # kamera ochilmasa xizmat to'xtamasin
                    print(f"[camera-service] kameralarni sinxronlashda xato: {exc}")
                self._last_reload = now

            with self._lock:
                runtimes = list(self._runtimes.values())

            if not runtimes:
                time.sleep(0.5)
                continue

            processed_any = False
            for runtime in runtimes:
                if self._stop_event.is_set():
                    break
                # Faqat YANGI kadr qayta ishlanadi. Aks holda oqim sekin bo'lsa
                # (yoki uzilib qolsa) bir xil kadr GPU'ga qayta-qayta yuborilib,
                # FPS va "topilgan yuzlar" ko'rsatkichlari soxta bo'lib ketardi.
                new_frame = runtime.stream.get_frame_if_new(runtime.last_seq)
                if new_frame is None:
                    continue
                runtime.last_seq, frame = new_frame
                processed_any = True
                try:
                    self._process(runtime, frame)
                    runtime.last_error = None
                except Exception as exc:
                    runtime.last_error = str(exc)

            if not processed_any:
                time.sleep(IDLE_SLEEP)

    def _process(self, runtime: CameraRuntime, frame) -> None:
        camera = runtime.camera
        faces = self._engine.detect(frame)

        runtime.frame_times.append(time.monotonic())
        runtime.faces_detected += len(faces)
        runtime.last_frame = frame

        if not faces:
            return

        matcher = self.matchers.get()
        for face in faces:
            embedding = face["embedding"]
            match, best_sim = matcher.best(embedding)

            if match is not None:
                runtime.faces_recognized += 1
                self._handle_known(camera, match, embedding)
                continue

            # Tanilmadi. Kirish kamerasi begonani ham qayd qiladi — lekin faqat
            # aniq begona bo'lsa: chegaraga yaqin (shubhali) kadrlar xodimning
            # noqulay burchagi bo'lishi mumkin, ularni mehmon qilib yozmaymiz.
            if camera.role != ROLE_ENTRANCE:
                continue
            if not is_confident_stranger(best_sim, face["det_score"], face["bbox"]):
                continue

            event = self.visitors.record(
                embedding,
                camera_id=camera.id,
                zone=camera.zone,
                frame=frame,
                bbox=face["bbox"],
            )
            if event:
                self._push_event(
                    camera,
                    name=event["label"],
                    kind="visitor_new" if event["is_new"] else "visitor_seen",
                )

    def _handle_known(self, camera, match: dict, embedding: np.ndarray) -> None:
        if camera.role == ROLE_ENTRANCE:
            event = self.attendance.record(
                match["employee_id"], camera.id, match["similarity"], direction=camera.direction
            )
            if event:
                self._push_event(camera, name=match["name"], kind=event["event_type"])
        else:
            event = self.presence.record(
                match["employee_id"], camera.id, match["similarity"], zone=camera.zone
            )
            if event:
                self._push_event(camera, name=match["name"], kind="presence")

    def _push_event(self, camera, name: str, kind: str) -> None:
        self.recent_events.appendleft(
            {
                "camera_id": camera.id,
                "camera_name": camera.name,
                "zone": camera.zone,
                "name": name,
                "kind": kind,  # in | out | presence | visitor_new | visitor_seen
                "time": time.strftime("%H:%M:%S"),
            }
        )

    # ---- ko'rsatkichlar -------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            runtimes = list(self._runtimes.values())

        cameras = [
            {
                "id": r.camera.id,
                "name": r.camera.name,
                "role": r.camera.role,
                "zone": r.camera.zone,
                "connected": r.stream.connected,
                "fps": round(r.fps, 1),
                "faces_detected": r.faces_detected,
                "faces_recognized": r.faces_recognized,
                "last_error": r.last_error,
            }
            for r in runtimes
        ]
        return {
            "running": self.running,
            "camera_count": len(cameras),
            "connected_count": sum(1 for c in cameras if c["connected"]),
            "total_fps": round(sum(c["fps"] for c in cameras), 1),
            "cameras": cameras,
            "uptime_seconds": int(time.monotonic() - self.started_at) if self.started_at else 0,
            "recent_events": list(self.recent_events)[:20],
        }

    def get_frame(self, camera_id: str):
        with self._lock:
            runtime = self._runtimes.get(camera_id)
        return runtime.stream.get_frame() if runtime else None

    def get_frame_if_new(self, camera_id: str, last_seq: int):
        with self._lock:
            runtime = self._runtimes.get(camera_id)
        return runtime.stream.get_frame_if_new(last_seq) if runtime else None

    def camera_for(self, camera_id: str):
        with self._lock:
            runtime = self._runtimes.get(camera_id)
        return runtime.camera if runtime else None


_service: MultiCameraService | None = None
_service_lock = threading.Lock()


def get_service(engine_factory) -> MultiCameraService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = MultiCameraService(engine_factory)
    return _service


def current_service() -> MultiCameraService | None:
    return _service
