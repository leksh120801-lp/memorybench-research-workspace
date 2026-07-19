"""Process-wide singletons wired up once and shared across routes via
FastAPI dependency functions. Offline-safe by construction: every component
degrades to a free local fallback when DashScope/OSS credentials aren't set,
so `uvicorn backend.app:app` runs with zero configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # loads .env from cwd if present; never overrides already-set env vars

from .alibaba_cloud import OSSClient
from .bench.lexical_embed import hashing_bow_embedding
from .documents.faiss_index import SessionVectorIndex
from .llm import QwenClient
from .memory.embeddings import EmbeddingFn
from .memory.extractor import MemoryExtractor
from .memory.manager import MemoryManager
from .sessions import SessionStore

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

qwen = QwenClient()
oss = OSSClient()


def _embed(text: str) -> list[float]:
    if qwen.is_configured():
        return qwen.embed(text)
    return hashing_bow_embedding(text)


def _extract(user_text: str, context: dict):
    if qwen.is_configured():
        return qwen.extract(user_text, context)
    return []  # offline: nothing gets auto-persisted from chat turns


embedding_fn = EmbeddingFn(fn=_embed)

memory_manager = MemoryManager(
    extractor=MemoryExtractor(llm_fn=_extract),
    embedding_fn=embedding_fn,
    storage_path=os.path.join(DATA_DIR, "memory_store.json"),
)


def _backup_faiss(session_id: str, index_path: str, meta_path: str):
    if oss.is_configured():
        oss.backup_faiss_index(session_id, index_path, meta_path)


vector_index = SessionVectorIndex(
    storage_dir=os.path.join(DATA_DIR, "faiss"),
    backup_fn=_backup_faiss,
)

session_store = SessionStore(storage_path=os.path.join(DATA_DIR, "sessions.json"))


def get_memory_manager() -> MemoryManager:
    return memory_manager


def get_vector_index() -> SessionVectorIndex:
    return vector_index


def get_session_store() -> SessionStore:
    return session_store


def get_qwen_client() -> QwenClient:
    return qwen


def get_oss_client() -> OSSClient:
    return oss


def get_embedding_fn():
    return embedding_fn
