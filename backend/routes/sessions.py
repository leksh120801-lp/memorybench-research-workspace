from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import SessionCreateRequest, SessionOut
from ..sessions import SessionStore
from ..state import get_session_store

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_out(rec) -> SessionOut:
    d = rec.to_dict()
    return SessionOut(**d)


@router.post("", response_model=SessionOut)
def create_session(body: SessionCreateRequest, store: SessionStore = Depends(get_session_store)):
    rec = store.create(title=body.title)
    return _to_out(rec)


@router.get("", response_model=list[SessionOut])
def list_sessions(store: SessionStore = Depends(get_session_store)):
    return [_to_out(r) for r in store.list()]


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    rec = store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _to_out(rec)
