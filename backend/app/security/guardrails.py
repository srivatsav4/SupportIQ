"""Guardrails: prompt-injection detection, PII masking, sensitive-data detection."""
import re
from dataclasses import dataclass

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|your) (instructions|rules|guidelines)",
    r"(reveal|show|print|display|tell me|repeat|leak).{0,30}(system prompt|hidden prompt|your instructions|internal instructions|initial prompt)",
    r"you are now (?!a customer)",
    r"\bact as (an? )?(admin|administrator|developer|root|dan)\b",
    r"\bjailbreak\b|\bdeveloper mode\b|\bdo anything now\b",
    r"(show|dump|list|give|export).{0,25}(the )?(entire |whole |full )?(database|db|all customers?|customer list|all orders|every customer|all users)",
    r"(give|show|list|send).{0,20}(all|every).{0,15}(customer|user).{0,15}(information|data|emails?|records|details)",
    r"\bselect\b.{0,40}\bfrom\b.{0,40}(customers|orders|users)|\bdrop table\b|\bunion select\b",
    r"override (your )?(safety|guardrails|policy|policies|restrictions)",
    r"(bypass|disable|turn off).{0,20}(safety|guardrails|verification|approval|filters?)",
    r"pretend (that )?(you have|there is) no (rules|restrictions|policy)",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]

PII_REQUEST_PATTERNS = [
    r"(full|complete|entire)\s+(credit |debit )?card (number|details)",
    r"\b(cvv|cvc|otp|password|pin)\b.{0,20}(of|for|from|show|tell|what)",
    r"(show|tell|give|reveal|what).{0,30}(another|other|someone else'?s?|his|her|their) (customer'?s? )?(address|phone|email|order|details|payment|card)",
    r"(address|phone number|email)( address)? of (customer|user|c\d{4})",
    r"(customer|user)\s+c\d{4}",
]
_PII_REQ = [re.compile(p, re.I) for p in PII_REQUEST_PATTERNS]

CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CVV_RE = re.compile(r"\b(cvv|cvc)\D{0,5}\d{3,4}\b", re.I)
OTP_RE = re.compile(r"\botp\D{0,5}\d{4,8}\b", re.I)
PASSWORD_RE = re.compile(r"\bpassword\s*(is|:|=)\s*\S+", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\+?\d[\d\- ]{8,14}\d")
SECRET_LEAK_RE = re.compile(r"(system prompt|you are novasupport|internal instructions)", re.I)


@dataclass
class GuardResult:
    blocked: bool
    category: str = ""
    reason: str = ""


def detect_prompt_injection(text: str) -> GuardResult:
    for rx in _INJ:
        if rx.search(text):
            return GuardResult(True, "prompt_injection", "Message attempts to override instructions or extract internal/system data.")
    return GuardResult(False)


def detect_pii_request(text: str) -> GuardResult:
    for rx in _PII_REQ:
        if rx.search(text):
            return GuardResult(True, "pii_request", "Message requests sensitive or third-party personal data.")
    return GuardResult(False)


def contains_secret_credentials(text: str) -> bool:
    return bool(CARD_RE.search(text) or CVV_RE.search(text) or OTP_RE.search(text) or PASSWORD_RE.search(text))


def mask_card(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    return "**** **** **** " + digits[-4:] if len(digits) >= 4 else "****"


def mask_email(e: str) -> str:
    if "@" not in e:
        return "***"
    u, d = e.split("@", 1)
    return (u[:1] + "***") + "@" + d


def mask_phone(p: str) -> str:
    d = re.sub(r"\D", "", p)
    return "*" * max(len(d) - 4, 0) + d[-4:]


def redact_sensitive(text: str) -> str:
    """Redact credentials / card numbers before storage or logging."""
    text = CVV_RE.sub("[REDACTED-CVV]", text)
    text = OTP_RE.sub("[REDACTED-OTP]", text)
    text = PASSWORD_RE.sub("[REDACTED-PASSWORD]", text)
    text = CARD_RE.sub(lambda m: mask_card(m.group(0)) if len(re.sub(r"\D", "", m.group(0))) >= 13 else m.group(0), text)
    return text


def redact_output(text: str) -> str:
    """Last line of defense on model output: mask emails/phones/cards that slipped through."""
    text = redact_sensitive(text)
    text = EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    return text
