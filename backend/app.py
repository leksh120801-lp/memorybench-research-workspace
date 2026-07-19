from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import bench, chat, documents, memory, sessions

app = FastAPI(title="MemoryBench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(bench.router)


@app.get("/health")
def health():
    return {"status": "ok"}
