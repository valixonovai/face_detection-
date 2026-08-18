"""
Kameralar reyestri — kameralar endi `config.yaml`da emas, bazada saqlanadi,
shuning uchun ularni UI orqali qo'shish/o'chirish mumkin.

`config.yaml` faqat birinchi ishga tushirishda boshlang'ich qiymat sifatida
ishlatiladi (baza bo'sh bo'lsa).
"""
import re

from sqlalchemy import select

from app.cameras.rtsp import DEFAULT_RTSP_PORT, detect_brand, parse_rtsp_url
from app.config.settings import CONFIG
from app.db.models import DIRECTION_AUTO, ROLE_ENTRANCE, ROLE_MONITORING, Camera


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "camera"


def unique_camera_id(session, base: str) -> str:
    """Band bo'lmagan kalit qaytaradi: entrance, entrance_2, entrance_3 ..."""
    slug = slugify(base)
    candidate = slug
    suffix = 2
    while session.get(Camera, candidate) is not None:
        candidate = f"{slug}_{suffix}"
        suffix += 1
    return candidate


def _connection_fields(entry: dict) -> dict:
    """
    config.yaml yozuvidan ulanish maydonlarini oladi. Ikki shakl qo'llanadi:
    qismlarga ajratilgan (`host`/`username`/`password`) yoki tayyor `rtsp_url` —
    ikkinchisi qismlarga ajratib olinadi.
    """
    if entry.get("source_type", "rtsp") != "rtsp":
        return {}

    if entry.get("host"):
        stream_path = entry.get("stream_path", "/")
        brand, stream_kind = detect_brand(stream_path)
        return {
            "host": entry["host"],
            "port": entry.get("port", DEFAULT_RTSP_PORT),
            "username": entry.get("username"),
            "password": entry.get("password"),
            "brand": entry.get("brand", brand),
            "stream_kind": entry.get("stream_kind", stream_kind),
            "stream_path": stream_path,
        }

    parts = parse_rtsp_url(entry.get("rtsp_url"))
    if parts is None:
        # Ajratib bo'lmadi — manzilni o'z holicha saqlaymiz
        return {"rtsp_url": entry.get("rtsp_url")}

    brand, stream_kind = detect_brand(parts["path"])
    return {
        "host": parts["host"],
        "port": parts["port"],
        "username": parts["username"],
        "password": parts["password"],
        "brand": brand,
        "stream_kind": stream_kind,
        "stream_path": parts["path"],
    }


def seed_from_config(session) -> int:
    """
    Baza bo'sh bo'lsa, config.yaml'dagi kameralarni ko'chiradi.
    Qaytaradi: qo'shilgan kameralar soni.
    """
    existing = session.execute(select(Camera.id)).first()
    if existing is not None:
        return 0

    added = 0
    for entry in CONFIG.get("cameras", []):
        direction = entry.get("direction", "both")
        connection = _connection_fields(entry)
        session.add(
            Camera(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                source_type=entry.get("source_type", "rtsp"),
                device_index=entry.get("device_index"),
                **connection,
                # config.yaml'da rol tushunchasi yo'q edi — mavjud kameralar
                # kirish kamerasi deb hisoblanadi (avvalgi xatti-harakat shunday edi).
                role=entry.get("role", ROLE_ENTRANCE),
                direction=DIRECTION_AUTO if direction == "both" else direction,
                zone=entry.get("zone"),
                enabled=True,
            )
        )
        added += 1

    session.commit()
    return added


def active_cameras(session) -> list[Camera]:
    return list(
        session.execute(
            select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.name)
        ).scalars()
    )


def entrance_cameras(session) -> list[Camera]:
    return [c for c in active_cameras(session) if c.role == ROLE_ENTRANCE]


def monitoring_cameras(session) -> list[Camera]:
    return [c for c in active_cameras(session) if c.role == ROLE_MONITORING]
