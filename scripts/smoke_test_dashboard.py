import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dashboard.app import app
from app.db.database import init_db

init_db()
client = app.test_client()

for path in [
    "/", "/employees", "/departments", "/analytics", "/attendance",
    "/cameras", "/live", "/live/events.json", "/system", "/system/metrics.json",
]:
    resp = client.get(path)
    print(f"{path}: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.data[:1000])
