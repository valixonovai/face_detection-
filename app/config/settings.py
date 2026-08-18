"""
Konfiguratsiya yuklash.

Qiymatlar ikki manbadan olinadi:
1. `config.yaml` — asosiy sozlamalar (kameralar, model, davomat qoidalari)
2. Muhit o'zgaruvchilari (env vars) — ular YAML qiymatlarini ustidan yozadi

Env vars Docker va AWS uchun muhim: parol/manzil kabi narsalarni kodga
yozmasdan, konteyner sozlamalari orqali beriladi.
"""
import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = Path(os.environ.get("APP_CONFIG_PATH", Path(__file__).resolve().parent / "config.yaml"))


def _resolve_path(value: str) -> str:
    """Nisbiy yo'lni loyiha ildiziga nisbatan to'liq yo'lga aylantiradi."""
    path = Path(value)
    return str(path if path.is_absolute() else BASE_DIR / path)


def _apply_env_overrides(cfg: dict) -> dict:
    # DATA_DIR — barcha o'zgaruvchan ma'lumot (baza, yuz rasmlari, loglar) uchun
    # yagona papka; Docker'da shu papka volume sifatida ulanadi.
    if data_dir := os.environ.get("DATA_DIR"):
        cfg["paths"]["enrolled_faces_dir"] = str(Path(data_dir) / "enrolled_faces")
        cfg["paths"]["logs_dir"] = str(Path(data_dir) / "logs")
        cfg["database"]["path"] = str(Path(data_dir) / "attendance.db")

    # Ma'lumotlar bazasi: to'liq URL (masalan AWS RDS PostgreSQL) yoki SQLite fayl yo'li.
    # Bular DATA_DIR'dan keyin qo'llanadi — aniq ko'rsatilgan qiymat ustun turadi.
    if database_url := os.environ.get("DATABASE_URL"):
        cfg["database"]["url"] = database_url
    if db_path := os.environ.get("DATABASE_PATH"):
        cfg["database"]["path"] = db_path

    if host := os.environ.get("DASHBOARD_HOST"):
        cfg["dashboard"]["host"] = host
    if port := os.environ.get("DASHBOARD_PORT"):
        cfg["dashboard"]["port"] = int(port)

    if threshold := os.environ.get("SIMILARITY_THRESHOLD"):
        cfg["recognition"]["similarity_threshold"] = float(threshold)
    if model_name := os.environ.get("MODEL_NAME"):
        cfg["recognition"]["model_name"] = model_name
    if frame_skip := os.environ.get("FRAME_SKIP"):
        cfg["recognition"]["frame_skip"] = int(frame_skip)

    if debounce := os.environ.get("DEBOUNCE_SECONDS"):
        cfg["attendance"]["debounce_seconds"] = int(debounce)

    if timezone := os.environ.get("TIMEZONE"):
        cfg["timezone"] = timezone

    # Kameralarni env orqali to'liq almashtirish (JSON ro'yxati) — Docker uchun qulay
    if cameras_json := os.environ.get("CAMERAS_JSON"):
        import json

        cfg["cameras"] = json.loads(cameras_json)

    return cfg


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg = _apply_env_overrides(cfg)

    cfg["database"]["path"] = _resolve_path(cfg["database"]["path"])
    cfg["paths"]["enrolled_faces_dir"] = _resolve_path(cfg["paths"]["enrolled_faces_dir"])
    cfg["paths"]["logs_dir"] = _resolve_path(cfg["paths"]["logs_dir"])
    return cfg


CONFIG = load_config()


def database_url() -> str:
    """SQLAlchemy ulanish satri. DATABASE_URL berilgan bo'lsa (AWS RDS), o'sha ishlatiladi."""
    if url := CONFIG["database"].get("url"):
        return url
    return f"sqlite:///{CONFIG['database']['path']}"
