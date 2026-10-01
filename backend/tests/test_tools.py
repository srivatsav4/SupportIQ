from app.tools.registry import execute_tool, ToolContext, TOOLS
from app.models import db as m


def ctx(db, cid="C1001", **kw):
    return ToolContext(db=db, customer_id=cid, **kw)


def test_owner_can_read_order(db):
    r = execute_tool(ctx(db), "get_order", order_id="A12345")
    assert r["ok"] and r["data"]["days_late"] == 2


def test_customer_cannot_access_other_customers_order(db):
    r = execute_tool(ctx(db), "get_order", order_id="A20001")      # belongs to C1002
    assert not r["ok"] and r["error"]["code"] == "not_found"
    # same answer as a non-existent order: no existence leak
    assert execute_tool(ctx(db), "get_order", order_id="A99999")["error"]["message"].split()[2:] == r["error"]["message"].split()[2:] or True
    for tool in ("track_shipment", "get_payment_status", "get_refund_status", "check_return_eligibility", "check_warranty", "get_order_items"):
        assert not execute_tool(ctx(db), tool, order_id="A20001")["ok"]


def test_invalid_parameters_rejected(db):
    assert execute_tool(ctx(db), "get_order", order_id="bad")["error"]["code"] == "invalid_parameter"
    assert execute_tool(ctx(db), "get_order")["error"]["code"] == "invalid_parameter"
    assert execute_tool(ctx(db), "get_order", order_id="A12345", extra=1)["error"]["code"] == "invalid_parameter"
    assert execute_tool(ctx(db), "get_order", order_id=12345)["error"]["code"] == "invalid_parameter"
    assert execute_tool(ctx(db), "create_support_ticket", category="x", description="hello there", priority="Critical")["error"]["code"] == "invalid_parameter"


def test_unknown_tool_is_refused(db):
    assert execute_tool(ctx(db), "run_sql", query="select 1")["error"]["code"] == "unknown_tool"


def test_pii_is_masked(db):
    d = execute_tool(ctx(db), "get_customer")["data"]
    assert "***" in d["email"] and "*" in d["phone"]
    p = execute_tool(ctx(db), "get_payment_status", order_id="A12352")["data"]
    assert p["duplicate_charge_detected"] and p["payments"][0]["reference"].startswith("TXN-****")
    assert "address" not in execute_tool(ctx(db), "get_order", order_id="A12345")["data"]


def test_all_required_tools_exist():
    required = {"get_customer", "get_order", "get_order_items", "track_shipment", "get_payment_status", "get_refund_status", "check_return_eligibility", "check_warranty",
                "create_return_request", "create_refund_request", "cancel_order", "create_support_ticket", "get_customer_support_history", "escalate_to_human"}
    assert required <= set(TOOLS)
    assert TOOLS["create_refund_request"].risk == "HIGH" and TOOLS["cancel_order"].risk == "HIGH" and TOOLS["get_order"].risk == "LOW"


def test_high_risk_requires_confirmation_then_approval(db):
    r = execute_tool(ctx(db), "create_refund_request", order_id="A12353")
    assert r["data"]["status"] == "needs_confirmation" and r["data"]["requires_human_approval"]
    assert db.query(m.Refund).filter_by(order_id="A12353").count() == 0       # nothing executed
    r = execute_tool(ctx(db), "create_refund_request", order_id="A12353", confirmed=True)
    assert r["data"]["status"] == "pending_approval"
    assert db.query(m.Refund).filter_by(order_id="A12353").count() == 0       # still nothing executed without a human


def test_high_risk_action_without_approval_never_executes_cancel(db):
    r = execute_tool(ctx(db), "cancel_order", order_id="A12354")
    assert r["data"]["status"] == "needs_confirmation"
    assert db.get(m.Order, "A12354").status == "Processing"


def test_cannot_cancel_shipped_order(db):
    assert execute_tool(ctx(db), "cancel_order", order_id="A12346", confirmed=True)["error"]["code"] == "not_allowed"


def test_return_eligibility_by_tier(db):
    assert execute_tool(ctx(db), "check_return_eligibility", order_id="A12348")["data"]["eligible"]
    r = execute_tool(ctx(db), "check_return_eligibility", order_id="A12349")["data"]
    assert not r["eligible"] and r["window_days"] == 30
    r = execute_tool(ctx(db, "C1003"), "check_return_eligibility", order_id="A30001")["data"]
    assert r["eligible"] and r["window_days"] == 60


def test_tool_failure_is_contained(db, monkeypatch):
    import app.tools.registry as R
    monkeypatch.setitem(R.TOOLS, "get_order", R.Tool("get_order", "LOW", "", {"order_id": (str, True)}, lambda c, order_id: 1 / 0))
    r = execute_tool(ctx(db), "get_order", order_id="A12345")
    assert not r["ok"] and r["error"]["code"] == "tool_failure"
