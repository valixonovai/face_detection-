"""
Dashboard'ning jonli ko'rsatkichlar API'siga (`/system/metrics.json`) so'rov.

Kamera ulanish holati, FPS va topilgan yuzlar soni faqat kuzatuv xizmati
ishlaydigan jarayonning xotirasida bor (`MultiCameraService`). Bot alohida
konteynerda ishlagani uchun bu ma'lumotga faqat dashboard'ning HTTP API'si
orqali (docker tarmog'i ichida) yetadi. Dashboard vaqtincha ishlamay qolsa
bot butunlay to'xtamasin — shunchaki "holat noma'lum" deb ko'rsatadi.
"""
import logging

import httpx

from bot.config import DASHBOARD_URL

log = logging.getLogger("bot.dashboard_client")

_TIMEOUT = httpx.Timeout(4.0)


async def get_live_metrics() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{DASHBOARD_URL}/system/metrics.json")
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.debug("dashboard metrics olinmadi: %s", exc)
        return None
