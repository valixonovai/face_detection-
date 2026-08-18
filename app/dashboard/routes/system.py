import platform
import sys

from flask import Blueprint, jsonify, render_template
from sqlalchemy import func, select

from app.config.settings import CONFIG
from app.db.database import SessionLocal
from app.db.models import AttendanceLog, Camera, Employee
from app.workers.camera_worker import current_service

bp = Blueprint("system", __name__, url_prefix="/system")


def _gpu_info() -> dict:
    """onnxruntime qaysi providerni ishlatayotganini aniqlaydi (modelni yuklamasdan)."""
    try:
        import app.gpu_bootstrap  # noqa: F401 — DLL yo'llarini ro'yxatdan o'tkazadi
        import onnxruntime as ort

        available = ort.get_available_providers()
    except Exception as exc:  # onnxruntime yo'q yoki yuklanmadi
        return {"available_providers": [], "gpu_enabled": False, "error": str(exc)}

    return {
        "available_providers": available,
        "gpu_enabled": "CUDAExecutionProvider" in available,
        "error": None,
    }


def _engine_providers() -> list[str]:
    """Model allaqachon yuklangan bo'lsa — u aslida qaysi providerda ishlayapti."""
    from app.dashboard.services import loaded_engine

    engine = loaded_engine()
    if engine is None:
        return []
    try:
        return engine.app.models["detection"].session.get_providers()
    except Exception:
        return []


@bp.route("")
def index():
    service = current_service()
    metrics = service.metrics() if service else None

    session = SessionLocal()
    try:
        employee_count = session.execute(
            select(func.count(Employee.id)).where(Employee.status == "active")
        ).scalar_one()
        log_count = session.execute(select(func.count(AttendanceLog.id))).scalar_one()
        avg_similarity = session.execute(select(func.avg(AttendanceLog.similarity))).scalar()
        cameras = list(session.execute(select(Camera).order_by(Camera.name)).scalars())
        session.expunge_all()
    finally:
        session.close()

    gpu = _gpu_info()
    active_providers = _engine_providers()

    return render_template(
        "system.html",
        active_page="system",
        cameras=cameras,
        recognition=CONFIG["recognition"],
        attendance=CONFIG["attendance"],
        metrics=metrics,
        gpu=gpu,
        active_providers=active_providers,
        employee_count=employee_count,
        log_count=log_count,
        avg_similarity=round(avg_similarity, 3) if avg_similarity else None,
        python_version=sys.version.split()[0],
        platform_name=f"{platform.system()} {platform.release()}",
    )


@bp.route("/metrics.json")
def metrics_json():
    """Jonli ko'rsatkichlar — sahifa avtomatik yangilanishi uchun."""
    service = current_service()
    return jsonify(service.metrics() if service else {"running": False})
