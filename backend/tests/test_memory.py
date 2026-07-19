"""Unit tests for the memory layer. All DashScope/OSS calls are mocked —
extractor.llm_fn and embedding_fn are always injected with fakes, never the
real dashscope-backed defaults."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.memory import (
    ContradictionResolver,
    EmbeddingFn,
    EpisodicStore,
    MemoryExtractor,
    MemoryManager,
    MemoryStatus,
    MemoryType,
    PreferenceStore,
    RetrievalCandidate,
    SemanticStore,
    WorkingStore,
    apply_decay,
    compute_decay_score,
    deterministic_fake_embedding,
    knapsack_select,
)
from backend.memory.models import MemoryRecord


def now():
    return datetime(2026, 7, 19, tzinfo=timezone.utc)


def fake_embedding_fn():
    return EmbeddingFn(fn=deterministic_fake_embedding)


def make_manager(llm_responses=None):
    """llm_responses: list consumed in order by successive extractor calls."""
    responses = list(llm_responses or [])

    def llm_fn(user_text, context):
        return responses.pop(0) if responses else []

    return MemoryManager(
        extractor=MemoryExtractor(llm_fn=llm_fn),
        embedding_fn=fake_embedding_fn(),
    )


# --------------------------------------------------------------------- WRITE


def test_not_every_turn_writes():
    mgr = make_manager(llm_responses=[[]])
    written = mgr.process_turn("s1", "how's the weather", now=now())
    assert written == []
    assert mgr.all() == []


def test_extractor_writes_returned_candidates():
    mgr = make_manager(
        llm_responses=[
            [{"store": "preference", "key": "preference:editor", "content": "User prefers Vim.", "importance": 0.8}]
        ]
    )
    written = mgr.process_turn("s1", "I prefer Vim over VSCode", now=now())
    assert len(written) == 1
    assert written[0].store == MemoryType.PREFERENCE
    assert written[0].explicit_importance == 0.8


def test_duplicate_write_bumps_access_not_new_record():
    mgr = make_manager()
    mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:x", "Model X gets 90% accuracy.", importance=0.5, now=now())
    mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:x", "Model X gets 90% accuracy.", importance=0.9, now=now())
    active = mgr.active(store=MemoryType.SEMANTIC)
    assert len(active) == 1
    assert active[0].access_count == 1
    assert active[0].explicit_importance == 0.9  # bumped to the higher importance


# ------------------------------------------------------------ CONTRADICTION


def test_contradiction_supersedes_not_appends():
    mgr = make_manager()
    old = mgr.write_direct("s1", MemoryType.PREFERENCE, "preference:language", "User prefers Python.", now=now())
    new = mgr.write_direct(
        "s1", MemoryType.PREFERENCE, "preference:language", "User prefers Rust now.", now=now() + timedelta(days=1)
    )

    all_records = mgr.all()
    assert len(all_records) == 2  # old kept, not deleted
    assert old.status == MemoryStatus.SUPERSEDED
    assert old.superseded_by == new.id
    assert old.supersede_reason is not None and "Rust" in old.supersede_reason
    assert new.supersedes == old.id
    assert mgr.active(store=MemoryType.PREFERENCE) == [new]


def test_contradiction_uses_custom_reason_fn():
    calls = []

    def reason_fn(old_content, new_content):
        calls.append((old_content, new_content))
        return "custom reason"

    mgr = MemoryManager(
        extractor=MemoryExtractor(llm_fn=lambda *_: []),
        embedding_fn=fake_embedding_fn(),
        contradiction_resolver=ContradictionResolver(reason_fn=reason_fn),
    )
    mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:y", "Result is 10%.", now=now())
    new = mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:y", "Result is 20%.", now=now())
    assert calls == [("Result is 10%.", "Result is 20%.")]
    old = [r for r in mgr.all() if r.id != new.id][0]
    assert old.supersede_reason == "custom reason"


def test_different_keys_do_not_conflict():
    mgr = make_manager()
    mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:a", "A is true.", now=now())
    mgr.write_direct("s1", MemoryType.SEMANTIC, "fact:b", "B is true.", now=now())
    assert len(mgr.active(store=MemoryType.SEMANTIC)) == 2


# -------------------------------------------------------------------- DECAY


def test_decay_archives_below_threshold_but_keeps_the_record():
    old_record = MemoryRecord(
        content="stale fact",
        store=MemoryType.EPISODIC,
        session_id="s1",
        key="episodic:x",
        explicit_importance=0.1,
        access_count=0,
    )
    old_record.last_accessed_at = now() - timedelta(days=60)  # far past 14d half-life, low importance
    records = [old_record]

    archived = apply_decay(records, now=now(), threshold=0.2)

    assert len(archived) == 1
    assert old_record.status == MemoryStatus.ARCHIVED
    assert old_record.archived_reason is not None
    assert "below threshold" in old_record.archived_reason
    assert old_record in records  # never deleted


def test_decay_keeps_fresh_or_important_records_active():
    fresh = MemoryRecord(content="fresh", store=MemoryType.EPISODIC, session_id="s1", key="episodic:fresh")
    fresh.last_accessed_at = now()
    important = MemoryRecord(
        content="important old",
        store=MemoryType.SEMANTIC,
        session_id="s1",
        key="semantic:important",
        explicit_importance=1.0,
        access_count=20,
    )
    important.last_accessed_at = now() - timedelta(days=200)

    archived = apply_decay([fresh, important], now=now(), threshold=0.2)

    assert archived == []
    assert fresh.status == MemoryStatus.ACTIVE
    assert important.status == MemoryStatus.ACTIVE


def test_decay_score_is_function_of_recency_access_importance():
    base = dict(store=MemoryType.SEMANTIC, session_id="s1", key="k")
    r1 = MemoryRecord(content="a", explicit_importance=0.5, access_count=0, **base)
    r1.last_accessed_at = now()
    r2 = MemoryRecord(content="b", explicit_importance=0.5, access_count=0, **base)
    r2.last_accessed_at = now() - timedelta(days=180)  # two half-lives for semantic (90d)

    s1 = compute_decay_score(r1, now=now())
    s2 = compute_decay_score(r2, now=now())
    assert s1 > s2  # more recent -> higher score


def test_working_memory_half_life_is_short():
    working = MemoryRecord(content="scratch", store=MemoryType.WORKING, session_id="s1", key="working:x", explicit_importance=0.3)
    working.last_accessed_at = now() - timedelta(hours=12)
    semantic = MemoryRecord(content="fact", store=MemoryType.SEMANTIC, session_id="s1", key="semantic:x", explicit_importance=0.3)
    semantic.last_accessed_at = now() - timedelta(hours=12)

    assert compute_decay_score(working, now=now()) < compute_decay_score(semantic, now=now())


# ----------------------------------------------------------------- RETRIEVE


def test_knapsack_beats_naive_topk():
    # One expensive, highly-relevant item vs two cheap, slightly-less-relevant
    # items that fit together. Top-1-by-relevance picks `big`; the optimal
    # budgeted selection picks `small_a` + `small_b` for higher total value.
    big = RetrievalCandidate(id="big", token_cost=100, relevance=1.0)
    small_a = RetrievalCandidate(id="a", token_cost=50, relevance=0.6)
    small_b = RetrievalCandidate(id="b", token_cost=50, relevance=0.6)

    selected = knapsack_select([big, small_a, small_b], budget_tokens=100)

    ids = {c.id for c in selected}
    assert ids == {"a", "b"}
    total_relevance = sum(c.relevance for c in selected)
    assert total_relevance == pytest.approx(1.2)
    assert total_relevance > big.relevance


def test_knapsack_respects_hard_budget():
    candidates = [RetrievalCandidate(id=str(i), token_cost=30, relevance=1.0 / (i + 1)) for i in range(10)]
    selected = knapsack_select(candidates, budget_tokens=100)
    assert sum(c.token_cost for c in selected) <= 100


def test_knapsack_empty_budget_selects_nothing():
    candidates = [RetrievalCandidate(id="a", token_cost=10, relevance=0.9)]
    assert knapsack_select(candidates, budget_tokens=0) == []


def test_manager_retrieve_respects_budget_and_bumps_access():
    mgr = make_manager()
    for i in range(5):
        mgr.write_direct("s1", MemoryType.SEMANTIC, f"fact:{i}", f"Fact number {i} about transformers.", now=now())

    results = mgr.retrieve("transformers", budget_tokens=20, session_id="s1", now=now())
    assert sum(r.token_cost for r in results) <= 20
    for r in results:
        assert r.access_count == 1


def test_retrieve_excludes_other_sessions_working_memory():
    mgr = make_manager()
    mgr.write_direct("s1", MemoryType.WORKING, "working:note", "scratch note for s1", now=now())
    mgr.write_direct("s2", MemoryType.WORKING, "working:note", "scratch note for s2", now=now())

    results = mgr.retrieve("scratch note", budget_tokens=1000, session_id="s1", now=now())
    assert all(r.session_id == "s1" for r in results if r.store == MemoryType.WORKING)


# --------------------------------------------------------------- FOUR STORES


def test_four_stores_are_independent_views():
    mgr = make_manager()
    episodic, semantic, preference, working = (
        EpisodicStore(mgr),
        SemanticStore(mgr),
        PreferenceStore(mgr),
        WorkingStore(mgr),
    )

    episodic.write("s1", "episodic:session1", "User uploaded paper A.", now=now())
    semantic.write("s1", "fact:paperA:result", "Paper A reports 92% F1.", now=now())
    preference.write("s1", "preference:tone", "User likes concise answers.", now=now())
    working.write("s1", "working:scratch", "Currently comparing paper A vs B.", now=now())

    assert len(episodic.active()) == 1
    assert len(semantic.active()) == 1
    assert len(preference.active()) == 1
    assert len(working.active()) == 1

    cleared = working.clear("s1")
    assert len(cleared) == 1
    assert working.active() == []
    assert working.forgotten()[0].archived_reason == "session ended"
    # other stores untouched by clearing working memory
    assert len(episodic.active()) == 1


def test_forgotten_records_carry_a_reason():
    mgr = make_manager()
    r = mgr.write_direct("s1", MemoryType.EPISODIC, "episodic:x", "old event", importance=0.0, now=now() - timedelta(days=100))
    apply_decay(mgr.records, now=now(), threshold=0.2)
    forgotten = mgr.forgotten(store=MemoryType.EPISODIC)
    assert forgotten == [r]
    assert forgotten[0].archived_reason
