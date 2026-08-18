"""
Demo ma'lumot generatori — UI va hisobotlarni sinash uchun.

    python scripts/seed_demo.py          # demo ma'lumot yaratadi
    python scripts/seed_demo.py --clear  # BARCHA ma'lumotni o'chiradi

Diqqat: yaratilgan xodimlarning yuz embeddinglari soxta (nol vektor), shuning
uchun ular kamerada tanilmaydi — faqat hisobot/UI sinovi uchun mo'ljallangan.
"""
import argparse
import json
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal, init_db
from app.db.models import AttendanceLog, Department, Employee

NAMES = [
    "Aziz Karimov", "Dilnoza Yusupova", "Bekzod Rahimov", "Malika Tosheva",
    "Sardor Aliyev", "Nilufar Ergasheva", "Jasur Nazarov", "Kamola Sobirova",
    "Otabek Yo'ldoshev", "Zilola Qodirova", "Rustam Ismoilov", "Feruza Xolmatova",
]
DEPARTMENTS = [
    ("Sotuv bo'limi", time(9, 0), time(18, 0)),
    ("IT bo'limi", time(10, 0), time(19, 0)),
    ("Buxgalteriya", time(9, 0), time(18, 0)),
]


def clear(session) -> None:
    session.query(AttendanceLog).delete()
    session.query(Employee).delete()
    session.query(Department).delete()
    session.commit()
    print("Barcha ma'lumot o'chirildi.")


def seed(session, days: int = 14) -> None:
    random.seed(42)

    departments = []
    for name, start, end in DEPARTMENTS:
        dept = Department(name=name, expected_start_time=start, expected_end_time=end)
        session.add(dept)
        departments.append(dept)
    session.commit()

    employees = []
    for i, name in enumerate(NAMES):
        employee = Employee(
            full_name=name,
            external_code=f"EMP{i + 1:03d}",
            embedding_json=json.dumps([0.0] * 512),
            department_id=departments[i % len(departments)].id,
            position=random.choice(["Menejer", "Mutaxassis", "Katta mutaxassis", "Bo'lim boshlig'i"]),
            status="active",
        )
        session.add(employee)
        employees.append(employee)
    session.commit()

    today = date.today()
    for offset in range(days):
        day = today - timedelta(days=offset)
        for employee in employees:
            if random.random() < 0.12:
                continue  # kelmagan
            dept = next(d for d in departments if d.id == employee.department_id)
            late = random.choice([0, 0, 0, 0, 5, 12, 25, 40])
            check_in = datetime.combine(day, dept.expected_start_time) + timedelta(
                minutes=late - random.randint(0, 8)
            )
            check_out = datetime.combine(day, dept.expected_end_time) + timedelta(
                minutes=random.randint(-25, 45)
            )
            session.add(AttendanceLog(
                employee_id=employee.id, camera_id="pc_webcam", event_type="in",
                similarity=round(random.uniform(0.55, 0.85), 2), timestamp=check_in,
            ))
            session.add(AttendanceLog(
                employee_id=employee.id, camera_id="pc_webcam", event_type="out",
                similarity=round(random.uniform(0.55, 0.85), 2), timestamp=check_out,
            ))
    session.commit()
    print(f"{len(departments)} bo'lim, {len(employees)} xodim, {days} kunlik davomat yaratildi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo ma'lumot generatori")
    parser.add_argument("--clear", action="store_true", help="Barcha ma'lumotni o'chirish")
    parser.add_argument("--days", type=int, default=14, help="Necha kunlik davomat yaratilsin")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        if args.clear:
            clear(session)
        else:
            seed(session, days=args.days)
    finally:
        session.close()
