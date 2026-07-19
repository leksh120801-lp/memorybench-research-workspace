from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .documents.faiss_index import SessionVectorIndex
from .llm import QwenClient
from .memory.manager import MemoryManager

SYSTEM_PROMPT = (
    "You are a research assistant with access to the user's uploaded papers and to your own "
    "memory of this user (preferences, prior facts, session history). Answer using the provided "
    "context. Cite sources by filename and page when you use a document passage. If the context "
    "doesn't contain the answer, say so."
)

MEMORY_RETRIEVAL_BUDGET_TOKENS = 300
DOC_TOP_K = 4


@dataclass
class Citation:
    source: str
    page: int
    snippet: str
    score: float


@dataclass
class ChatResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    memories_written: int = 0
    used_llm: bool = False


def _build_context(mem_hits, doc_hits) -> str:
    parts = []
    if mem_hits:
        parts.append("Known about this user:\n" + "\n".join(f"- {m.content}" for m in mem_hits))
    if doc_hits:
        parts.append(
            "Relevant document passages:\n"
            + "\n".join(f"[{h['source']} p.{h['page']}] {h['text']}" for h in doc_hits)
        )
    return "\n\n".join(parts) if parts else "(no relevant memory or documents found)"


def _extractive_stub_answer(user_message: str, doc_hits, mem_hits) -> str:
    if doc_hits:
        top = doc_hits[0]
        return (
            f"[offline stub — DASHSCOPE_API_KEY not set] Closest passage to your question, "
            f"from {top['source']} p.{top['page']}: “{top['text'][:280]}”"
        )
    if mem_hits:
        return "[offline stub — DASHSCOPE_API_KEY not set] Based on what I remember: " + " ".join(
            m.content for m in mem_hits[:3]
        )
    return "[offline stub — DASHSCOPE_API_KEY not set] No relevant memory or documents found for this question."


def answer_chat(
    session_id: str,
    user_message: str,
    memory_manager: MemoryManager,
    vector_index: SessionVectorIndex,
    embedding_fn: Callable[[str], list[float]],
    llm_client: QwenClient,
) -> ChatResponse:
    """Deliberately thin: retrieve memory (budgeted knapsack), retrieve
    document chunks (FAISS top-k), build context, generate (or fall back to
    an extractive stub offline), then let the extractor decide what from
    this turn is worth persisting."""
    mem_hits = memory_manager.retrieve(user_message, budget_tokens=MEMORY_RETRIEVAL_BUDGET_TOKENS, session_id=session_id)
    query_emb = embedding_fn(user_message)
    doc_hits = vector_index.search(session_id, query_emb, k=DOC_TOP_K)

    if llm_client.is_configured():
        context = _build_context(mem_hits, doc_hits)
        answer = llm_client.chat(SYSTEM_PROMPT, f"{context}\n\nUser question: {user_message}")
        used_llm = True
    else:
        answer = _extractive_stub_answer(user_message, doc_hits, mem_hits)
        used_llm = False

    written = memory_manager.process_turn(session_id, user_message, answer)

    citations = [Citation(source=h["source"], page=h["page"], snippet=h["text"][:200], score=h["score"]) for h in doc_hits]
    return ChatResponse(answer=answer, citations=citations, memories_written=len(written), used_llm=used_llm)
