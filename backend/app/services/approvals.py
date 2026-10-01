"""Human-in-the-loop approvals for high-risk actions."""
import uuid
from sqlalchemy.orm import Session
from app.models import db as m
from app.services.clock import now


def create_approval(db: Session, customer_id: str, conversation_id: str | None, action: str, params: dict, risk: str, reason: str) -> m.ApprovalRequest:
    for existing in db.query(m.ApprovalRequest).filter_by(customer_id=customer_id, action=action, status="PENDING").all():
        if existing.params == params:           # don't queue the same request twice
            return existing
    a = m.ApprovalRequest(approval_id="AP" + uuid.uuid4().hex[:8].upper(), customer_id=customer_id, conversation_id=conversation_id, action=action,
                          params=params, risk_level=risk, reason=reason, status="PENDING", created_at=now())
    db.add(a)
    db.commit()
    return a


def approve(db: Session, approval_id: str, reviewer: str) -> m.ApprovalRequest:
    from app.tools.registry import TOOLS, ToolContext
    a = db.get(m.ApprovalRequest, approval_id)
    if not a:
        raise LookupError("Approval not found")
    if a.status != "PENDING":
        raise ValueError(f"Approval already {a.status}")
    ctx = ToolContext(db=db, customer_id=a.customer_id, conversation_id=a.conversation_id, system_override=True)
    tool = TOOLS[a.action]
    try:
        params = dict(a.params)
        if "confirmed" in tool.params:
            params["confirmed"] = True
        result = tool.fn(ctx, **params)
        a.status, a.result = "EXECUTED", result
    except Exception as e:
        db.rollback()
        a.status, a.result = "FAILED", {"error": str(e)}
    a.reviewer, a.resolved_at = reviewer, now()
    db.commit()
    return a


def reject(db: Session, approval_id: str, reviewer: str, note: str = "") -> m.ApprovalRequest:
    a = db.get(m.ApprovalRequest, approval_id)
    if not a:
        raise LookupError("Approval not found")
    if a.status != "PENDING":
        raise ValueError(f"Approval already {a.status}")
    a.status, a.reviewer, a.resolved_at, a.result = "REJECTED", reviewer, now(), {"note": note}
    db.commit()
    return a
