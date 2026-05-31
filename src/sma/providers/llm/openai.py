"""OpenAI LLM provider. Wraps the official openai SDK with retries and usage tracking."""

from __future__ import annotations

from typing import Any

from loguru import logger
from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.llm.base import LLMResponse
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        if not api_key:
            raise ValueError("OpenAI API key required")
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APIError)),
        reraise=True,
    )
    def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self._client.chat.completions.create(**kwargs)

        text = resp.choices[0].message.content or ""
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0

        cost = pricing.cost_for_tokens(self.name, model, tokens_in, tokens_out)
        record(
            UsageEvent(
                provider=self.name,
                model=model,
                operation="complete",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
            )
        )
        logger.debug(f"OpenAI {model}: in={tokens_in} out={tokens_out} cost=${cost:.6f}")

        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
