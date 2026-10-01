"""LLM abstraction. Default provider is 'demo' = no model call (deterministic extractive composer is used).
Optional: Ollama (local) or any OpenAI-compatible endpoint. Failures never crash a turn: callers fall back."""
import time
import httpx
from app.config import get_settings
from app.observability.metrics import LLM_CALLS, LLM_LATENCY, LLM_TOKENS, LLM_COST


class LLMUnavailable(Exception):
    pass


def llm_enabled() -> bool:
    return get_settings().llm_provider in ("ollama", "openai_compatible")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def generate(system: str, prompt: str, json_mode: bool = False) -> tuple[str, int]:
    s = get_settings()
    prov = s.llm_provider
    if prov == "demo":
        raise LLMUnavailable("demo provider has no generative model")
    t0 = time.perf_counter()
    try:
        if prov == "ollama":
            r = httpx.post(f"{s.ollama_base_url}/api/chat", timeout=s.llm_timeout_seconds, json={
                "model": s.ollama_model, "stream": False, "format": "json" if json_mode else "",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "options": {"temperature": 0.1}})
            r.raise_for_status()
            d = r.json()
            text = d["message"]["content"]
            tokens = d.get("prompt_eval_count", 0) + d.get("eval_count", 0) or estimate_tokens(system + prompt + text)
        elif prov == "openai_compatible":
            headers = {"Authorization": f"Bearer {s.openai_api_key}"} if s.openai_api_key else {}
            r = httpx.post(f"{s.openai_base_url.rstrip('/')}/chat/completions", headers=headers, timeout=s.llm_timeout_seconds,
                           json={"model": s.openai_model, "temperature": 0.1,
                                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
            r.raise_for_status()
            d = r.json()
            text = d["choices"][0]["message"]["content"]
            tokens = d.get("usage", {}).get("total_tokens") or estimate_tokens(system + prompt + text)
        else:
            raise LLMUnavailable(f"unknown provider {prov}")
    except LLMUnavailable:
        raise
    except Exception as e:
        LLM_CALLS.labels(prov, "error").inc()
        raise LLMUnavailable(f"{type(e).__name__}: {e}")
    LLM_CALLS.labels(prov, "ok").inc()
    LLM_LATENCY.labels(prov).observe(time.perf_counter() - t0)
    LLM_TOKENS.inc(tokens)
    LLM_COST.inc(tokens / 1000 * s.llm_cost_per_1k_tokens)
    return text.strip(), tokens
