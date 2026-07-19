"use client";

import { useEffect, useState } from "react";
import { createSession, listSessions, SessionOut } from "@/lib/api";

export default function SessionBar({
  sessionId,
  onChangeSession,
}: {
  sessionId: string | null;
  onChangeSession: (id: string) => void;
}) {
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    listSessions()
      .then(setSessions)
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleCreate = async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await createSession();
      setSessions((prev) => [s, ...prev]);
      onChangeSession(s.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-black/10 bg-white/60 px-4 py-3 text-sm dark:border-white/10 dark:bg-black/30">
      <span className="font-medium text-zinc-500">Session</span>
      <select
        className="rounded-md border border-black/10 bg-white px-2 py-1 dark:border-white/15 dark:bg-zinc-900"
        value={sessionId || ""}
        onChange={(e) => onChangeSession(e.target.value)}
      >
        <option value="" disabled>
          {sessions.length ? "Resume a session…" : "No sessions yet"}
        </option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {s.title} — {s.turn_count} turns — {s.id.slice(0, 8)}
          </option>
        ))}
      </select>
      <button
        onClick={handleCreate}
        disabled={loading}
        className="rounded-md bg-emerald-600 px-3 py-1 font-medium text-white transition hover:bg-emerald-700 disabled:opacity-50"
      >
        + New session
      </button>
      <button onClick={refresh} className="text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">
        ↻ refresh
      </button>
      {sessionId && <span className="text-xs text-zinc-400">current: {sessionId}</span>}
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
