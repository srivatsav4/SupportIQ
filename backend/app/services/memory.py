"""Conversation memory in Redis (falls back to an in-process fake Redis if Redis is unreachable).
Stores only minimal, redacted state and expires after 30 minutes of inactivity."""
import json, logging
from app.config import get_settings
from app.security.guardrails import redact_sensitive

log = logging.getLogger("memory")
TTL = 1800
MAX_MESSAGES = 10
_client = None
_backend = "unknown"


def get_redis():
    global _client, _backend
    if _client is not None:
        return _client
    s = get_settings()
    try:
        import redis
        c = redis.Redis.from_url(s.redis_url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
        c.ping()
        _client, _backend = c, "redis"
    except Exception as e:
        log.warning("Redis unavailable (%s); using in-process fallback", type(e).__name__)
        import fakeredis
        _client, _backend = fakeredis.FakeRedis(decode_responses=True), "in-memory-fallback"
    return _client


def backend() -> str:
    get_redis()
    return _backend


def reset_client():
    global _client
    _client = None


def _key(cid: str) -> str:
    return f"conv:{cid}"


def new_state(conversation_id: str, customer_id: str) -> dict:
    return {"conversation_id": conversation_id, "customer_id": customer_id, "messages": [], "intent": None, "active_order": None,
            "entities": {}, "tool_results": {}, "escalated": False, "failed_attempts": 0, "pending_action": None, "clarifications": 0}


def load(conversation_id: str, customer_id: str) -> dict:
    try:
        raw = get_redis().get(_key(conversation_id))
    except Exception:
        raw = None
    if raw:
        st = json.loads(raw)
        if st.get("customer_id") == customer_id:   # never share state across customers
            return st
    return new_state(conversation_id, customer_id)


def save(state: dict) -> None:
    state["messages"] = state["messages"][-MAX_MESSAGES:]
    # keep only compact, masked summaries of tool results
    state["tool_results"] = {k: v for k, v in list(state["tool_results"].items())[-6:]}
    try:
        get_redis().setex(_key(state["conversation_id"]), TTL, json.dumps(state, default=str))
    except Exception as e:
        log.warning("memory save failed: %s", type(e).__name__)


def add_message(state: dict, role: str, content: str):
    state["messages"].append({"role": role, "content": redact_sensitive(content)[:1000]})


def clear(conversation_id: str):
    try:
        get_redis().delete(_key(conversation_id))
    except Exception:
        pass
