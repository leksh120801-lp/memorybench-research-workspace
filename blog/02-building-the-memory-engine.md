# Building the memory engine

In the last post I talked about *why* memory should behave like careful
human memory instead of a tape recorder. This post is about how that
actually turns into code — four stores, and four behaviors, all living in
`backend/memory/`.

## Four stores, one shape

Every memory in the system — no matter which store it belongs to — is the
same kind of record: some text content, a timestamp, an access count, an
importance score, and a `key` that identifies *what it's about* (so a later
statement on the same topic can find it). What differs between stores is
policy, not structure:

- **Episodic** — what happened in a session. Medium importance, medium decay.
- **Semantic** — facts, e.g. "paper X reports metric Y." Long-lived; these
  are the ones most worth protecting from going stale.
- **Preference** — what the user wants, e.g. tone, format, editor of choice.
  High importance by default, since preferences quietly shape every answer.
- **Working** — a scratchpad for the current session. Decays in hours, and
  gets explicitly cleared when the session ends rather than waiting around.

## Write selectively

Not every message is worth remembering. If you ask "what's the weather
like," there's nothing to store. So writing isn't automatic — a small
extraction step (a Qwen `qwen-plus` call) looks at a turn and decides
whether anything in it is worth persisting, and if so, under what key:

```python
# backend/memory/extractor.py (simplified)
candidates = extractor.extract(session_id, user_text, assistant_text)
# candidates might be [] — most turns write nothing at all
for c in candidates:
    manager.write_direct(session_id, c.store, c.key, c.content, c.importance)
```

## Resolve contradictions, don't pile up

This is the part that actually matters. When a new memory arrives with the
same `key` as an existing one but different content — the user changed
their mind, or a fact got corrected — the old record doesn't just sit there
next to the new one. It gets marked `superseded`, with a plain-English
reason, and the new record remembers what it replaced:

```python
# a preference changes between sessions
mgr.write_direct(s, PREFERENCE, "preference:language", "User prefers Python.")
mgr.write_direct(s, PREFERENCE, "preference:language", "User prefers Rust now.")

# the old record is still there — just marked, not deleted:
# status = "superseded"
# supersede_reason = "Superseded by new information: 'User prefers Python.' -> 'User prefers Rust now.'"
```

That's the whole trick: superseded records are excluded when the system
decides what's currently *active*, so retrieval can never accidentally
surface the old answer instead of the new one — not because it got lucky,
but because the stale record was never in the pool being searched.

## Decay: archive, never delete

Memories that haven't been touched in a while, aren't very important, and
haven't been accessed much should quietly fade — but "fade" means *archived
with a logged reason*, not gone. Every record's score comes from three
things: how recently it was touched, how often it's been accessed, and how
important it was marked:

```python
score = 0.5 * recency_score + 0.2 * access_score + 0.3 * importance
# recency_score halves every "half_life" days — 6 hours for working memory,
# 90 days for semantic facts. Below a threshold, the record gets archived:
if score < 0.2:
    record.status = "archived"
    record.archived_reason = f"decay score {score:.3f} below threshold ..."
```

The Memory Inspector's "Forgotten" panel is just a filtered view over
records with `status == "archived"` — and because every one of them carries
a reason, "why did it forget that" always has an answer.

## Retrieve under budget, not top-k

The last piece is retrieval: given a question and a hard token budget (you
can't paste unlimited context into a model call), which memories do you
actually include? The obvious approach is "grab the N most relevant" — but
that's not actually optimal. Picture a budget that fits either one very
relevant memory, *or* two slightly-less-relevant ones that together add up
to more total relevance. Top-k picks the one expensive item and leaves
budget on the table. We solve it as a knapsack instead — pick the subset of
memories that maximizes total relevance without exceeding the budget:

```python
selected = knapsack_select(candidates, budget_tokens=200)
# maximizes sum(relevance) subject to sum(token_cost) <= budget —
# not just "top k by relevance"
```

There's a unit test (`test_knapsack_beats_naive_topk`) that constructs
exactly that scenario and checks the knapsack picks the two cheaper items
over the one expensive one, because that's provably the better choice under
the budget.

Put together, that's the whole engine: selective writes, contradictions
resolved instead of accumulated, decay that explains itself, and retrieval
that respects a budget on purpose. The next post covers how we actually
measured whether any of this is worth doing — MemoryBench, and what "beats
the baselines" really means.
