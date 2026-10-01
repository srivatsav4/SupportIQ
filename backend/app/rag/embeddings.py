"""Embedding backends. Default 'hash' needs no download (signed feature hashing over word uni/bi-grams,
with light stemming and stop-word removal). Optionally uses sentence-transformers."""
import hashlib, math, re
import numpy as np
from app.config import get_settings

STOP = set("policy policies novacart what whats tell about a an the is are was were be to of in on for and or my me i it its this that with at by from as do does did can could would should will have has had your you we our us if so not no please hi hello hey".split())
TOKEN = re.compile(r"[a-z0-9]+")


def stem(w: str) -> str:
    for suf in ("able", "ing", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            base = w[: -len(suf)]
            if suf in ("ing", "ed") and len(base) > 3 and base[-1] == base[-2] and base[-1] not in "lsz":
                base = base[:-1]          # shipped -> ship
            elif suf in ("ing", "ed") and base.endswith("ll") and len(base) > 5:
                base = base[:-1]          # cancelled -> cancel
            return base
    return w


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in TOKEN.findall(text.lower()) if t not in STOP]


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim

    def _h(self, tok: str) -> tuple[int, float]:
        d = hashlib.md5(tok.encode()).digest()
        return int.from_bytes(d[:4], "little") % self.dim, 1.0 if d[4] & 1 else -1.0

    def embed(self, text: str) -> np.ndarray:
        toks = tokenize(text)
        v = np.zeros(self.dim, dtype=np.float32)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for f in feats:
            i, sgn = self._h(f)
            v[i] += sgn * (1.0 if "_" not in f else 0.7)
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_many(self, texts):
        return np.vstack([self.embed(t) for t in texts]) if texts else np.zeros((0, self.dim), dtype=np.float32)


class STEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, text):
        return self.model.encode(text, normalize_embeddings=True)

    def embed_many(self, texts):
        return self.model.encode(texts, normalize_embeddings=True)


_emb = None


def get_embedder():
    global _emb
    if _emb is None:
        s = get_settings()
        if s.embedding_backend == "sentence-transformers":
            try:
                _emb = STEmbedder(s.embedding_model)
            except Exception:  # missing dependency / no network -> degrade gracefully
                _emb = HashEmbedder(s.embedding_dim)
        else:
            _emb = HashEmbedder(s.embedding_dim)
    return _emb


SYNONYMS = [
    (r"how long|how many days|timeline|time ?frame|duration|\btake\b|taking|\bwhen\b", "time days timeline"),
    (r"money back|reimburse", "refund"),
    (r"\bfees?\b|\bcosts?\b|charges?\b|how much", "fee cost price"),
    (r"free (shipping|delivery)", "shipping fees free orders"),
    (r"pay(ing)?\b|payment method|accepted|credit|debit|upi|wallet|cod|cash on delivery", "payment methods accepted"),
    (r"guarantee", "warranty"),
    (r"send (it )?back|return window|days to return", "return window days"),
    (r"arrive|deliver|reach", "delivery"),
    (r"charged twice|double charge|paid twice", "duplicate payment charged twice"),
    (r"safe|secure|data|personal information", "privacy security data"),
    (r"upgrade|spend|level|status tier", "membership tiers spending threshold"),
    (r"broken|cracked|defect", "damaged defective"),
    (r"become|reach|earn|qualify|get (gold|platinum)", "earning tiers spending"),
    (r"isn.?t covered|not covered|exclu|doesn.?t cover|what.?s not", "not covered physical damage liquid damage unauthorized repairs"),
    (r"escalat", "escalation threshold days past expected delivery"),
    (r"\\b(keep|retain|retention)\\b|how long.*(data|conversation|record)", "retention retained data months"),
    (r"hello|hi there", ""),
]
import re as _re


def expand_query(text: str) -> str:
    extra = [add for pat, add in SYNONYMS if add and _re.search(pat, text, _re.I)]
    return text + " " + " ".join(extra) if extra else text
