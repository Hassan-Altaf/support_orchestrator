"""Focused tests for `call_with_retry` — the senior-signal retry mechanism.

Verifies:
* First-attempt success returns (result, 0)
* Validation failure on first call -> retry succeeds -> (result, 1)
* All-fail path raises the final ValidationError
* The user prompt is augmented with the prior error on retry, NOT just
  re-sent verbatim (this is the "feedback" in retry-with-feedback)
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.models import Classification
from app.llm.mock_provider import MockProvider
from app.llm.provider import call_with_retry


class TestCallWithRetry:
    async def test_first_try_success_returns_attempt_zero(
        self, mock_provider: MockProvider, good_classification
    ) -> None:
        mock_provider.queue(good_classification())
        result, attempts = await call_with_retry(
            mock_provider, system="s", user="u", response_model=Classification
        )
        assert attempts == 0
        assert isinstance(result, Classification)

    async def test_one_retry_returns_attempt_one(
        self,
        mock_provider: MockProvider,
        good_classification,
        validation_error_instance,
    ) -> None:
        mock_provider.queue(validation_error_instance, good_classification())
        result, attempts = await call_with_retry(
            mock_provider, system="s", user="u", response_model=Classification, max_retries=2
        )
        assert attempts == 1
        assert isinstance(result, Classification)

    async def test_exhausted_retries_raise_validation_error(
        self, mock_provider: MockProvider, validation_error_instance
    ) -> None:
        for _ in range(3):
            mock_provider.queue(validation_error_instance)
        with pytest.raises(ValidationError):
            await call_with_retry(
                mock_provider, system="s", user="u", response_model=Classification, max_retries=2
            )

    async def test_user_prompt_is_augmented_with_prior_error(
        self,
        good_classification,
        validation_error_instance,
    ) -> None:
        """Spy provider records each user prompt to confirm the retry feeds the error back."""

        seen_users: list[str] = []

        class SpyProvider:
            async def complete_structured(
                self,
                system: str,
                user: str,
                response_model: type[BaseModel],
                temperature: float = 0.0,
            ):
                seen_users.append(user)
                if len(seen_users) == 1:
                    raise validation_error_instance
                return good_classification()

        result, attempts = await call_with_retry(
            SpyProvider(),  # type: ignore[arg-type]
            system="s",
            user="ORIGINAL_USER_PROMPT",
            response_model=Classification,
        )
        assert attempts == 1
        assert isinstance(result, Classification)
        # First call: untouched original
        assert seen_users[0] == "ORIGINAL_USER_PROMPT"
        # Second call: augmented with prior validation error
        assert "PREVIOUS ATTEMPT FAILED VALIDATION" in seen_users[1]
        assert seen_users[1].startswith("ORIGINAL_USER_PROMPT")
