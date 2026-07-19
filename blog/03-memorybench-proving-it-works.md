# MemoryBench: proving it works

It's easy to build a memory system and just *say* it's better than the
obvious alternatives. It's much harder — and much more convincing — to
build the obvious alternatives too, run them all through the same test, and
let the numbers do the talking. That's what MemoryBench is: not a demo, a
benchmark.

## What a benchmark like this actually is

At its simplest, a benchmark is three things: a set of test cases with known
correct answers, a handful of competing systems to run through those test
cases, and a scoring rule that's the same for everyone. MemoryBench's test
cases are 30 synthetic "users," each with a few sessions of conversation.
Some sessions state a preference ("I prefer concise answers"), and some
introduce a fact about a paper ("this paper reports a BLEU score of 27.3").
Crucially, some of those preferences and facts get *changed* in a later
session — a preference update, or a correction to a paper's reported
number. After each relevant session, we ask a "probe" question — "what's the
user's preferred response length," "what BLEU score does this paper
report" — and we already know, by construction, what the correct answer is
*at that point in the story*.

## Three baselines, on purpose

A benchmark is only convincing if the things it's compared against are
things people would actually reach for:

- **No memory** — nothing persists between sessions at all. This is the
  floor: it can't possibly answer a question about a prior session.
- **Full-history stuffing** — every single thing ever said gets pasted back
  into context, unfiltered. This is the "just give it everything" approach.
- **Naive top-k RAG** — similarity search over all raw messages, picking the
  most relevant few, with no awareness that a fact might have been
  corrected since. This is what a lot of "add memory" tutorials actually
  build.

Our system runs the exact same production code covered in the last post —
the real `MemoryManager`, not a simplified stand-in — through the same
scenarios.

## The metrics

Two numbers matter most:

- **Recall@budget** — does the system's retrieved context contain the
  *current, correct* answer to the probe?
- **Staleness rate** — does it contain an *outdated* answer instead (a fact
  that was later corrected, a preference that was later changed)?

Recall tells you whether a system can find the right thing. Staleness tells
you whether it can tell the right thing from the wrong thing — and that
second question is exactly the one full-history stuffing and naive RAG
structurally can't answer well, because neither of them ever marks anything
as "this got replaced." We also track context tokens per turn and an
illustrative cost estimate, since "technically correct but three times more
expensive" is a real cost worth surfacing.

## The result

Here's the actual output from a real run of `python -m backend.bench.run
--traces 30 --seed 42` in this project (see the root README for the always-
current numbers and the chart):

| Metric | No Memory | Full-History | Naive Top-K RAG | Our system |
|---|---|---|---|---|
| Recall@budget | 0% | 100% | 100% | **100%** |
| Staleness rate | 0% | 47.1% | 47.1% | **0%** |
| Tokens/turn | 0 | 149 | 90 | **50** |

Read that staleness row carefully: full-history and naive top-k both get
the right answer into context *almost half the time alongside a wrong one*
— because they have no mechanism for ever retiring a fact once it's been
corrected. Our system matches their recall exactly, at a third of the
token cost, with staleness at zero — not "usually avoided," actually zero,
because superseded records are structurally excluded from what gets
searched in the first place. That's not a fluke of this particular run,
either — it's just what contradiction resolution guarantees by
construction.

## A benchmark can also be wrong

Worth admitting: an earlier version of this benchmark had a bug in *itself*,
not in the memory system. A probe's "correct answer" was sometimes computed
without accounting for the fact that a correction might land in the very
session the probe was checked against — so the benchmark's own ground truth
was occasionally stale, and it made our system look artificially worse than
the baselines that just kept every version of a fact around forever, since
they'd happen to still contain the (by-then-wrong) expected text. Finding
and fixing that was a good reminder that a benchmark is code too, and code
you didn't test carefully enough can lie to you just as easily as a demo
can.

Next up: what it actually takes to run this for real, on Alibaba Cloud's
free tier.
