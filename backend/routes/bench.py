from __future__ import annotations

import os

from fastapi import APIRouter

from ..bench.report import write_outputs
from ..bench.runner import run_default_benchmark
from ..schemas import BenchMetricOut, BenchRunRequest, BenchRunResponse

router = APIRouter(prefix="/bench", tags=["bench"])

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bench", "output")


@router.post("/run", response_model=BenchRunResponse)
def run_bench(body: BenchRunRequest = BenchRunRequest()):
    results = run_default_benchmark(n_traces=body.n_traces, seed=body.seed)
    paths = write_outputs(results, OUTPUT_DIR)
    return BenchRunResponse(
        results=[
            BenchMetricOut(
                system_name=v.system_name,
                num_probes=v.num_probes,
                recall_at_k=v.recall_at_k,
                staleness_rate=v.staleness_rate,
                avg_tokens_per_turn=v.avg_tokens_per_turn,
                avg_cost_per_session=v.avg_cost_per_session,
                avg_latency_s=v.avg_latency_s,
            )
            for v in results.values()
        ],
        table_path=paths["table"],
        chart_path=paths["chart"],
        json_path=paths["json"],
    )


@router.get("/latest")
def latest_bench():
    json_path = os.path.join(OUTPUT_DIR, "results.json")
    if not os.path.exists(json_path):
        return {"available": False}
    import json

    with open(json_path) as f:
        return {"available": True, "results": json.load(f)}
