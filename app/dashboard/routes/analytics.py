from datetime import datetime

from flask import Blueprint, render_template, request

from app import timeutil
from app.analytics import daily_trend, day_records, day_summary, department_breakdown
from app.db.database import SessionLocal

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@bp.route("")
def index():
    date_str = request.args.get("date")
    day = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timeutil.today()

    session = SessionLocal()
    try:
        records = day_records(session, day)
        summary = day_summary(records)
        by_department = department_breakdown(records)
        trend = daily_trend(session, day, days=14)
    finally:
        session.close()

    late_list = sorted(
        [r for r in records if r.late_minutes > 0],
        key=lambda r: r.late_minutes,
        reverse=True,
    )[:10]

    return render_template(
        "analytics.html",
        active_page="analytics",
        day=day.isoformat(),
        summary=summary,
        by_department=by_department,
        trend=trend,
        late_list=[
            {"name": r.name, "department": r.department or "—", "late_minutes": r.late_minutes}
            for r in late_list
        ],
    )
