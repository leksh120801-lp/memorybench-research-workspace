from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from .models import MemoryRecord, MemoryStatus, MemoryType, utcnow

# Each store has its own forgetting policy: working memory is ephemeral and
# decays in hours, semantic facts are meant to last, preferences sit in
# between.
DEFAULT_HALF_LIFE_DAYS: dict[MemoryType, float] = {
    MemoryType.WORKING: 0.25,  # ~6 hours
    MemoryType.EPISODIC: 14.0,
    MemoryType.PREFERENCE: 60.0,
    MemoryType.SEMANTIC: 90.0,
}

DEFAULT_THRESHOLD = 0.2
DEFAULT_WEIGHTS = {"recency": 0.5, "access": 0.2, "importance": 0.3}
ACCESS_CAP = 10


def recency_score(record: MemoryRecord, now: datetime, half_life_days: float) -> float:
    age_days = max(0.0, (now - record.last_accessed_at).total_seconds() / 86400.0)
    if half_life_days <= 0:
        return 1.0 if age_days == 0 else 0.0
    return 0.5 ** (age_days / half_life_days)


def access_score(record: MemoryRecord) -> float:
    return min(1.0, math.log1p(record.access_count) / math.log1p(ACCESS_CAP))


def compute_decay_score(
    record: MemoryRecord,
    now: Optional[datetime] = None,
    half_life_days: Optional[float] = None,
    weights: Optional[dict[str, float]] = None,
) -> float:
    now = now or utcnow()
    half_life = half_life_days if half_life_days is not None else DEFAULT_HALF_LIFE_DAYS[record.store]
    w = weights or DEFAULT_WEIGHTS
    r = recency_score(record, now, half_life)
    a = access_score(record)
    i = max(0.0, min(1.0, record.explicit_importance))
    return w["recency"] * r + w["access"] * a + w["importance"] * i


def apply_decay(
    records: list[MemoryRecord],
    now: Optional[datetime] = None,
    threshold: float = DEFAULT_THRESHOLD,
    weights: Optional[dict[str, float]] = None,
) -> list[tuple[MemoryRecord, float, str]]:
    """Archive (never delete) ACTIVE records whose decay score falls below
    threshold. Mutates records in place and returns (record, score, reason)
    for everything newly archived, so callers can log/display it."""
    now = now or utcnow()
    archived: list[tuple[MemoryRecord, float, str]] = []
    for r in records:
        if r.status != MemoryStatus.ACTIVE:
            continue
        score = compute_decay_score(r, now, weights=weights)
        if score < threshold:
            reason = (
                f"decay score {score:.3f} below threshold {threshold:.2f} "
                f"(last_accessed={r.last_accessed_at.isoformat()}, "
                f"access_count={r.access_count}, importance={r.explicit_importance:.2f})"
            )
            r.status = MemoryStatus.ARCHIVED
            r.archived_reason = reason
            r.archived_at = now
            archived.append((r, score, reason))
    return archived
