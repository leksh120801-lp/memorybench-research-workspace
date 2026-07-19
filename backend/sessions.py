from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SessionRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled session"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    document_ids: list[str] = field(default_factory=list)
    turn_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        return cls(
            id=d["id"],
            title=d.get("title", "Untitled session"),
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            document_ids=d.get("document_ids", []),
            turn_count=d.get("turn_count", 0),
        )


class SessionStore:
    """Explicit, resumable sessions — created once, looked up by id on every
    later call. JSON-file persisted so a resumed session survives a backend
    restart, same pattern as MemoryManager's storage_path."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.sessions: dict[str, SessionRecord] = {}
        if storage_path and os.path.exists(storage_path):
            self._load()

    def create(self, title: Optional[str] = None) -> SessionRecord:
        rec = SessionRecord(title=title or "Untitled session")
        self.sessions[rec.id] = rec
        self._save()
        return rec

    def get(self, session_id: str) -> Optional[SessionRecord]:
        return self.sessions.get(session_id)

    def require(self, session_id: str) -> SessionRecord:
        rec = self.get(session_id)
        if rec is None:
            raise KeyError(session_id)
        return rec

    def list(self) -> list[SessionRecord]:
        return sorted(self.sessions.values(), key=lambda r: r.updated_at, reverse=True)

    def touch(self, session_id: str, increment_turn: bool = False) -> SessionRecord:
        rec = self.require(session_id)
        rec.updated_at = utcnow()
        if increment_turn:
            rec.turn_count += 1
        self._save()
        return rec

    def add_document(self, session_id: str, document_id: str) -> SessionRecord:
        rec = self.require(session_id)
        rec.document_ids.append(document_id)
        rec.updated_at = utcnow()
        self._save()
        return rec

    def _save(self):
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump([r.to_dict() for r in self.sessions.values()], f, indent=2)

    def _load(self):
        with open(self.storage_path) as f:
            data = json.load(f)
        self.sessions = {d["id"]: SessionRecord.from_dict(d) for d in data}
