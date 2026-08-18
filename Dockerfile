# NVIDIA CUDA 12 runtime + cuDNN 9 — onnxruntime-gpu shuni talab qiladi.
# GPU'siz ishlatmoqchi bo'lsangiz: FROM python:3.10-slim va requirements'da
# onnxruntime-gpu o'rniga onnxruntime.
FROM nvidia/cuda:12.6.2-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# python3.10 Ubuntu 22.04 bilan birga keladi.
# libgl1/libglib2.0 — OpenCV uchun; ffmpeg — RTSP oqimlarini o'qish uchun.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        libgl1 \
        libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY app/ ./app/
COPY scripts/ ./scripts/

# Ma'lumotlar (baza, yuz rasmlari) va model kesh papkalari — volume sifatida ulanadi
ENV DATA_DIR=/data \
    INSIGHTFACE_HOME=/models \
    DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=5000
RUN mkdir -p /data/enrolled_faces /data/logs /models

EXPOSE 5000

# Jonli kamera oqimi (MJPEG) uzoq davom etadigan so'rov — timeout 0 va thread'li
# worker kerak. Bitta worker: GPU modeli va kamera ulanishi bitta jarayonda turadi.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", \
     "--timeout", "0", "app.dashboard.app:app"]
