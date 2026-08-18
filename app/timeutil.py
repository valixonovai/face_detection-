"""
Vaqt bilan ishlash.

Davomat tizimida barcha qoidalar mahalliy "devor soati" bo'yicha ifodalanadi:
ish 09:00 da boshlanadi, ish kuni 04:00 da almashadi va hokazo. Shuning uchun
vaqt tamg'alari ham mahalliy vaqtda saqlanadi — aks holda UTC'da saqlangan
yozuv 09:00 bilan solishtirilganda kechikish noto'g'ri hisoblanadi.

Vaqt mintaqasi `config.yaml` dagi `timezone` yoki `TIMEZONE` env orqali
beriladi; Docker konteynerlarida tizim vaqti odatda UTC bo'lgani uchun bu
muhim.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config.settings import CONFIG

_TZ = ZoneInfo(CONFIG.get("timezone", "Asia/Tashkent"))


def now() -> datetime:
    """Mahalliy vaqt (naive) — bazaga shu ko'rinishda yoziladi."""
    return datetime.now(_TZ).replace(tzinfo=None)


def today() -> date:
    return now().date()


def timezone_name() -> str:
    return str(_TZ)
