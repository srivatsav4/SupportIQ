import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import get_settings, DATA_DIR
from app.database.session import Base, engine, SessionLocal, init_db
from app.models import db as m
from app.security.auth import hash_password
from app.services.synthetic import generate

TABLES = [("customers", m.Customer), ("products", m.Product), ("orders", m.Order), ("order_items", m.OrderItem),
          ("payments", m.Payment), ("refunds", m.Refund), ("shipments", m.Shipment), ("tickets", m.SupportTicket)]
DT = {"created_at", "order_date", "expected_delivery", "delivered_at", "last_update", "initiated_at", "completed_at"}


def _conv(row: dict) -> dict:
    return {k: (datetime.fromisoformat(v) if k in DT and v else v) for k, v in row.items()}


def write_json(data: dict, out_dir: Path | None = None) -> Path:
    out = out_dir or (DATA_DIR / "synthetic")
    out.mkdir(parents=True, exist_ok=True)
    for k, rows in data.items():
        (out / f"{k}.json").write_text(json.dumps(rows, indent=1))
    return out


def seed(reset: bool = True, n_customers=None, n_products=None, n_orders=None) -> dict:
    s = get_settings()
    init_db()
    if reset:
        Base.metadata.drop_all(engine)
        init_db()
    data = generate(seed=s.seed, n_customers=n_customers or s.n_customers, n_products=n_products or s.n_products,
                    n_orders=n_orders or s.n_orders)
    pw = hash_password(s.demo_password)
    with SessionLocal() as db:
        for name, model in TABLES:
            rows = data[name]
            if name == "customers":
                for r in rows:
                    r["password_hash"] = pw
            db.bulk_insert_mappings(model, [_conv(r) for r in rows])
            db.commit()
    return {k: len(v) for k, v in data.items()}
