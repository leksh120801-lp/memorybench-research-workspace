from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from .models import MemoryType

_EXTRACTION_PROMPT = """You extract durable memories from a single conversation turn for a \
personal research-assistant agent. Not every turn is worth remembering — most turns \
(small talk, clarifying questions, acknowledgements) produce nothing.

Return a JSON array (possibly empty) of objects, each with:
  - "store": one of "episodic", "semantic", "preference", "working"
  - "key": a short stable identifier for what this memory is *about*, so that a later
    contradicting statement on the same topic can be matched and superseded
    (e.g. "preference:editor", "fact:transformer_paper:result", "episodic:session_summary")
  - "content": one self-contained sentence stating the memory
  - "importance": float 0-1, how important this is to remember

Only extract things that are genuinely worth persisting: stated facts, preferences,
decisions, or a summary of what happened. Return [] if nothing qualifies.

User message: {user_text}
Assistant reply: {assistant_text}
"""


@dataclass
class ExtractionCandidate:
    store: MemoryType
    key: str
    content: str
    importance: float = 0.5


class MemoryExtractor:
    """Decides what (if anything) from a turn should be persisted. `llm_fn` is
    injected so tests and the benchmark harness never call DashScope — pass a
    fake that returns a list[dict] or a JSON string directly."""

    def __init__(self, llm_fn: Optional[Callable[[str, dict], object]] = None, model: str = "qwen-plus"):
        self.llm_fn = llm_fn or self._call_dashscope
        self.model = model

    def extract(self, session_id: str, user_text: str, assistant_text: str = "") -> list[ExtractionCandidate]:
        raw = self.llm_fn(user_text, {"session_id": session_id, "assistant_text": assistant_text})
        return self._parse(raw)

    def _parse(self, raw) -> list[ExtractionCandidate]:
        if raw is None:
            return []
        items = raw
        if isinstance(raw, str):
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                return []
        if not isinstance(items, list):
            return []
        candidates = []
        for item in items:
            try:
                candidates.append(
                    ExtractionCandidate(
                        store=MemoryType(item["store"]),
                        key=item["key"],
                        content=item["content"],
                        importance=float(item.get("importance", 0.5)),
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        return candidates

    def _call_dashscope(self, user_text: str, context: dict):
        from ..dashscope_config import configure_dashscope

        dashscope = configure_dashscope()
        prompt = _EXTRACTION_PROMPT.format(user_text=user_text, assistant_text=context.get("assistant_text", ""))
        resp = dashscope.Generation.call(model=self.model, prompt=prompt, result_format="message")
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope extraction call failed: {resp.code} {resp.message}")
        return resp.output.choices[0].message.content
