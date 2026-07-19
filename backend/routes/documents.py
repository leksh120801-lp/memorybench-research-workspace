from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

import os

from ..documents.faiss_index import SessionVectorIndex
from ..documents.ingest import ingest_pdf
from ..schemas import DocumentOut
from ..sessions import SessionStore
from ..state import DATA_DIR, get_oss_client, get_session_store, get_vector_index, get_embedding_fn

router = APIRouter(prefix="/sessions", tags=["documents"])


@router.post("/{session_id}/documents", response_model=DocumentOut)
async def upload_document(
    session_id: str,
    file: UploadFile,
    store: SessionStore = Depends(get_session_store),
    vector_index: SessionVectorIndex = Depends(get_vector_index),
    embedding_fn=Depends(get_embedding_fn),
    oss=Depends(get_oss_client),
):
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only PDF uploads are supported")

    file_bytes = await file.read()
    result = ingest_pdf(
        session_id=session_id,
        filename=file.filename,
        file_bytes=file_bytes,
        embedding_fn=embedding_fn,
        vector_index=vector_index,
        oss_client=oss,
        local_upload_dir=os.path.join(DATA_DIR, "uploads"),
    )
    store.add_document(session_id, result.document_id)
    return DocumentOut(
        document_id=result.document_id,
        filename=result.filename,
        num_pages=result.num_pages,
        num_chunks=result.num_chunks,
        storage_uri=result.storage_uri,
    )
