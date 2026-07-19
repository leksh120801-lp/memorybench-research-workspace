"use client";

import { useEffect, useState } from "react";
import SessionBar from "@/components/SessionBar";
import ChatTab from "@/components/ChatTab";
import MemoryInspectorTab from "@/components/MemoryInspectorTab";
import MemoryBenchTab from "@/components/MemoryBenchTab";

type Tab = "chat" | "inspector" | "bench";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "inspector", label: "Memory Inspector" },
  { id: "bench", label: "MemoryBench" },
];

const STORAGE_KEY = "memorybench.sessionId";

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    // one-time hydration from localStorage — must run client-only, after mount, to avoid SSR mismatch
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved) setSessionId(saved);
  }, []);

  const handleChangeSession = (id: string) => {
    setSessionId(id);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, id);
  };

  return (
    <div className="flex flex-1 flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b border-black/10 px-4 py-3 dark:border-white/10">
        <h1 className="text-lg font-semibold">MemoryBench</h1>
        <p className="text-xs text-zinc-500">Track 1 (MemoryAgent) — four-store memory layer + benchmark, on Qwen via DashScope</p>
      </header>

      <SessionBar sessionId={sessionId} onChangeSession={handleChangeSession} />

      <nav className="flex gap-1 border-b border-black/10 bg-white px-4 pt-2 dark:border-white/10 dark:bg-zinc-950">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-t-md px-4 py-2 text-sm font-medium transition ${
              tab === t.id
                ? "border border-b-0 border-black/10 bg-zinc-50 text-emerald-600 dark:border-white/10 dark:bg-black dark:text-emerald-400"
                : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="flex-1">
        {tab === "chat" && <ChatTab sessionId={sessionId} />}
        {tab === "inspector" && <MemoryInspectorTab sessionId={sessionId} />}
        {tab === "bench" && <MemoryBenchTab />}
      </main>
    </div>
  );
}
