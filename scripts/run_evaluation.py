"""Thin wrapper around `python -m app.evaluation.run` (writes evaluation/results/latest.json + latest_report.txt)."""
import sys
from pathlib import Path
for _p in (Path(__file__).resolve().parents[1] / "backend", Path(__file__).resolve().parents[1]):
    if (_p / "app").exists():
        sys.path.insert(0, str(_p))
        break
from app.evaluation.run import main

if __name__ == "__main__":
    main()
