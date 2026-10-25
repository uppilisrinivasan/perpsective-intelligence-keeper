"""Local TF-IDF helpers (no embedding model needed; methodology 04 §5)."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for t in _TOKEN.findall(text or ""):
        parts = [p for p in re.split(r"_+", _CAMEL.sub("_", t)) if p]
        out.append(t.lower())
        if len(parts) > 1:
            out.extend(p.lower() for p in parts)
    return out


def identifiers(code: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", code or "")]


def _vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(tokenizer=tokens, lowercase=False, token_pattern=None, sublinear_tf=True,
                           stop_words=list(STOP), min_df=1)


def tfidf_matrix(texts: Sequence[str]):
    texts = [t if t and t.strip() else "_empty_" for t in texts]
    v = _vectorizer()
    try:
        return v.fit_transform(texts), v
    except ValueError:  # all stop words
        v = TfidfVectorizer(tokenizer=tokens, lowercase=False, token_pattern=None)
        return v.fit_transform([t + " _x_" for t in texts]), v


def cosine_matrix(a: Sequence[str], b: Sequence[str]) -> np.ndarray:
    """Cosine similarity of every text in a against every text in b, in one shared vocabulary."""
    if not a or not b:
        return np.zeros((len(a), len(b)))
    m, _ = tfidf_matrix(list(a) + list(b))
    ma, mb = m[: len(a)], m[len(a):]
    return (ma @ mb.T).toarray()


def similarity(x: str, y: str) -> float:
    return float(cosine_matrix([x], [y])[0, 0])


STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be", "this", "that", "it", "with",
    "as", "at", "by", "we", "you", "i", "not", "can", "should", "would", "could", "here", "there", "please", "if",
    "do", "does", "so", "but", "from", "was", "has", "have", "will", "just", "also", "any", "all", "one", "its",
    "our", "your", "than", "then", "into", "when", "what", "which", "how", "why", "they", "them", "me", "my",
}
