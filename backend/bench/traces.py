from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

PREF_DIMENSIONS: dict[str, list[str]] = {
    "preference:response_length": [
        "concise, bullet-point answers",
        "long-form answers with full explanations",
        "medium-length answers with section headers",
    ],
    "preference:editor": ["Vim", "VSCode", "Emacs", "PyCharm", "Neovim"],
    "preference:citation_style": ["APA", "IEEE", "MLA", "Chicago"],
    "preference:primary_language": ["Python", "Rust", "Go", "TypeScript", "C++"],
    "preference:tone": ["formal and academic", "casual and conversational", "terse and technical"],
}

PAPERS: list[str] = [
    "Attention Is All You Need",
    "Deep Residual Learning for Image Recognition",
    "BERT: Pre-training of Deep Bidirectional Transformers",
    "GPT-3: Language Models are Few-Shot Learners",
    "Denoising Diffusion Probabilistic Models",
    "Neural Machine Translation by Jointly Learning to Align and Translate",
    "AlphaFold: Highly Accurate Protein Structure Prediction",
    "CLIP: Learning Transferable Visual Models From Natural Language",
    "LoRA: Low-Rank Adaptation of Large Language Models",
    "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
    "Switch Transformers: Scaling to Trillion Parameter Models",
    "Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
    "Sparse Attention with Routing Transformers",
    "An Image is Worth 16x16 Words: Vision Transformers at Scale",
    "Constitutional AI: Harmlessness from AI Feedback",
]

PAPER_METRICS: list[str] = ["BLEU score", "top-1 accuracy", "F1 score", "perplexity", "ROUGE-L score"]


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")[:40]


@dataclass
class FactEvent:
    session_index: int
    key: str
    content: str
    is_correction: bool = False


@dataclass
class Probe:
    after_session_index: int
    query: str
    target_key: str
    correct_content: str
    stale_content: Optional[str] = None


@dataclass
class SyntheticTrace:
    trace_id: str
    user_id: str
    num_sessions: int
    sessions: list[list[FactEvent]] = field(default_factory=list)
    probes: list[Probe] = field(default_factory=list)


def _make_preference_events(rng: random.Random, num_sessions: int) -> tuple[list[FactEvent], dict[str, list[tuple[int, str]]]]:
    """Pick 1-2 preference dimensions and let each evolve once or twice across
    sessions. Returns events plus, per key, the ordered (session, value)
    history so probes can be generated with known-correct answers."""
    dims = rng.sample(list(PREF_DIMENSIONS.keys()), k=rng.choice([1, 2]))
    events: list[FactEvent] = []
    history: dict[str, list[tuple[int, str]]] = {}
    for key in dims:
        values = rng.sample(PREF_DIMENSIONS[key], k=min(len(PREF_DIMENSIONS[key]), rng.choice([2, 3])))
        change_sessions = sorted(rng.sample(range(num_sessions), k=min(len(values), num_sessions)))
        history[key] = []
        for i, (session_idx, value) in enumerate(zip(change_sessions, values)):
            dim_label = key.split(":", 1)[1].replace("_", " ")
            if i == 0:
                content = f"The user's preferred {dim_label} is: {value}."
            else:
                content = f"The user changed their preferred {dim_label} to: {value} (updated from before)."
            events.append(FactEvent(session_index=session_idx, key=key, content=content, is_correction=(i > 0)))
            history[key].append((session_idx, content))
    return events, history


def _make_paper_events(rng: random.Random, num_sessions: int) -> tuple[list[FactEvent], dict[str, list[tuple[int, str]]]]:
    """Pick 2-3 papers; each gets a reported metric, and about half get a
    later revision (preprint -> camera-ready correction) that supersedes the
    first value."""
    papers = rng.sample(PAPERS, k=rng.choice([2, 3]))
    events: list[FactEvent] = []
    history: dict[str, list[tuple[int, str]]] = {}
    for paper in papers:
        metric = rng.choice(PAPER_METRICS)
        key = f"fact:{_slug(paper)}:{_slug(metric)}"
        v1 = round(rng.uniform(60.0, 95.0), 1)
        s1 = rng.randrange(0, max(1, num_sessions - 1))
        content1 = f"The paper '{paper}' reports a {metric} of {v1} in the preprint version."
        events.append(FactEvent(session_index=s1, key=key, content=content1))
        history[key] = [(s1, content1)]

        if rng.random() < 0.7 and s1 < num_sessions - 1:
            v2 = round(v1 + rng.uniform(-4.0, 6.0), 1)
            s2 = rng.randrange(s1 + 1, num_sessions)
            content2 = (
                f"Correction: the camera-ready version of '{paper}' actually reports a {metric} of {v2}, "
                f"not the preprint number."
            )
            events.append(FactEvent(session_index=s2, key=key, content=content2, is_correction=True))
            history[key].append((s2, content2))
    return events, history


def _make_probes(rng: random.Random, num_sessions: int, history: dict[str, list[tuple[int, str]]], query_templates: dict[str, str]) -> list[Probe]:
    probes = []
    for key, entries in history.items():
        # probe once right after the first value is established, and again
        # after each correction (if any) — this is exactly what tests whether
        # a system cites current vs. stale info. Each probe must land BEFORE
        # the *next* correction (if any) so "correct_content" stays true at
        # probe time — otherwise a system that already picked up the next
        # correction would be unfairly marked wrong, while a system that
        # hoards every version ever seen would be unfairly marked right.
        for i, (session_idx, content) in enumerate(entries):
            next_session_idx = entries[i + 1][0] if i + 1 < len(entries) else num_sessions
            window_end = min(next_session_idx - 1, num_sessions - 1)
            preferred = session_idx + 1
            probe_after = preferred if preferred <= window_end else session_idx
            stale = entries[i - 1][1] if i > 0 else None
            probes.append(
                Probe(
                    after_session_index=probe_after,
                    query=query_templates[key],
                    target_key=key,
                    correct_content=content,
                    stale_content=stale,
                )
            )
    return probes


def generate_trace(trace_id: str, seed: int, num_sessions: Optional[int] = None) -> SyntheticTrace:
    rng = random.Random(seed)
    num_sessions = num_sessions or rng.choice([3, 4, 5])

    pref_events, pref_history = _make_preference_events(rng, num_sessions)
    paper_events, paper_history = _make_paper_events(rng, num_sessions)

    query_templates: dict[str, str] = {}
    for key in pref_history:
        dim_label = key.split(":", 1)[1].replace("_", " ")
        query_templates[key] = f"What is the user's preferred {dim_label}?"
    for key in paper_history:
        # key format fact:<paper_slug>:<metric_slug> — recover a readable query from the first event's content
        first_content = paper_history[key][0][1]
        paper_name = first_content.split("'")[1]
        metric = next((m for m in PAPER_METRICS if m in first_content), "reported metric")
        query_templates[key] = f"What {metric} does '{paper_name}' report?"

    all_events = pref_events + paper_events
    sessions: list[list[FactEvent]] = [[] for _ in range(num_sessions)]
    for e in all_events:
        sessions[e.session_index].append(e)

    history = {**pref_history, **paper_history}
    probes = _make_probes(rng, num_sessions, history, query_templates)
    probes.sort(key=lambda p: p.after_session_index)

    return SyntheticTrace(
        trace_id=trace_id,
        user_id=f"user-{trace_id}",
        num_sessions=num_sessions,
        sessions=sessions,
        probes=probes,
    )


def generate_traces(n: int = 30, seed: int = 42) -> list[SyntheticTrace]:
    base_rng = random.Random(seed)
    return [generate_trace(trace_id=f"trace-{i:02d}", seed=base_rng.randrange(1_000_000)) for i in range(n)]
