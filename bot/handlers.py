"""
Bot buyruqlari va tugma bosishlari. Foydalanuvchi hech qachon matn
yozmaydi — hammasi inline tugmalar orqali, dashboard'dagi kabi aniq va
tartibli bo'limlarga bo'lingan.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.db.database import SessionLocal
from app.db.models import BotSubscriber
from bot import formatters as F
from bot import keyboards as K
from bot.config import ADMIN_IDS
from bot.dashboard_client import get_live_metrics

log = logging.getLogger("bot.handlers")

WELCOME = (
    "👋 <b>Xush kelibsiz!</b>\n\n"
    "Bu — davomat nazorati tizimining Telegram boti. Quyidagi tugmalar orqali "
    "xodimlar, davomat, kameralar va tizim holatini istalgan payt ko'rishingiz "
    "mumkin.\n\n"
    "🔔 Yangi keldi/ketdi hodisalari haqida jonli xabar olish uchun "
    "\"Bildirishnomalar\" bo'limidan yoqing (sukut bo'yicha yoqilgan)."
)

DENIED = (
    "🚫 Sizda bu botdan foydalanish ruxsati yo'q.\n\n"
    "Administratorga shu Telegram ID'ni bering, u sizni ruxsat berilganlar "
    "ro'yxatiga (<code>TELEGRAM_ADMIN_IDS</code>) qo'shsin:\n\n"
    "<code>{user_id}</code>"
)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _deny(update: Update) -> None:
    user_id = update.effective_user.id if update.effective_user else 0
    text = DENIED.format(user_id=user_id)
    if update.message:
        await update.message.reply_html(text)
    elif update.callback_query:
        await update.callback_query.answer("Ruxsat yo'q", show_alert=True)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_admin(user.id):
        await _deny(update)
        return

    session = SessionLocal()
    try:
        sub = session.get(BotSubscriber, update.effective_chat.id)
        if sub is None:
            sub = BotSubscriber(
                chat_id=update.effective_chat.id,
                username=user.username,
                full_name=user.full_name,
            )
            session.add(sub)
        else:
            sub.username = user.username
            sub.full_name = user.full_name
        session.commit()
    finally:
        session.close()

    await update.message.reply_html(WELCOME, reply_markup=K.main_menu())


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await _deny(update)
        return
    await update.message.reply_html("📋 <b>Bosh menyu</b> — nimani ko'rsataylik?", reply_markup=K.main_menu())


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi matn yozsa — tugmalarga yo'naltiramiz (bot faqat tugma bilan boshqariladi)."""
    if not _is_admin(update.effective_user.id):
        await _deny(update)
        return
    await update.message.reply_html(
        "Iltimos, tugmalardan foydalaning 👇", reply_markup=K.main_menu()
    )


# ------------------------------------------------------------- callback'lar

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await _deny(update)
        return

    await query.answer()
    data = query.data or ""
    session = SessionLocal()
    try:
        if data == "menu":
            await query.edit_message_text(
                "📋 <b>Bosh menyu</b> — nimani ko'rsataylik?", parse_mode="HTML", reply_markup=K.main_menu()
            )

        elif data == "overview":
            await query.edit_message_text(
                F.format_overview(session), parse_mode="HTML", reply_markup=K.refresh_and_back("overview")
            )

        elif data == "stats":
            await query.edit_message_text(
                F.format_stats(session), parse_mode="HTML", reply_markup=K.refresh_and_back("stats")
            )

        elif data == "employees":
            await query.edit_message_text(
                F.format_employees(session), parse_mode="HTML", reply_markup=K.refresh_and_back("employees")
            )

        elif data == "departments":
            choices = F.department_choices(session)
            if not choices:
                await query.edit_message_text(
                    "🏢 Hali bo'lim qo'shilmagan.", reply_markup=K.back_to_menu()
                )
            else:
                await query.edit_message_text(
                    "🏢 <b>Bo'limlar</b> — birini tanlang:",
                    parse_mode="HTML",
                    reply_markup=K.departments_list(choices),
                )

        elif data.startswith("dept:"):
            key = data.split(":", 1)[1]
            if key == "all":
                text = F.format_employees(session)
                back_cb = "departments"
            else:
                text = F.format_department_detail(session, int(key))
                back_cb = "departments"
            await query.edit_message_text(
                text, parse_mode="HTML", reply_markup=K.refresh_and_back(back_cb)
            )

        elif data.startswith("log:"):
            page = int(data.split(":", 1)[1])
            text, has_next = F.format_attendance_log(session, page)
            await query.edit_message_text(
                text, parse_mode="HTML", reply_markup=K.log_pager(page, has_next)
            )

        elif data == "cameras":
            metrics = await get_live_metrics()
            await query.edit_message_text(
                F.format_cameras(session, metrics), parse_mode="HTML", reply_markup=K.refresh_and_back("cameras")
            )

        elif data == "system":
            metrics = await get_live_metrics()
            await query.edit_message_text(
                F.format_system(session, metrics), parse_mode="HTML", reply_markup=K.refresh_and_back("system")
            )

        elif data == "notify" or data.startswith("notify:"):
            sub = session.get(BotSubscriber, update.effective_chat.id)
            if sub is None:
                sub = BotSubscriber(chat_id=update.effective_chat.id, username=update.effective_user.username)
                session.add(sub)

            if data == "notify:att":
                sub.notify_attendance = not sub.notify_attendance
            elif data == "notify:presence":
                sub.notify_presence = not sub.notify_presence
            session.commit()

            text = (
                "🔔 <b>Bildirishnomalar</b>\n\n"
                "Davomat — xodim keldi/ketdi qayd qilinganda darhol xabar.\n"
                "Harakat — kuzatuv kamerasi xodimni ko'rganda xabar "
                "(tez-tez bo'lishi mumkin, sukut bo'yicha o'chiq)."
            )
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=K.notify_settings(sub.notify_attendance, sub.notify_presence),
            )

        else:
            log.warning("noma'lum callback: %s", data)
    finally:
        session.close()
