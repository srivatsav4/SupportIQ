"""Prometheus metrics, structured logging, optional OpenTelemetry tracing."""
import json, logging, time, contextvars
from prometheus_client import Counter, Histogram, Gauge

REQUESTS = Counter("novasupport_http_requests_total", "HTTP requests", ["method", "path", "status"])
REQ_LATENCY = Histogram("novasupport_http_request_seconds", "Total request latency", ["path"])
LLM_CALLS = Counter("novasupport_llm_calls_total", "LLM calls", ["provider", "outcome"])
LLM_LATENCY = Histogram("novasupport_llm_latency_seconds", "LLM latency", ["provider"])
LLM_TOKENS = Counter("novasupport_llm_tokens_total", "LLM tokens (estimated if provider omits)")
LLM_COST = Counter("novasupport_llm_cost_usd_total", "Estimated LLM cost in USD")
TOOL_CALLS = Counter("novasupport_tool_calls_total", "Tool calls", ["tool", "outcome"])
TOOL_LATENCY = Histogram("novasupport_tool_latency_seconds", "Tool latency", ["tool"])
RAG_LATENCY = Histogram("novasupport_rag_latency_seconds", "RAG retrieval latency")
DB_LATENCY = Histogram("novasupport_db_latency_seconds", "DB query latency (health probe)")
ESCALATIONS = Counter("novasupport_escalations_total", "Escalations to humans", ["reason"])
GUARDRAIL_BLOCKS = Counter("novasupport_guardrail_blocks_total", "Guardrail blocks", ["category"])
VERIFIER = Counter("novasupport_verifier_total", "Verifier outcomes", ["result"])
AGENT_TURNS = Counter("novasupport_agent_turns_total", "Agent turns", ["intent"])
ERRORS = Counter("novasupport_errors_total", "Errors", ["where"])

request_id_var = contextvars.ContextVar("request_id", default="-")
conversation_id_var = contextvars.ContextVar("conversation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)), "level": record.levelname,
             "logger": record.name, "msg": record.getMessage(), "request_id": request_id_var.get(),
             "conversation_id": conversation_id_var.get()}
        for k in ("event", "tool", "latency_ms", "intent", "agent", "outcome"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d)


def setup_logging():
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)


def setup_tracing(app=None):
    """OpenTelemetry is optional: enabled only if the SDK is installed. Console exporter by default,
    OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    try:
        import os
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        provider = TracerProvider(resource=Resource.create({"service.name": "novasupport-backend"}))
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        elif os.getenv("OTEL_CONSOLE", "0") == "1":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        return True
    except Exception:
        return False


def span(name: str):
    """Context manager creating an OTel span if available, else a no-op."""
    try:
        from opentelemetry import trace
        return trace.get_tracer("novasupport").start_as_current_span(name)
    except Exception:
        import contextlib
        return contextlib.nullcontext()
