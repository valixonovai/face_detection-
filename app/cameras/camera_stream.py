import sys
import threading
import time

import cv2


def webcam_backend_options() -> list[tuple[str, int]]:
    """
    Lokal kamera uchun backendlar — (nom, OpenCV konstantasi), sinash tartibida.

    Muhim: qurilma indeksi backendga qarab BOSHQA qurilmani bildiradi. Masalan
    DSHOW virtual kameralarni ham sanaydi, MSMF esa yo'q — shuning uchun bir xil
    "№0" ikki backendda ikki xil kamera bo'lishi mumkin. Kamerani ro'yxatga olish
    ham, ochish ham shuning uchun backend bilan birga saqlanadi.
    """
    if sys.platform == "win32":
        # DSHOW ataylab birinchi emas: ba'zi Windows kameralarida u bir necha
        # soniyadan keyin butunlay qora kadr qaytara boshlaydi. MSMF barqaror.
        return [("msmf", cv2.CAP_MSMF), ("any", cv2.CAP_ANY), ("dshow", cv2.CAP_DSHOW)]
    return [("any", cv2.CAP_ANY)]


def webcam_backends() -> list[int]:
    return [const for _, const in webcam_backend_options()]


def webcam_backend_const(name: str | None) -> int | None:
    """Backend nomi bo'yicha konstanta; nom bo'sh yoki noma'lum bo'lsa None."""
    return dict(webcam_backend_options()).get(name or "")


class CameraStream:
    """
    Video manbani (RTSP tarmoq kamerasi yoki lokal webcam) alohida threadda
    o'qiydi va faqat eng oxirgi kadrni saqlaydi. OpenCV VideoCapture ichki
    bufferi sabab yuzaga keladigan kechikishning (latency) oldini olish uchun
    shart — aks holda tanish real vaqtdan orqada qoladi. Ulanish uzilsa
    (RTSP uchun) avtomatik qayta ulanadi.

    source_type="rtsp"   -> source: RTSP URL (masalan Hikvision kamera)
    source_type="webcam" -> source: qurilma indeksi (odatda 0)
    """

    def __init__(
        self,
        camera_id: str,
        source,
        source_type: str = "rtsp",
        reconnect_delay: float = 3.0,
        backend: str | None = None,
    ):
        self.camera_id = camera_id
        self.source = source
        self.source_type = source_type
        self.reconnect_delay = reconnect_delay
        # Lokal kamera uchun aniq backend nomi ("msmf"/"dshow"/"any").
        # Bo'sh bo'lsa — barchasi navbat bilan sinaladi (eski xatti-harakat).
        self.backend = backend

        self._cap = None
        self._frame = None
        # Har bir yangi kadrda oshadi. Iste'molchi shu raqam orqali "bu kadrni
        # allaqachon ko'rganmanmi?" degan savolga javob oladi — aks holda oqim
        # uzilganda ham oxirgi kadr qayta-qayta qayta ishlanaverardi.
        self._frame_seq = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self.connected = False

    def start(self) -> "CameraStream":
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"cam-{self.camera_id}")
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()

    def _open(self) -> bool:
        for backend in self._backends():
            cap = (
                cv2.VideoCapture(int(self.source), backend)
                if self.source_type == "webcam"
                else cv2.VideoCapture(self.source, backend)
            )
            # Bufferni minimal qilamiz — eski kadrlar to'planib qolmasin
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if cap.isOpened() and self._yields_usable_frames(cap):
                self._cap = cap
                self.connected = True
                return True
            cap.release()
        return False

    def _backends(self) -> list[int]:
        if self.source_type != "webcam":
            return [cv2.CAP_FFMPEG]
        chosen = webcam_backend_const(self.backend)
        # Aniq backend tanlangan bo'lsa boshqasiga o'tmaymiz: indeks raqami
        # faqat o'sha backendda to'g'ri qurilmani bildiradi.
        return [chosen] if chosen is not None else webcam_backends()

    @staticmethod
    def _yields_usable_frames(cap, attempts: int = 15) -> bool:
        """
        Kamera ochilgani yetarli emas — ba'zi backendlar ochiladi-yu, faqat qora
        kadr beradi. Shuning uchun bir necha kadr o'qib, mazmunli tasvir
        kelayotganini tekshiramiz (kamera "isishi" uchun ham vaqt kerak).
        """
        for _ in range(attempts):
            ok, frame = cap.read()
            if ok and frame is not None and frame.mean() > 1.0:
                return True
            time.sleep(0.1)
        return False

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None or not self.connected:
                if not self._open():
                    time.sleep(self.reconnect_delay)
                    continue

            ok, frame = self._cap.read()
            if not ok:
                self.connected = False
                self._cap.release()
                self._cap = None
                # Oxirgi kadrni ham tashlaymiz: uzilgan kamera "muzlab qolgan"
                # tasvirni tirik oqim sifatida ko'rsatishi kerak emas.
                with self._lock:
                    self._frame = None
                time.sleep(self.reconnect_delay)
                continue

            # Nusxa olamiz: ba'zi backendlarda read() bir xil buferni qayta
            # ishlatadi — havolani saqlasak, keyingi o'qish uni ustidan yozib,
            # iste'molchi yarim yangilangan kadrni ko'radi.
            with self._lock:
                self._frame = frame.copy()
                self._frame_seq += 1

    def get_frame(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def get_frame_if_new(self, last_seq: int):
        """
        Oxirgi ko'rilganidan keyin yangi kadr kelgan bo'lsa `(seq, kadr)`,
        aks holda None. Bir xil kadrni ikki marta qayta ishlamaslik uchun.
        """
        with self._lock:
            if self._frame is None or self._frame_seq == last_seq:
                return None
            return self._frame_seq, self._frame.copy()

    @classmethod
    def from_config(cls, cam_config: dict) -> "CameraStream":
        source_type = cam_config.get("source_type", "rtsp")
        source = cam_config["device_index"] if source_type == "webcam" else cam_config["rtsp_url"]
        return cls(
            cam_config["id"],
            source,
            source_type=source_type,
            backend=cam_config.get("backend"),
        )
