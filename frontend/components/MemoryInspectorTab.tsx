"use client";

import { useEffect, useState } from "react";
import { getMemory, MemoryInspectorOut, MemoryRecordOut, runDecayNow } from "@/lib/api";

const STORE_LABELS: Record<string, string> = {
  episodic: "Episodic",
  semantic: "Semantic",
  preference: "Preference",
  working: "Working",
};

const STORE_COLORS: Record<string, string> = {
  episodic: "border-sky-300 bg-sky-50 dark:border-sky-800 dark:bg-sky-950/40",
  semantic: "border-violet-300 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40",
  preference: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40",
  working: "border-zinc-300 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900",
};

function RecordCard({ r }: { r: MemoryRecordOut }) {
  return (
    <div className="rounded-md border border-black/10 bg-white/70 p-2 text-xs dark:border-white/10 dark:bg-black/20">
      <p className="text-[13px] text-zinc-800 dark:text-zinc-100">{r.content}</p>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-zinc-500">
        <span>key: {r.key}</span>
        <span>access ×{r.access_count}</span>
        <span>importance {r.explicit_importance.toFixed(2)}</span>
        {r.decay_score !== null && <span>decay {r.decay_score.toFixed(2)}</span>}
        <span>{r.token_cost} tok</span>
      </div>
      {r.decay_score !== null && (
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
          <div
            className={`h-full ${r.decay_score < 0.2 ? "bg-red-500" : r.decay_score < 0.5 ? "bg-amber-500" : "bg-emerald-500"}`}
            style={{ width: `${Math.min(100, Math.max(2, r.decay_score * 100))}%` }}
          />
        </div>
      )}
    </div>
  );
}

export default function MemoryInspectorTab({ sessionId }: { sessionId: string | null }) {
  const [scope, setScope] = useState<"session" | "all">("session");
  const [data, setData] = useState<MemoryInspectorOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    getMemory(scope === "session" ? sessionId || undefined : undefined)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, scope]);

  const handleDecay = async () => {
    await runDecayNow();
    load();
  };

  const storeGroups = ["episodic", "semantic", "preference", "working"];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="font-medium text-zinc-500">Scope</span>
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value as "session" | "all")}
          className="rounded-md border border-black/10 bg-white px-2 py-1 dark:border-white/15 dark:bg-zinc-900"
        >
          <option value="session">This session only</option>
          <option value="all">All sessions</option>
        </select>
        <button onClick={load} className="text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">↻ refresh</button>
        <button
          onClick={handleDecay}
          className="ml-auto rounded-md bg-zinc-800 px-3 py-1.5 font-medium text-white hover:bg-zinc-700 dark:bg-zinc-700"
        >
          Run decay pass now
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {loading && <p className="text-sm text-zinc-400">Loading…</p>}

      {data && (
        <>
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Active memories ({data.active.length})
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {storeGroups.map((store) => {
                const recs = data.active.filter((r) => r.store === store);
                return (
                  <div key={store} className={`rounded-lg border p-3 ${STORE_COLORS[store]}`}>
                    <h3 className="mb-2 text-sm font-semibold">
                      {STORE_LABELS[store]} <span className="font-normal text-zinc-500">({recs.length})</span>
                    </h3>
                    <div className="space-y-2">
                      {recs.length === 0 && <p className="text-xs text-zinc-400">empty</p>}
                      {recs.map((r) => (
                        <RecordCard key={r.id} r={r} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Superseded ({data.superseded.length})
            </h2>
            <p className="mb-2 text-xs text-zinc-400">Corrected by newer information — kept, not deleted, with a reason.</p>
            <div className="space-y-2">
              {data.superseded.length === 0 && <p className="text-xs text-zinc-400">none yet</p>}
              {data.superseded.map((r) => (
                <div key={r.id} className="rounded-md border border-orange-300 bg-orange-50 p-2 text-xs dark:border-orange-800 dark:bg-orange-950/30">
                  <p className="text-zinc-700 line-through dark:text-zinc-300">{r.content}</p>
                  <p className="mt-1 text-orange-700 dark:text-orange-300">{r.supersede_reason}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Forgotten ({data.forgotten.length})
            </h2>
            <p className="mb-2 text-xs text-zinc-400">Archived by the decay policy — every entry has a logged reason.</p>
            <div className="space-y-2">
              {data.forgotten.length === 0 && <p className="text-xs text-zinc-400">nothing archived yet — try “Run decay pass now”</p>}
              {data.forgotten.map((r) => (
                <div key={r.id} className="rounded-md border border-red-300 bg-red-50 p-2 text-xs dark:border-red-900 dark:bg-red-950/30">
                  <p className="text-zinc-500 line-through">{r.content}</p>
                  <p className="mt-1 text-red-700 dark:text-red-300">{r.archived_reason}</p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
