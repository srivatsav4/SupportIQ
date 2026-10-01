import logging, time, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.api.routes import router
from app.config import get_settings
from app.database.session import init_db, SessionLocal
from app.observability.metrics import REQUESTS, REQ_LATENCY, ERRORS, request_id_var, setup_logging, setup_tracing

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_tracing(app)
    init_db()
    # auto-initialise on first run so `docker compose up` is enough
    from app.models.db import Customer, KBChunk
    with SessionLocal() as db:
        if db.query(Customer).count() == 0:
            from app.services.seeding import seed
            log.info("empty database: seeding synthetic NovaCart data %s", seed(reset=False))
        if db.query(KBChunk).count() == 0:
            from app.rag.ingest import ingest
            log.info("empty knowledge base: ingesting %s", ingest())
    yield


s = get_settings()
app = FastAPI(title="NovaSupport AI", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan,
              description="GenAI customer-support automation platform for the fictional company NovaCart Technologies. **All data is synthetic.**")
app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def observe(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    t0 = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        ERRORS.labels("http").inc()
        log.exception("unhandled error")
        resp = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    dt = time.perf_counter() - t0
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    REQUESTS.labels(request.method, path, resp.status_code).inc()
    REQ_LATENCY.labels(path).observe(dt)
    resp.headers["x-request-id"] = rid
    log.info("request", extra={"event": "http", "latency_ms": round(dt * 1000, 1), "outcome": resp.status_code})
    return resp


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(router)
