import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import onnxruntime as ort

print("Available ONNX providers:", ort.get_available_providers())

from app.recognition.face_engine import FaceEngine

engine = FaceEngine()
print("FaceEngine loaded OK, providers in use:", engine.app.models["detection"].session.get_providers())
