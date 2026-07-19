from __future__ import annotations

from .metrics import ProbeOutcome, SystemMetrics, aggregate, evaluate_probe
from .systems import build_systems
from .traces import SyntheticTrace, generate_traces


def run_benchmark(traces: list[SyntheticTrace], seed: int = 42) -> dict[str, SystemMetrics]:
    factories = build_systems()
    results: dict[str, SystemMetrics] = {}

    for name, factory in factories.items():
        outcomes: list[ProbeOutcome] = []
        for trace in traces:
            system = factory()
            probes_by_session: dict[int, list] = {}
            for probe in trace.probes:
                probes_by_session.setdefault(probe.after_session_index, []).append(probe)

            for session_index in range(trace.num_sessions):
                system.ingest_session(trace, session_index)
                for probe in probes_by_session.get(session_index, []):
                    result = system.answer_probe(trace, probe)
                    hit, stale = evaluate_probe(result.retrieved_contents, probe.correct_content, probe.stale_content)
                    outcomes.append(
                        ProbeOutcome(
                            hit=hit,
                            stale_cited=stale,
                            token_cost=result.token_cost,
                            latency_s=result.latency_s,
                            cost=result.cost,
                        )
                    )
        results[name] = aggregate(name, outcomes, num_traces=len(traces))

    return results


def run_default_benchmark(n_traces: int = 30, seed: int = 42) -> dict[str, SystemMetrics]:
    traces = generate_traces(n=n_traces, seed=seed)
    return run_benchmark(traces, seed=seed)
