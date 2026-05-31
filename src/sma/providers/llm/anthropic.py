"""Anthropic LLM provider — stub for v1.1.

Implementing the protocol so the registry + admin panel dropdowns work,
but raising NotImplementedError until we wire it up.
"""

from __future__ import annotations

from sma.providers.llm.base import LLMResponse


class AnthropicProvider:
    name = "anthropic"

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
        raise NotImplementedError("Anthropic provider lands in v1.1")
