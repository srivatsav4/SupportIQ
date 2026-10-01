"""Parse, chunk, embed and index data/knowledge_base/*.md into the vector store (pgvector on Postgres)."""
import sys
from pathlib import Path
for _p in (Path(__file__).resolve().parents[1] / "backend", Path(__file__).resolve().parents[1]):
    if (_p / "app").exists():
        sys.path.insert(0, str(_p))
        break
from app.rag.ingest import ingest

if __name__ == "__main__":
    print("ingested:", ingest())
