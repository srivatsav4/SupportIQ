"""Intent classification (weighted rules; optionally LLM-assisted with strict JSON validation)."""
import json, re
from app.agents import llm

INTENTS = ["ORDER_TRACKING", "ORDER_DELAY", "ORDER_CANCELLATION", "REFUND_REQUEST", "REFUND_STATUS", "RETURN_REQUEST",
           "EXCHANGE_REQUEST", "DAMAGED_PRODUCT", "WRONG_PRODUCT", "PAYMENT_FAILURE", "DUPLICATE_PAYMENT",
           "ADDRESS_CHANGE", "PRODUCT_INFORMATION", "WARRANTY", "MEMBERSHIP", "ACCOUNT_HELP", "GENERAL_FAQ",
           "COMPLAINT", "HUMAN_ESCALATION"]

ORDER_RE = re.compile(r"\b(A\d{5})\b", re.I)
TICKET_RE = re.compile(r"\b(TK\d{5})\b", re.I)

# (regex, weight)
RULES: dict[str, list[tuple[str, float]]] = {
    "HUMAN_ESCALATION": [(r"\b(human|real person|live agent|support agent|representative|manager|supervisor)\b", 2.0),
                         (r"(talk|speak|connect|transfer).{0,20}(to|with).{0,15}(someone|agent|person|human)", 2.5)],
    "DUPLICATE_PAYMENT": [(r"(charged|billed|paid|debited|deducted).{0,15}(twice|two times|2 times|double)", 4),
                          (r"duplicate (payment|charge)|double (charge|payment)|paid twice", 4)],
    "PAYMENT_FAILURE": [(r"payment.{0,15}(fail|declin|stuck|pending|not go|didn.?t go)", 3.5),
                        (r"(money|amount).{0,25}(deducted|debited|cut).{0,40}(order|not|fail)", 3.5), (r"transaction (fail|declin)", 3.5)],
    "REFUND_STATUS": [(r"status (of|for|on) (my |the )?refund", 4), (r"refund.{0,30}(status|yet|received|when|where|how long|take|taking|track)", 3.5),
                      (r"(where|when).{0,15}(is|will).{0,10}my refund", 4), (r"(haven.?t|have not|not) (got|received).{0,15}refund", 4),
                      (r"how long.{0,25}refund", 3.5), (r"refund.{0,10}(processing )?time", 3)],
    "REFUND_REQUEST": [(r"(i )?(want|need|would like|request|like).{0,20}(a )?refund", 3.5), (r"refund (my|the|this|for)", 2.5),
                       (r"(money back|get a refund|give me a refund|issue a refund)", 3.5), (r"\brefund\b", 1.0)],
    "RETURN_REQUEST": [(r"\breturn(s|ed|ing)?\b", 2.5), (r"send\b.{0,25}\bback\b", 3), (r"eligible.{0,10}return|return.{0,15}eligib", 3)],
    "EXCHANGE_REQUEST": [(r"\bexchange\b|\bswap\b|\breplace(ment)? (size|color|variant)\b", 3.5), (r"different (size|colou?r)", 3)],
    "DAMAGED_PRODUCT": [(r"\b(damaged|broken|cracked|shattered|defective|dented|torn|not working|stopped working|faulty)\b", 3.5), (r"arrived (broken|damaged)", 4)],
    "WRONG_PRODUCT": [(r"wrong (item|product|size|colou?r)|different (item|product) (than|from)|not what i ordered|received (the )?wrong|incorrect (item|product)", 4.5)],
    "ORDER_CANCELLATION": [(r"\bcancel(l?ed|l?ing|lation)?\b", 3.5)],
    "ORDER_DELAY": [(r"\b(delay(ed)?|late|overdue|taking (so |too |very |this )?long|still (not|hasn.?t)|not (arrived|here|delivered)|hasn.?t (arrived|come|been delivered))\b", 3.0),
                    (r"where is my (order|package|parcel)", 2.0), (r"hasn.?t arrived", 3.5), (r"(never|didn.?t) (arrive|received)", 3)],
    "ORDER_TRACKING": [(r"\b(show|view|see|check|find|get|details? (of|for|about)|info(rmation)? (on|about)).{0,25}\border\b", 2.5), (r"\btrack(ing)?\b", 3.0), (r"where.{0,12}(my )?(order|package|parcel|shipment)", 3.0), (r"(order|shipment|delivery) status", 3.5),
                       (r"status (of|for) (my )?(order|shipment)", 3.5), (r"when will.{0,25}(arrive|deliver|reach)", 3)],
    "ADDRESS_CHANGE": [(r"(change|update|edit|modify|correct).{0,20}(shipping |delivery )?address", 4.5), (r"wrong address", 3.5)],
    "WARRANTY": [(r"\bwarrant(y|ies)\b|\bguarantee\b", 4.0)],
    "MEMBERSHIP": [(r"\b(membership|tier|tiers|member benefits?|loyalty)\b", 3.0), (r"\b(gold|platinum|silver)\b", 1.5)],
    "ACCOUNT_HELP": [(r"\b(my account|password|log ?in|sign ?in|delete (my )?account|update (my )?(email|phone)|profile)\b", 3.0)],
    "PRODUCT_INFORMATION": [(r"(in stock|availab|specs?|features?|does (it|this|the).{0,20}(have|support|come)|compatible|price of|how much (is|does))", 2.5),
                            (r"tell me about (the |this )?(product|item)", 3), (r"tell me about (the |a |an )?[a-z0-9 -]{3,40}\??$", 2.5)],
    "COMPLAINT": [(r"\b(complain|complaint|unacceptable|terrible|worst|disgusting|furious|fed up|ridiculous|scam|fraud(ulent)?|lawyer|legal action|consumer court)\b", 3.0)],
    "GENERAL_FAQ": [(r"(what is|what are|what's|how (do|does|long)|do you|can i|is there|policy|policies|do i)\b", 1.0),
                    (r"\b(shipping|delivery) (fee|cost|charges?|methods?|time)|payment methods?|accepted payment|cash on delivery|\bcod\b|price match|gift card|bulk order", 2.5)],
}
_COMPILED = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in RULES.items()}
URGENT_INTENTS = {"DUPLICATE_PAYMENT", "PAYMENT_FAILURE", "COMPLAINT", "HUMAN_ESCALATION"}
CUSTOMER_DATA_INTENTS = {"ORDER_TRACKING", "ORDER_DELAY", "ORDER_CANCELLATION", "REFUND_REQUEST", "REFUND_STATUS", "RETURN_REQUEST",
                         "EXCHANGE_REQUEST", "DAMAGED_PRODUCT", "WRONG_PRODUCT", "PAYMENT_FAILURE", "DUPLICATE_PAYMENT",
                         "ADDRESS_CHANGE", "ACCOUNT_HELP"}


def extract_order_id(text: str) -> str | None:
    m = ORDER_RE.search(text)
    return m.group(1).upper() if m else None


def classify_rules(text: str, has_order_context: bool = False) -> dict:
    scores = {}
    for intent, rules in _COMPILED.items():
        s = sum(w for rx, w in rules if rx.search(text))
        if s:
            scores[intent] = s
    has_order = bool(ORDER_RE.search(text))
    own = re.search(r"\b(my|mine|this order|that order|this item|i (want|need|would|'d|have|had|was|got|received|am|'m|'ve|think|ordered))\b|\bi'(m|d|ve)\b", text, re.I)
    policy_word = re.search(r"\bpolic(y|ies)\b", text, re.I)
    starter = re.search(r"^\s*(how long|how many days|what (is|are|'s)|do you|does novacart|is there|can i (use|pay|get|buy|return|exchange|cancel|replace|change)|which)\b", text, re.I)
    shipping_fee_q = re.search(r"how much.{0,30}(shipping|delivery|express|fees?|charges?|cost)", text, re.I)
    product_q = scores.get("PRODUCT_INFORMATION", 0) >= 2.5 and not shipping_fee_q and not policy_word
    if not has_order and not product_q and not (has_order_context and not policy_word) and (policy_word or shipping_fee_q or re.search(r"\bwhat (is|are) (the|your|a)\b", text, re.I) or (starter and not own) or (text.strip().endswith("?") and not own and not has_order_context)):
        scores["GENERAL_FAQ"] = scores.get("GENERAL_FAQ", 0) + 6
        for k in ("REFUND_STATUS", "REFUND_REQUEST", "RETURN_REQUEST", "WARRANTY", "MEMBERSHIP", "ORDER_TRACKING", "ORDER_DELAY", "EXCHANGE_REQUEST", "ORDER_CANCELLATION", "PAYMENT_FAILURE", "ADDRESS_CHANGE", "DAMAGED_PRODUCT"):
            if k in scores and not (own and not policy_word):
                scores[k] *= 0.4
    if not scores:
        return {"intent": "ORDER_TRACKING" if has_order else "GENERAL_FAQ", "confidence": 0.5 if has_order else 0.3, "scores": {}}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top, ts = ranked[0]
    # disambiguation: strong refund-status wording beats generic return/refund; damaged beats refund
    second = ranked[1][1] if len(ranked) > 1 else 0
    margin = (ts - second) / ts if ts else 0
    conf = min(0.97, 0.55 + 0.08 * ts + 0.25 * margin)
    if ts < 2:
        conf = min(conf, 0.5)
    return {"intent": top, "confidence": round(conf, 2), "scores": scores}


def classify(text: str, has_order_context: bool = False) -> dict:
    base = classify_rules(text, has_order_context)
    result = {"intent": base["intent"], "confidence": base["confidence"], "source": "rules"}
    if llm.llm_enabled() and base["confidence"] < 0.8:
        try:
            out, _ = llm.generate("You classify customer support messages. Reply ONLY with JSON: "
                                  '{"intent": <one of %s>, "confidence": <0-1>}' % INTENTS, text, json_mode=True)
            d = json.loads(out)
            if d.get("intent") in INTENTS and 0 <= float(d.get("confidence", 0)) <= 1:
                result = {"intent": d["intent"], "confidence": round(float(d["confidence"]), 2), "source": "llm"}
        except Exception:
            pass  # malformed / unavailable -> keep rule result
    it = result["intent"]
    result["urgency"] = "high" if it in URGENT_INTENTS else ("medium" if it in {"REFUND_STATUS", "REFUND_REQUEST", "ORDER_DELAY", "DAMAGED_PRODUCT", "WRONG_PRODUCT", "ORDER_CANCELLATION"} else "low")
    result["requires_customer_data"] = it in CUSTOMER_DATA_INTENTS
    result["requires_human"] = it in {"HUMAN_ESCALATION"}
    return result
