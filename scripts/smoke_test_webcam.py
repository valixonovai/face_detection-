import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cameras.camera_stream import CameraStream
from app.config.settings import CONFIG

cam_cfg = next(c for c in CONFIG["cameras"] if c["source_type"] == "webcam")
stream = CameraStream.from_config(cam_cfg).start()

frame = None
for _ in range(50):
    frame = stream.get_frame()
    if frame is not None:
        break
    time.sleep(0.2)

if frame is None:
    print("Webcam'dan kadr olinmadi — qurilma band yoki mavjud emas.")
else:
    print(f"Webcam OK — kadr o'lchami: {frame.shape}")

stream.stop()
