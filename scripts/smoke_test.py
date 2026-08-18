import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import CONFIG
from app.db.database import init_db
from app.db.models import Employee, AttendanceLog
from app.attendance import AttendanceTracker
from app.cameras.camera_stream import CameraStream

print("Core modules OK")
print("Cameras configured:", [c["id"] for c in CONFIG["cameras"]])
init_db()
print("DB initialized at", CONFIG["database"]["path"])
