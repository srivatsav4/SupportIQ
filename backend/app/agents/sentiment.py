"""Lexicon-based sentiment + urgency analysis with a human-readable reason."""
import re

NEG = ["angry", "furious", "terrible", "worst", "horrible", "awful", "unacceptable", "ridiculous", "disgusted", "useless", "fed up",
       "frustrated", "annoyed", "disappointed", "scam", "fraud", "cheated", "never again", "waste", "still waiting", "no response", "again and again", "pathetic", "rude"]
POS = ["thanks", "thank you", "great", "awesome", "love", "perfect", "happy", "appreciate", "excellent", "helpful"]
URG = ["urgent", "asap", "immediately", "right now", "emergency", "today", "charged twice", "double charged", "fraud", "stolen", "unauthorized", "legal", "lawyer"]
REPEAT = re.compile(r"(again|third time|second time|repeated(ly)?|multiple times|several times|keep (getting|failing)|still (not|no))", re.I)
FAILED = re.compile(r"(refund|payment|transaction).{0,25}(fail|declin|reject)", re.I)


def analyze(text: str, intent: str = "") -> dict:
    t = text.lower()
    neg = sum(1 for w in NEG if w in t)
    pos = sum(1 for w in POS if w in t)
    urg = sum(1 for w in URG if w in t)
    rep = bool(REPEAT.search(text))
    sentiment = "negative" if neg >= 1 or (rep and neg) else ("positive" if pos > neg else "neutral")
    if "!!" in text or (text.isupper() and len(text) > 12):
        neg += 1
        sentiment = "negative"
    score = urg * 2 + neg + (2 if rep else 0) + (2 if FAILED.search(text) else 0) + (2 if intent in ("DUPLICATE_PAYMENT", "PAYMENT_FAILURE") else 0)
    urgency = "high" if score >= 3 else ("medium" if score >= 1 or sentiment == "negative" else "low")
    reasons = []
    if FAILED.search(text) and rep:
        reasons.append("Customer reports repeated failed refund/payment attempts")
    elif FAILED.search(text):
        reasons.append("Customer reports a failed refund/payment")
    if intent in ("DUPLICATE_PAYMENT",):
        reasons.append("Possible duplicate charge")
    if neg:
        reasons.append("Customer expresses dissatisfaction")
    if urg:
        reasons.append("Urgent wording used")
    if rep and not reasons:
        reasons.append("Customer indicates the issue is recurring")
    return {"sentiment": sentiment, "urgency": urgency, "reason": "; ".join(reasons) or "No distress signals detected",
            "severe": neg >= 2 or (neg >= 1 and urg >= 1)}
