import json
from app.evaluation import dataset
from app.evaluation.run import run_evaluation


def test_dataset_size_and_coverage():
    assert len(dataset.CASES) >= 100
    cats = {c["category"] for c in dataset.CASES}
    assert {"prompt_injection", "pii_request", "unauthorized", "high_risk", "escalation", "general_faq", "false_premise", "ambiguous"} <= cats


def test_eval_computes_metrics_from_runs():
    out = run_evaluation(limit=30, write=False)
    assert out["cases"] == 30 and out["metrics"]["intent_accuracy"]["n"] > 0
    assert 0 <= out["metrics"]["intent_accuracy"]["value_pct"] <= 100
