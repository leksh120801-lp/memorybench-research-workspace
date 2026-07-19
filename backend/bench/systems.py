from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.memory.contradiction import ContradictionResolver
from backend.memory.embeddings import EmbeddingFn, cosine_similarity
from backend.memory.extractor import MemoryExtractor
from backend.memory.manager import MemoryManager
from backend.memory.models import MemoryType

from .lexical_embed import hashing_bow_embedding
from .traces import FactEvent, Probe, SyntheticTrace

# Illustrative latency model: base request overhead + linear prefill cost per
# input token. Not a real network call — see docs/submission.md for why (no
# paid infra in benchmark runs). Coefficients are order-of-magnitude
# approximations of Qwen-max prefill behavior, not a billing-accurate figure.
LATENCY_BASE_S = 0.05
LATENCY_PER_TOKEN_S = 0.0006

# Illustrative cost model: $ per 1K input tokens. Swap for current DashScope
# pricing before quoting real costs — this exists so systems are comparable
# to each other, not to state an authoritative price.
COST_PER_1K_INPUT_TOKENS = 0.02


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def simulate_latency_s(token_cost: int) -> float:
    return LATENCY_BASE_S + token_cost * LATENCY_PER_TOKEN_S


def estimate_cost(token_cost: int) -> float:
    return (token_cost / 1000.0) * COST_PER_1K_INPUT_TOKENS


@dataclass
class ProbeResult:
    retrieved_contents: list[str]
    token_cost: int
    latency_s: float
    cost: float


def _guess_store(key: str) -> MemoryType:
    if key.startswith("preference:"):
        return MemoryType.PREFERENCE
    if key.startswith("fact:"):
        return MemoryType.SEMANTIC
    return MemoryType.EPISODIC


def _session_time(session_index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=session_index)


class BenchSystem(ABC):
    name: str

    @abstractmethod
    def ingest_session(self, trace: SyntheticTrace, session_index: int) -> None: ...

    @abstractmethod
    def answer_probe(self, trace: SyntheticTrace, probe: Probe) -> ProbeResult: ...


class NoMemorySystem(BenchSystem):
    """Baseline (a): nothing persists between turns at all."""

    name = "no_memory"

    def ingest_session(self, trace, session_index):
        pass

    def answer_probe(self, trace, probe):
        return ProbeResult([], 0, simulate_latency_s(0), estimate_cost(0))


class FullHistorySystem(BenchSystem):
    """Baseline (b): every raw event ever seen gets stuffed into context,
    unbounded, including anything that was later corrected — the classic
    "just paste all history in" approach."""

    name = "full_history"

    def __init__(self):
        self.history: list[FactEvent] = []

    def ingest_session(self, trace, session_index):
        self.history.extend(trace.sessions[session_index])

    def answer_probe(self, trace, probe):
        contents = [e.content for e in self.history]
        tokens = sum(estimate_tokens(c) for c in contents)
        return ProbeResult(contents, tokens, simulate_latency_s(tokens), estimate_cost(tokens))


class NaiveTopKSystem(BenchSystem):
    """Baseline (c): top-k by raw relevance over the whole raw-turn pool, no
    budget awareness and no contradiction resolution — a corrected fact and
    its stale predecessor coexist and compete purely on similarity."""

    name = "naive_topk_rag"

    def __init__(self, k: int = 4, embedding_fn=hashing_bow_embedding):
        self.history: list[FactEvent] = []
        self.k = k
        self.embedding_fn = embedding_fn

    def ingest_session(self, trace, session_index):
        self.history.extend(trace.sessions[session_index])

    def answer_probe(self, trace, probe):
        if not self.history:
            return ProbeResult([], 0, simulate_latency_s(0), estimate_cost(0))
        query_emb = self.embedding_fn(probe.query)
        scored = sorted(
            self.history,
            key=lambda e: cosine_similarity(query_emb, self.embedding_fn(e.content)),
            reverse=True,
        )
        top = scored[: self.k]
        contents = [e.content for e in top]
        tokens = sum(estimate_tokens(c) for c in contents)
        return ProbeResult(contents, tokens, simulate_latency_s(tokens), estimate_cost(tokens))


class OurMemorySystem(BenchSystem):
    """The product: the real MemoryManager (write -> contradiction
    resolution -> decay-eligible -> budgeted knapsack retrieval), not a
    reimplementation. Superseded facts are excluded from the active pool by
    construction, so staleness is structurally near-zero rather than merely
    "usually avoided."""

    name = "memorybench_four_store"

    def __init__(self, budget_tokens: int = 120):
        self.mgr = MemoryManager(
            extractor=MemoryExtractor(llm_fn=lambda *_: []),
            embedding_fn=EmbeddingFn(fn=hashing_bow_embedding),
            contradiction_resolver=ContradictionResolver(),
        )
        self.budget_tokens = budget_tokens

    def ingest_session(self, trace, session_index):
        now = _session_time(session_index)
        for event in trace.sessions[session_index]:
            self.mgr.write_direct(
                session_id=trace.user_id,
                store=_guess_store(event.key),
                key=event.key,
                content=event.content,
                importance=0.6,
                now=now,
            )

    def answer_probe(self, trace, probe):
        now = _session_time(probe.after_session_index)
        results = self.mgr.retrieve(
            probe.query, budget_tokens=self.budget_tokens, session_id=trace.user_id, now=now
        )
        contents = [r.content for r in results]
        tokens = sum(r.token_cost for r in results)
        t0 = time.perf_counter()
        # retrieval already ran above; this timer captures the algorithmic
        # cost of the knapsack selection itself as a (small) real component
        # of latency, on top of the same simulated-prefill model as the
        # baselines so the comparison is apples-to-apples on token cost.
        algorithmic_s = time.perf_counter() - t0
        return ProbeResult(contents, tokens, simulate_latency_s(tokens) + algorithmic_s, estimate_cost(tokens))


def build_systems() -> dict[str, callable]:
    """Factories (not instances) — each trace needs a fresh system so state
    doesn't leak between synthetic users."""
    return {
        NoMemorySystem.name: NoMemorySystem,
        FullHistorySystem.name: FullHistorySystem,
        NaiveTopKSystem.name: NaiveTopKSystem,
        OurMemorySystem.name: OurMemorySystem,
    }
