"""
Xabar matnlarini shakllantirish. Ma'lumot to'g'ridan-to'g'ri bazadan va
`app.analytics` modulidan olinadi — dashboard bilan bir xil hisob-kitob
mantig'i, ikki marta yozilmagan.
"""
from html import escape as esc

from sqlalchemy import desc, func, select

from app import analytics as A
from app import timeutil
from app.config.settings import CONFIG
from app.db.models import (
    AttendanceLog,
    Camera,
    Department,
    Employee,
    Visitor,
)

from bot.config import PAGE_SIZE

EVENT_ICON = {"in": "🟢", "out": "🔴"}
EVENT_LABEL = {"in": "KELDI", "out": "KETDI"}


def _pct_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "▓" * filled + "░" * (width - filled)


# ---------------------------------------------------------------- overview

def format_overview(session) -> str:
    today = timeutil.today()
    records = A.day_records(session, today)
    summary = A.day_summary(records)

    lines = [
        f"📊 <b>Umumiy holat</b> — {today.strftime('%d.%m.%Y')}",
        "",
        f"{_pct_bar(summary['attendance_rate'])}  <b>{summary['attendance_rate']}%</b>",
        "",
        f"👥 Jami xodim: <b>{summary['total']}</b>",
        f"✅ Keldi: <b>{summary['present']}</b>",
        f"❌ Kelmadi: <b>{summary['absent']}</b>",
        f"⏰ Kechikdi: <b>{summary['late']}</b>",
    ]
    if summary["late"]:
        lines.append(f"   (jami {summary['total_late_minutes']} daqiqa)")
    if summary["present"]:
        lines.append(f"🕐 O'rtacha ish vaqti: <b>{summary['avg_worked_hours']} soat</b>")

    late_rows = [r for r in records if r.late_minutes > 0][:5]
    if late_rows:
        lines.append("")
        lines.append("<b>Kechikkanlar:</b>")
        for r in late_rows:
            lines.append(f"  • {esc(r.name)} — {r.late_minutes} daqiqa")

    return "\n".join(lines)


# ------------------------------------------------------------------ stats

def format_stats(session) -> str:
    today = timeutil.today()
    records = A.day_records(session, today)
    breakdown = A.department_breakdown(records)
    trend = A.daily_trend(session, today, days=7)

    lines = [f"📈 <b>Statistika</b> — {today.strftime('%d.%m.%Y')}", ""]

    if breakdown:
        lines.append("<b>Bo'limlar kesimida:</b>")
        for row in breakdown:
            extra = f", {row['late']} kechikdi" if row["late"] else ""
            lines.append(
                f"  🏢 {esc(row['department'])}: {row['present']}/{row['total']} "
                f"({row['attendance_rate']}%){extra}"
            )
        lines.append("")

    lines.append("<b>Oxirgi 7 kun:</b>")
    for day in trend:
        bar = _pct_bar(day["attendance_rate"], width=8)
        lines.append(f"  {day['label']}  {bar}  {day['attendance_rate']}%")

    return "\n".join(lines)


# -------------------------------------------------------------- employees

def format_employees(session, department_id: int | None = None) -> str:
    query = select(Employee).where(Employee.status == "active").order_by(Employee.full_name)
    if department_id is not None:
        query = query.where(Employee.department_id == department_id)
    employees = session.execute(query).scalars().all()

    dept_names = {d.id: d.name for d in session.execute(select(Department)).scalars()}

    if not employees:
        return "👥 <b>Xodimlar</b>\n\nHozircha xodim yo'q."

    lines = [f"👥 <b>Xodimlar</b> — jami {len(employees)}", ""]
    for e in employees:
        dept = dept_names.get(e.department_id, "Bo'limsiz")
        pos = f" · {esc(e.position)}" if e.position else ""
        lines.append(f"  • {esc(e.full_name)} — {esc(dept)}{pos}")
    return "\n".join(lines)


# ------------------------------------------------------------ departments

def department_choices(session) -> list[tuple[int, str]]:
    rows = session.execute(select(Department).order_by(Department.name)).scalars().all()
    return [(d.id, d.name) for d in rows]


def format_department_detail(session, department_id: int) -> str:
    dept = session.get(Department, department_id)
    if dept is None:
        return "Bo'lim topilmadi."

    today = timeutil.today()
    records = [r for r in A.day_records(session, today) if r.department == dept.name]
    summary = A.day_summary(records)

    start = dept.expected_start_time.strftime("%H:%M") if dept.expected_start_time else "09:00"
    end = dept.expected_end_time.strftime("%H:%M") if dept.expected_end_time else "18:00"

    lines = [
        f"🏢 <b>{esc(dept.name)}</b>",
        f"🕐 Ish vaqti: {start}–{end}",
        "",
        f"👥 Xodim: <b>{summary['total']}</b> · Keldi: <b>{summary['present']}</b> "
        f"· Kelmadi: <b>{summary['absent']}</b>",
    ]
    if summary["total"]:
        lines.append(f"📊 Davomat: <b>{summary['attendance_rate']}%</b>")

    present = [r for r in records if r.check_in is not None]
    if present:
        lines.append("")
        lines.append("<b>Bugun keldi:</b>")
        for r in present[:15]:
            mark = " ⏰" if r.late_minutes > 0 else ""
            lines.append(f"  • {esc(r.name)} — {r.check_in.strftime('%H:%M')}{mark}")

    return "\n".join(lines)


# --------------------------------------------------------- attendance log

def format_attendance_log(session, page: int = 0) -> tuple[str, bool]:
    """Bugungi davomat jurnali, sahifalab. Qaytaradi: (matn, keyingi_sahifa_bormi)."""
    today = timeutil.today()
    day_start, day_end = A.work_day_bounds(today)

    offset = page * PAGE_SIZE
    rows = session.execute(
        select(AttendanceLog, Employee.full_name, Camera.name, Camera.zone)
        .join(Employee, AttendanceLog.employee_id == Employee.id)
        .outerjoin(Camera, AttendanceLog.camera_id == Camera.id)
        .where(AttendanceLog.timestamp >= day_start, AttendanceLog.timestamp < day_end)
        .order_by(desc(AttendanceLog.timestamp))
        .offset(offset)
        .limit(PAGE_SIZE + 1)
    ).all()

    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]

    lines = [f"📋 <b>Davomat jurnali</b> — {today.strftime('%d.%m.%Y')}", ""]
    if not rows:
        lines.append("Bu sahifada yozuv yo'q." if page else "Bugun hali yozuv yo'q.")
        return "\n".join(lines), False

    for log, name, cam_name, zone in rows:
        icon = EVENT_ICON.get(log.event_type, "•")
        label = EVENT_LABEL.get(log.event_type, log.event_type)
        place = cam_name or log.camera_id
        if zone:
            place = f"{place} ({zone})"
        lines.append(
            f"{icon} <b>{esc(name)}</b> — {label}\n"
            f"    🕐 {log.timestamp.strftime('%H:%M:%S')} · 📷 {esc(place)}"
        )

    return "\n".join(lines), has_next


def format_attendance_event(name: str, dept_name, event_type: str,
                             camera_name: str, zone, ts) -> str:
    """Jonli bildirishnoma matni — yangi davomat hodisasi kelganda."""
    icon = EVENT_ICON.get(event_type, "•")
    label = EVENT_LABEL.get(event_type, event_type)
    place = camera_name
    if zone:
        place = f"{place} ({zone})"
    dept_line = f"\n🏢 {esc(dept_name)}" if dept_name else ""
    return (
        f"{icon} <b>{esc(name)}</b> — {label}{dept_line}\n"
        f"🕐 {ts.strftime('%H:%M:%S')} · 📷 {esc(place)}"
    )


def format_presence_event(name: str, camera_name: str, zone, ts) -> str:
    place = f"{camera_name} ({zone})" if zone else camera_name
    return f"🚶 <b>{esc(name)}</b> ko'rindi\n🕐 {ts.strftime('%H:%M:%S')} · 📍 {esc(place)}"


# ------------------------------------------------------------------ cameras

def format_cameras(session, live_metrics: dict | None) -> str:
    cameras = session.execute(select(Camera).order_by(Camera.role, Camera.name)).scalars().all()
    live_by_id = {c["id"]: c for c in live_metrics["cameras"]} if live_metrics else {}

    if not cameras:
        return "📷 <b>Kameralar</b>\n\nHali kamera qo'shilmagan."

    lines = ["📷 <b>Kameralar</b>", ""]
    for cam in cameras:
        if not cam.enabled:
            lines.append(f"⏸ <s>{esc(cam.name)}</s> — o'chirilgan")
            continue

        live = live_by_id.get(cam.id)
        if live is None:
            status = "❔ dashboard bilan bog'lanilmadi" if live_metrics is None else "❔ holat noma'lum"
        elif live["connected"]:
            status = (
                f"🟢 ulangan · {live['fps']} FPS · "
                f"{live['faces_recognized']}/{live['faces_detected']} yuz"
            )
        else:
            status = "🔴 ulanmagan"
            if live.get("last_error"):
                status += f" ({esc(str(live['last_error'])[:60])})"

        role = "Kirish" if cam.role == "entrance" else "Kuzatuv"
        zone = f" · {esc(cam.zone)}" if cam.zone else ""
        lines.append(f"<b>{esc(cam.name)}</b> — {role}{zone}\n    {status}")

    return "\n".join(lines)


# ------------------------------------------------------------------- system

def format_system(session, live_metrics: dict | None) -> str:
    employee_count = session.execute(
        select(func.count(Employee.id)).where(Employee.status == "active")
    ).scalar_one()
    log_count = session.execute(select(func.count(AttendanceLog.id))).scalar_one()
    visitor_count = session.execute(select(func.count(Visitor.id))).scalar_one()
    avg_similarity = session.execute(select(func.avg(AttendanceLog.similarity))).scalar()

    lines = [
        "⚙️ <b>Tizim holati</b>",
        "",
        f"👥 Faol xodim: <b>{employee_count}</b>",
        f"📋 Jami davomat yozuvi: <b>{log_count}</b>",
        f"🚶 Qayd etilgan begonalar: <b>{visitor_count}</b>",
    ]
    if avg_similarity:
        lines.append(f"🎯 O'rtacha tanish aniqligi: <b>{avg_similarity:.1%}</b>")

    lines.append("")
    if live_metrics is None:
        lines.append("🔴 Dashboard bilan bog'lanib bo'lmadi (kuzatuv xizmati holati noma'lum).")
    else:
        uptime_h = live_metrics["uptime_seconds"] // 3600
        uptime_m = (live_metrics["uptime_seconds"] % 3600) // 60
        lines += [
            f"🟢 Kuzatuv xizmati ishlamoqda — {uptime_h}s {uptime_m}d",
            f"📷 Kameralar: <b>{live_metrics['connected_count']}/{live_metrics['camera_count']}</b> ulangan",
            f"⚡ Jami FPS: <b>{live_metrics['total_fps']}</b>",
        ]

    rec_cfg = CONFIG["recognition"]
    lines += [
        "",
        f"🧠 Model: <code>{rec_cfg['model_name']}</code>",
        f"🎚 Tanish chegarasi: <code>{rec_cfg['similarity_threshold']}</code>",
    ]
    return "\n".join(lines)
