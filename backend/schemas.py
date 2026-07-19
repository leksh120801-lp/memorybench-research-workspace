from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    document_ids: list[str]
    turn_count: int


class DocumentOut(BaseModel):
    document_id: str
    filename: str
    num_pages: int
    num_chunks: int
    storage_uri: str


class ChatRequest(BaseModel):
    message: str


class CitationOut(BaseModel):
    source: str
    page: int
    snippet: str
    score: float


class ChatResponseOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    memories_written: int
    used_llm: bool


class MemoryRecordOut(BaseModel):
    id: str
    content: str
    store: str
    session_id: str
    key: str
    status: str
    created_at: str
    last_accessed_at: str
    access_count: int
    explicit_importance: float
    decay_score: Optional[float] = None
    supersede_reason: Optional[str] = None
    archived_reason: Optional[str] = None
    token_cost: int


class MemoryInspectorOut(BaseModel):
    active: list[MemoryRecordOut]
    superseded: list[MemoryRecordOut]
    forgotten: list[MemoryRecordOut]


class BenchRunRequest(BaseModel):
    n_traces: int = 30
    seed: int = 42


class BenchMetricOut(BaseModel):
    system_name: str
    num_probes: int
    recall_at_k: float
    staleness_rate: float
    avg_tokens_per_turn: float
    avg_cost_per_session: float
    avg_latency_s: float


class BenchRunResponse(BaseModel):
    results: list[BenchMetricOut]
    table_path: str
    chart_path: str
    json_path: str
