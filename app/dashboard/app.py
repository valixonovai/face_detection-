"""
Davomat CRM dashboardi: umumiy ko'rinish, xodimlar, bo'limlar, davomat
jurnali va jonli kamera oynasi.

Ishlatish:
    python -m app.dashboard.app
"""
from flask import Flask

from app.config.settings import CONFIG
from app.dashboard.routes.analytics import bp as analytics_bp
from app.dashboard.routes.attendance import bp as attendance_bp
from app.dashboard.routes.cameras import bp as cameras_bp
from app.dashboard.routes.departments import bp as departments_bp
from app.dashboard.routes.employees import bp as employees_bp
from app.dashboard.routes.live import bp as live_bp
from app.dashboard.routes.overview import bp as overview_bp
from app.dashboard.routes.system import bp as system_bp
from app.db.database import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "attendance-dashboard-local"  # faqat lokal foydalanish uchun

    # Jadval va boshlang'ich ma'lumotni shu yerda tayyorlaymiz — gunicorn
    # (Docker/AWS) ilovani `create_app()` orqali import qiladi, `__main__`
    # blokiga kirmaydi. Aks holda jadvallar yaratilmay, har sahifa xato berardi.
    init_db()

    app.register_blueprint(overview_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(system_bp)

    return app


app = create_app()


if __name__ == "__main__":
    cfg = CONFIG["dashboard"]
    app.run(host=cfg["host"], port=cfg["port"], debug=False, threaded=True)
