from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Simple sliding-window chunker over characters, paragraph-aware where
    possible. Good enough for citation-grade granularity without pulling in
    a tokenizer dependency."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    step = max(1, chunk_size - overlap)
    while start < n:
        end = min(start + chunk_size, n)
        # try not to cut mid-word
        if end < n:
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start += step
    return chunks
