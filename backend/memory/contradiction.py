from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .models import MemoryRecord, MemoryStatus, utcnow


@dataclass
class Supersession:
    old_record: MemoryRecord
    reason: str


def _truncate(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def default_reason_fn(old_content: str, new_content: str) -> str:
    return f"Superseded by new information: '{_truncate(old_content)}' -> '{_truncate(new_content)}'"


class ContradictionResolver:
    """Detects conflicting memories and supersedes them (never appends
    silently). Detection is key-based and deterministic: two ACTIVE records
    in the same store sharing a `key` (e.g. "preference:editor",
    "fact:paper_x:conclusion") with different content are a conflict.
    `reason_fn` is pluggable so a caller can swap in an LLM-generated
    explanation instead of the default template."""

    def __init__(self, reason_fn: Optional[Callable[[str, str], str]] = None):
        self.reason_fn = reason_fn or default_reason_fn

    def resolve(
        self,
        candidates: list[MemoryRecord],
        key: str,
        new_content: str,
        now=None,
    ) -> list[Supersession]:
        now = now or utcnow()
        supersessions = []
        for r in candidates:
            if r.status != MemoryStatus.ACTIVE or r.key != key:
                continue
            if r.content.strip() == new_content.strip():
                continue  # identical — not a conflict, handled as a duplicate by the caller
            reason = self.reason_fn(r.content, new_content)
            r.status = MemoryStatus.SUPERSEDED
            r.supersede_reason = reason
            r.updated_at = now
            supersessions.append(Supersession(old_record=r, reason=reason))
        return supersessions
