# Devpost submission

**Track:** Track 1 (MemoryAgent) — Global AI Hackathon with Qwen Cloud

This file is written to be pasted directly into Devpost's submission form —
each `##` heading below corresponds to one form field.

## Project name (3 options)

1. **MemoryBench**
2. MemoryBench: Four-Store Memory for LLM Agents
3. Forget Me Not — A Benchmarked Memory Layer for Qwen Agents

## Elevator pitch

_(one sentence, under 200 characters)_

> A four-store memory layer for LLM agents that resolves contradictions,
> decays gracefully, and retrieves under a token budget — proven against 3
> baselines.

(154 characters.)

## About the project

### What inspired it

Every "agent with memory" demo we'd seen picked one of two failure modes:
remember nothing across sessions, so the agent re-asks what it already knows
— or paste the entire conversation history back into every prompt and call
that "memory." The second one *looks* like it works right up until a user
corrects something. Full-history stuffing doesn't have a way to say "that
fact changed" — the old and new statements just sit next to each other in
the context, and there's no principled reason the model favors the current
one over the stale one. We wanted to build the boring, unglamorous
infrastructure that actually solves this: a memory layer with an opinion
about what to keep, what to supersede, and what to forget — and then prove
that opinion is worth having, instead of just asserting it.

### What I learned

The interesting part turned out not to be storage — it's policy. Deciding
*when* two memories conflict (same key, different content), *how fast*
different kinds of memory should decay (a scratchpad note from ten minutes
ago and a stated preference from three months ago don't have the same
half-life), and *what to keep* under a hard token budget when everything
can't fit are all judgment calls that are easy to get subtly wrong if you
don't measure them. Building MemoryBench alongside the memory layer — not
after it — caught a real bug: an early version of the benchmark's synthetic
probes could ask "what's true right now" using a ground-truth answer that a
later correction had already invalidated by the time the probe fired. That
bug made our own system look *worse* than the baselines, because it was
correctly returning the truly current answer against a stale expected value.
Fixing the probe generator (not the memory system) fixed the discrepancy —
a good reminder that when a benchmark and the thing it's testing disagree,
check the benchmark first.

### How I built it

Four stores — episodic, semantic, preference, working — share one record
schema and one `MemoryManager`, but each has its own decay half-life and a
few store-specific behaviors (working memory is explicitly cleared at
session end rather than waiting for decay). Four behaviors were the actual
spec:

**Write selectively.** A Qwen `qwen-plus` extraction call looks at each turn
and decides what — if anything — is worth persisting. Most turns write
nothing.

**Resolve contradictions, don't append.** Records share a `key` (e.g.
`preference:editor`, `fact:paper_x:bleu_score`). When a new value arrives
for an existing key with different content, the old record is marked
`superseded` with a logged reason and kept (not deleted); the new record
points back at what it replaced.

**Decay, don't delete.** Each record's score is:

$$
\text{score}(r, t) = w_r \cdot \text{recency}(r, t) + w_a \cdot \text{access}(r) + w_i \cdot \text{importance}(r)
$$

$$
\text{recency}(r, t) = 0.5^{\,\text{age\_days}(r,t)\, /\, \text{half\_life}(\text{store}(r))}
$$

with default weights $w_r{=}0.5,\ w_a{=}0.2,\ w_i{=}0.3$, `access(r)` a
log-scaled access-count term capped at 1, and per-store half-lives from ~6
hours (working memory) to 90 days (semantic facts). Records scoring below a
threshold (default 0.2) are archived — status flips, a reason string is
logged, nothing is deleted.

**Retrieve under a hard token budget, optimally.** Given a query and budget
$B$, retrieval is a 0/1 knapsack, not top-k:

$$
\max_{x \in \{0,1\}^n} \sum_{i=1}^{n} \text{relevance}_i \cdot x_i
\quad \text{subject to} \quad
\sum_{i=1}^{n} \text{token\_cost}_i \cdot x_i \le B
$$

solved with a standard DP over the budget. This matters concretely: two
cheaper, slightly-less-relevant memories can beat one expensive, highly
relevant one if they both fit the budget and it doesn't — this is asserted
directly in a unit test (`test_knapsack_beats_naive_topk`), not just implied.

**MemoryBench** then exercises the real production code (not a
reimplementation) across 30 synthetic multi-session traces with evolving
preferences and papers that get corrected mid-trace, against three
baselines: no memory, full-history stuffing, and naive top-k RAG (greedy
by relevance under the same budget, no contradiction resolution — so a
corrected fact and its stale predecessor compete purely on embedding
similarity). Metrics: **recall@budget** (does the retrieved context contain
the current correct answer, exact substring match against ground truth),
**staleness rate** (does it contain a superseded answer instead), context
tokens/turn, and an illustrative cost/latency model. See the root README for
the current numbers and exactly how to regenerate them.

### Challenges faced

- **The benchmark can lie to you.** Covered above — a ground-truth bug in
  the synthetic probe generator made the real system look worse than naive
  baselines that just hoard every version of a fact forever. Fixed by
  constraining each probe's valid time window to before the *next*
  correction to the same key lands.
- **Relevance signal quality without paid embeddings.** MemoryBench needs to
  be free and deterministic to re-run, so it can't call `text-embedding-v3`
  per probe. A naive hashed bag-of-words embedding made unrelated memories
  look deceptively similar (common words like "the paper reports" dominated
  the signal); adding stopword filtering fixed the relevance ranking without
  needing a real embedding model.
- **Staying honest about what's simulated.** Cost-per-session and
  latency-per-turn in the benchmark are a documented linear model (token
  count × published DashScope pricing/prefill-time order-of-magnitude), not
  live billing calls — see "What's real vs. illustrative" below.

## Architecture Diagram

Uploaded as [`docs/architecture.png`](architecture.png) (PDF version also at
[`docs/architecture.pdf`](architecture.pdf) — Devpost accepts pdf/png/jpg/jpeg
only, not the mermaid source, which is kept at
[`docs/architecture.mmd`](architecture.mmd) and inline in the README for
editing).

The Next.js frontend talks to the FastAPI backend over plain REST. The
backend's `MemoryManager` and document-ingest pipeline both call out to Qwen
Cloud via DashScope — `qwen-plus` decides what from a turn is worth
persisting, `qwen-max` generates cited chat answers, and
`text-embedding-v3` embeds both memories and uploaded-PDF chunks for
retrieval. Uploaded PDFs and each session's local FAISS vector index both
get backed up to an Alibaba Cloud OSS bucket through a single integration
point (`backend/alibaba_cloud.py`); the whole backend is designed to run on
a free-tier Alibaba Cloud ECS instance behind nginx. See
[`docs/architecture.md`](architecture.md) for a component-by-component
breakdown.

## Built with

`python` · `fastapi` · `uvicorn` · `pydantic` · `qwen` · `dashscope` ·
`qwen-max` · `qwen-plus` · `text-embedding-v3` · `alibaba-cloud` · `oss` ·
`oss2` · `ecs` · `faiss` · `faiss-cpu` · `nextjs` · `react` · `typescript` ·
`tailwindcss` · `pytest` · `matplotlib` · `numpy` · `pypdf2` · `nginx` ·
`systemd`

(25 tags, all directly used in `backend/requirements.txt`,
`frontend/package.json`, or `backend/deploy/`.)

## Started or existed before the submission period?

**No.** Every file in this repository was written from scratch during this
project's build session — see the git history: the first commit
(`af7391f`, "chore: scaffold repo, MIT license, project structure") was made
2026-07-19, and it starts from an empty directory (`mkdir` + `git init`),
not an imported or pre-existing codebase.

## Which AI tools did you leverage?

Two, in clearly different roles:

- **Claude (Claude Code)** was used as the coding agent for the entire
  build: reading these requirements, writing the backend/frontend source,
  writing and running the test suite, generating the benchmark and this
  documentation, and driving a real browser to smoke-test the UI. It did not
  write any part of this document's numbers by guessing — benchmark figures
  come from actually running `backend/bench/run.py`.
- **Qwen** (`qwen-max`, `qwen-plus`, `text-embedding-v3`, via Alibaba
  Cloud's DashScope) is the *runtime* the product itself calls: chat
  reasoning, memory-write extraction, and embeddings all go through Qwen,
  not through Claude or any other model, at request time. Claude never
  substitutes for Qwen in the running application — see
  `backend/dashscope_config.py` and `backend/llm.py`. The two are not
  interchangeable in this project: Claude built the tool, Qwen powers it.

---

## What's real vs. illustrative in the numbers

- **Real:** the memory algorithms (contradiction resolution, decay, knapsack
  retrieval) are the actual production code in `backend/memory/`, exercised
  directly by the benchmark — not a reimplementation for the demo.
- **Real:** recall and staleness are measured by exact substring match
  against each probe's ground-truth answer, computed per-probe from each
  system's actual retrieved context.
- **Illustrative:** cost-per-session and latency-per-turn are a documented
  linear model (base overhead + token count × published per-token
  DashScope pricing/prefill-time order-of-magnitude), not live billing calls
  or network round-trips — see `backend/bench/systems.py`. This is
  intentional: the project's cost-discipline rule is to never call paid
  infra in automated runs, and it keeps the benchmark free and deterministic
  to re-run. Token counts and the relative ordering between systems are
  real; the absolute $/latency units are a stated approximation.
- Current benchmark numbers, if you haven't run it yet in your checkout:
  **[FILL AFTER FIRST BENCH RUN — `python -m backend.bench.run --traces 30 --seed 42`]**
  (the root README has the numbers from the last run in this build session).

## Deployment proof

`backend/alibaba_cloud.py` is the only file in the codebase that calls the
`oss2` SDK — PDF uploads and FAISS index backups both flow through it, with
a local-disk fallback when OSS credentials aren't present so the app stays
fully runnable offline. ECS provisioning is scripted end-to-end in
`backend/deploy/` (`setup_ecs.sh`, a systemd unit, an nginx reverse-proxy
config) and walked through step-by-step in `docs/deploy.md`.

**Honesty note:** this repo was built in an environment without a real
Alibaba Cloud account attached, so the ECS instance has not been provisioned
by the agent, and no live URL is included here — that step is left to the
human running `docs/deploy.md` against their own account. Live URL:
**`http://<ECS_PUBLIC_IP>` [FILL AFTER MANUAL DEPLOY]**.

## Video script outline (~3 min)

1. **0:00–0:20 — The problem.** Agent memory demos either remember nothing
   across sessions, or dump the entire transcript back in and call it
   "memory." Neither survives contact with a long-running assistant: no
   memory can't track preferences or corrections; full-history stuffing gets
   expensive and confidently repeats stale facts.
2. **0:20–1:00 — The four stores, live.** Open the Memory Inspector tab.
   Upload a paper, ask about it, state a preference. Show the record
   land in the right store with a decay score and access count.
3. **1:00–1:40 — Contradiction resolution.** Correct a previously-stated fact
   (e.g. "actually the camera-ready number was X, not Y"). Show the old
   record flip to "superseded" with the logged reason, not a duplicate.
4. **1:40–2:10 — Forgotten, with reasons.** Run a decay pass. Show the
   Forgotten panel — archived records each with a logged reason, not a
   silent delete.
5. **2:10–2:50 — MemoryBench.** Switch to the MemoryBench tab, run it live,
   walk the chart: same recall as the baselines, zero staleness, a third of
   the tokens.
6. **2:50–3:00 — Close.** Stack: Qwen via DashScope for inference, Alibaba
   Cloud OSS + ECS for storage/hosting, MIT-licensed, Track 1 (MemoryAgent).
