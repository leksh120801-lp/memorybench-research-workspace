# MemoryBench Results

| Metric | No Memory | Full-History Stuffing | Naive Top-K RAG | MemoryBench (ours) |
|---|---|---|---|---|
| Recall@budget | 0.0% | 100.0% | 100.0% | 100.0% |
| Staleness rate | 0.0% | 47.1% | 47.1% | 0.0% |
| Avg context tokens/turn | 0 | 149 | 90 | 50 |
| Avg cost/session ($, illustrative) | 0.0000 | 0.0225 | 0.0136 | 0.0075 |
| Avg latency/turn (s, illustrative) | 0.050 | 0.139 | 0.104 | 0.080 |
| # probes evaluated | 227 | 227 | 227 | 227 |
