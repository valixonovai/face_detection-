from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.config.settings import CONFIG, database_url
from app.db.models import Base, Camera

_url = database_url()

# SQLite bo'lsa fayl papkasi mavjudligini ta'minlaymiz
if _url.startswith("sqlite"):
    Path(CONFIG["database"]["path"]).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(_url, echo=False, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Kamera ulanishi qismlarga ajratilganda qo'shilgan ustunlar.
# `create_all` mavjud jadvalga ustun qo'shmaydi, shuning uchun qo'lda qo'shamiz.
_CAMERA_COLUMNS = {
    "backend": "VARCHAR(16)",
    "host": "VARCHAR(160)",
    "port": "INTEGER",
    "username": "VARCHAR(120)",
    "password": "VARCHAR(255)",
    "brand": "VARCHAR(32)",
    "stream_kind": "VARCHAR(16)",
    "stream_path": "VARCHAR(255)",
}


def _add_missing_camera_columns() -> None:
    inspector = inspect(engine)
    if "cameras" not in inspector.get_table_names():
        return  # jadval endi yaratilgan — ustunlar allaqachon bor

    existing = {column["name"] for column in inspector.get_columns("cameras")}
    missing = {name: ddl for name, ddl in _CAMERA_COLUMNS.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl_type in missing.items():
            conn.execute(text(f"ALTER TABLE cameras ADD COLUMN {name} {ddl_type}"))


def _split_existing_rtsp_urls() -> None:
    """
    Eski yozuvlardagi to'liq RTSP manzilini qismlarga ajratadi, shunda ular ham
    yangi shaklda (login/parol alohida) tahrirlanadi. Ajratib bo'lmasa —
    `rtsp_url` o'z holicha qoladi va ulanish avvalgidek ishlayveradi.
    """
    from app.cameras.rtsp import detect_brand, parse_rtsp_url

    session = SessionLocal()
    try:
        cameras = session.execute(
            select(Camera).where(
                Camera.source_type == "rtsp",
                Camera.host.is_(None),
                Camera.rtsp_url.is_not(None),
            )
        ).scalars().all()

        migrated = 0
        for camera in cameras:
            parts = parse_rtsp_url(camera.rtsp_url)
            if parts is None:
                continue
            brand, stream_kind = detect_brand(parts["path"])
            camera.host = parts["host"]
            camera.port = parts["port"]
            camera.username = parts["username"]
            camera.password = parts["password"]
            camera.brand = brand
            camera.stream_kind = stream_kind
            camera.stream_path = parts["path"]
            camera.rtsp_url = None  # endi manzil qismlardan yig'iladi
            migrated += 1

        if migrated:
            session.commit()
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_camera_columns()
    _split_existing_rtsp_urls()

    # Kameralar bazada saqlanadi; birinchi ishga tushirishda config.yaml'dan ko'chiriladi
    from app.cameras.registry import seed_from_config

    session = SessionLocal()
    try:
        seed_from_config(session)
    finally:
        session.close()
