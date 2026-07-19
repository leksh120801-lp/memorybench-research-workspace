from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..chat import answer_chat
from ..documents.faiss_index import SessionVectorIndex
from ..llm import QwenClient
from ..memory.manager import MemoryManager
from ..schemas import ChatRequest, ChatResponseOut, CitationOut
from ..sessions import SessionStore
from ..state import get_memory_manager, get_qwen_client, get_session_store, get_vector_index, get_embedding_fn

router = APIRouter(prefix="/sessions", tags=["chat"])


@router.post("/{session_id}/chat", response_model=ChatResponseOut)
def chat(
    session_id: str,
    body: ChatRequest,
    store: SessionStore = Depends(get_session_store),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    vector_index: SessionVectorIndex = Depends(get_vector_index),
    embedding_fn=Depends(get_embedding_fn),
    llm_client: QwenClient = Depends(get_qwen_client),
):
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    result = answer_chat(
        session_id=session_id,
        user_message=body.message,
        memory_manager=memory_manager,
        vector_index=vector_index,
        embedding_fn=embedding_fn,
        llm_client=llm_client,
    )
    store.touch(session_id, increment_turn=True)

    return ChatResponseOut(
        answer=result.answer,
        citations=[CitationOut(**vars(c)) for c in result.citations],
        memories_written=result.memories_written,
        used_llm=result.used_llm,
    )
