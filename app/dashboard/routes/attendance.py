from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import AttendanceLog, Employee

bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@bp.route("")
def index():
    employee_id = request.args.get("employee_id", type=int)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    session = SessionLocal()
    try:
        employee_options = session.execute(
            select(Employee.id, Employee.full_name).order_by(Employee.full_name)
        ).all()

        query = (
            select(AttendanceLog, Employee.full_name)
            .join(Employee, Employee.id == AttendanceLog.employee_id)
        )
        if employee_id:
            query = query.where(AttendanceLog.employee_id == employee_id)
        if date_from:
            query = query.where(AttendanceLog.timestamp >= datetime.strptime(date_from, "%Y-%m-%d"))
        if date_to:
            query = query.where(
                AttendanceLog.timestamp < datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            )
        query = query.order_by(AttendanceLog.timestamp.desc()).limit(500)

        rows = session.execute(query).all()
    finally:
        session.close()

    logs = [
        {
            "name": full_name,
            "event_type": log.event_type,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": log.camera_id,
            "similarity": f"{log.similarity:.2f}",
        }
        for log, full_name in rows
    ]

    return render_template(
        "attendance.html",
        active_page="attendance",
        logs=logs,
        employee_options=employee_options,
        selected_employee=employee_id,
        date_from=date_from,
        date_to=date_to,
    )
