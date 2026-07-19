from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RetrievalCandidate:
    id: str
    token_cost: int
    relevance: float
    record: Optional[Any] = None


def knapsack_select(candidates: list[RetrievalCandidate], budget_tokens: int) -> list[RetrievalCandidate]:
    """0/1 knapsack over (relevance, token_cost): pick the subset of candidates
    that maximizes total relevance subject to a hard token budget.

    This is deliberately NOT top-k-by-relevance: top-k can waste budget on one
    expensive high-relevance item when several cheaper, slightly-less-relevant
    items would fit together and sum to more total relevance.
    """
    budget = int(budget_tokens)
    if budget <= 0 or not candidates:
        return []

    n = len(candidates)
    dp = [0.0] * (budget + 1)
    keep = [[False] * (budget + 1) for _ in range(n)]

    for i, c in enumerate(candidates):
        w = c.token_cost
        v = c.relevance
        if w <= 0:
            w = 1
        for b in range(budget, w - 1, -1):
            candidate_val = dp[b - w] + v
            if candidate_val > dp[b]:
                dp[b] = candidate_val
                keep[i][b] = True

    selected: list[RetrievalCandidate] = []
    b = budget
    for i in range(n - 1, -1, -1):
        if keep[i][b]:
            c = candidates[i]
            selected.append(c)
            b -= max(1, c.token_cost)

    selected.reverse()
    return selected
