from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import Department, Employee

bp = Blueprint("departments", __name__, url_prefix="/departments")


def _parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time() if value else None


@bp.route("")
def index():
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Department, func.count(Employee.id))
            .outerjoin(Employee, Employee.department_id == Department.id)
            .group_by(Department.id)
            .order_by(Department.name)
        ).all()
    finally:
        session.close()

    departments = [
        {
            "id": dept.id,
            "name": dept.name,
            "expected_start_time": dept.expected_start_time.strftime("%H:%M") if dept.expected_start_time else "",
            "expected_end_time": dept.expected_end_time.strftime("%H:%M") if dept.expected_end_time else "",
            "employee_count": count,
        }
        for dept, count in rows
    ]
    return render_template("departments.html", active_page="departments", departments=departments)


@bp.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Bo'lim nomini kiriting.", "error")
        return redirect(url_for("departments.index"))

    session = SessionLocal()
    try:
        department = Department(
            name=name,
            expected_start_time=_parse_time(request.form.get("expected_start_time", "")),
            expected_end_time=_parse_time(request.form.get("expected_end_time", "")),
        )
        session.add(department)
        session.commit()
        flash(f"'{name}' bo'limi qo'shildi.", "success")
    except IntegrityError:
        session.rollback()
        flash("Bu nomdagi bo'lim allaqachon mavjud.", "error")
    finally:
        session.close()
    return redirect(url_for("departments.index"))


@bp.route("/<int:department_id>/delete", methods=["POST"])
def delete(department_id: int):
    session = SessionLocal()
    try:
        department = session.get(Department, department_id)
        if department:
            session.execute(
                Employee.__table__.update()
                .where(Employee.department_id == department_id)
                .values(department_id=None)
            )
            session.delete(department)
            session.commit()
            flash("Bo'lim o'chirildi.", "success")
    finally:
        session.close()
    return redirect(url_for("departments.index"))
