"""OpenAI structured-output provider.

Uses `client.chat.completions.parse()` (the GA path in openai-python 1.40+,
which the spec referred to as `client.beta.chat.completions.parse()` — the
beta alias still works but is deprecated). The SDK derives the JSON schema
from the Pydantic model, sends it via `response_format`, and returns the
parsed instance directly.

If the model refuses or the parse fails, we surface that as a
`pydantic.ValidationError` so the retry-with-feedback loop triggers
deterministically.
"""

from __future__ import annotations

from typing import TypeVar

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.config import Settings

T = TypeVar("T", bound=BaseModel)


class OpenAIProviderError(RuntimeError):
    """Raised for transport/auth/refusal failures (NOT for validation errors)."""


class OpenAIProvider:
    """AsyncOpenAI-backed implementation of LLMProvider."""

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise RuntimeError(
                "OpenAIProvider requires OPENAI_API_KEY. "
                "Set it in .env or switch LLM_PROVIDER to mock."
            )
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.request_timeout_seconds,
        )
        self._model = settings.openai_model

    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        try:
            response = await self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=response_model,
                temperature=temperature,
            )
        except (RateLimitError, APITimeoutError, APIError) as e:
            # Re-raise with context; the calling node decides whether to
            # fall back or propagate.
            raise OpenAIProviderError(
                f"OpenAI API call failed for {response_model.__name__}: {e}"
            ) from e

        choice = response.choices[0]
        if choice.message.refusal:
            # A refusal is a model-side decision, not a validation problem.
            # Surface as a provider error so node-level fallback engages.
            raise OpenAIProviderError(
                f"OpenAI refused to answer for {response_model.__name__}: {choice.message.refusal}"
            )

        parsed = choice.message.parsed
        if parsed is None:
            # `parse()` returned no parsed object — treat as a validation
            # failure so retry-with-feedback kicks in.
            raw = choice.message.content or ""
            try:
                return response_model.model_validate_json(raw)
            except ValidationError:
                raise
            except Exception as e:  # pragma: no cover — extremely defensive
                raise OpenAIProviderError(
                    f"OpenAI returned no parsed output and raw content could not "
                    f"be parsed as {response_model.__name__}: {e}"
                ) from e
        return parsed
