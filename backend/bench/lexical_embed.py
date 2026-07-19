from __future__ import annotations

import hashlib
import math
import re

_WORD_RE = re.compile(r"[a-z0-9]+")

# Common function words carry ~no topical signal and, left in, dilute the
# distinctiveness of the words that actually distinguish one fact from
# another (paper titles, metric names, preference values). A real embedding
# model learns this weighting implicitly; a hashed bag-of-words needs it
# spelled out.
_STOPWORDS = {
    "the", "a", "an", "is", "in", "of", "to", "on", "for", "and", "that",
    "this", "was", "were", "its", "not", "but", "now", "at", "by", "from",
    "with", "as", "be", "are", "user", "s", "actually", "does", "what",
}


def hashing_bow_embedding(text: str, dim: int = 256) -> list[float]:
    """Feature-hashed bag-of-words embedding: a real (if simple), offline,
    zero-cost text similarity signal. Unlike the SHA256-digest fake used in
    unit tests (which is intentionally semantically meaningless — fine for
    testing algorithm plumbing), this one gives sentences that share words a
    genuinely higher cosine similarity, which MemoryBench needs to model
    realistic retrieval-relevance ambiguity between a fact and its
    correction (they share almost every word)."""
    vec = [0.0] * dim
    for word in _WORD_RE.findall(text.lower()):
        if word in _STOPWORDS:
            continue
        h = hashlib.md5(word.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % dim
        sign = 1.0 if int(h[8:9], 16) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec
