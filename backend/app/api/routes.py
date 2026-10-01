import json, time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from app.agents.orchestrator import Orchestrator
from app.config import get_settings, DATA_DIR
from app.database.session import get_db, is_postgres
from app.models import db as m
from app.observability.metrics import DB_LATENCY
from app.rag import retriever
from app.schemas.api import *
from app.security import auth, guardrails as gr
from app.services import analytics, approvals, memory
from app.services.clock import now

router = APIRouter(prefix="/api")
Staff = Depends(auth.require_roles(*auth.STAFF))
AdminOnly = Depends(auth.require_roles("ADMIN"))


def _user_dict(u: m.Customer):
    return {"customer_id": u.customer_id, "name": u.name, "email": u.email, "role": u.role, "membership_tier": u.membership_tier}


# ------------------------------------------------------------------------ auth
@router.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    db.execute(text("SELECT 1"))
    DB_LATENCY.observe(time.perf_counter() - t0)
    return {"status": "ok", "database": "up", "redis": memory.backend(), "llm_provider": get_settings().llm_provider}


@router.get("/auth/demo-users", tags=["auth"], summary="Synthetic demo accounts for the login screen")
def demo_users(db: Session = Depends(get_db)):
    ids = ["C1001", "C1002", "C1003", "S9001", "S9002"]
    return [{**_user_dict(u), "password": get_settings().demo_password} for u in db.query(m.Customer).filter(m.Customer.customer_id.in_(ids)).all()]


@router.post("/auth/login", tags=["auth"])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    u = db.query(m.Customer).filter(m.Customer.email == body.email.lower().strip()).first()
    if not u or not auth.verify_password(body.password, u.password_hash or ""):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": auth.create_token(u), "token_type": "bearer", "user": _user_dict(u)}


@router.get("/me", tags=["auth"])
def me(u: m.Customer = Depends(auth.current_user)):
    return _user_dict(u)


# ------------------------------------------------------------------------ chat
@router.post("/chat", tags=["chat"], summary="Send a message to the AI support agent")
def chat(body: ChatRequest, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    if body.conversation_id:
        c = db.get(m.Conversation, body.conversation_id)
        if c and c.customer_id != u.customer_id:
            raise HTTPException(404, "Conversation not found")
    return Orchestrator(db, u).handle(body.message, body.conversation_id)


@router.post("/chat/confirm", tags=["chat"], summary="Confirm or decline a pending high-risk action")
def chat_confirm(body: ConfirmRequest, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    c = db.get(m.Conversation, body.conversation_id)
    if not c or c.customer_id != u.customer_id:
        raise HTTPException(404, "Conversation not found")
    return Orchestrator(db, u).handle("yes" if body.confirm else "no", body.conversation_id)


def _conv_summary(c: m.Conversation):
    last = (c.messages or [])[-1]["content"][:120] if c.messages else ""
    return {"conversation_id": c.conversation_id, "customer_id": c.customer_id, "intent": c.intent, "sentiment": c.sentiment, "resolution_status": c.resolution_status,
            "turns": c.turns, "created_at": c.created_at, "updated_at": c.updated_at, "preview": last}


@router.get("/conversations", tags=["chat"])
def conversations(limit: int = Query(50, le=200), all: bool = False, status: str | None = None, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    q = db.query(m.Conversation)
    if not (all and u.role in auth.STAFF):
        q = q.filter(m.Conversation.customer_id == u.customer_id)
    if status:
        q = q.filter(m.Conversation.resolution_status == status)
    return [_conv_summary(c) for c in q.order_by(m.Conversation.updated_at.desc()).limit(limit).all()]


@router.get("/conversations/{cid}", tags=["chat"])
def conversation(cid: str, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    c = db.get(m.Conversation, cid)
    if not c or (c.customer_id != u.customer_id and u.role not in auth.STAFF):
        raise HTTPException(404, "Conversation not found")
    return {**_conv_summary(c), "messages": c.messages}


# ------------------------------------------------------------------------ orders / tickets
@router.get("/orders", tags=["orders"])
def orders(limit: int = Query(30, le=100), u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    rows = db.query(m.Order).filter_by(customer_id=u.customer_id).order_by(m.Order.order_date.desc()).limit(limit).all()
    return [{"order_id": o.order_id, "status": o.status, "order_date": o.order_date, "total_amount": o.total_amount, "expected_delivery": o.expected_delivery,
             "items": [i.product.name for i in o.items if i.product]} for o in rows]


@router.get("/orders/{order_id}", tags=["orders"])
def order_detail(order_id: str, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    from app.tools.registry import execute_tool, ToolContext
    ctx = ToolContext(db=db, customer_id=u.customer_id, role=u.role)
    res = {k: execute_tool(ctx, k, order_id=order_id) for k in ("get_order", "track_shipment", "get_order_items", "get_refund_status")}
    if not res["get_order"]["ok"]:
        raise HTTPException(404, res["get_order"]["error"]["message"])
    return {k: v["data"] for k, v in res.items() if v["ok"]}


def _ticket(t: m.SupportTicket):
    return {"ticket_id": t.ticket_id, "customer_id": t.customer_id, "category": t.category, "priority": t.priority, "status": t.status, "description": t.description,
            "assigned_agent": t.assigned_agent, "order_id": t.order_id, "conversation_id": t.conversation_id, "created_at": t.created_at, "escalation_context": t.escalation_context}


@router.get("/tickets", tags=["tickets"])
def tickets(limit: int = Query(50, le=300), all: bool = False, status: str | None = None, priority: str | None = None, u: m.Customer = Depends(auth.current_user), db: Session = Depends(get_db)):
    q = db.query(m.SupportTicket)
    if not (all and u.role in auth.STAFF):
        q = q.filter_by(customer_id=u.customer_id)
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)
    return [_ticket(t) for t in q.order_by(m.SupportTicket.created_at.desc()).limit(limit).all()]


@router.patch("/tickets/{tid}", tags=["tickets"], dependencies=[Staff])
def update_ticket(tid: str, body: TicketUpdate, db: Session = Depends(get_db)):
    t = db.get(m.SupportTicket, tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if body.status:
        t.status = body.status
    if body.assigned_agent is not None:
        t.assigned_agent = body.assigned_agent
    db.commit()
    return _ticket(t)


# ------------------------------------------------------------------------ admin
@router.get("/admin/analytics/summary", tags=["admin"], dependencies=[AdminOnly])
def a_summary(db: Session = Depends(get_db)):
    return analytics.summary(db)


@router.get("/admin/analytics/timeseries", tags=["admin"], dependencies=[AdminOnly])
def a_series(days: int = Query(14, ge=2, le=60), db: Session = Depends(get_db)):
    return analytics.timeseries(db, days)


@router.get("/admin/analytics/distributions", tags=["admin"], dependencies=[AdminOnly])
def a_dist(db: Session = Depends(get_db)):
    return analytics.distributions(db)


def _approval(a: m.ApprovalRequest):
    return {"approval_id": a.approval_id, "customer_id": a.customer_id, "conversation_id": a.conversation_id, "action": a.action, "params": a.params, "risk_level": a.risk_level,
            "reason": a.reason, "status": a.status, "reviewer": a.reviewer, "result": a.result, "created_at": a.created_at, "resolved_at": a.resolved_at}


@router.get("/admin/approvals", tags=["admin"], dependencies=[AdminOnly])
def list_approvals(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(m.ApprovalRequest)
    if status:
        q = q.filter_by(status=status)
    return [_approval(a) for a in q.order_by(m.ApprovalRequest.created_at.desc()).limit(100).all()]


@router.post("/admin/approvals/{aid}/approve", tags=["admin"])
def approve(aid: str, u: m.Customer = AdminOnly, db: Session = Depends(get_db)):
    try:
        return _approval(approvals.approve(db, aid, u.name))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/admin/approvals/{aid}/reject", tags=["admin"])
def reject(aid: str, body: ReviewRequest, u: m.Customer = AdminOnly, db: Session = Depends(get_db)):
    try:
        return _approval(approvals.reject(db, aid, u.name, body.note))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/admin/customers", tags=["admin"], dependencies=[Staff])
def customers(q: str = "", limit: int = Query(25, le=100), db: Session = Depends(get_db)):
    qs = db.query(m.Customer).filter(m.Customer.role == "CUSTOMER")
    if q:
        like = f"%{q}%"
        qs = qs.filter(or_(m.Customer.name.ilike(like), m.Customer.customer_id.ilike(like), m.Customer.email.ilike(like)))
    return [{"customer_id": c.customer_id, "name": c.name, "email": gr.mask_email(c.email), "phone": gr.mask_phone(c.phone or ""), "membership_tier": c.membership_tier,
             "orders": db.query(m.Order).filter_by(customer_id=c.customer_id).count()} for c in qs.order_by(m.Customer.customer_id).limit(limit).all()]


@router.get("/admin/knowledge", tags=["admin"], dependencies=[Staff])
def knowledge(db: Session = Depends(get_db)):
    rows = db.query(m.KBChunk).all()
    docs = {}
    for r in rows:
        d = docs.setdefault(r.document, {"document": r.document, "source": r.source, "chunks": 0, "sections": []})
        d["chunks"] += 1
        if r.section not in d["sections"]:
            d["sections"].append(r.section)
    return {"documents": sorted(docs.values(), key=lambda x: x["document"]), "total_chunks": len(rows), "embedding_backend": get_settings().embedding_backend, "vector_store": "pgvector" if is_postgres() else "in-memory (SQLite dev mode)"}


@router.post("/admin/knowledge/search", tags=["admin"], dependencies=[Staff])
def kb_search(body: KBSearch):
    r = retriever.retrieve(body.query)
    return {"latency_ms": round(r.latency_ms, 2), "error": r.error, "results": [c.__dict__ for c in r.chunks]}


@router.post("/admin/knowledge/reingest", tags=["admin"], dependencies=[AdminOnly])
def reingest():
    from app.rag.ingest import ingest
    return ingest()


@router.get("/admin/evaluation/latest", tags=["admin"], dependencies=[Staff])
def eval_latest():
    p = Path(__file__).resolve().parents[3] / "evaluation" / "results" / "latest.json"
    if not p.exists():
        p = DATA_DIR.parent / "evaluation" / "results" / "latest.json"
    if not p.exists():
        return {"available": False, "message": "No evaluation run yet. Run: python -m app.evaluation.run"}
    return {"available": True, **json.loads(p.read_text())}


@router.post("/admin/evaluation/run", tags=["admin"], dependencies=[AdminOnly])
def eval_run(limit: int | None = Query(None, ge=1, le=500)):
    from app.evaluation.run import run_evaluation
    return run_evaluation(limit=limit)


@router.get("/admin/system", tags=["admin"], dependencies=[Staff])
def system(db: Session = Depends(get_db)):
    s = get_settings()
    t0 = time.perf_counter()
    db.execute(text("SELECT 1"))
    db_ms = (time.perf_counter() - t0) * 1000
    rag = retriever.retrieve("refund policy")
    llm_ok = None
    if s.llm_provider != "demo":
        from app.agents import llm
        try:
            llm.generate("ping", "ping"); llm_ok = True
        except Exception:
            llm_ok = False
    return {"database": {"status": "up", "engine": db.bind.dialect.name, "latency_ms": round(db_ms, 2)},
            "redis": {"backend": memory.backend()}, "vector_search": {"status": "error" if rag.error else "up", "latency_ms": round(rag.latency_ms, 2), "error": rag.error},
            "llm": {"provider": s.llm_provider, "available": True if s.llm_provider == "demo" else llm_ok, "model": s.ollama_model if s.llm_provider == "ollama" else s.openai_model or None},
            "embedding": s.embedding_backend, "grafana_url": "http://localhost:3001", "prometheus_url": "http://localhost:9090", "as_of_date": s.as_of_date or "real-time"}
