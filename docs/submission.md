# Submission notes

**Track:** Track 1 (MemoryAgent) — Global AI Hackathon with Qwen Cloud

## What this is

MemoryBench is a four-store memory layer for LLM agents — episodic,
semantic, preference, and working memory — plus the benchmark that justifies
its design decisions instead of just asserting them.

The memory layer implements four behaviors that most "agent memory" demos
skip:

- **Write selectively.** An extractor call (Qwen `qwen-plus`) decides what,
  if anything, from a turn is worth persisting. Most turns write nothing.
- **Resolve contradictions.** When new information conflicts with an
  existing memory (same key, different content — e.g. a corrected paper
  metric, a changed preference), the old record is superseded with a logged
  reason string, not silently duplicated. Superseded records are kept, not
  deleted, so the Memory Inspector can show the correction history.
- **Decay, don't delete.** Each record's score is a function of recency,
  access count, and explicit importance, with a different half-life per
  store (working memory decays in hours, semantic facts in months). Records
  below threshold are archived with a logged reason, never deleted.
- **Retrieve under budget, optimally.** Given a query and a hard token
  budget, retrieval is a 0/1 knapsack over (relevance, token cost) — not
  top-k. `backend/memory/retrieval.py` has a unit test constructing a case
  where two cheaper, slightly-less-relevant memories beat one expensive,
  highly-relevant one, because they fit the budget together.

MemoryBench (`backend/bench/`) then puts a number on why this matters: 30
synthetic multi-session traces with evolving preferences and papers that get
corrected mid-trace, scored against three baselines — no memory, full-history
stuffing, and naive top-k RAG. The headline result: our system matches the
naive baselines' 100% recall while cutting staleness from 47% to 0% and
context cost by roughly two-thirds. See the root README for the current
numbers and how to regenerate them.

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

## Deployment proof

`backend/alibaba_cloud.py` is the only file in the codebase that calls the
`oss2` SDK — PDF uploads and FAISS index backups both flow through it, with
a local-disk fallback when OSS credentials aren't present so the app stays
fully runnable offline. ECS provisioning is scripted end-to-end in
`backend/deploy/` (`setup_ecs.sh`, a systemd unit, an nginx reverse-proxy
config) and walked through step-by-step in `docs/deploy.md`.

**Honesty note:** this repo was built in an environment without a real
Alibaba Cloud account attached, so the ECS instance has not been provisioned
and no live URL is included here. The deploy path is fully scripted and
should take about 15 minutes to run end-to-end against a real account
following `docs/deploy.md`.

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
