from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from .chunker import chunk_text
from .faiss_index import SessionVectorIndex


@dataclass
class IngestResult:
    document_id: str
    filename: str
    num_pages: int
    num_chunks: int
    storage_uri: str  # oss://... if OSS configured, else a local file:// path


def extract_pdf_text(file_bytes: bytes) -> list[tuple[int, str]]:
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]


def ingest_pdf(
    session_id: str,
    filename: str,
    file_bytes: bytes,
    embedding_fn: Callable[[str], list[float]],
    vector_index: SessionVectorIndex,
    oss_client=None,
    local_upload_dir: Optional[str] = None,
) -> IngestResult:
    """PDF upload -> OSS (or local fallback) -> chunk -> embed -> FAISS.
    `oss_client` is an alibaba_cloud.OSSClient; when it isn't configured
    (no credentials), the raw PDF is saved to `local_upload_dir` instead so
    the pipeline still runs end-to-end offline."""
    document_id = str(uuid.uuid4())

    if oss_client is not None and oss_client.is_configured():
        storage_uri = oss_client.upload_bytes(f"documents/{session_id}/{document_id}_{filename}", file_bytes)
    else:
        local_upload_dir = local_upload_dir or os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
        os.makedirs(local_upload_dir, exist_ok=True)
        local_path = os.path.join(local_upload_dir, f"{document_id}_{filename}")
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        storage_uri = f"file://{os.path.abspath(local_path)}"

    pages = extract_pdf_text(file_bytes)
    chunks = []
    for page_num, text in pages:
        for chunk in chunk_text(text):
            chunks.append({"text": chunk, "source": filename, "page": page_num, "document_id": document_id})

    if chunks:
        embeddings = [embedding_fn(c["text"]) for c in chunks]
        vector_index.add(session_id, chunks, embeddings)

    return IngestResult(
        document_id=document_id,
        filename=filename,
        num_pages=len(pages),
        num_chunks=len(chunks),
        storage_uri=storage_uri,
    )
