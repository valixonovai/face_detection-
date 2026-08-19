"""
Jonli bildirishnoma xizmati: bazadagi yangi davomat/harakat hodisalarini
davriy tekshirib, obuna bo'lgan foydalanuvchilarga yuboradi.

Nega DB o'zgarishini "eshitish" o'rniga so'rov qilib turamiz (polling)?
Bot alohida jarayon/konteynerda ishlaydi — kamera kuzatuv xizmati
(xotiradagi `recent_events`) boshqa jarayonda, unga bevosita kira olmaymiz.
Baza ikkalasi uchun ham umumiy, shuning uchun eng ishonchli yo'l — yangi
qatorlarni ID bo'yicha kuzatish (watermark), qayta ishga tushirilganda ham
hech narsa yo'qolmaydi va qayta yuborilmaydi.
"""
import asyncio
import logging

from sqlalchemy import select
from telegram import Bot
from telegram.error import Forbidden, TelegramError

from app.db.database import SessionLocal
from app.db.models import AttendanceLog, BotState, BotSubscriber, Camera, Department, Employee, PresenceEvent
from bot import formatters as F
from bot.config import POLL_INTERVAL_SECONDS

log = logging.getLogger("bot.notifier")


def _get_state(session) -> BotState:
    state = session.get(BotState, 1)
    if state is None:
        state = BotState(id=1, last_attendance_id=0, last_presence_id=0)
        session.add(state)
        session.commit()
    return state


async def _dispatch(bot: Bot, chat_id: int, text: str, subscriber: BotSubscriber, session) -> None:
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Forbidden:
        # Foydalanuvchi botni bloklagan — obunani o'chiramiz, keyingi safar urinmaymiz
        log.info("chat %s botni bloklagan, obuna o'chirildi", chat_id)
        session.delete(subscriber)
        session.commit()
    except TelegramError as exc:
        log.warning("chat %s ga yuborib bo'lmadi: %s", chat_id, exc)


async def _check_attendance(bot: Bot, session, state: BotState) -> None:
    rows = session.execute(
        select(AttendanceLog, Employee.full_name, Department.name, Camera.name, Camera.zone)
        .join(Employee, AttendanceLog.employee_id == Employee.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .outerjoin(Camera, AttendanceLog.camera_id == Camera.id)
        .where(AttendanceLog.id > state.last_attendance_id)
        .order_by(AttendanceLog.id)
        .limit(200)  # bitta siklda cheklaymiz — birdaniga minglab yozuv kelib qolsa ham bot osilib qolmaydi
    ).all()
    if not rows:
        return

    subscribers = session.execute(
        select(BotSubscriber).where(BotSubscriber.notify_attendance.is_(True))
    ).scalars().all()

    for log_row, emp_name, dept_name, cam_name, zone in rows:
        text = F.format_attendance_event(
            emp_name, dept_name, log_row.event_type, cam_name or log_row.camera_id, zone, log_row.timestamp
        )
        for sub in list(subscribers):
            await _dispatch(bot, sub.chat_id, text, sub, session)
        state.last_attendance_id = log_row.id

    session.commit()


async def _check_presence(bot: Bot, session, state: BotState) -> None:
    rows = session.execute(
        select(PresenceEvent, Employee.full_name, Camera.name, Camera.zone)
        .join(Employee, PresenceEvent.employee_id == Employee.id)  # faqat xodimlar — mehmonlar bezovta qilmasin
        .outerjoin(Camera, PresenceEvent.camera_id == Camera.id)
        .where(PresenceEvent.id > state.last_presence_id, PresenceEvent.employee_id.is_not(None))
        .order_by(PresenceEvent.id)
        .limit(200)
    ).all()
    if not rows:
        return

    subscribers = session.execute(
        select(BotSubscriber).where(BotSubscriber.notify_presence.is_(True))
    ).scalars().all()

    for event, emp_name, cam_name, zone in rows:
        if subscribers:
            text = F.format_presence_event(emp_name, cam_name or event.camera_id, zone, event.timestamp)
            for sub in list(subscribers):
                await _dispatch(bot, sub.chat_id, text, sub, session)
        state.last_presence_id = event.id

    session.commit()


async def run_notifier(bot: Bot, stop_event: asyncio.Event) -> None:
    """Botning butun umri davomida fonda ishlaydigan hodisa kuzatuvchisi."""
    log.info("bildirishnoma xizmati ishga tushdi (har %.0fs tekshiradi)", POLL_INTERVAL_SECONDS)

    # Ishga tushishda mavjud yozuvlarni "ko'rilgan" deb belgilaymiz — aks holda
    # birinchi start'da bazadagi barcha eski hodisa birdaniga yuborilib ketardi.
    session = SessionLocal()
    try:
        state = _get_state(session)
        if state.last_attendance_id == 0:
            last_att = session.execute(select(AttendanceLog.id).order_by(AttendanceLog.id.desc())).scalars().first()
            state.last_attendance_id = last_att or 0
        if state.last_presence_id == 0:
            last_pres = session.execute(select(PresenceEvent.id).order_by(PresenceEvent.id.desc())).scalars().first()
            state.last_presence_id = last_pres or 0
        session.commit()
    finally:
        session.close()

    while not stop_event.is_set():
        session = SessionLocal()
        try:
            state = _get_state(session)
            await _check_attendance(bot, session, state)
            await _check_presence(bot, session, state)
        except Exception:
            log.exception("bildirishnoma siklida xato")
        finally:
            session.close()

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
