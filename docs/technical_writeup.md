# Technical writeup

This is the engineering-level companion to `docs/submission.md` (which is
written for Devpost's form fields). It covers system design, the exact
memory policies with their formulas, benchmark design, and what the
deployment proof actually demonstrates.

## 1. System design

### 1.1 Components

- **`backend/memory/`** — the memory layer: record schema
  (`models.py`), contradiction resolution (`contradiction.py`), decay
  (`decay.py`), budgeted retrieval (`retrieval.py`), orchestration
  (`manager.py`), and four thin per-store policy views (`stores.py`).
- **`backend/bench/`** — MemoryBench: synthetic trace generation
  (`traces.py`), the real system plus three baselines (`systems.py`),
  metrics (`metrics.py`), and reporting/chart generation (`report.py`).
- **`backend/documents/`** — PDF ingest: text extraction, chunking
  (`chunker.py`), and a per-session FAISS index with OSS backup
  (`faiss_index.py`).
- **`backend/routes/`** + **`backend/app.py`** — the FastAPI surface:
  sessions, document upload, chat, memory inspection, benchmark runs.
- **`backend/alibaba_cloud.py`** — the sole Alibaba Cloud OSS integration
  point (see §4).
- **`backend/llm.py`** / **`backend/dashscope_config.py`** — the DashScope
  (Qwen) client: chat, extraction, and embedding calls, with a
  configurable endpoint (international vs. mainland).
- **`frontend/`** — Next.js App Router UI: Chat, Memory Inspector,
  MemoryBench tabs, all talking to the backend over plain REST.

### 1.2 Design principle: offline-safe by construction

Every external dependency (DashScope, OSS) is wrapped behind an
`is_configured()` check with a free local fallback — hashed bag-of-words
embeddings instead of `text-embedding-v3`, an extractive stub instead of a
generated chat answer, local disk instead of an OSS bucket. The call sites
never branch on this themselves; the wrapper does. This is what makes the
test suite (36 tests) run with zero cost and zero network access, and it's
also just good practice: the same code path that runs in CI is the one that
runs in production, with credentials as the only difference.

## 2. Memory policies, formally

### 2.1 Record model

Every memory record has: `content`, `store` (episodic / semantic /
preference / working), `session_id`, a `key` used for contradiction
matching, `status` (active / superseded / archived), `access_count`,
`explicit_importance` $\in [0,1]$, and timestamps.

### 2.2 Write

An extraction step (`MemoryExtractor`, backed by `qwen-plus`) maps a
conversation turn to zero or more `(store, key, content, importance)`
candidates. Most turns produce none. This is a policy choice, not a
limitation: unconditionally writing every turn is exactly the
full-history-stuffing failure mode this project is designed against.

### 2.3 Contradiction resolution

Given a new candidate with key $k$ and content $c$, and the set of existing
`ACTIVE` records $R_k = \{r : r.\text{key} = k\}$:

- If $\exists r \in R_k$ with $r.\text{content} = c$: treat as a duplicate,
  bump `access_count` and `last_accessed_at`, write nothing new.
- If $\exists r \in R_k$ with $r.\text{content} \ne c$: mark every such $r$
  as `SUPERSEDED` with a generated reason string, set the new record's
  `supersedes` pointer to $r.\text{id}$, and insert the new record as
  `ACTIVE`. $r$ is never deleted.
- Otherwise: insert the new record as `ACTIVE`.

This guarantees an invariant retrieval depends on: at most one `ACTIVE`
record exists per `(store, key)` (per session, for working memory) at any
time, so retrieval can never return two conflicting answers for the same
question.

### 2.4 Decay

For record $r$ at time $t$:

$$
\text{score}(r, t) = w_r \cdot \text{recency}(r, t) + w_a \cdot \text{access}(r) + w_i \cdot \text{importance}(r)
$$

$$
\text{recency}(r, t) = 0.5^{\,\text{age\_days}(r,t)\, /\, \text{half\_life}(\text{store}(r))}, \qquad
\text{age\_days}(r,t) = \frac{t - r.\text{last\_accessed\_at}}{86400\text{s}}
$$

$$
\text{access}(r) = \min\!\left(1,\ \frac{\ln(1+\text{access\_count}(r))}{\ln(1+\text{access\_cap})}\right), \qquad \text{access\_cap} = 10
$$

Default weights $w_r = 0.5,\ w_a = 0.2,\ w_i = 0.3$. Default half-lives:
working memory 0.25 days (~6h), episodic 14 days, preference 60 days,
semantic 90 days. When $\text{score}(r,t)$ falls below a threshold (default
$0.2$), $r.\text{status} \leftarrow \text{ARCHIVED}$ and a reason string
recording the score and its components is attached. Archived records are
excluded from retrieval but never removed from storage.

### 2.5 Retrieval (budgeted knapsack)

Given a query $q$, a candidate pool of `ACTIVE` records (filtered by store
and session as requested), and a hard token budget $B$: let
$\text{relevance}_i = \cos(\text{embed}(q), \text{embed}(r_i))$ and
$\text{token\_cost}_i = \lceil \text{len}(r_i.\text{content}) / 4 \rceil$.
Retrieval solves

$$
\max_{x \in \{0,1\}^n} \sum_{i=1}^{n} \text{relevance}_i \cdot x_i
\quad \text{s.t.} \quad
\sum_{i=1}^{n} \text{token\_cost}_i \cdot x_i \le B
$$

via a standard 0/1 knapsack DP over integer token capacity (`O(n · B)`
time), not top-k by relevance. `backend/tests/test_memory.py::test_knapsack_beats_naive_topk`
verifies this is a real behavioral difference, not just an implementation
detail: it constructs a case where two cheaper, slightly-less-relevant
records have higher combined relevance than one expensive, highly-relevant
record, and asserts the knapsack picks the former.

## 3. Benchmark design

### 3.1 Synthetic traces

`generate_traces(n=30, seed=42)` produces reproducible synthetic users, each
with 3–5 sessions. Each trace mixes: 1–2 evolving preference dimensions
(each changing value once or twice across sessions) and 2–3 paper facts
(each with ~70% probability of a later "camera-ready correction" that
supersedes the original value). Every state change is paired with a probe
question, windowed so its `after_session_index` falls strictly before the
*next* correction to the same key — otherwise a probe's "correct" answer
could be invalidated by information a system had already legitimately
learned, which would penalize correct behavior (see the bug described in
blog post 3).

### 3.2 Systems under test

All four implement the same interface (`ingest_session`, `answer_probe`):
`NoMemorySystem` (nothing persists), `FullHistorySystem` (every raw event,
unbounded), `NaiveTopKSystem` (fixed top-$k$ by relevance over raw events,
no contradiction resolution, no budget awareness), and
`OurMemorySystem` — a thin wrapper around the actual production
`MemoryManager`, not a reimplementation.

### 3.3 Metrics

For each probe, `evaluate_probe` checks two independent booleans against
the system's retrieved context via exact substring match:
$\text{hit} = \exists c \in \text{context} : \text{correct\_content} \subseteq c$
and $\text{stale\_cited} = \exists c \in \text{context} : \text{stale\_content} \subseteq c$.
Aggregated across all probes: **recall@budget** ($\overline{\text{hit}}$),
**staleness rate** ($\overline{\text{stale\_cited}}$), average context
tokens/turn, and an illustrative cost/latency model (§3.4).

### 3.4 What's simulated, and why

Cost and latency are $\text{base} + \text{tokens} \times \text{rate}$ —
order-of-magnitude constants documented in `backend/bench/systems.py`, not
live DashScope calls. This is a deliberate consequence of the project's
cost-discipline rule (never call paid infrastructure in automated runs): it
keeps MemoryBench free and byte-for-byte reproducible
(`generate_traces(seed=42)` is deterministic) to re-run on demand. Recall,
staleness, and token counts are all real, measured quantities from actual
system behavior — nothing about *those* is simulated.

## 4. Deployment proof

`backend/alibaba_cloud.py` is the only file that imports the `oss2` SDK.
`OSSClient.upload_bytes` / `upload_file` are called from
`backend/documents/ingest.py` for every uploaded PDF; `backup_faiss_index`
(which itself calls `upload_file` twice) is called from
`backend/documents/faiss_index.py` after every FAISS index write. Both are
covered by mocked-`oss2` unit tests in `backend/tests/test_alibaba_cloud.py`.
`OSSClient.is_configured()` gates a local-disk fallback so the exact same
code path is exercised in CI/dev (no credentials) and production (real OSS
bucket) — see §1.2. ECS provisioning is scripted in `backend/deploy/`
(`setup_ecs.sh`, a systemd unit, an nginx reverse-proxy config); the
full walkthrough lives in `docs/deploy.md` (intentionally excluded from
this technical-submission bundle — see `scripts/make_submission_zip.sh`).
