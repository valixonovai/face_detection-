"""
Xodimni ro'yxatga olish: rasmdan yuz embedding chiqarib, bazaga saqlaydi.

Ishlatish:
    python -m app.recognition.enroll --name "Aziz Karimov" --code "EMP001" --image "path/to/photo.jpg"

Eslatma: rasmda faqat bitta yuz bo'lishi va yaxshi yoritilgan, kameraga tik
qaragan holatda bo'lishi tavsiya etiladi (natija sifati shunga bog'liq).
"""
import argparse
import json
import shutil
from pathlib import Path

import cv2

from app.config.settings import CONFIG
from app.db.database import SessionLocal, init_db
from app.db.models import Employee
from app.recognition.face_engine import FaceEngine


def enroll(name: str, code: str | None, image_path: str) -> None:
    init_db()
    frame = cv2.imread(image_path)
    if frame is None:
        raise SystemExit(f"Rasmni o'qib bo'lmadi: {image_path}")

    engine = FaceEngine()
    faces = engine.detect(frame)

    if not faces:
        raise SystemExit("Rasmda yuz topilmadi. Boshqa, yaxshi yoritilgan rasm bilan urinib ko'ring.")
    if len(faces) > 1:
        raise SystemExit(f"Rasmda {len(faces)} ta yuz topildi. Rasmda faqat bitta odam bo'lishi kerak.")

    embedding = faces[0]["embedding"].tolist()

    faces_dir = Path(CONFIG["paths"]["enrolled_faces_dir"])
    faces_dir.mkdir(parents=True, exist_ok=True)
    dest = faces_dir / f"{(code or name).replace(' ', '_')}{Path(image_path).suffix}"
    shutil.copy(image_path, dest)

    session = SessionLocal()
    try:
        employee = Employee(
            full_name=name,
            external_code=code,
            embedding_json=json.dumps(embedding),
            photo_path=str(dest),
        )
        session.add(employee)
        session.commit()
        print(f"Xodim qo'shildi: {name} (id={employee.id}, det_score={faces[0]['det_score']:.3f})")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Xodimni yuz tanish tizimiga ro'yxatga olish")
    parser.add_argument("--name", required=True, help="Xodimning to'liq ismi")
    parser.add_argument("--code", default=None, help="Xodim ID/kodi (ixtiyoriy)")
    parser.add_argument("--image", required=True, help="Xodim rasmiga yo'l")
    args = parser.parse_args()
    enroll(args.name, args.code, args.image)
