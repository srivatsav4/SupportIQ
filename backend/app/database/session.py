from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

Base = declarative_base()
_settings = get_settings()

_url = _settings.database_url
if _url.startswith("postgresql://") or _url.startswith("postgres://"):
    _url = "postgresql+psycopg2://" + _url.split("://", 1)[1]      # SQLAlchemy 2.1 defaults to psycopg3; we ship psycopg2
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create extension (Postgres), tables and indexes. Idempotent."""
    from app.models import db as _models  # noqa: F401  (register models)
    if is_postgres():
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    if is_postgres():
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding vector(%d)" % _settings.embedding_dim))
            conn.execute(text("CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops)"))
