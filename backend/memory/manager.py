from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from .contradiction import ContradictionResolver
from .decay import DEFAULT_THRESHOLD, apply_decay
from .embeddings import EmbeddingFn, cosine_similarity
from .extractor import ExtractionCandidate, MemoryExtractor
from .models import MemoryRecord, MemoryStatus, MemoryType, utcnow
from .retrieval import RetrievalCandidate, knapsack_select


class MemoryManager:
    """Owns all four memory stores as one record list keyed by `store`, and
    implements the four required behaviors: WRITE (via extractor, not every
    turn persists), CONTRADICTION RESOLUTION (supersede, never silently
    append), DECAY (archive below threshold, never delete), RETRIEVE (budgeted
    knapsack selection, not top-k)."""

    def __init__(
        self,
        extractor: Optional[MemoryExtractor] = None,
        embedding_fn: Optional[EmbeddingFn] = None,
        contradiction_resolver: Optional[ContradictionResolver] = None,
        decay_threshold: float = DEFAULT_THRESHOLD,
        storage_path: Optional[str] = None,
    ):
        self.extractor = extractor or MemoryExtractor()
        self.embedding_fn = embedding_fn or EmbeddingFn()
        self.resolver = contradiction_resolver or ContradictionResolver()
        self.decay_threshold = decay_threshold
        self.storage_path = storage_path
        self.records: list[MemoryRecord] = []
        if storage_path and os.path.exists(storage_path):
            self._load()

    # ---------------------------------------------------------------- WRITE
    def process_turn(
        self, session_id: str, user_text: str, assistant_text: str = "", now: Optional[datetime] = None
    ) -> list[MemoryRecord]:
        """Runs the extractor over a turn and writes whatever (if anything)
        it decides is worth persisting."""
        now = now or utcnow()
        candidates = self.extractor.extract(session_id, user_text, assistant_text)
        written = []
        for c in candidates:
            rec = self._write_candidate(session_id, c, now)
            if rec is not None:
                written.append(rec)
        if written and self.storage_path:
            self._save()
        return written

    def write_direct(
        self,
        session_id: str,
        store: MemoryType,
        key: str,
        content: str,
        importance: float = 0.5,
        now: Optional[datetime] = None,
    ) -> Optional[MemoryRecord]:
        """Bypasses the extractor for callers that already know exactly what
        to write (API endpoints, the benchmark harness seeding traces)."""
        now = now or utcnow()
        rec = self._write_candidate(session_id, ExtractionCandidate(store=store, key=key, content=content, importance=importance), now)
        if rec is not None and self.storage_path:
            self._save()
        return rec

    def _write_candidate(self, session_id: str, c: ExtractionCandidate, now: datetime) -> Optional[MemoryRecord]:
        existing = [
            r
            for r in self.records
            if r.key == c.key
            and r.store == c.store
            and (r.store != MemoryType.WORKING or r.session_id == session_id)
        ]

        supersessions = self.resolver.resolve(existing, c.key, c.content, now=now)

        if not supersessions:
            dup = next(
                (r for r in existing if r.status == MemoryStatus.ACTIVE and r.content.strip() == c.content.strip()),
                None,
            )
            if dup is not None:
                dup.access_count += 1
                dup.last_accessed_at = now
                dup.explicit_importance = max(dup.explicit_importance, c.importance)
                return None

        record = MemoryRecord(
            content=c.content,
            store=c.store,
            session_id=session_id,
            key=c.key,
            explicit_importance=c.importance,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
        )
        record.embedding = self.embedding_fn(c.content)
        if supersessions:
            record.metadata["supersedes_ids"] = [s.old_record.id for s in supersessions]
            record.supersedes = supersessions[0].old_record.id
            for s in supersessions:
                s.old_record.superseded_by = record.id
        self.records.append(record)
        return record

    # ---------------------------------------------------------------- DECAY
    def run_decay(self, now: Optional[datetime] = None):
        now = now or utcnow()
        archived = apply_decay(self.records, now=now, threshold=self.decay_threshold)
        if archived and self.storage_path:
            self._save()
        return archived

    # ------------------------------------------------------------- RETRIEVE
    def retrieve(
        self,
        query: str,
        budget_tokens: int,
        session_id: Optional[str] = None,
        stores: Optional[list[MemoryType]] = None,
        now: Optional[datetime] = None,
    ) -> list[MemoryRecord]:
        now = now or utcnow()
        query_emb = self.embedding_fn(query)
        pool = [r for r in self.records if r.status == MemoryStatus.ACTIVE]
        if stores:
            pool = [r for r in pool if r.store in stores]
        if session_id:
            pool = [r for r in pool if r.store != MemoryType.WORKING or r.session_id == session_id]

        candidates = [
            RetrievalCandidate(id=r.id, token_cost=r.token_cost, relevance=cosine_similarity(query_emb, r.embedding or []), record=r)
            for r in pool
        ]
        selected = knapsack_select(candidates, budget_tokens)

        result = []
        for c in selected:
            c.record.access_count += 1
            c.record.last_accessed_at = now
            result.append(c.record)
        if selected and self.storage_path:
            self._save()
        return result

    # ----------------------------------------------------------- inspector
    def forgotten(self, store: Optional[MemoryType] = None) -> list[MemoryRecord]:
        recs = [r for r in self.records if r.status == MemoryStatus.ARCHIVED]
        if store:
            recs = [r for r in recs if r.store == store]
        return recs

    def active(self, store: Optional[MemoryType] = None, session_id: Optional[str] = None) -> list[MemoryRecord]:
        recs = [r for r in self.records if r.status == MemoryStatus.ACTIVE]
        if store:
            recs = [r for r in recs if r.store == store]
        if session_id:
            recs = [r for r in recs if r.session_id == session_id]
        return recs

    def superseded(self, store: Optional[MemoryType] = None) -> list[MemoryRecord]:
        recs = [r for r in self.records if r.status == MemoryStatus.SUPERSEDED]
        if store:
            recs = [r for r in recs if r.store == store]
        return recs

    def all(self) -> list[MemoryRecord]:
        return list(self.records)

    def clear_working(self, session_id: str, reason: str = "session ended", now: Optional[datetime] = None) -> list[MemoryRecord]:
        """Working memory's own policy: it doesn't wait for decay, it gets
        explicitly archived when a session ends."""
        now = now or utcnow()
        cleared = []
        for r in self.records:
            if r.store == MemoryType.WORKING and r.session_id == session_id and r.status == MemoryStatus.ACTIVE:
                r.status = MemoryStatus.ARCHIVED
                r.archived_reason = reason
                r.archived_at = now
                cleared.append(r)
        if cleared and self.storage_path:
            self._save()
        return cleared

    # ------------------------------------------------------------ persist
    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump([r.to_dict() for r in self.records], f, indent=2)

    def _load(self):
        with open(self.storage_path) as f:
            data = json.load(f)
        self.records = [MemoryRecord.from_dict(d) for d in data]
