"""
Telegram bot sozlamalari — muhit o'zgaruvchilaridan o'qiladi.
"""
import os


def _int_list(value: str) -> set[int]:
    result = set()
    for part in value.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            result.add(int(part))
    return result


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Faqat shu Telegram user_id'larga davomat ma'lumotlariga kirish ruxsati
# beriladi. Bo'sh bo'lsa — HECH KIM kira olmaydi (xavfsiz sukut holat);
# xodimlarning kelish-ketish vaqti nozik ma'lumot, tasodifan ochiq
# qoldirilmasligi kerak.
ADMIN_IDS: set[int] = _int_list(os.environ.get("TELEGRAM_ADMIN_IDS", ""))

# Dashboard'ning ichki manzili — jonli kamera holatini shu yerdan olamiz
# (docker-compose tarmog'ida servis nomi orqali, masalan "http://dashboard:5000").
DASHBOARD_URL = os.environ.get("DASHBOARD_INTERNAL_URL", "http://localhost:5000").rstrip("/")

# Yangi davomat/harakat hodisalarini necha soniyada bir tekshirish
POLL_INTERVAL_SECONDS = float(os.environ.get("BOT_POLL_INTERVAL", "3"))

# Bitta xabarda ko'rsatiladigan davomat jurnali yozuvlari soni
PAGE_SIZE = 10
