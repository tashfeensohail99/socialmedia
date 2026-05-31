"""LLM provider protocol. All chat/completion calls flow through this interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    model: str
    raw: dict | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Implementations: openai.OpenAIProvider, anthropic.AnthropicProvider, gemini.GeminiProvider."""

    name: str  # "openai" | "anthropic" | "gemini"

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse: ...
