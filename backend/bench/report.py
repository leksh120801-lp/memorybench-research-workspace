from __future__ import annotations

import json
import os

from .metrics import SystemMetrics

DISPLAY_NAMES = {
    "no_memory": "No Memory",
    "full_history": "Full-History Stuffing",
    "naive_topk_rag": "Naive Top-K RAG",
    "memorybench_four_store": "MemoryBench (ours)",
}

COLUMN_ORDER = ["no_memory", "full_history", "naive_topk_rag", "memorybench_four_store"]


def render_table(results: dict[str, SystemMetrics]) -> str:
    headers = ["Metric"] + [DISPLAY_NAMES.get(k, k) for k in COLUMN_ORDER if k in results]
    rows = [
        ("Recall@budget", "{:.1%}", "recall_at_k"),
        ("Staleness rate", "{:.1%}", "staleness_rate"),
        ("Avg context tokens/turn", "{:.0f}", "avg_tokens_per_turn"),
        ("Avg cost/session ($, illustrative)", "{:.4f}", "avg_cost_per_session"),
        ("Avg latency/turn (s, illustrative)", "{:.3f}", "avg_latency_s"),
        ("# probes evaluated", "{:d}", "num_probes"),
    ]

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for label, fmt, attr in rows:
        cells = [label]
        for k in COLUMN_ORDER:
            if k not in results:
                continue
            value = getattr(results[k], attr)
            cells.append(fmt.format(int(value)) if attr == "num_probes" else fmt.format(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_chart(results: dict[str, SystemMetrics], output_path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    systems = [k for k in COLUMN_ORDER if k in results]
    labels = [DISPLAY_NAMES.get(k, k) for k in systems]
    colors = ["#9CA3AF", "#F59E0B", "#EF4444", "#10B981"]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle("MemoryBench: our four-store memory vs. 3 baselines (30 synthetic multi-session traces)", fontsize=12)

    def bar(ax, values, title, pct=False):
        bars = ax.bar(labels, values, color=colors[: len(labels)])
        ax.set_title(title, fontsize=10)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
        for b, v in zip(bars, values):
            label = f"{v:.1%}" if pct else f"{v:.2f}"
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), label, ha="center", va="bottom", fontsize=8)

    bar(axes[0][0], [results[k].recall_at_k for k in systems], "Recall@budget (higher is better)", pct=True)
    bar(axes[0][1], [results[k].staleness_rate for k in systems], "Staleness rate (lower is better)", pct=True)
    bar(axes[1][0], [results[k].avg_tokens_per_turn for k in systems], "Avg context tokens/turn (lower is better)")
    bar(axes[1][1], [results[k].avg_cost_per_session for k in systems], "Avg illustrative cost/session $ (lower is better)")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def write_outputs(results: dict[str, SystemMetrics], output_dir: str) -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    table_md = render_table(results)
    table_path = os.path.join(output_dir, "results.md")
    with open(table_path, "w") as f:
        f.write("# MemoryBench Results\n\n" + table_md + "\n")

    json_path = os.path.join(output_dir, "results.json")
    with open(json_path, "w") as f:
        json.dump(
            {
                k: {
                    "system_name": v.system_name,
                    "num_probes": v.num_probes,
                    "recall_at_k": v.recall_at_k,
                    "staleness_rate": v.staleness_rate,
                    "avg_tokens_per_turn": v.avg_tokens_per_turn,
                    "avg_cost_per_session": v.avg_cost_per_session,
                    "avg_latency_s": v.avg_latency_s,
                }
                for k, v in results.items()
            },
            f,
            indent=2,
        )

    chart_path = os.path.join(output_dir, "chart.png")
    render_chart(results, chart_path)

    return {"table": table_path, "json": json_path, "chart": chart_path}
