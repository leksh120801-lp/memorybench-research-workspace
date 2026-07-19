from backend.bench.metrics import evaluate_probe
from backend.bench.runner import run_benchmark
from backend.bench.traces import generate_traces


def test_generates_30_traces_with_probes_by_default():
    traces = generate_traces(n=30, seed=42)
    assert len(traces) == 30
    assert all(len(t.probes) > 0 for t in traces)
    assert all(t.num_sessions >= 3 for t in traces)


def test_generate_traces_is_deterministic():
    a = generate_traces(n=5, seed=7)
    b = generate_traces(n=5, seed=7)
    assert [t.probes[0].correct_content for t in a] == [t.probes[0].correct_content for t in b]


def test_evaluate_probe_hit_and_staleness():
    hit, stale = evaluate_probe(["Fact X is 42.", "unrelated"], correct_content="Fact X is 42.", stale_content="Fact X is 40.")
    assert hit is True
    assert stale is False

    hit2, stale2 = evaluate_probe(["Fact X is 40."], correct_content="Fact X is 42.", stale_content="Fact X is 40.")
    assert hit2 is False
    assert stale2 is True


def test_our_system_beats_all_three_baselines_on_a_small_run():
    traces = generate_traces(n=10, seed=1)
    results = run_benchmark(traces)

    ours = results["memorybench_four_store"]
    baselines = [results["no_memory"], results["full_history"], results["naive_topk_rag"]]

    for b in baselines:
        assert ours.recall_at_k >= b.recall_at_k
        assert ours.staleness_rate <= b.staleness_rate

    # must clearly beat the naive baselines on cost/tokens (no_memory is a
    # degenerate zero-cost/zero-recall floor, not a real comparison point)
    for b in [results["full_history"], results["naive_topk_rag"]]:
        assert ours.avg_tokens_per_turn < b.avg_tokens_per_turn
        assert ours.avg_cost_per_session < b.avg_cost_per_session

    # the whole point of contradiction resolution: staleness should be ~zero
    assert ours.staleness_rate == 0.0
