from app.services.synthetic import generate
from app.rag.retriever import retrieve, build_context
from app.rag.ingest import build_chunks
from app.config import get_settings


def test_generator_is_deterministic():
    assert generate(seed=7, n_customers=30, n_products=20, n_orders=50) == generate(seed=7, n_customers=30, n_products=20, n_orders=50)


def test_full_size_dataset_meets_spec():
    d = generate()
    assert len([c for c in d["customers"] if c["role"] == "CUSTOMER"]) >= 1000
    assert len(d["orders"]) >= 2000 and len(d["products"]) >= 100
    assert d["payments"] and d["refunds"] and d["shipments"] and d["tickets"]


def test_chunks_have_metadata():
    chunks = build_chunks(get_settings().knowledge_base_dir)
    assert len(chunks) > 50
    for c in chunks[:10]:
        assert {"document", "section", "chunk_id", "source", "content"} <= set(c)


def test_retrieval_finds_right_document():
    r = retrieve("how long does a refund take")
    assert r.chunks and r.chunks[0].document in ("refund_policy.md", "return_policy.md")
    assert any(c.document == "refund_policy.md" for c in r.chunks)
    r = retrieve("what is the return window for gold members")
    assert r.chunks[0].document == "return_policy.md"


def test_context_builder_numbers_citations():
    ctx = build_context(retrieve("express shipping cost").chunks)
    assert ctx.startswith("[1]")


def test_retrieval_failure_degrades_gracefully(monkeypatch):
    import app.rag.retriever as R
    monkeypatch.setattr(R, "_vector_search", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = R.retrieve("refund")
    assert r.chunks == [] and "boom" in r.error
