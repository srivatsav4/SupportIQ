"""Write the deterministic synthetic dataset to data/synthetic/*.json (for inspection). All data is fake."""
import sys
from pathlib import Path
for _p in (Path(__file__).resolve().parents[1] / "backend", Path(__file__).resolve().parents[1]):   # repo checkout or Docker image layout
    if (_p / "app").exists():
        sys.path.insert(0, str(_p))
        break
from app.config import get_settings
from app.services.synthetic import generate
from app.services.seeding import write_json

if __name__ == "__main__":
    s = get_settings()
    d = generate(seed=s.seed, n_customers=s.n_customers, n_products=s.n_products, n_orders=s.n_orders)
    print("wrote", write_json(d), {k: len(v) for k, v in d.items()})
