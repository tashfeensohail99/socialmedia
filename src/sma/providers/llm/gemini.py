"""Gemini LLM provider — stub for v1.1.

The Nano Banana image provider already uses google-genai for image generation;
this stub will be filled in when we add Gemini text completion as an LLM option.
"""

from __future__ import annotations

from sma.providers.llm.base import LLMResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        raise NotImplementedError("Gemini text provider lands in v1.1")
