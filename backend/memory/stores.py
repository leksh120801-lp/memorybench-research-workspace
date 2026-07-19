from __future__ import annotations

from datetime import datetime
from typing import Optional

from .manager import MemoryManager
from .models import MemoryRecord, MemoryType


class _TypedStoreView:
    """Thin, independently-testable view over one MemoryType slice of a
    shared MemoryManager. Each subclass encodes that store's own policy
    (default importance, whether it's session-scoped, extra lifecycle
    methods) while sharing the manager's write/decay/retrieve machinery."""

    store_type: MemoryType
    default_importance: float = 0.5

    def __init__(self, manager: MemoryManager):
        self.manager = manager

    def write(self, session_id: str, key: str, content: str, importance: Optional[float] = None, now: Optional[datetime] = None) -> Optional[MemoryRecord]:
        return self.manager.write_direct(
            session_id=session_id,
            store=self.store_type,
            key=key,
            content=content,
            importance=self.default_importance if importance is None else importance,
            now=now,
        )

    def active(self, session_id: Optional[str] = None) -> list[MemoryRecord]:
        return self.manager.active(store=self.store_type, session_id=session_id)

    def forgotten(self) -> list[MemoryRecord]:
        return self.manager.forgotten(store=self.store_type)

    def superseded(self) -> list[MemoryRecord]:
        return self.manager.superseded(store=self.store_type)


class EpisodicStore(_TypedStoreView):
    """What happened, per session — timestamped, medium half-life (14d)."""

    store_type = MemoryType.EPISODIC
    default_importance = 0.4


class SemanticStore(_TypedStoreView):
    """Extracted facts about papers/topics — long half-life (90d), the
    memory type most worth protecting from staleness via supersession."""

    store_type = MemoryType.SEMANTIC
    default_importance = 0.6


class PreferenceStore(_TypedStoreView):
    """The user's stated & inferred preferences — long-ish half-life (60d),
    high default importance since preferences quietly shape every answer."""

    store_type = MemoryType.PREFERENCE
    default_importance = 0.7


class WorkingStore(_TypedStoreView):
    """Current-session scratchpad — short half-life (~6h) AND explicitly
    cleared at session end rather than waiting for decay."""

    store_type = MemoryType.WORKING
    default_importance = 0.3

    def clear(self, session_id: str, reason: str = "session ended") -> list[MemoryRecord]:
        return self.manager.clear_working(session_id, reason=reason)
