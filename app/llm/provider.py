"""LLM provider abstraction and the validation-aware retry helper.

The `LLMProvider` Protocol is intentionally duck-typed: concrete
implementations don't inherit from it. This lets us swap real, mock, and
recording providers transparently and keep test code trivial.

`call_with_retry` is the core senior move: instead of naively retrying on
validation failure, we feed the previous attempt's error back to the model
so it has a concrete signal to correct. Two-attempt budget by default.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Structural type for any LLM provider used by the graph nodes."""

    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call the underlying LLM and return a validated Pydantic instance.

        Implementations MUST:
        * raise `pydantic.ValidationError` if the model output cannot be
          coerced into `response_model` — this is what triggers retry
        * raise provider-specific exceptions for transport/auth failures
          (those bubble past `call_with_retry` and trigger node fallback)
        """
        ...


async def call_with_retry(
    provider: LLMProvider,
    system: str,
    user: str,
    response_model: type[T],
    max_retries: int = 2,
    temperature: float = 0.0,
) -> tuple[T, int]:
    """Call `provider.complete_structured` with validation-feedback retry.

    Returns
    -------
    (parsed_output, retry_count)
        `retry_count` is 0 for first-try success, 1 if one retry was needed, etc.

    Raises
    ------
    pydantic.ValidationError
        If every attempt (including the initial call) produces invalid output.
        The caller (a graph node) is expected to catch this and apply a
        safe fallback.
    """
    last_error: ValidationError | None = None
    augmented_user = user

    for attempt in range(max_retries + 1):
        try:
            parsed = await provider.complete_structured(
                system=system,
                user=augmented_user,
                response_model=response_model,
                temperature=temperature,
            )
            return parsed, attempt
        except ValidationError as e:
            last_error = e
            # Feed the validation error back to the model so it can self-correct.
            # Truncate to keep token usage bounded on pathological errors.
            augmented_user = (
                f"{user}\n\n"
                f"PREVIOUS ATTEMPT FAILED VALIDATION: {str(e)[:500]}\n"
                f"Correct the issues and respond again with valid structured output."
            )

    # Loop exhausted — last_error is guaranteed non-None here (only path to
    # this line is via the except branch on every iteration).
    assert last_error is not None
    raise last_error
