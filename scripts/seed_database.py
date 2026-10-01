"""Create tables and load the deterministic synthetic NovaCart database."""
import sys
from pathlib import Path
for _p in (Path(__file__).resolve().parents[1] / "backend", Path(__file__).resolve().parents[1]):   # repo checkout or Docker image layout
    if (_p / "app").exists():
        sys.path.insert(0, str(_p))
        break
from app.services.seeding import seed

if __name__ == "__main__":
    print("seeded:", seed(reset="--keep" not in sys.argv))
