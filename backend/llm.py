from __future__ import annotations

import os
from typing import Optional


class QwenClient:
    """Thin wrapper around the DashScope SDK for Qwen models. NOT the
    Anthropic API — per project rules, all inference goes through DashScope.
    `is_configured()` lets callers degrade gracefully (extractive stub
    answers, offline lexical embeddings) when no API key is present, so the
    app runs and is demoable without incurring cost or requiring secrets."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        reasoning_model: Optional[str] = None,
        extraction_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self.reasoning_model = reasoning_model or os.environ.get("QWEN_REASONING_MODEL", "qwen-max")
        self.extraction_model = extraction_model or os.environ.get("QWEN_EXTRACTION_MODEL", "qwen-plus")
        self.embedding_model = embedding_model or os.environ.get("QWEN_EMBEDDING_MODEL", "text-embedding-v3")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        import dashscope

        dashscope.api_key = self.api_key
        resp = dashscope.Generation.call(
            model=self.reasoning_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            result_format="message",
        )
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope chat call failed: {resp.code} {resp.message}")
        return resp.output.choices[0].message.content

    def extract(self, user_text: str, context: dict) -> str:
        import dashscope

        from .memory.extractor import _EXTRACTION_PROMPT

        dashscope.api_key = self.api_key
        prompt = _EXTRACTION_PROMPT.format(user_text=user_text, assistant_text=context.get("assistant_text", ""))
        resp = dashscope.Generation.call(model=self.extraction_model, prompt=prompt, result_format="message")
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope extraction call failed: {resp.code} {resp.message}")
        return resp.output.choices[0].message.content

    def embed(self, text: str) -> list[float]:
        import dashscope

        dashscope.api_key = self.api_key
        resp = dashscope.TextEmbedding.call(model=self.embedding_model, input=text)
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope embedding call failed: {resp.code} {resp.message}")
        return resp.output["embeddings"][0]["embedding"]
