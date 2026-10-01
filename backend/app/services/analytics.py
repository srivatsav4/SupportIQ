"""Admin analytics computed from real interaction logs, conversations and tickets."""
from collections import Counter, defaultdict
from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import db as m
from app.services.clock import now


def _avg(x):
    x = [v for v in x if v is not None]
    return round(sum(x) / len(x), 3) if x else None


def summary(db: Session) -> dict:
    convs = db.query(m.Conversation).all()
    logs = db.query(m.InteractionLog).all()
    total = len(convs)
    by = Counter(c.resolution_status for c in convs)
    calls = sum(l.tool_calls for l in logs)
    fails = sum(l.tool_failures for l in logs)
    tokens = sum(l.tokens for l in logs)
    done = [c for c in convs if c.resolution_status in ("ai_resolved", "escalated") and c.updated_at and c.created_at]
    open_t = db.query(m.SupportTicket).filter(m.SupportTicket.status.in_(["Open", "In Progress"])).count()
    high_t = db.query(m.SupportTicket).filter(m.SupportTicket.priority.in_(["High", "Urgent"]), m.SupportTicket.status.in_(["Open", "In Progress"])).count()
    return {
        "total_conversations": total,
        "ai_resolution_rate": round(by["ai_resolved"] / total, 4) if total else None,
        "human_escalation_rate": round(by["escalated"] / total, 4) if total else None,
        "avg_response_time_ms": _avg([l.latency_ms for l in logs]),
        "avg_resolution_time_s": _avg([(c.updated_at - c.created_at).total_seconds() for c in done]),
        "open_tickets": open_t, "high_priority_tickets": high_t,
        "tool_failure_rate": round(fails / calls, 4) if calls else None,
        "rag_retrieval_quality": _avg([l.top_retrieval_score for l in logs if l.top_retrieval_score]),
        "groundedness": _avg([l.groundedness for l in logs]),
        "citation_accuracy": _avg([l.citation_accuracy for l in logs]),
        "verifier_pass_rate": round(sum(1 for l in logs if l.verifier_passed) / len(logs), 4) if logs else None,
        "estimated_llm_cost_usd": round(tokens / 1000 * get_settings().llm_cost_per_1k_tokens, 4),
        "llm_tokens": tokens, "ai_turns": len(logs),
        "pending_approvals": db.query(m.ApprovalRequest).filter_by(status="PENDING").count(),
    }


def timeseries(db: Session, days: int = 14) -> dict:
    start = now() - timedelta(days=days - 1)
    day = lambda d: d.strftime("%Y-%m-%d")
    labels = [day(start + timedelta(days=i)) for i in range(days)]
    conv = defaultdict(lambda: Counter())
    for c in db.query(m.Conversation).filter(m.Conversation.created_at >= start.replace(hour=0, minute=0, second=0)).all():
        conv[day(c.created_at)]["total"] += 1
        conv[day(c.created_at)][c.resolution_status] += 1
    lat = defaultdict(list)
    for l in db.query(m.InteractionLog).filter(m.InteractionLog.created_at >= start.replace(hour=0, minute=0, second=0)).all():
        lat[day(l.created_at)].append(l.latency_ms)
    return {"labels": labels,
            "conversations": [conv[d]["total"] for d in labels],
            "ai_resolved": [conv[d]["ai_resolved"] for d in labels],
            "escalated": [conv[d]["escalated"] for d in labels],
            "avg_latency_ms": [round(sum(lat[d]) / len(lat[d]), 1) if lat[d] else 0 for d in labels]}


def distributions(db: Session) -> dict:
    intents = Counter(i for (i,) in db.query(m.Conversation.intent).all() if i)
    prio = Counter(p for (p,) in db.query(m.SupportTicket.priority).all())
    cats = Counter(c for (c,) in db.query(m.SupportTicket.category).all())
    perf = db.query(m.InteractionLog.intent, func.avg(m.InteractionLog.groundedness), func.avg(m.InteractionLog.latency_ms), func.count()).group_by(m.InteractionLog.intent).all()
    return {"intents": dict(intents.most_common()), "ticket_priority": dict(prio), "ticket_categories": dict(cats.most_common(8)),
            "ai_performance": [{"intent": i, "groundedness": round(g or 0, 3), "avg_latency_ms": round(l or 0, 1), "turns": n} for i, g, l, n in perf]}
