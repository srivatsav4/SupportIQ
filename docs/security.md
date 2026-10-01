# Security model

* **No raw DB access for the AI.** Every operation goes through `execute_tool` (`backend/app/tools/registry.py`): allow-listed tool names, parameter names/types validated, ownership enforced against the *authenticated* customer, errors normalised.
* **Tenant isolation.** A customer's order that doesn't belong to them returns the same "not found on your account" response as a missing order. Conversations and Redis memory are bound to the customer id. Staff endpoints require roles (`SUPPORT_AGENT`, `ADMIN`); approvals are `ADMIN` only.
* **Risk levels.** LOW: reads. MEDIUM: tickets, returns, address-change requests. HIGH: refunds, cancellations, payment records. High-risk writes need explicit customer confirmation; refunds >= $200 and duplicate-payment cases need human approval; orders >= $500 cancel only with approval.
* **PII.** Emails/phones masked in tool output and admin lists, card shown as last 4, full shipping address never returned (city only), payment references masked. Output passes a final redaction filter.
* **Prompt injection.** Pattern-based detection blocks override/exfiltration attempts, including those mixed into otherwise normal requests. Pattern matching is a baseline and **can be evaded** by novel phrasing; the structural defences (no DB access, ownership checks, approval gates) are what actually bound the damage.
* **Auth.** PBKDF2-SHA256 password hashes, HS256 JWTs. All demo accounts share one synthetic password. **Do not deploy this auth as is**: it has no rate limiting, refresh tokens, lockout or MFA, and the token is kept in `localStorage`.
* **Secrets.** No keys in the repo; `.env.example` only. `JWT_SECRET` default is for local demo.
* **Known limitations.** The `/api/auth/demo-users` endpoint exposes demo credentials by design; remove it outside demos. Postgres port 5432 is published in compose for convenience.
