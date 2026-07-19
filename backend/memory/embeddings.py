from __future__ import annotations

import hashlib
import math
from typing import Callable, Optional


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def deterministic_fake_embedding(text: str, dim: int = 32) -> list[float]:
    """Cheap, deterministic, hash-based embedding — no network call.

    Used as the default in tests/offline mode so unit tests never touch
    DashScope. Similar strings hash to similar-ish vectors often enough for
    ranking tests; retrieval-quality tests use hand-crafted relevance scores
    instead of relying on this being a real embedding model.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    return [(h[i % len(h)] / 255.0) * 2 - 1 for i in range(dim)]


class EmbeddingFn:
    """Wraps DashScope text-embedding-v3. Injectable so callers (tests, the
    benchmark harness) can swap in `deterministic_fake_embedding` and never
    hit the network or incur cost."""

    def __init__(self, fn: Optional[Callable[[str], list[float]]] = None, model: str = "text-embedding-v3"):
        self.fn = fn or self._call_dashscope
        self.model = model

    def __call__(self, text: str) -> list[float]:
        return self.fn(text)

    def _call_dashscope(self, text: str) -> list[float]:
        from ..dashscope_config import configure_dashscope

        dashscope = configure_dashscope()
        resp = dashscope.TextEmbedding.call(model=self.model, input=text)
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope embedding call failed: {resp.code} {resp.message}")
        return resp.output["embeddings"][0]["embedding"]
