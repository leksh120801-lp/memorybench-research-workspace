"use client";

import { useRef, useState } from "react";
import { CitationOut, DocumentOut, sendChat, uploadDocument } from "@/lib/api";

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations?: CitationOut[];
  usedLlm?: boolean;
  memoriesWritten?: number;
}

export default function ChatTab({ sessionId }: { sessionId: string | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    if (!sessionId) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(sessionId, file);
      setDocs((prev) => [...prev, doc]);
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleSend = async () => {
    if (!sessionId || !input.trim()) return;
    const message = input.trim();
    setInput("");
    setTurns((prev) => [...prev, { role: "user", text: message }]);
    setSending(true);
    setError(null);
    try {
      const res = await sendChat(sessionId, message);
      setTurns((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, citations: res.citations, usedLlm: res.used_llm, memoriesWritten: res.memories_written },
      ]);
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  };

  if (!sessionId) {
    return <div className="p-8 text-center text-zinc-500">Create or resume a session above to start chatting.</div>;
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <div className="flex items-center gap-3 rounded-lg border border-black/10 bg-white p-3 text-sm dark:border-white/10 dark:bg-zinc-900">
        <label className="cursor-pointer rounded-md bg-zinc-800 px-3 py-1.5 font-medium text-white hover:bg-zinc-700 dark:bg-zinc-700">
          {uploading ? "Uploading…" : "Upload PDF"}
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
          />
        </label>
        <span className="text-zinc-500">
          {docs.length === 0 ? "No documents uploaded this session yet." : `${docs.length} document(s): ${docs.map((d) => d.filename).join(", ")}`}
        </span>
      </div>

      <div className="flex min-h-[320px] flex-col gap-4 rounded-lg border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-900">
        {turns.length === 0 && (
          <p className="text-sm text-zinc-400">
            Ask about an uploaded paper, or state a preference (e.g. “I prefer concise answers”) and revisit it next session.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={t.role === "user" ? "self-end max-w-[80%]" : "self-start max-w-[85%]"}>
            <div
              className={
                t.role === "user"
                  ? "rounded-2xl rounded-br-sm bg-emerald-600 px-4 py-2 text-white"
                  : "rounded-2xl rounded-bl-sm bg-zinc-100 px-4 py-2 dark:bg-zinc-800"
              }
            >
              <p className="whitespace-pre-wrap text-sm">{t.text}</p>
            </div>
            {t.role === "assistant" && (
              <div className="mt-1 flex flex-wrap gap-2 px-1 text-xs text-zinc-400">
                {!t.usedLlm && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">offline stub — no DASHSCOPE_API_KEY</span>}
                {(t.memoriesWritten ?? 0) > 0 && <span>· wrote {t.memoriesWritten} memory record(s)</span>}
              </div>
            )}
            {t.citations && t.citations.length > 0 && (
              <div className="mt-1 space-y-1 px-1">
                {t.citations.map((c, ci) => (
                  <div key={ci} className="rounded border border-black/10 bg-zinc-50 px-2 py-1 text-xs text-zinc-500 dark:border-white/10 dark:bg-zinc-950">
                    <span className="font-mono">{c.source} p.{c.page}</span> — “{c.snippet}”
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question…"
          className="flex-1 rounded-lg border border-black/10 bg-white px-3 py-2 text-sm dark:border-white/15 dark:bg-zinc-900"
        />
        <button
          onClick={handleSend}
          disabled={sending || !input.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
