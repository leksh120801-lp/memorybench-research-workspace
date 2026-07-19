"""API-level tests using FastAPI's TestClient with dependency_overrides for
fresh, isolated storage per test — never touches the real backend/data
directory. No DashScope/OSS calls: QwenClient/OSSClient are left
unconfigured, so chat uses the extractive stub and uploads fall back to
local disk under the test's own tmp_path."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.documents.faiss_index import SessionVectorIndex
from backend.memory.extractor import MemoryExtractor
from backend.memory.manager import MemoryManager
from backend.sessions import SessionStore
from backend.state import (
    get_embedding_fn,
    get_memory_manager,
    get_oss_client,
    get_qwen_client,
    get_session_store,
    get_vector_index,
)
from backend.bench.lexical_embed import hashing_bow_embedding
from backend.alibaba_cloud import OSSClient
from backend.llm import QwenClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Hermetic regardless of what's in the developer's ambient .env (backend.state
    # calls load_dotenv() on import) — tests must never pick up real credentials.
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("OSS_ACCESS_KEY_SECRET", raising=False)

    test_manager = MemoryManager(
        extractor=MemoryExtractor(llm_fn=lambda *_: []),
        embedding_fn=hashing_bow_embedding,
        storage_path=str(tmp_path / "memory_store.json"),
    )
    test_sessions = SessionStore(storage_path=str(tmp_path / "sessions.json"))
    test_vectors = SessionVectorIndex(storage_dir=str(tmp_path / "faiss"))
    test_qwen = QwenClient(api_key=None)
    test_oss = OSSClient(access_key_id=None, access_key_secret=None)

    app.dependency_overrides[get_memory_manager] = lambda: test_manager
    app.dependency_overrides[get_session_store] = lambda: test_sessions
    app.dependency_overrides[get_vector_index] = lambda: test_vectors
    app.dependency_overrides[get_embedding_fn] = lambda: hashing_bow_embedding
    app.dependency_overrides[get_qwen_client] = lambda: test_qwen
    app.dependency_overrides[get_oss_client] = lambda: test_oss

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _tiny_pdf_bytes() -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure()
    fig.text(0.1, 0.5, "The paper Attention Is All You Need reports a BLEU score of 28.4 on WMT14 En-De.")
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_session_create_and_resume(client):
    r = client.post("/sessions", json={"title": "t1"})
    assert r.status_code == 200
    session_id = r.json()["id"]

    r2 = client.get(f"/sessions/{session_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == session_id

    r3 = client.get("/sessions/does-not-exist")
    assert r3.status_code == 404


def test_pdf_upload_and_cited_chat(client):
    session_id = client.post("/sessions", json={}).json()["id"]

    pdf_bytes = _tiny_pdf_bytes()
    r = client.post(
        f"/sessions/{session_id}/documents",
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["num_chunks"] >= 1

    r2 = client.post(f"/sessions/{session_id}/chat", json={"message": "What BLEU score is reported?"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["used_llm"] is False  # no DASHSCOPE_API_KEY in test env
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["source"] == "paper.pdf"


def test_reject_non_pdf_upload(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    r = client.post(
        f"/sessions/{session_id}/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_memory_inspector_endpoint_starts_empty(client):
    r = client.get("/memory")
    assert r.status_code == 200
    assert r.json() == {"active": [], "superseded": [], "forgotten": []}


def test_bench_run_endpoint_beats_baselines(client):
    r = client.post("/bench/run", json={"n_traces": 5, "seed": 1})
    assert r.status_code == 200
    by_name = {row["system_name"]: row for row in r.json()["results"]}
    ours = by_name["memorybench_four_store"]
    assert ours["staleness_rate"] == 0.0
    assert ours["avg_tokens_per_turn"] < by_name["full_history"]["avg_tokens_per_turn"]
