# Bot yengil konteyner — GPU, OpenCV yoki InsightFace kerak emas. U faqat
# bazani o'qiydi (SQLAlchemy) va Telegram/dashboard bilan HTTP orqali
# gaplashadi. Shuning uchun `nvidia/cuda` emas, oddiy `python:slim` yetarli —
# image hajmi ~3GB o'rniga ~150MB, qurilish va yuklab olish tezroq.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY bot/requirements.txt ./bot/requirements.txt
RUN pip install --no-cache-dir -r bot/requirements.txt

# `app/` ning to'liq nusxasi kerak — bot `app.db.models`, `app.analytics`,
# `app.config.settings` kabi modullarni bevosita ishlatadi (kod
# takrorlanmasin uchun). `app/recognition`, `app/cameras/camera_stream.py`
# kabi cv2/insightface talab qiladigan fayllar ham nusxalanadi, lekin bot
# ularni HECH QACHON import qilmaydi — shuning uchun ular o'rnatilmagan
# bo'lsa ham muammo tug'dirmaydi (Python faqat ishlatilgan modulni yuklaydi).
COPY app/ ./app/
COPY bot/ ./bot/

CMD ["python", "-m", "bot.main"]
