"""Central configuration. All values come from environment variables with safe local defaults."""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
# In Docker the repo data dir is mounted at /data; locally it is ../data
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
if not DATA_DIR.exists():
    DATA_DIR = Path("/data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NovaSupport AI"
    environment: str = "local"
    database_url: str = "sqlite:///./novasupport.db"
    redis_url: str = "redis://localhost:6379/0"
    use_fake_redis: bool = True          # falls back to in-process store when Redis is unreachable
    jwt_secret: str = "change-me-local-demo-secret"
    jwt_expire_minutes: int = 480
    demo_password: str = "demo1234"     # password for ALL synthetic demo accounts

    # LLM: "demo" (deterministic, no model needed) | "ollama" | "openai_compatible"
    llm_provider: str = "demo"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    llm_timeout_seconds: float = 20.0
    llm_cost_per_1k_tokens: float = 0.0   # local models are free; set if using a paid API

    embedding_backend: str = "hash"       # "hash" (no download) | "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    rag_top_k: int = 4
    rag_min_score: float = 0.12

    knowledge_base_dir: str = str(DATA_DIR / "knowledge_base")
    seed: int = 42
    as_of_date: str = "2026-09-30"   # fixed reference date so synthetic data + demos stay deterministic; set empty for real time
    n_customers: int = 1000
    n_products: int = 120
    n_orders: int = 2200

    high_value_refund_review: float = 200.0
    high_value_refund_manager: float = 500.0
    cors_origins: str = "http://localhost:5173,http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
