"""Parser -> cleaning -> chunking -> metadata -> embeddings -> store (pgvector on Postgres)."""
import re
from pathlib import Path
from sqlalchemy import text
from app.config import get_settings
from app.database.session import SessionLocal, init_db, is_postgres
from app.models.db import KBChunk
from app.rag.embeddings import get_embedder


def clean(md: str) -> str:
    md = md.replace("\r", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def parse_document(path: Path) -> dict:
    raw = clean(path.read_text(encoding="utf-8"))
    lines = raw.split("\n")
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("# ") else path.stem.replace("_", " ").title()
    sections, cur, buf = [], "Overview", []
    for ln in lines[1:] if lines and lines[0].startswith("# ") else lines:
        if ln.startswith("## "):
            if "".join(buf).strip():
                sections.append((cur, "\n".join(buf).strip()))
            cur, buf = ln[3:].strip(), []
        else:
            buf.append(ln)
    if "".join(buf).strip():
        sections.append((cur, "\n".join(buf).strip()))
    return {"document": path.name, "title": title, "sections": sections}


def chunk_section(body: str, max_chars: int = 700) -> list[str]:
    sents = re.split(r"(?<=[.!?])\s+", body.replace("\n", " "))
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > max_chars and cur:
            chunks.append(cur.strip()); cur = ""
        cur += " " + s
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def build_chunks(kb_dir: str) -> list[dict]:
    out = []
    for p in sorted(Path(kb_dir).glob("*.md")):
        doc = parse_document(p)
        prefix = p.stem.replace("_policy", "").replace("_guidelines", "").replace("_", "")[:10]
        n = 0
        for section, body in doc["sections"]:
            for c in chunk_section(body):
                n += 1
                out.append({"chunk_id": f"{prefix}_{n:03d}", "document": doc["document"], "section": section,
                            "source": doc["title"], "content": c})
    return out


def ingest(kb_dir: str | None = None) -> dict:
    s = get_settings()
    init_db()
    chunks = build_chunks(kb_dir or s.knowledge_base_dir)
    emb = get_embedder()
    vecs = emb.embed_many([f"{c['source']} {c['section']}. {c['content']}" for c in chunks])
    with SessionLocal() as db:
        db.query(KBChunk).delete()
        for c, v in zip(chunks, vecs):
            db.add(KBChunk(**c, embedding_json=[round(float(x), 5) for x in v]))
        db.commit()
        if is_postgres():
            for c, v in zip(chunks, vecs):
                db.execute(text("UPDATE kb_chunks SET embedding = :e WHERE chunk_id = :i"),
                           {"e": "[" + ",".join(f"{float(x):.5f}" for x in v) + "]", "i": c["chunk_id"]})
            db.commit()
    from app.rag.retriever import invalidate_cache
    invalidate_cache()
    return {"documents": len({c["document"] for c in chunks}), "chunks": len(chunks)}
