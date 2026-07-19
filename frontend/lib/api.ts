export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface SessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  document_ids: string[];
  turn_count: number;
}

export interface DocumentOut {
  document_id: string;
  filename: string;
  num_pages: number;
  num_chunks: number;
  storage_uri: string;
}

export interface CitationOut {
  source: string;
  page: number;
  snippet: string;
  score: number;
}

export interface ChatResponseOut {
  answer: string;
  citations: CitationOut[];
  memories_written: number;
  used_llm: boolean;
}

export interface MemoryRecordOut {
  id: string;
  content: string;
  store: "episodic" | "semantic" | "preference" | "working";
  session_id: string;
  key: string;
  status: "active" | "superseded" | "archived";
  created_at: string;
  last_accessed_at: string;
  access_count: number;
  explicit_importance: number;
  decay_score: number | null;
  supersede_reason: string | null;
  archived_reason: string | null;
  token_cost: number;
}

export interface MemoryInspectorOut {
  active: MemoryRecordOut[];
  superseded: MemoryRecordOut[];
  forgotten: MemoryRecordOut[];
}

export interface BenchMetricOut {
  system_name: string;
  num_probes: number;
  recall_at_k: number;
  staleness_rate: number;
  avg_tokens_per_turn: number;
  avg_cost_per_session: number;
  avg_latency_s: number;
}

export interface BenchRunResponse {
  results: BenchMetricOut[];
  table_path: string;
  chart_path: string;
  json_path: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function createSession(title?: string): Promise<SessionOut> {
  return request("/sessions", { method: "POST", body: JSON.stringify({ title: title || null }) });
}

export function listSessions(): Promise<SessionOut[]> {
  return request("/sessions");
}

export function getSession(id: string): Promise<SessionOut> {
  return request(`/sessions/${id}`);
}

export async function uploadDocument(sessionId: string, file: File): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/documents`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

export function sendChat(sessionId: string, message: string): Promise<ChatResponseOut> {
  return request(`/sessions/${sessionId}/chat`, { method: "POST", body: JSON.stringify({ message }) });
}

export function getMemory(sessionId?: string, store?: string): Promise<MemoryInspectorOut> {
  const params = new URLSearchParams();
  if (sessionId) params.set("session_id", sessionId);
  if (store) params.set("store", store);
  const qs = params.toString();
  return request(`/memory${qs ? `?${qs}` : ""}`);
}

export function runDecayNow(): Promise<{ archived_count: number; archived_ids: string[] }> {
  return request("/memory/decay", { method: "POST" });
}

export function runBench(nTraces: number, seed: number): Promise<BenchRunResponse> {
  return request("/bench/run", { method: "POST", body: JSON.stringify({ n_traces: nTraces, seed }) });
}

export function getLatestBench(): Promise<{ available: boolean; results?: Record<string, BenchMetricOut> }> {
  return request("/bench/latest");
}
