.PHONY: up down seed ingest eval test frontend-build dev-backend dev-frontend lint-data

up:            ## Start everything (Postgres+pgvector, Redis, backend, frontend, Prometheus, Grafana)
	docker compose up --build
down:
	docker compose down
seed:          ## (Re)load synthetic data  (inside the container: docker compose exec backend python scripts/seed_database.py)
	python scripts/seed_database.py
ingest:
	python scripts/ingest_knowledge_base.py
eval:
	cd backend && python -m app.evaluation.run
test:
	cd backend && python -m pytest -q
dev-backend:   ## Local dev without Docker (SQLite + in-process Redis fallback)
	cd backend && uvicorn app.main:app --reload --port 8000
dev-frontend:
	cd frontend && npm install && npm run dev
frontend-build:
	cd frontend && npm install && npm run build
