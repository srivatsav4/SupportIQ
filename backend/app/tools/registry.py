"""Controlled tools. The LLM/agent NEVER touches the database directly: every operation goes through
`execute_tool`, which validates parameters, enforces customer ownership, applies risk-level gating
(confirmation / human approval), masks PII and records metrics."""
import re, time, uuid, logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import db as m
from app.observability.metrics import TOOL_CALLS, TOOL_LATENCY, span
from app.security.guardrails import mask_email, mask_phone
from app.services.clock import now

log = logging.getLogger("tools")
ORDER_ID = re.compile(r"^A\d{5}$")
RETURN_WINDOW = {"Silver": 30, "Gold": 45, "Platinum": 60}
NON_RETURNABLE = {"Personal Care"}
CANCELLABLE = {"Pending", "Confirmed", "Processing"}


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


@dataclass
class ToolContext:
    db: Session
    customer_id: str          # the AUTHENTICATED customer; tools can never act for anyone else
    role: str = "CUSTOMER"
    conversation_id: str | None = None
    system_override: bool = False   # True only when executing an already human-approved request


@dataclass
class Tool:
    name: str
    risk: str                 # LOW | MEDIUM | HIGH
    description: str
    params: dict              # name -> (type, required)
    fn: Callable[..., dict]


def _days(a: datetime, b: datetime) -> int:
    return (a.date() - b.date()).days


def _own_order(ctx: ToolContext, order_id: str) -> m.Order:
    if not isinstance(order_id, str) or not ORDER_ID.match(order_id):
        raise ToolError("invalid_parameter", "Order ID must look like A12345.")
    o = ctx.db.get(m.Order, order_id)
    if not o or o.customer_id != ctx.customer_id:      # identical error for missing & foreign orders: no existence leak
        raise ToolError("not_found", f"Order {order_id} was not found on your account.")
    return o


def _delay_info(o: m.Order, sh: m.Shipment | None) -> dict:
    today = now()
    exp = (sh.expected_delivery if sh else None) or o.expected_delivery
    if o.status in ("Delivered", "Returned", "Cancelled") or (sh and sh.status == "Delivered"):
        return {"is_delayed": False, "days_late": 0, "expected_delivery": exp.date().isoformat() if exp else None}
    late = max(_days(today, exp), 0) if exp else 0
    return {"is_delayed": late > 0, "days_late": late, "expected_delivery": exp.date().isoformat() if exp else None}


# ----------------------------------------------------------------------------- LOW RISK
def get_customer(ctx: ToolContext) -> dict:
    c = ctx.db.get(m.Customer, ctx.customer_id)
    if not c:
        raise ToolError("not_found", "Customer not found.")
    return {"customer_id": c.customer_id, "name": c.name, "membership_tier": c.membership_tier,
            "email": mask_email(c.email), "phone": mask_phone(c.phone or "")}


def get_order(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    sh = ctx.db.query(m.Shipment).filter_by(order_id=order_id).first()
    d = _delay_info(o, sh)
    city = (o.shipping_address or "").split(",")[-1].strip()    # never return the full address
    return {"order_id": o.order_id, "status": o.status, "order_date": o.order_date.date().isoformat(), "total_amount": o.total_amount,
            "currency": "USD", "ship_to_city": city, "expected_delivery": d["expected_delivery"],
            "delivered_on": o.delivered_at.date().isoformat() if o.delivered_at else None, **{k: d[k] for k in ("is_delayed", "days_late")}}


def get_order_items(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    items = []
    for it in o.items:
        items.append({"product_id": it.product_id, "name": it.product.name if it.product else "?", "category": it.product.category if it.product else None,
                      "quantity": it.quantity, "price": it.price})
    return {"order_id": order_id, "items": items}


def track_shipment(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    sh = ctx.db.query(m.Shipment).filter_by(order_id=order_id).first()
    if not sh:
        return {"order_id": order_id, "has_shipment": False, "order_status": o.status,
                "message": "No shipment has been created for this order yet."}
    d = _delay_info(o, sh)
    return {"order_id": order_id, "has_shipment": True, "carrier": sh.carrier, "tracking_number": sh.tracking_number, "shipment_status": sh.status,
            "last_update": sh.last_update.date().isoformat() if sh.last_update else None, **d}


def get_payment_status(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    pays = ctx.db.query(m.Payment).filter_by(order_id=order_id).order_by(m.Payment.created_at).all()
    succ = [p for p in pays if p.status == "Success"]
    return {"order_id": order_id, "payments": [{"payment_id": p.payment_id, "method": p.payment_method,
            "card_last4": p.card_last4, "amount": p.amount, "status": p.status, "reference": "TXN-****" + p.transaction_reference[-4:]} for p in pays],
            "duplicate_charge_detected": len(succ) > 1, "successful_payments": len(succ)}


def get_refund_status(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    rs = ctx.db.query(m.Refund).filter_by(order_id=order_id).order_by(m.Refund.initiated_at).all()
    return {"order_id": order_id, "has_refund": bool(rs), "refunds": [{"refund_id": r.refund_id, "amount": r.amount, "status": r.status, "reason": r.reason,
            "initiated_on": r.initiated_at.date().isoformat(), "completed_on": r.completed_at.date().isoformat() if r.completed_at else None} for r in rs]}


def check_return_eligibility(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    c = ctx.db.get(m.Customer, ctx.customer_id)
    window = RETURN_WINDOW.get(c.membership_tier, 30)
    base = {"order_id": order_id, "membership_tier": c.membership_tier, "window_days": window}
    if o.status != "Delivered" or not o.delivered_at:
        return {**base, "eligible": False, "reason_code": "not_delivered", "reason": f"Order status is {o.status}; returns apply only after delivery."}
    since = _days(now(), o.delivered_at)
    cats = {it.product.category for it in o.items if it.product}
    if cats & NON_RETURNABLE:
        return {**base, "eligible": False, "reason_code": "non_returnable", "days_since_delivery": since, "reason": "The order contains a non-returnable item category (Personal Care).", "needs_human": True}
    if since > window:
        return {**base, "eligible": False, "reason_code": "window_expired", "days_since_delivery": since, "days_overdue": since - window,
                "reason": f"Delivered {since} days ago; the {c.membership_tier} return window is {window} days."}
    return {**base, "eligible": True, "reason_code": "ok", "days_since_delivery": since, "days_left": window - since, "reason": "Within the return window."}


def check_warranty(ctx: ToolContext, order_id: str) -> dict:
    o = _own_order(ctx, order_id)
    if not o.delivered_at:
        return {"order_id": order_id, "covered": False, "reason": "Warranty starts on the delivery date; this order has not been delivered."}
    c = ctx.db.get(m.Customer, ctx.customer_id)
    out = []
    for it in o.items:
        p = it.product
        months = p.warranty_period or 0
        if months and p.category == "Electronics" and c.membership_tier == "Platinum":
            months += 6
        elapsed = (now().year - o.delivered_at.year) * 12 + now().month - o.delivered_at.month
        out.append({"product": p.name, "category": p.category, "warranty_months": months, "months_elapsed": elapsed, "in_warranty": months > 0 and elapsed < months})
    return {"order_id": order_id, "items": out, "covered": any(i["in_warranty"] for i in out)}


def get_customer_support_history(ctx: ToolContext, limit: int = 5) -> dict:
    ts = ctx.db.query(m.SupportTicket).filter_by(customer_id=ctx.customer_id).order_by(m.SupportTicket.created_at.desc()).limit(max(1, min(int(limit), 20))).all()
    return {"tickets": [{"ticket_id": t.ticket_id, "category": t.category, "priority": t.priority, "status": t.status, "order_id": t.order_id,
                         "created_on": t.created_at.date().isoformat()} for t in ts]}


def get_product_info(ctx: ToolContext, query: str) -> dict:
    """Public catalogue lookup (not customer data)."""
    q = re.sub(r"[^A-Za-z0-9 ]", "", query or "").strip()
    if len(q) < 3:
        raise ToolError("invalid_parameter", "Please give a product name.")
    rows = []
    for w in [w for w in q.split() if len(w) > 2][:4]:
        rows = ctx.db.query(m.Product).filter(m.Product.name.ilike(f"%{w}%")).limit(3).all()
        if rows:
            break
    def stock(n):
        return "Out of Stock" if n == 0 else ("Low Stock" if n < 10 else "In Stock")
    return {"matches": [{"product_id": p.product_id, "name": p.name, "category": p.category, "price": p.price, "availability": stock(p.inventory),
                         "warranty_months": p.warranty_period} for p in rows]}


# ----------------------------------------------------------------------------- MEDIUM RISK
def _new_ticket(ctx: ToolContext, category: str, priority: str, description: str, order_id: str | None = None, context: dict | None = None) -> m.SupportTicket:
    n = ctx.db.query(m.SupportTicket).count() + 1
    tid = f"TK{n:05d}"
    while ctx.db.get(m.SupportTicket, tid):
        n += 1
        tid = f"TK{n:05d}"
    t = m.SupportTicket(ticket_id=tid, customer_id=ctx.customer_id, category=category, priority=priority, status="Open", description=description[:2000],
                        order_id=order_id, conversation_id=ctx.conversation_id, escalation_context=context, created_at=now())
    ctx.db.add(t)
    ctx.db.commit()
    return t


def create_support_ticket(ctx: ToolContext, category: str, description: str, priority: str = "Medium", order_id: str | None = None) -> dict:
    if priority not in ("Low", "Medium", "High", "Urgent"):
        raise ToolError("invalid_parameter", "Priority must be Low, Medium, High or Urgent.")
    if not description or len(description) < 3:
        raise ToolError("invalid_parameter", "A description is required.")
    if order_id:
        _own_order(ctx, order_id)
    t = _new_ticket(ctx, category, priority, description, order_id)
    return {"ticket_id": t.ticket_id, "status": t.status, "priority": t.priority, "category": t.category}


def create_return_request(ctx: ToolContext, order_id: str, reason: str = "Customer requested return") -> dict:
    el = check_return_eligibility(ctx, order_id)
    if not el["eligible"]:
        raise ToolError("not_eligible", el["reason"])
    t = _new_ticket(ctx, "Return", "Medium", f"Return request for {order_id}: {reason}", order_id)
    return {"return_request_id": t.ticket_id, "order_id": order_id, "status": "Created", "label": "A prepaid return label will be issued within 1 business day."}


def request_address_change(ctx: ToolContext, order_id: str, new_address: str) -> dict:
    o = _own_order(ctx, order_id)
    if o.status not in CANCELLABLE:
        raise ToolError("not_allowed", f"The address cannot be changed once the order status is {o.status}.")
    if len(new_address or "") < 8:
        raise ToolError("invalid_parameter", "Please provide the full new address.")
    t = _new_ticket(ctx, "Address Change", "Medium", f"Address change for {order_id}", order_id)
    return {"ticket_id": t.ticket_id, "order_id": order_id, "status": "Created"}


# ----------------------------------------------------------------------------- HIGH RISK
def _gate(ctx: ToolContext, action: str, params: dict, amount: float, confirmed: bool, always_approval: bool, reason: str):
    """Returns None if the action may run now, otherwise a dict describing the required confirmation/approval."""
    s = get_settings()
    if ctx.system_override:
        return None
    needs_approval = always_approval or amount >= s.high_value_refund_review
    if not confirmed:
        return {"status": "needs_confirmation", "action": action, "params": params, "requires_human_approval": needs_approval,
                "amount": amount, "message": "Customer confirmation required before proceeding."}
    if needs_approval:
        from app.services.approvals import create_approval
        a = create_approval(ctx.db, ctx.customer_id, ctx.conversation_id, action, params, "HIGH", reason)
        return {"status": "pending_approval", "approval_id": a.approval_id, "action": action, "amount": amount,
                "message": "Submitted for human approval."}
    return None


def create_refund_request(ctx: ToolContext, order_id: str, reason: str = "Customer requested refund", confirmed: bool = False) -> dict:
    o = _own_order(ctx, order_id)
    if o.status not in ("Delivered", "Cancelled"):
        raise ToolError("not_allowed", f"A refund cannot be requested while the order status is {o.status}.")
    if ctx.db.query(m.Refund).filter(m.Refund.order_id == order_id, m.Refund.status.in_(["Initiated", "Approved", "Completed"])).first():
        raise ToolError("duplicate", "A refund already exists for this order.")
    if o.status == "Delivered":
        el = check_return_eligibility(ctx, order_id)
        if not el["eligible"]:
            raise ToolError("not_eligible", el["reason"])
    gate = _gate(ctx, "create_refund_request", {"order_id": order_id, "reason": reason}, float(o.total_amount), confirmed, False,
                 f"Refund of ${o.total_amount:.2f} for {order_id}: {reason}")
    if gate:
        return gate
    n = ctx.db.query(m.Refund).count() + 1
    rid = f"R{n}"
    while ctx.db.get(m.Refund, rid):
        n += 1
        rid = f"R{n}"
    ctx.db.add(m.Refund(refund_id=rid, order_id=order_id, amount=o.total_amount, reason=reason[:190], status="Initiated", initiated_at=now()))
    ctx.db.commit()
    return {"status": "created", "refund_id": rid, "order_id": order_id, "amount": o.total_amount, "refund_status": "Initiated"}


def cancel_order(ctx: ToolContext, order_id: str, confirmed: bool = False) -> dict:
    o = _own_order(ctx, order_id)
    if o.status not in CANCELLABLE:
        raise ToolError("not_allowed", f"Orders with status {o.status} cannot be cancelled.")
    gate = _gate(ctx, "cancel_order", {"order_id": order_id}, float(o.total_amount), confirmed, False, f"Cancel order {order_id} (${o.total_amount:.2f})")
    if gate:
        if gate["status"] == "needs_confirmation":
            gate["requires_human_approval"] = o.total_amount >= get_settings().high_value_refund_manager
        if gate["status"] == "needs_confirmation" or o.total_amount >= get_settings().high_value_refund_manager:
            return gate
    if not ctx.system_override and confirmed and o.total_amount >= get_settings().high_value_refund_manager and not gate:
        from app.services.approvals import create_approval
        a = create_approval(ctx.db, ctx.customer_id, ctx.conversation_id, "cancel_order", {"order_id": order_id}, "HIGH", f"Cancel order {order_id}")
        return {"status": "pending_approval", "approval_id": a.approval_id, "action": "cancel_order", "message": "Submitted for human approval."}
    o.status = "Cancelled"
    refund_note = None
    paid = ctx.db.query(m.Payment).filter_by(order_id=order_id, status="Success").first()
    if paid:
        n = ctx.db.query(m.Refund).count() + 1
        ctx.db.add(m.Refund(refund_id=f"R{n}", order_id=order_id, amount=o.total_amount, reason="Order cancelled before shipment", status="Initiated", initiated_at=now()))
        refund_note = f"R{n}"
    ctx.db.commit()
    return {"status": "cancelled", "order_id": order_id, "refund_id": refund_note}


def escalate_to_human(ctx: ToolContext, reason: str, priority: str = "High", order_id: str | None = None, summary: str = "", context: dict | None = None) -> dict:
    if order_id:
        _own_order(ctx, order_id)
    t = _new_ticket(ctx, (context or {}).get("category", "Escalation"), priority, f"[ESCALATION] {reason}\n{summary}"[:2000], order_id, context)
    return {"ticket_id": t.ticket_id, "priority": t.priority, "status": t.status, "expected_response": {"Urgent": "2 hours", "High": "8 hours", "Medium": "24 hours", "Low": "48 hours"}[priority]}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_customer", "LOW", "Own profile (masked).", {}, get_customer),
    Tool("get_product_info", "LOW", "Catalogue lookup.", {"query": (str, True)}, get_product_info),
    Tool("get_order", "LOW", "Order summary.", {"order_id": (str, True)}, get_order),
    Tool("get_order_items", "LOW", "Order line items.", {"order_id": (str, True)}, get_order_items),
    Tool("track_shipment", "LOW", "Shipment status.", {"order_id": (str, True)}, track_shipment),
    Tool("get_payment_status", "HIGH", "Payment records (masked). Read-only but payment-related.", {"order_id": (str, True)}, get_payment_status),
    Tool("get_refund_status", "LOW", "Refund status.", {"order_id": (str, True)}, get_refund_status),
    Tool("check_return_eligibility", "LOW", "Return window check.", {"order_id": (str, True)}, check_return_eligibility),
    Tool("check_warranty", "LOW", "Warranty coverage.", {"order_id": (str, True)}, check_warranty),
    Tool("get_customer_support_history", "LOW", "Own tickets.", {"limit": (int, False)}, get_customer_support_history),
    Tool("create_support_ticket", "MEDIUM", "Create ticket.", {"category": (str, True), "description": (str, True), "priority": (str, False), "order_id": (str, False)}, create_support_ticket),
    Tool("create_return_request", "MEDIUM", "Create return.", {"order_id": (str, True), "reason": (str, False)}, create_return_request),
    Tool("request_address_change", "MEDIUM", "Address change request.", {"order_id": (str, True), "new_address": (str, True)}, request_address_change),
    Tool("create_refund_request", "HIGH", "Refund (needs confirmation; >= $200 needs human approval).", {"order_id": (str, True), "reason": (str, False), "confirmed": (bool, False)}, create_refund_request),
    Tool("cancel_order", "HIGH", "Cancel order (needs confirmation; >= $500 needs approval).", {"order_id": (str, True), "confirmed": (bool, False)}, cancel_order),
    Tool("escalate_to_human", "MEDIUM", "Escalate with context.", {"reason": (str, True), "priority": (str, False), "order_id": (str, False), "summary": (str, False), "context": (dict, False)}, escalate_to_human),
]}


def execute_tool(ctx: ToolContext, name: str, **params) -> dict:
    """Single entry point. Returns {ok, data|error, risk, latency_ms}. Never raises."""
    t0 = time.perf_counter()
    tool = TOOLS.get(name)
    if not tool:
        TOOL_CALLS.labels(name, "unknown_tool").inc()
        return {"ok": False, "tool": name, "error": {"code": "unknown_tool", "message": "Tool not allowed."}, "risk": None, "latency_ms": 0}
    try:
        for p in params:
            if p not in tool.params:
                raise ToolError("invalid_parameter", f"Unexpected parameter '{p}'.")
        for p, (typ, req) in tool.params.items():
            if req and p not in params:
                raise ToolError("invalid_parameter", f"Missing parameter '{p}'.")
            if p in params and params[p] is not None and not isinstance(params[p], typ):
                raise ToolError("invalid_parameter", f"Parameter '{p}' must be {typ.__name__}.")
        if ctx.role not in ("CUSTOMER", "SUPPORT_AGENT", "ADMIN") or not ctx.customer_id:
            raise ToolError("unauthorized", "Not authorized.")
        with span(f"tool.{name}"):
            data = tool.fn(ctx, **params)
        TOOL_CALLS.labels(name, "ok").inc()
        res = {"ok": True, "tool": name, "data": data, "risk": tool.risk}
    except ToolError as e:
        TOOL_CALLS.labels(name, e.code).inc()
        res = {"ok": False, "tool": name, "error": {"code": e.code, "message": e.message}, "risk": tool.risk}
    except Exception as e:  # tool failure must not crash the turn
        ctx.db.rollback()
        TOOL_CALLS.labels(name, "exception").inc()
        log.exception("tool failure", extra={"tool": name})
        res = {"ok": False, "tool": name, "error": {"code": "tool_failure", "message": "The tool is temporarily unavailable."}, "risk": tool.risk}
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    TOOL_LATENCY.labels(name).observe(res["latency_ms"] / 1000)
    return res
