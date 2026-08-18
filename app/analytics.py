"""
Davomat hisob-kitoblari: kunlik sessiyalar, kechikish, ish soatlari va
bo'limlar kesimidagi ko'rsatkichlar.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config.settings import CONFIG
from app.db.models import AttendanceLog, Department, Employee

DAY_BOUNDARY_HOUR = CONFIG["attendance"]["day_boundary_hour"]
DEFAULT_START = time(9, 0)
DEFAULT_END = time(18, 0)


def work_day_bounds(day: datetime | date) -> tuple[datetime, datetime]:
    if isinstance(day, date) and not isinstance(day, datetime):
        day = datetime.combine(day, time.min)
    start = day.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


@dataclass
class DayRecord:
    employee_id: int
    name: str
    department: str | None
    check_in: datetime | None
    check_out: datetime | None
    events: int
    expected_start: time
    expected_end: time

    @property
    def late_minutes(self) -> int:
        if self.check_in is None:
            return 0
        expected = datetime.combine(self.check_in.date(), self.expected_start)
        delta = (self.check_in - expected).total_seconds() / 60
        return max(0, int(delta))

    @property
    def early_leave_minutes(self) -> int:
        if self.check_out is None:
            return 0
        expected = datetime.combine(self.check_out.date(), self.expected_end)
        delta = (expected - self.check_out).total_seconds() / 60
        return max(0, int(delta))

    @property
    def worked_minutes(self) -> int:
        if self.check_in is None or self.check_out is None:
            return 0
        return max(0, int((self.check_out - self.check_in).total_seconds() / 60))

    @property
    def status(self) -> str:
        if self.check_in is None:
            return "absent"
        if self.late_minutes > 0:
            return "late"
        return "on_time"


def day_records(session, day: datetime | date) -> list[DayRecord]:
    """Tanlangan ish kunidagi barcha faol xodimlar bo'yicha yozuvlar."""
    day_start, day_end = work_day_bounds(day)

    employees = (
        session.execute(
            select(Employee)
            .options(joinedload(Employee.department))
            .where(Employee.status == "active")
            .order_by(Employee.full_name)
        )
        .scalars()
        .all()
    )

    logs = session.execute(
        select(AttendanceLog)
        .where(AttendanceLog.timestamp >= day_start, AttendanceLog.timestamp < day_end)
        .order_by(AttendanceLog.timestamp)
    ).scalars().all()

    logs_by_employee: dict[int, list[AttendanceLog]] = {}
    for log in logs:
        logs_by_employee.setdefault(log.employee_id, []).append(log)

    records = []
    for employee in employees:
        emp_logs = logs_by_employee.get(employee.id, [])
        first_in = next((l for l in emp_logs if l.event_type == "in"), None)
        last_out = next((l for l in reversed(emp_logs) if l.event_type == "out"), None)
        dept = employee.department

        records.append(
            DayRecord(
                employee_id=employee.id,
                name=employee.full_name,
                department=dept.name if dept else None,
                check_in=first_in.timestamp if first_in else None,
                check_out=last_out.timestamp if last_out else None,
                events=len(emp_logs),
                expected_start=(dept.expected_start_time if dept and dept.expected_start_time else DEFAULT_START),
                expected_end=(dept.expected_end_time if dept and dept.expected_end_time else DEFAULT_END),
            )
        )
    return records


def day_summary(records: list[DayRecord]) -> dict:
    present = [r for r in records if r.check_in is not None]
    late = [r for r in present if r.late_minutes > 0]
    total_worked = sum(r.worked_minutes for r in present)

    return {
        "total": len(records),
        "present": len(present),
        "absent": len(records) - len(present),
        "late": len(late),
        "total_late_minutes": sum(r.late_minutes for r in late),
        "avg_worked_hours": round(total_worked / 60 / len(present), 1) if present else 0.0,
        "attendance_rate": round(len(present) / len(records) * 100) if records else 0,
    }


def department_breakdown(records: list[DayRecord]) -> list[dict]:
    groups: dict[str, list[DayRecord]] = {}
    for record in records:
        groups.setdefault(record.department or "Belgilanmagan", []).append(record)

    rows = []
    for name, group in sorted(groups.items()):
        present = [r for r in group if r.check_in is not None]
        late = [r for r in present if r.late_minutes > 0]
        rows.append(
            {
                "department": name,
                "total": len(group),
                "present": len(present),
                "absent": len(group) - len(present),
                "late": len(late),
                "attendance_rate": round(len(present) / len(group) * 100) if group else 0,
            }
        )
    return rows


def daily_trend(session, end_day: date, days: int = 14) -> list[dict]:
    """Oxirgi N kun uchun kunlik davomat foizi."""
    trend = []
    for offset in range(days - 1, -1, -1):
        day = end_day - timedelta(days=offset)
        records = day_records(session, day)
        summary = day_summary(records)
        trend.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%d.%m"),
                "present": summary["present"],
                "absent": summary["absent"],
                "late": summary["late"],
                "attendance_rate": summary["attendance_rate"],
            }
        )
    return trend
