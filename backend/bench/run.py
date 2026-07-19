"""CLI entrypoint: python -m backend.bench.run"""

from __future__ import annotations

import argparse
import os

from .report import write_outputs
from .runner import run_default_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MemoryBench against no-memory, full-history, and naive top-k RAG baselines.")
    parser.add_argument("--traces", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=os.path.join(os.path.dirname(__file__), "output"))
    args = parser.parse_args()

    results = run_default_benchmark(n_traces=args.traces, seed=args.seed)
    paths = write_outputs(results, args.output_dir)

    print(f"\nMemoryBench — {args.traces} synthetic traces, seed={args.seed}\n")
    from .report import render_table

    print(render_table(results))
    print(f"\nWrote: {paths['table']}\n       {paths['json']}\n       {paths['chart']}")


if __name__ == "__main__":
    main()
