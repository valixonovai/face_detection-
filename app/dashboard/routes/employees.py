import base64
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.config.settings import CONFIG
from app.dashboard.services import get_engine
from app.db.database import SessionLocal
from app.db.models import Department, Employee
from app.workers.camera_worker import current_service

bp = Blueprint("employees", __name__, url_prefix="/employees")


def _refresh_face_cache() -> None:
    """
    Xodim ro'yxati o'zgargach tanish keshini darhol eskirtiradi — aks holda
    yangi qo'shilgan xodim (yoki holati o'zgargani) 20 soniyagacha tanilmasdi.
    Kuzatuv xizmati hali ishga tushmagan bo'lsa — hech narsa qilinmaydi.
    """
    service = current_service()
    if service is not None:
        service.matchers.invalidate()


@bp.route("")
def index():
    department_id = request.args.get("department_id", type=int)

    session = SessionLocal()
    try:
        query = select(Employee).options(joinedload(Employee.department)).order_by(Employee.full_name)
        if department_id:
            query = query.where(Employee.department_id == department_id)
        rows = session.execute(query).scalars().all()
        departments = session.execute(select(Department).order_by(Department.name)).scalars().all()
    finally:
        session.close()

    return render_template(
        "employees.html",
        active_page="employees",
        employees=rows,
        departments=departments,
        selected_department=department_id,
    )


@bp.route("/add", methods=["POST"])
def add():
    name = request.form.get("full_name", "").strip()
    code = request.form.get("external_code", "").strip() or None
    position = request.form.get("position", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    department_id = request.form.get("department_id", type=int) or None
    hired_date_str = request.form.get("hired_date", "").strip()
    hired_date = datetime.strptime(hired_date_str, "%Y-%m-%d").date() if hired_date_str else None

    if not name:
        flash("Xodim ismini kiriting.", "error")
        return redirect(url_for("employees.index"))

    image_bytes = None
    file = request.files.get("photo")
    if file and file.filename:
        image_bytes = file.read()
    else:
        webcam_data_url = request.form.get("webcam_image", "")
        if webcam_data_url.startswith("data:image"):
            _, b64data = webcam_data_url.split(",", 1)
            image_bytes = base64.b64decode(b64data)

    if not image_bytes:
        flash("Rasm tanlanmadi yoki kameradan surat olinmadi.", "error")
        return redirect(url_for("employees.index"))

    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        flash("Rasmni o'qib bo'lmadi.", "error")
        return redirect(url_for("employees.index"))

    faces = get_engine().detect(frame)
    if not faces:
        flash("Rasmda yuz topilmadi. Yaxshi yoritilgan, tik qaragan rasm bilan urinib ko'ring.", "error")
        return redirect(url_for("employees.index"))
    if len(faces) > 1:
        flash(f"Rasmda {len(faces)} ta yuz topildi — faqat bitta odam bo'lishi kerak.", "error")
        return redirect(url_for("employees.index"))

    faces_dir = Path(CONFIG["paths"]["enrolled_faces_dir"])
    faces_dir.mkdir(parents=True, exist_ok=True)
    dest = faces_dir / f"{uuid4().hex}.jpg"
    cv2.imwrite(str(dest), frame)

    session = SessionLocal()
    try:
        employee = Employee(
            full_name=name,
            external_code=code,
            position=position,
            phone=phone,
            department_id=department_id,
            hired_date=hired_date,
            embedding_json=json.dumps(faces[0]["embedding"].tolist()),
            photo_path=str(dest),
        )
        session.add(employee)
        session.commit()
        _refresh_face_cache()
        flash(f"{name} muvaffaqiyatli qo'shildi.", "success")
    except IntegrityError:
        session.rollback()
        dest.unlink(missing_ok=True)
        flash("Bu kod bilan xodim allaqachon mavjud.", "error")
    finally:
        session.close()

    return redirect(url_for("employees.index"))


@bp.route("/<int:employee_id>/delete", methods=["POST"])
def delete(employee_id: int):
    session = SessionLocal()
    try:
        employee = session.get(Employee, employee_id)
        if employee:
            session.delete(employee)
            session.commit()
            _refresh_face_cache()
            flash("Xodim o'chirildi.", "success")
    finally:
        session.close()
    return redirect(url_for("employees.index"))


@bp.route("/<int:employee_id>/status", methods=["POST"])
def toggle_status(employee_id: int):
    session = SessionLocal()
    try:
        employee = session.get(Employee, employee_id)
        if employee:
            employee.status = "inactive" if employee.status == "active" else "active"
            session.commit()
            # Faolsizlantirilgan xodim tanish keshidan chiqishi (yoki qaytishi) kerak
            _refresh_face_cache()
    finally:
        session.close()
    return redirect(url_for("employees.index"))


@bp.route("/<int:employee_id>/photo")
def photo(employee_id: int):
    session = SessionLocal()
    try:
        employee = session.get(Employee, employee_id)
    finally:
        session.close()
    if not employee or not employee.photo_path or not Path(employee.photo_path).exists():
        abort(404)
    return send_file(employee.photo_path)
