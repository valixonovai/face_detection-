"""
Telegram bot — kirish nuqtasi.

Ishlatish:
    python -m bot.main

Talab qilinadigan muhit o'zgaruvchilari:
    TELEGRAM_BOT_TOKEN   — @BotFather'dan olingan token
    TELEGRAM_ADMIN_IDS   — ruxsat berilgan Telegram user_id'lar, vergul bilan

Bot xodimlar/davomat bazasi bilan bevosita ishlaydi (dashboard bilan bir xil
baza) va kamera holatini dashboard'ning HTTP API'sidan oladi — shuning uchun
GPU yoki OpenCV kerak emas, yengil konteynerda ishlaydi.
"""
import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.db.database import init_db
from bot import handlers
from bot.config import ADMIN_IDS, BOT_TOKEN
from bot.notifier import run_notifier

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
# Kutubxonaning har HTTP so'rovini logga chiqarmaslik uchun
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

log = logging.getLogger("bot.main")


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Botni ishga tushirish / bosh menyu"),
            BotCommand("menu", "Bosh menyuni ko'rsatish"),
        ]
    )
    stop_event = asyncio.Event()
    application.bot_data["stop_event"] = stop_event
    application.bot_data["notifier_task"] = asyncio.create_task(run_notifier(application.bot, stop_event))
    log.info("bot ishga tushdi — ruxsat berilgan foydalanuvchilar: %s", sorted(ADMIN_IDS) or "(yo'q!)")


async def _post_shutdown(application: Application) -> None:
    stop_event: asyncio.Event = application.bot_data.get("stop_event")
    task: asyncio.Task = application.bot_data.get("notifier_task")
    if stop_event:
        stop_event.set()
    if task:
        await task


def main() -> None:
    if not BOT_TOKEN:
        log.error(
            "TELEGRAM_BOT_TOKEN berilmagan. @BotFather'dan token oling va "
            "muhit o'zgaruvchisi sifatida bering."
        )
        sys.exit(1)
    if not ADMIN_IDS:
        log.warning(
            "TELEGRAM_ADMIN_IDS bo'sh — HECH KIM botdan foydalana olmaydi. "
            "/start bosgan foydalanuvchi o'z ID'sini ko'radi, uni shu o'zgaruvchiga qo'shing."
        )

    # Bazani tayyorlaymiz (jadvallar, config.yaml'dan boshlang'ich seed) —
    # dashboard ilova ichida create_app() orqali qiladi, bot alohida
    # jarayon bo'lgani uchun shu yerda o'zi qiladi.
    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", handlers.cmd_start))
    application.add_handler(CommandHandler("menu", handlers.cmd_menu))
    application.add_handler(CallbackQueryHandler(handlers.on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))

    log.info("polling boshlandi")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
