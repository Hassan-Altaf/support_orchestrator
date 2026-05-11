"""Anthropic structured-output provider via forced tool use.

Anthropic doesn't have a native `response_format=Pydantic` analog, so we:
1. Convert the Pydantic model to a JSON schema via `model_json_schema()`
2. Send it as a single tool with `tool_choice={"type":"tool","name":...}`
3. Parse the returned `tool_use` block back into the Pydantic model

The Pydantic validation on the returned `input` dict is what triggers the
retry-with-feedback loop when Claude produces a deviating shape.
"""

from __future__ import annotations

from typing import TypeVar

from anthropic import APIError, APITimeoutError, AsyncAnthropic, RateLimitError
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam, ToolUseBlock
from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)

# Anthropic's max_tokens cap for structured outputs. Generous default since
# our largest expected payload (InternalSummary) is well under this.
_DEFAULT_MAX_TOKENS = 2048


class AnthropicProviderError(RuntimeError):
    """Raised for transport/auth/no-tool-use failures (NOT for validation errors)."""


class AnthropicProvider:
    """AsyncAnthropic-backed implementation of LLMProvider."""

    def __init__(self, settings: Settings) -> None:
        if settings.anthropic_api_key is None:
            raise RuntimeError(
                "AnthropicProvider requires ANTHROPIC_API_KEY. "
                "Set it in .env or switch LLM_PROVIDER to mock."
            )
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.request_timeout_seconds,
        )
        self._model = settings.anthropic_model

    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        tool_name = response_model.__name__
        tool: ToolParam = {
            "name": tool_name,
            "description": f"Return a structured {tool_name} payload.",
            "input_schema": response_model.model_json_schema(),
        }
        messages: list[MessageParam] = [{"role": "user", "content": user}]
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": tool_name}
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_DEFAULT_MAX_TOKENS,
                system=system,
                messages=messages,
                tools=[tool],
                tool_choice=tool_choice,
                temperature=temperature,
            )
        except (RateLimitError, APITimeoutError, APIError) as e:
            raise AnthropicProviderError(f"Anthropic API call failed for {tool_name}: {e}") from e

        for block in response.content:
            if isinstance(block, ToolUseBlock) and block.name == tool_name:
                # block.input is the model-emitted dict; Pydantic does the validation
                # which feeds the retry-with-feedback loop on shape mismatch.
                return response_model.model_validate(block.input)

        raise AnthropicProviderError(
            f"Anthropic response contained no tool_use block for {tool_name!r}; "
            f"stop_reason={response.stop_reason}"
        )
