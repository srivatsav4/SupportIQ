from app.agents.verifier import verify
from app.rag.retriever import Retrieved

CH = [Retrieved("x_1", "refund_policy.md", "Processing", "NovaCart Refund Policy", "Approved refunds are issued within 5 to 7 business days.", 1.0)]


def test_grounded_passes():
    v = verify("Your refund R5 for $20.00 is Approved. Approved refunds are issued within 5 to 7 business days [1].", {"refund_id": "R5", "amount": 20.0, "status": "Approved"}, CH, "refund R5")
    assert v["passed"], v["issues"]


def test_unsupported_number_fails():
    assert not verify("Refunds take 3 days.", {}, CH, "refund")["passed"]


def test_invalid_citation_fails():
    assert not verify("Approved refunds are issued within 5 to 7 business days [4].", {}, CH, "refund")["passed"]


def test_citation_must_support_sentence():
    assert not verify("Gold members get free parking at every store [1].", {}, CH, "x")["passed"]


def test_forbidden_promise_fails():
    assert not verify("I guarantee your refund will be approved.", {}, CH, "x")["passed"]


def test_sensitive_info_fails():
    assert not verify("Your card 4111 1111 1111 1111 was charged.", {}, CH, "x", trusted=True)["passed"]
    assert not verify("Contact priya@example.com", {}, CH, "x", trusted=True)["passed"]


def test_unsupported_policy_claim_without_citation_fails():
    assert not verify("According to our policy you can return anything.", {}, CH, "x")["passed"]
