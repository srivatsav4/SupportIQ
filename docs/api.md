# API

Interactive docs: `http://localhost:8000/api/docs` (OpenAPI at `/api/openapi.json`). Metrics: `/metrics`.

| Method & path | Role | Purpose |
|---|---|---|
| `POST /api/auth/login` | any | email + password → JWT |
| `GET /api/auth/demo-users` | any | synthetic demo accounts |
| `POST /api/chat` | user | `{message, conversation_id?}` → answer, steps, citations, actions, escalation, confirmation, verification |
| `POST /api/chat/confirm` | user | `{conversation_id, confirm}` confirm/decline a pending high-risk action |
| `GET /api/conversations[/{id}]` | user (own) / staff (`?all=true`) | history |
| `GET /api/orders[/{id}]` | user (own) | orders, shipment, items, refunds |
| `GET /api/tickets`, `PATCH /api/tickets/{id}` | user (own) / staff | tickets |
| `GET /api/admin/analytics/{summary,timeseries,distributions}` | admin | dashboard data |
| `GET /api/admin/approvals`, `POST .../{id}/approve|reject` | admin | human-in-the-loop |
| `GET /api/admin/customers` | staff | masked customer search |
| `GET /api/admin/knowledge`, `POST .../search`, `POST .../reingest` | staff / admin | knowledge base |
| `GET /api/admin/evaluation/latest`, `POST .../run` | staff / admin | evaluation |
| `GET /api/admin/system`, `GET /api/health` | staff / any | health |

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"priya.sharma@example.com","password":"demo1234"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s localhost:8000/api/chat -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"My order A12345 has not arrived yet."}'
```
