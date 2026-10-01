# Architecture

```
React (Vite, Tailwind) ──/api──▶ FastAPI ──▶ Orchestrator ──▶ Guardrails ─▶ Intent+Sentiment ─▶ Plan
                                                   │                                      │
                                   ┌───────────────┼───────────────┐                      ▼
                                   ▼               ▼               ▼              Escalation / Approvals
                             RAG (pgvector)   Controlled tools   Verifier
                                   │               │
                                PostgreSQL      PostgreSQL        Redis: conversation memory (30 min TTL)
                           Prometheus ◀── /metrics        Grafana        OpenTelemetry (optional)
```

## One turn (`backend/app/agents/orchestrator.py`)
1. **Guardrails**: prompt-injection and third-party-PII patterns are blocked before any tool or model sees the message; card/CVV/OTP/password strings are redacted before storage.
2. **Intent** (19 intents, weighted rules; optional LLM refinement with strict JSON validation and rule fallback) and **sentiment/urgency**.
3. **Retrieval**: query expansion → vector search (pgvector `<=>` on Postgres, NumPy cosine on SQLite) + lexical candidates → rerank (semantic + lexical/section overlap) → numbered context.
4. **Plan per intent**: low-risk tools run directly; medium-risk tools create tickets/returns; high-risk tools return `needs_confirmation`, and above policy thresholds become **approval requests** that only an admin can execute.
5. **Compose**: in the default demo mode, answers are assembled from tool output plus *extractive* policy sentences (each tied to a chunk). With `LLM_PROVIDER=ollama|openai_compatible` an LLM drafts the answer instead.
6. **Verify** (`agents/verifier.py`): sensitive data, forbidden promises, unsupported numbers/ids, lexical groundedness, citation validity. LLM drafts that fail fall back to the extractive answer; if that fails too the turn escalates with the "not enough verified information" message.
7. **Persist**: conversation, per-turn interaction log (latency, groundedness, tool calls, tokens) feeding the dashboard; Redis holds minimal masked state.

## Why extractive by default
Policy claims are quoted from retrieved chunks, so they are traceable and cannot be invented. The cost is stilted prose. A local LLM improves tone, and the verifier still gates it.

## Data
`backend/app/services/synthetic.py` generates 1,000 customers, 120 products, ~2,200 orders with payments, shipments, refunds, tickets, plus fixed demo scenarios (A12345 ... A12354, A20001, A30001). Deterministic for a seed. `AS_OF_DATE` fixes "today" so delays stay reproducible.
