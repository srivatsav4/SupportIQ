"""Response verification service. Checks groundedness, citation validity, policy compliance, unsupported
claims and sensitive information BEFORE any answer reaches the customer."""
import re
from app.rag.embeddings import tokenize
from app.security.guardrails import CARD_RE, EMAIL_RE, PHONE_RE, SECRET_LEAK_RE
from app.observability.metrics import VERIFIER

ID_RE = re.compile(r"\b(?:A\d{5}|TK\d{5}|AP[0-9A-F]{8}|R\d+|PAY\d+|(?:SS|BL|RP)\d{8,12}|C\d{4}|P\d{4})\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")
CITE_RE = re.compile(r"\[(\d+)\]")
# words that legitimately appear in conversational glue / safe boilerplate
BOILER = set(tokenize(
    "your you order orders currently latest status according policy please help ticket escalated team within hours hour support agent review confirm "
    "reply yes no cancel sorry apologize understand frustrating thank thanks glad happy assist information available details verified based record "
    "records show shows shown found find would like proceed next step steps option options contact contacted reach shortly soon response expected "
    "customer account request requested created submitted pending approval approved human specialist look looking checked check checking result results "
    "unfortunately however also still already currently now today days day business item items product products refund refunds return returns "
    "delivery shipment shipping package carrier tracking paid payment payments charge charged amount total method card ending note noted "
    "eligible eligibility qualify qualifies window left remaining past expected date delivered delayed delay late normal variation "
    "possible anything else need let know provide share id number looks sure make cannot can't unable accurately accurate "
    "ask want wish choose either both need needs required require requires within may might will once after before when while "
    "covered coverage warranty months month elapsed started starts start begin tier membership benefits benefit "
    "sorry about this issue problem experience experienced inconvenience caused cause apologies appreciate patience "
    "novacart novasupport again few length usually otherwise isn aren wasn didn don doesn won ll ve re let there here their they them been being were "
    "was had has more most some any all one two other another such same different next soon last first second long short big small good great well "
    "reference outcome until course connect connecting create created creating just ago make made making get got getting give gave given send sent "
    "stay keep kept try tried trying going go went come came take took taken put set see saw seen say said tell told ask asked use used using "
    "arrange arranged arrives arrive arrived arriving escalate escalating escalation threshold normal carrier variation reply replies message messages "
    "chat conversation morning afternoon evening time times timely quickly quick fast prompt promptly detail further additional extra "
    "really very quite fully fully safe security secure safely personal own owner owners verify verifying verification "
    "person people someone anyone everyone everything anything something nothing whether which what who whom whose how why where "
    "happen happened happens happening good bad better best worse worst right wrong correct incorrect true false "
    "submit submitting cancell cancelled instead stop yet stopped yet new full need needed "))
BOILER |= {"t", "s", "d", "m"}

FORBIDDEN = [
    (r"\b(i|we)('ve| have)?\s+(approved|guarantee[d]?)\b", "makes an approval/guarantee the AI cannot give"),
    (r"\bwill (definitely|certainly) be (approved|refunded)\b", "promises an outcome requiring review"),
    (r"\bguarantee(d)?\b", "uses the word guarantee"),
    (r"\bi promise\b", "makes a promise"),
    (r"\b(system prompt|my instructions|internal prompt)\b", "refers to internal instructions"),
    (r"\bas an ai language model\b", "generic filler"),
]


def _canon(n: str) -> str:
    """Canonical numeric form so '$20.00', '20.0' and '20' are the same number."""
    n = n.replace("$", "").replace(",", "").rstrip(".")
    try:
        return f"{float(n):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return n


def _numbers(text: str) -> set[str]:
    t = ID_RE.sub(" ", DATE_RE.sub(" ", CITE_RE.sub(" ", text)))
    return {_canon(n) for n in NUM_RE.findall(t)}


def _ids(text: str) -> set[str]:
    return set(ID_RE.findall(text)) | set(DATE_RE.findall(text))


def build_evidence(facts: dict, chunks: list, user_text: str) -> str:
    parts = [user_text]

    def walk(k, v):
        if isinstance(v, dict):
            for kk, vv in v.items():
                walk(kk, vv)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(k, x)
        else:
            parts.append(f"{str(k).replace('_', ' ')} {v}")
    walk("facts", facts)
    parts += [c.content + " " + c.section for c in chunks]
    return "\n".join(parts)


def verify(answer: str, facts: dict, chunks: list, user_text: str, action_executed: bool = False, trusted: bool = False,
           unsafe_claim_allowed: bool = False) -> dict:
    issues, checks = [], {}
    evidence = build_evidence(facts, chunks, user_text)
    body = answer.split("\n\nSources:")[0]

    # --- sensitive information
    sens = []
    if CARD_RE.search(body) and not re.search(r"\*{2,}", body):
        sens.append("possible card number")
    if EMAIL_RE.search(body) and "***" not in EMAIL_RE.search(body).group(0):
        sens.append("unmasked email")
    if PHONE_RE.search(ID_RE.sub("", DATE_RE.sub("", body))) and not re.search(r"\*", body):
        sens.append("phone number")
    if SECRET_LEAK_RE.search(body):
        sens.append("internal instructions reference")
    checks["sensitive_information"] = not sens
    issues += [f"sensitive: {s}" for s in sens]

    # --- policy compliance
    viol = [why for rx, why in FORBIDDEN if re.search(rx, body, re.I)]
    if not action_executed and re.search(r"refund (has been|was|is now) (issued|processed|completed|sent)", body, re.I):
        viol.append("claims a refund was completed without evidence")
    checks["policy_compliance"] = not viol
    issues += [f"policy: {v}" for v in viol]

    if trusted:
        checks.update(groundedness=True, citation_validity=True, unsupported_claims=True)
        passed = checks["sensitive_information"] and checks["policy_compliance"]
        VERIFIER.labels("pass" if passed else "fail").inc()
        return {"passed": passed, "groundedness": 1.0, "citation_accuracy": 1.0, "checks": checks, "issues": issues, "trusted_template": True}

    # --- unsupported claims: numbers / ids / dates must exist in the evidence
    ev_nums, ev_ids = _numbers(evidence), _ids(evidence)
    bad_nums = [n for n in _numbers(body) if n not in ev_nums]
    bad_ids = [i for i in _ids(body) if i not in ev_ids]
    checks["unsupported_claims"] = not (bad_nums or bad_ids)
    issues += [f"unsupported number: {n}" for n in bad_nums] + [f"unsupported identifier: {i}" for i in bad_ids]

    # --- groundedness: share of content tokens supported by evidence (or safe conversational glue)
    ev_tok = set(tokenize(evidence)) | BOILER
    body_tokens = [t for t in tokenize(CITE_RE.sub(" ", ID_RE.sub(" ", DATE_RE.sub(" ", body)))) if not t.isdigit()]
    unsupported = [t for t in body_tokens if t not in ev_tok]
    groundedness = 1.0 if not body_tokens else round(1 - len(unsupported) / len(body_tokens), 3)
    checks["groundedness"] = groundedness >= 0.8 and not (bad_nums or bad_ids)
    if groundedness < 0.8:
        issues.append(f"low groundedness {groundedness}: e.g. {sorted(set(unsupported))[:6]}")

    # --- citation validity
    body_c = re.sub(r"([.!?])\s*(\[\d+\])", lambda mo: f" {mo.group(2)}{mo.group(1)}", body)
    cites = [int(x) for x in CITE_RE.findall(body)]
    valid = 0
    for sent in re.split(r"(?<=[.!?])\s+", body_c):
        for ci in [int(x) for x in CITE_RE.findall(sent)]:
            if 1 <= ci <= len(chunks):
                st = {x for x in tokenize(CITE_RE.sub(" ", ID_RE.sub(" ", sent))) if x not in BOILER and not x.isdigit()}
                ct = set(tokenize(chunks[ci - 1].content))
                if not st or len(st & ct) / len(st) >= 0.35:
                    valid += 1
                else:
                    issues.append(f"citation [{ci}] not supported by cited chunk")
            else:
                issues.append(f"citation [{ci}] does not exist")
    cite_acc = 1.0 if not cites else round(valid / len(cites), 3)
    claims_policy = bool(re.search(r"\bpolic(y|ies)\b", body, re.I)) and not re.search(r"(don't|do not) have", body, re.I)
    if claims_policy and not cites:
        issues.append("policy claim without citation")
        cite_acc = 0.0
    checks["citation_validity"] = cite_acc >= 1.0
    passed = all(checks.values())
    VERIFIER.labels("pass" if passed else "fail").inc()
    return {"passed": passed, "groundedness": groundedness, "citation_accuracy": cite_acc, "checks": checks, "issues": issues, "trusted_template": False}
