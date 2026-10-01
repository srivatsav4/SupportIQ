# Build context is the repository root (see docker-compose.yml)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/pytest.ini .
COPY scripts ./scripts
COPY data /data
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD curl -fs http://localhost:8000/api/health || exit 1
# Tables, pgvector extension/index, synthetic data and knowledge-base ingestion are created automatically on first start.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
