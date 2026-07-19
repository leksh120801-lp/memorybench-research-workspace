"use client";

import { useEffect, useState } from "react";
import { API_BASE, BenchMetricOut, getLatestBench, runBench } from "@/lib/api";

const DISPLAY_NAMES: Record<string, string> = {
  no_memory: "No Memory",
  full_history: "Full-History Stuffing",
  naive_topk_rag: "Naive Top-K RAG",
  memorybench_four_store: "MemoryBench (ours)",
};

const COLUMN_ORDER = ["no_memory", "full_history", "naive_topk_rag", "memorybench_four_store"];

function ResultsTable({ results }: { results: BenchMetricOut[] }) {
  const byName = Object.fromEntries(results.map((r) => [r.system_name, r]));
  const rows: [string, (r: BenchMetricOut) => string][] = [
    ["Recall@budget", (r) => `${(r.recall_at_k * 100).toFixed(1)}%`],
    ["Staleness rate", (r) => `${(r.staleness_rate * 100).toFixed(1)}%`],
    ["Avg context tokens/turn", (r) => r.avg_tokens_per_turn.toFixed(0)],
    ["Avg cost/session ($, illustrative)", (r) => r.avg_cost_per_session.toFixed(4)],
    ["Avg latency/turn (s, illustrative)", (r) => r.avg_latency_s.toFixed(3)],
    ["# probes evaluated", (r) => String(r.num_probes)],
  ];
  const cols = COLUMN_ORDER.filter((c) => byName[c]);
  return (
    <div className="overflow-x-auto rounded-lg border border-black/10 dark:border-white/10">
      <table className="w-full text-sm">
        <thead className="bg-zinc-100 dark:bg-zinc-800">
          <tr>
            <th className="p-2 text-left">Metric</th>
            {cols.map((c) => (
              <th key={c} className={`p-2 text-left ${c === "memorybench_four_store" ? "text-emerald-600 dark:text-emerald-400" : ""}`}>
                {DISPLAY_NAMES[c] || c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, fmt]) => (
            <tr key={label} className="border-t border-black/5 dark:border-white/10">
              <td className="p-2 text-zinc-500">{label}</td>
              {cols.map((c) => (
                <td key={c} className={`p-2 ${c === "memorybench_four_store" ? "font-semibold text-emerald-600 dark:text-emerald-400" : ""}`}>
                  {fmt(byName[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function MemoryBenchTab() {
  const [results, setResults] = useState<BenchMetricOut[] | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartTs, setChartTs] = useState(0);
  const [nTraces, setNTraces] = useState(30);

  useEffect(() => {
    getLatestBench()
      .then((r) => {
        if (r.available && r.results) {
          setResults(Object.values(r.results));
          setChartTs(Date.now());
        }
      })
      .catch(() => {});
  }, []);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await runBench(nTraces, 42);
      setResults(res.results);
      setChartTs(Date.now());
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="text-zinc-500">Synthetic traces</label>
        <input
          type="number"
          min={5}
          max={100}
          value={nTraces}
          onChange={(e) => setNTraces(Number(e.target.value))}
          className="w-20 rounded-md border border-black/10 bg-white px-2 py-1 dark:border-white/15 dark:bg-zinc-900"
        />
        <button
          onClick={handleRun}
          disabled={running}
          className="rounded-md bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {running ? "Running MemoryBench…" : "Run MemoryBench"}
        </button>
        {error && <span className="text-red-500">{error}</span>}
      </div>

      <p className="text-sm text-zinc-500">
        Runs synthetic multi-session traces with evolving preferences and papers that supersede each other, then
        compares our four-store memory against no-memory, full-history stuffing, and naive top-k RAG baselines. No
        paid inference is used — offline, deterministic, and free to re-run.
      </p>

      {results && (
        <>
          <ResultsTable results={results} />
          <div className="rounded-lg border border-black/10 bg-white p-3 dark:border-white/10 dark:bg-zinc-900">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`${API_BASE}/bench-output/chart.png?t=${chartTs}`} alt="MemoryBench comparison chart" className="w-full rounded" />
          </div>
        </>
      )}
      {!results && !running && <p className="text-sm text-zinc-400">No results yet — click “Run MemoryBench”.</p>}
    </div>
  );
}
