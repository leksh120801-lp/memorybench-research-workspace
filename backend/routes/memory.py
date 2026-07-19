from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..memory.decay import compute_decay_score
from ..memory.manager import MemoryManager
from ..memory.models import MemoryRecord, MemoryType
from ..schemas import MemoryInspectorOut, MemoryRecordOut
from ..state import get_memory_manager

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_out(r: MemoryRecord, with_decay: bool = False) -> MemoryRecordOut:
    return MemoryRecordOut(
        id=r.id,
        content=r.content,
        store=r.store.value,
        session_id=r.session_id,
        key=r.key,
        status=r.status.value,
        created_at=r.created_at.isoformat(),
        last_accessed_at=r.last_accessed_at.isoformat(),
        access_count=r.access_count,
        explicit_importance=r.explicit_importance,
        decay_score=compute_decay_score(r) if with_decay else None,
        supersede_reason=r.supersede_reason,
        archived_reason=r.archived_reason,
        token_cost=r.token_cost,
    )


@router.get("", response_model=MemoryInspectorOut)
def inspect_memory(
    session_id: Optional[str] = None,
    store: Optional[str] = None,
    manager: MemoryManager = Depends(get_memory_manager),
):
    store_type = MemoryType(store) if store else None
    active = manager.active(store=store_type, session_id=session_id)
    superseded = manager.superseded(store=store_type)
    forgotten = manager.forgotten(store=store_type)
    if session_id:
        superseded = [r for r in superseded if r.session_id == session_id]
        forgotten = [r for r in forgotten if r.session_id == session_id]
    return MemoryInspectorOut(
        active=[_to_out(r, with_decay=True) for r in active],
        superseded=[_to_out(r) for r in superseded],
        forgotten=[_to_out(r) for r in forgotten],
    )


@router.post("/decay")
def run_decay(manager: MemoryManager = Depends(get_memory_manager)):
    archived = manager.run_decay()
    return {"archived_count": len(archived), "archived_ids": [r.id for r, _, _ in archived]}
