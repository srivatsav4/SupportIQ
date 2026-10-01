def test_health_and_docs(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/docs").status_code == 200
    assert "novasupport_http_requests_total" in client.get("/metrics").text


def test_auth_required(client):
    assert client.get("/api/orders").status_code == 401
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401


def test_bad_login(client):
    assert client.post("/api/auth/login", json={"email": "priya.sharma@example.com", "password": "nope"}).status_code == 401


def test_customer_sees_only_own_data(client, priya):
    orders = client.get("/api/orders", headers=priya).json()
    assert orders and all(o["order_id"] != "A20001" for o in orders)
    assert client.get("/api/orders/A20001", headers=priya).status_code == 404
    assert client.get("/api/orders/A12345", headers=priya).status_code == 200
    assert all(t["customer_id"] == "C1001" for t in client.get("/api/tickets", headers=priya).json())


def test_customer_cannot_use_admin_endpoints(client, priya):
    for p in ("/api/admin/analytics/summary", "/api/admin/approvals", "/api/admin/customers", "/api/admin/system"):
        assert client.get(p, headers=priya).status_code == 403
    assert client.get("/api/tickets?all=true", headers=priya).json() == [t for t in client.get("/api/tickets", headers=priya).json()]


def test_conversation_isolation(client, priya, rohan):
    r = client.post("/api/chat", headers=priya, json={"message": "Where is order A12346?"}).json()
    cid = r["conversation_id"]
    assert client.get(f"/api/conversations/{cid}", headers=priya).status_code == 200
    assert client.get(f"/api/conversations/{cid}", headers=rohan).status_code == 404
    assert client.post("/api/chat", headers=rohan, json={"message": "hi", "conversation_id": cid}).status_code == 404


def test_chat_validation(client, priya):
    assert client.post("/api/chat", headers=priya, json={"message": ""}).status_code == 422
    assert client.post("/api/chat", headers=priya, json={"message": "x" * 5000}).status_code == 422


def test_admin_endpoints(client, admin):
    s = client.get("/api/admin/analytics/summary", headers=admin).json()
    assert "ai_resolution_rate" in s and "total_conversations" in s
    assert client.get("/api/admin/analytics/timeseries", headers=admin).status_code == 200
    assert client.get("/api/admin/analytics/distributions", headers=admin).status_code == 200
    assert client.get("/api/admin/knowledge", headers=admin).json()["total_chunks"] > 50
    c = client.get("/api/admin/customers?q=Priya", headers=admin).json()
    assert c and "***" in c[0]["email"]
    assert client.get("/api/admin/system", headers=admin).json()["database"]["status"] == "up"


def test_request_id_header(client):
    assert client.get("/api/health", headers={"x-request-id": "abc123"}).headers["x-request-id"] == "abc123"
