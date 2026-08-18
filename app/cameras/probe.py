"""
Kamera ulanishini sinash va tarmoqdan kameralarni topish.
"""
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

import cv2

RTSP_PORT = 554
ONVIF_PORT = 80
PROBE_TIMEOUT = 0.35


MAX_LOCAL_DEVICE_INDEX = 6


def list_local_cameras(skip: set[tuple[str, int]] | None = None) -> list[dict]:
    """
    Kompyuterga ulangan kameralarni har bir backend bo'yicha alohida topadi.

    Natijada (backend, indeks) juftligi qaytadi — indeksning o'zi yetarli emas,
    chunki u backendga qarab boshqa qurilmani bildiradi.

    `skip` — allaqachon ishlatilayotgan juftliklar. Ular ochib ko'rilmaydi:
    Windows'da band kamerani ikkinchi marta ochish ishlamaydi va ishlayotgan
    ulanishni ham buzib qo'yadi.
    """
    from app.cameras.camera_stream import webcam_backend_options

    skip = skip or set()
    devices: list[dict] = []

    for backend_name, backend_const in webcam_backend_options():
        if backend_name == "any":
            continue  # "any" boshqa backendlardan biriga tushadi — takror bo'ladi
        for index in range(MAX_LOCAL_DEVICE_INDEX):
            if (backend_name, index) in skip:
                continue
            cap = cv2.VideoCapture(index, backend_const)
            try:
                if not cap.isOpened():
                    continue
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                height, width = frame.shape[:2]
                devices.append(
                    {
                        "backend": backend_name,
                        "index": index,
                        "width": int(width),
                        "height": int(height),
                        # Qora kadr — odatda virtual kamera yoki yopiq obyektiv
                        "usable": float(frame.mean()) > 1.0,
                    }
                )
            finally:
                cap.release()
    return devices


def test_connection(
    source_type: str,
    rtsp_url: str | None,
    device_index: int | None,
    backend: str | None = None,
) -> tuple[bool, str]:
    """Kameraga ulanib, haqiqiy kadr kelishini tekshiradi."""
    from app.cameras.camera_stream import CameraStream

    if source_type == "webcam":
        device_index = device_index or 0
    elif not rtsp_url:
        return False, "RTSP manzili yig'ilmadi — kamera IP manzilini kiriting."

    config = {
        "id": "__probe__",
        "source_type": source_type,
        "rtsp_url": rtsp_url,
        "device_index": device_index,
        "backend": backend,
    }
    stream = CameraStream.from_config(config)
    try:
        if not stream._open():
            return False, "Ulanib bo'lmadi — manzil, login/parol yoki tarmoqni tekshiring."
        frame = None
        for _ in range(20):
            ok, candidate = stream._cap.read()
            if ok and candidate is not None:
                frame = candidate
                break
        if frame is None:
            return False, "Ulandi, lekin kadr kelmadi."
        h, w = frame.shape[:2]
        return True, f"Ulanish muvaffaqiyatli — {w}×{h}"
    except Exception as exc:
        return False, f"Xato: {exc}"
    finally:
        if stream._cap is not None:
            stream._cap.release()


def _port_open(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def local_subnet() -> str | None:
    """Mashinaning lokal tarmog'i, masalan "192.168.1"."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # paket yuborilmaydi, faqat marshrutni aniqlaydi
        ip = sock.getsockname()[0]
        sock.close()
        return ip.rsplit(".", 1)[0]
    except OSError:
        return None


def scan_network(subnet: str | None = None, max_workers: int = 64) -> list[dict]:
    """
    Lokal tarmoqdagi RTSP (554) yoki ONVIF (80) portini ochiq qurilmalarni topadi.
    Bu kamera ekanligini kafolatlamaydi — foydalanuvchi tasdiqlaydi.
    """
    subnet = subnet or local_subnet()
    if not subnet:
        return []

    found: list[dict] = []
    lock = threading.Lock()

    def probe(last_octet: int) -> None:
        host = f"{subnet}.{last_octet}"
        has_rtsp = _port_open(host, RTSP_PORT)
        if not has_rtsp and not _port_open(host, ONVIF_PORT):
            return
        with lock:
            # Faqat manzil qaytariladi — login/parol va oqim yo'li formada
            # alohida tanlanadi, shuning uchun bu yerda URL yig'ilmaydi.
            found.append({"host": host, "rtsp": has_rtsp})

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pool.map(probe, range(1, 255))

    return sorted(found, key=lambda item: [int(p) for p in item["host"].split(".")])
