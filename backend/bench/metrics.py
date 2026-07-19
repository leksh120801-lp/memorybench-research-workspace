from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProbeOutcome:
    hit: bool
    stale_cited: bool
    token_cost: int
    latency_s: float
    cost: float


@dataclass
class SystemMetrics:
    system_name: str
    num_probes: int
    recall_at_k: float
    staleness_rate: float
    avg_tokens_per_turn: float
    avg_cost_per_session: float
    avg_latency_s: float
    outcomes: list[ProbeOutcome] = field(default_factory=list)


def evaluate_probe(result_contents: list[str], correct_content: str, stale_content: str | None) -> tuple[bool, bool]:
    hit = any(correct_content in c for c in result_contents)
    stale_cited = stale_content is not None and any(stale_content in c for c in result_contents)
    return hit, stale_cited


def aggregate(system_name: str, outcomes: list[ProbeOutcome], num_traces: int) -> SystemMetrics:
    n = len(outcomes)
    if n == 0:
        return SystemMetrics(system_name, 0, 0.0, 0.0, 0.0, 0.0, 0.0, [])
    recall = sum(1 for o in outcomes if o.hit) / n
    staleness = sum(1 for o in outcomes if o.stale_cited) / n
    avg_tokens = sum(o.token_cost for o in outcomes) / n
    total_cost = sum(o.cost for o in outcomes)
    avg_cost_per_session = total_cost / max(1, num_traces)
    avg_latency = sum(o.latency_s for o in outcomes) / n
    return SystemMetrics(
        system_name=system_name,
        num_probes=n,
        recall_at_k=recall,
        staleness_rate=staleness,
        avg_tokens_per_turn=avg_tokens,
        avg_cost_per_session=avg_cost_per_session,
        avg_latency_s=avg_latency,
        outcomes=outcomes,
    )
