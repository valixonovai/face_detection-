from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import select

from app import timeutil
from app.config.settings import CONFIG
from app.db.database import SessionLocal
from app.db.models import AttendanceLog, Employee

bp = Blueprint("overview", __name__)
DAY_BOUNDARY_HOUR = CONFIG["attendance"]["day_boundary_hour"]


def work_day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


@bp.route("/")
def index():
    date_str = request.args.get("date")
    day = datetime.strptime(date_str, "%Y-%m-%d") if date_str else timeutil.now()
    day_start, day_end = work_day_bounds(day)

    session = SessionLocal()
    try:
        rows = session.execute(
            select(AttendanceLog, Employee.full_name, Employee.department_id)
            .join(Employee, Employee.id == AttendanceLog.employee_id)
            .where(AttendanceLog.timestamp >= day_start, AttendanceLog.timestamp < day_end)
            .order_by(Employee.full_name, AttendanceLog.timestamp)
        ).all()

        by_employee: dict[str, list] = {}
        for log, full_name, _dept_id in rows:
            by_employee.setdefault(full_name, []).append(log)

        summary = []
        for full_name, logs in sorted(by_employee.items()):
            first_in = next((l for l in logs if l.event_type == "in"), None)
            last_out = next((l for l in reversed(logs) if l.event_type == "out"), None)
            summary.append(
                {
                    "name": full_name,
                    "check_in": first_in.timestamp.strftime("%H:%M:%S") if first_in else "-",
                    "check_out": last_out.timestamp.strftime("%H:%M:%S") if last_out else "-",
                    "events": len(logs),
                }
            )

        total_employees = session.execute(
            select(Employee.id).where(Employee.status == "active")
        ).all()
    finally:
        session.close()

    return render_template(
        "overview.html",
        active_page="overview",
        summary=summary,
        day=day.strftime("%Y-%m-%d"),
        total_employees=len(total_employees),
        present_count=len(by_employee),
    )
