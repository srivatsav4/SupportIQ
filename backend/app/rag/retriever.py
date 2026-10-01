"""Retriever (pgvector or in-memory cosine) + lexical reranker + context builder with citations."""
import time
from dataclasses import dataclass, field
import numpy as np
from sqlalchemy import text
from app.config import get_settings
from app.database.session import SessionLocal, is_postgres
from app.models.db import KBChunk
from app.rag.embeddings import get_embedder, tokenize, expand_query
from app.observability.metrics import RAG_LATENCY

_cache = {"ids": None, "mat": None, "meta": None}


def invalidate_cache():
    _cache.update(ids=None, mat=None, meta=None, vocab=None)


@dataclass
class Retrieved:
    chunk_id: str
    document: str
    section: str
    source: str
    content: str
    score: float

    def citation(self) -> str:
        return f"{self.source} — {self.section}"


@dataclass
class RetrievalResult:
    chunks: list[Retrieved] = field(default_factory=list)
    latency_ms: float = 0.0
    top_score: float = 0.0
    error: str = ""


def _load_cache():
    if _cache["mat"] is not None:
        return
    with SessionLocal() as db:
        rows = db.query(KBChunk).all()
    _cache["ids"] = [r.chunk_id for r in rows]
    _cache["meta"] = {r.chunk_id: r for r in rows}
    _cache["mat"] = np.array([r.embedding_json for r in rows], dtype=np.float32) if rows else np.zeros((0, 1), dtype=np.float32)


def _lexical_candidates(query: str, k: int) -> list[tuple[KBChunk, float]]:
    _load_cache()
    qt = set(tokenize(query))
    scored = sorted(((_lexical(qt, c), c) for c in _cache["meta"].values()), key=lambda x: -x[0])
    return [(c, 0.0) for sc, c in scored[:k] if sc > 0]


def _vector_search(qv: np.ndarray, k: int) -> list[tuple[KBChunk, float]]:
    if is_postgres():
        with SessionLocal() as db:
            qs = "[" + ",".join(f"{float(x):.5f}" for x in qv) + "]"
            rows = db.execute(text("SELECT chunk_id, 1 - (embedding <=> CAST(:q AS vector)) AS score FROM kb_chunks ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"),
                              {"q": qs, "k": k}).fetchall()
            out = []
            for cid, sc in rows:
                out.append((db.get(KBChunk, cid), float(sc)))
            return out
    _load_cache()
    if _cache["mat"].shape[0] == 0:
        return []
    sims = _cache["mat"] @ qv
    idx = np.argsort(-sims)[:k]
    return [(_cache["meta"][_cache["ids"][i]], float(sims[i])) for i in idx]


def _lexical(query_toks: set[str], chunk: KBChunk) -> float:
    ct = set(tokenize(chunk.content))
    st = set(tokenize(chunk.section + " " + chunk.source))
    if not query_toks:
        return 0.0
    return 0.7 * len(query_toks & ct) / len(query_toks) + 0.3 * len(query_toks & st) / len(query_toks)


def retrieve(query: str, k: int | None = None, min_score: float | None = None) -> RetrievalResult:
    s = get_settings()
    k = k or s.rag_top_k
    min_score = s.rag_min_score if min_score is None else min_score
    t0 = time.perf_counter()
    try:
        query = expand_query(query)
        qv = get_embedder().embed(query)
        cands = _vector_search(qv, max(k * 4, 12))
        seen = {c.chunk_id for c, _ in cands}
        vec_scores = {c.chunk_id: vs for c, vs in cands}
        for c, _ in _lexical_candidates(query, max(k * 2, 8)):
            if c.chunk_id not in seen:
                cands.append((c, float(np.dot(np.array(c.embedding_json, dtype=np.float32), qv))))
        qt = set(tokenize(query))
        ranked = []
        for ch, vs in cands:
            lex = _lexical(qt, ch)
            ranked.append((0.5 * max(vs, 0) + 0.5 * lex, ch))        # rerank: blend semantic + lexical/title overlap
        ranked.sort(key=lambda x: -x[0])
        chunks = [Retrieved(c.chunk_id, c.document, c.section, c.source, c.content, round(sc, 4))
                  for sc, c in ranked[:k] if sc >= min_score]
        res = RetrievalResult(chunks=chunks, top_score=chunks[0].score if chunks else 0.0)
    except Exception as e:  # vector search failure -> degrade gracefully
        res = RetrievalResult(error=f"{type(e).__name__}: {e}")
    res.latency_ms = (time.perf_counter() - t0) * 1000
    RAG_LATENCY.observe(res.latency_ms / 1000)
    return res


def build_context(chunks: list[Retrieved]) -> str:
    return "\n\n".join(f"[{i}] ({c.source} — {c.section})\n{c.content}" for i, c in enumerate(chunks, 1))


GENERIC = set(tokenize("long much many take keep get make often soon free work works need want help know give use way thing things possible really long time day days buy cost price how become happen everyone gets right isn t guarantee"))


def out_of_vocabulary_ratio(question: str) -> float:
    """Share of the question's content words that the knowledge base has never seen (a cheap 'is this in scope?' signal)."""
    _load_cache()
    if not _cache["meta"]:
        return 0.0
    vocab = _cache.get("vocab")
    if vocab is None:
        vocab = set()
        for c in _cache["meta"].values():
            vocab |= set(tokenize(c.content + " " + c.section + " " + c.source))
        _cache["vocab"] = vocab
    qt = [t for t in tokenize(question) if not t.isdigit()]
    if not qt:
        return 0.0
    unk = [t for t in qt if t not in vocab and t not in GENERIC]
    return len(unk) / len(qt)
