from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    WORKING = "working"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


@dataclass
class MemoryRecord:
    content: str
    store: MemoryType
    session_id: str
    key: str  # dedupe / contradiction-matching key, e.g. "preference:editor"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    last_accessed_at: datetime = field(default_factory=utcnow)
    access_count: int = 0
    explicit_importance: float = 0.5
    status: MemoryStatus = MemoryStatus.ACTIVE
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    supersede_reason: Optional[str] = None
    archived_reason: Optional[str] = None
    archived_at: Optional[datetime] = None
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_cost(self) -> int:
        """Rough token estimate (~4 chars/token) — no tokenizer dependency needed."""
        return max(1, len(self.content) // 4)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "content": self.content,
            "store": self.store.value,
            "session_id": self.session_id,
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "access_count": self.access_count,
            "explicit_importance": self.explicit_importance,
            "status": self.status.value,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "supersede_reason": self.supersede_reason,
            "archived_reason": self.archived_reason,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "token_cost": self.token_cost,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryRecord":
        rec = cls(
            content=d["content"],
            store=MemoryType(d["store"]),
            session_id=d["session_id"],
            key=d["key"],
            id=d["id"],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            last_accessed_at=datetime.fromisoformat(d["last_accessed_at"]),
            access_count=d.get("access_count", 0),
            explicit_importance=d.get("explicit_importance", 0.5),
            status=MemoryStatus(d.get("status", "active")),
            supersedes=d.get("supersedes"),
            superseded_by=d.get("superseded_by"),
            supersede_reason=d.get("supersede_reason"),
            archived_reason=d.get("archived_reason"),
            archived_at=datetime.fromisoformat(d["archived_at"]) if d.get("archived_at") else None,
            embedding=d.get("embedding"),
            metadata=d.get("metadata", {}),
        )
        return rec
