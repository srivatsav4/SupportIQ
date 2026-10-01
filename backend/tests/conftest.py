import os, sys, tempfile
from pathlib import Path

# isolated SQLite DB + in-memory Redis fallback for tests; set BEFORE the app is imported
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["N_CUSTOMERS"] = "120"
os.environ["N_ORDERS"] = "300"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _setup():
    from app.services.seeding import seed
    from app.rag.ingest import ingest
    seed(n_customers=120, n_orders=300)
    ingest()


@pytest.fixture()
def db():
    from app.database.session import SessionLocal
    with SessionLocal() as s:
        yield s


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def priya(client):
    return _login(client, "priya.sharma@example.com")


@pytest.fixture(scope="session")
def rohan(client):
    return _login(client, "rohan.mehta@example.com")


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@novacart.example")


@pytest.fixture()
def ask(db):
    from app.agents.orchestrator import Orchestrator
    from app.models.db import Customer

    def _ask(msg, customer="C1001", conv=None):
        return Orchestrator(db, db.get(Customer, customer)).handle(msg, conv)
    return _ask


@pytest.fixture(autouse=True)
def _isolate_state():
    """Tests mutate the shared synthetic DB (refunds, approvals, tickets); restore the demo baseline after each test."""
    from app.database.session import SessionLocal
    from app.models import db as m
    with SessionLocal() as s:
        base = {"refunds": {r for (r,) in s.query(m.Refund.refund_id)}, "tickets": {t for (t,) in s.query(m.SupportTicket.ticket_id)}}
    yield
    with SessionLocal() as s:
        s.query(m.Refund).filter(~m.Refund.refund_id.in_(base["refunds"])).delete(synchronize_session=False)
        s.query(m.SupportTicket).filter(~m.SupportTicket.ticket_id.in_(base["tickets"])).delete(synchronize_session=False)
        s.query(m.ApprovalRequest).delete()
        s.query(m.Order).filter_by(order_id="A12354").update({"status": "Processing"})
        s.commit()
