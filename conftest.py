import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
for entry in (ROOT, BACKEND):
    value = str(entry)
    if value not in sys.path:
        sys.path.insert(0, value)
