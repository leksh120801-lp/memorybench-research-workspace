from __future__ import annotations

import json
import os
from typing import Callable, Optional

import numpy as np


class SessionVectorIndex:
    """One local FAISS index per session (flat inner-product over
    L2-normalized vectors == cosine similarity). Persisted to disk under
    `storage_dir`; `backup_fn` (if given, wired to OSSClient.backup_faiss_index
    in backend/state.py — see backend/alibaba_cloud.py) pushes each session's
    index to Alibaba Cloud OSS after every add, satisfying "local FAISS,
    backed up to OSS". Takes a plain callable rather than importing OSSClient
    directly, so this module has no dependency on the OSS integration."""

    def __init__(self, storage_dir: str, backup_fn: Optional[Callable[[str, str, str], dict]] = None):
        self.storage_dir = storage_dir
        self.backup_fn = backup_fn
        self._indexes: dict[str, "faiss.Index"] = {}
        self._chunks: dict[str, list[dict]] = {}
        os.makedirs(storage_dir, exist_ok=True)

    def _index_path(self, session_id: str) -> str:
        return os.path.join(self.storage_dir, f"{session_id}.index")

    def _meta_path(self, session_id: str) -> str:
        return os.path.join(self.storage_dir, f"{session_id}.meta.json")

    def _load_if_needed(self, session_id: str):
        if session_id in self._indexes:
            return
        index_path, meta_path = self._index_path(session_id), self._meta_path(session_id)
        if os.path.exists(index_path) and os.path.exists(meta_path):
            import faiss

            self._indexes[session_id] = faiss.read_index(index_path)
            with open(meta_path) as f:
                self._chunks[session_id] = json.load(f)

    def add(self, session_id: str, chunks: list[dict], embeddings: list[list[float]]) -> int:
        """chunks: list of {"text", "source", "page"}. Returns number added."""
        import faiss

        self._load_if_needed(session_id)
        vecs = np.array(embeddings, dtype="float32")
        faiss.normalize_L2(vecs)

        if session_id not in self._indexes:
            dim = vecs.shape[1]
            self._indexes[session_id] = faiss.IndexFlatIP(dim)
            self._chunks[session_id] = []

        self._indexes[session_id].add(vecs)
        self._chunks[session_id].extend(chunks)
        self._persist(session_id)
        return len(chunks)

    def search(self, session_id: str, query_embedding: list[float], k: int = 4) -> list[dict]:
        import faiss

        self._load_if_needed(session_id)
        if session_id not in self._indexes or self._indexes[session_id].ntotal == 0:
            return []
        q = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(q)
        scores, ids = self._indexes[session_id].search(q, min(k, self._indexes[session_id].ntotal))
        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            chunk = dict(self._chunks[session_id][idx])
            chunk["score"] = float(score)
            results.append(chunk)
        return results

    def _persist(self, session_id: str):
        import faiss

        faiss.write_index(self._indexes[session_id], self._index_path(session_id))
        with open(self._meta_path(session_id), "w") as f:
            json.dump(self._chunks[session_id], f, indent=2)
        if self.backup_fn:
            self.backup_fn(session_id, self._index_path(session_id), self._meta_path(session_id))
