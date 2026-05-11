"""RecordingProvider — record/replay wrapper for any LLMProvider.

Modes:
* `record`  — call the wrapped provider, save each request+response under
  a hash of the request to `recordings_dir`. Successful responses only.
* `replay`  — look up the recording by request hash and return it; raise
  if not found.

This is the cheapest possible regression test for prompt drift: capture
real LLM outputs once, replay them in CI without spending API tokens.
Recorded files are intentionally human-readable JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from app.llm.provider import LLMProvider

T = TypeVar("T", bound=BaseModel)

RecordingMode = Literal["record", "replay"]


class RecordingProviderError(RuntimeError):
    """Raised when replay cannot find a matching recording."""


class RecordingProvider:
    """Wrap any LLMProvider with deterministic record/replay."""

    def __init__(
        self,
        wrapped: LLMProvider,
        recordings_dir: Path,
        mode: RecordingMode,
    ) -> None:
        self._wrapped = wrapped
        self._dir = recordings_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._mode = mode

    @staticmethod
    def _key(system: str, user: str, model_name: str, temperature: float) -> str:
        payload = json.dumps(
            {"system": system, "user": user, "model": model_name, "temperature": temperature},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        key = self._key(system, user, response_model.__name__, temperature)
        path = self._dir / f"{key}.json"

        if self._mode == "replay":
            if not path.exists():
                raise RecordingProviderError(
                    f"No recording for {response_model.__name__} at {path}. "
                    f"Re-run in record mode against a live provider first."
                )
            data = json.loads(path.read_text(encoding="utf-8"))
            return response_model.model_validate(data["response"])

        # record mode
        result = await self._wrapped.complete_structured(
            system=system,
            user=user,
            response_model=response_model,
            temperature=temperature,
        )
        record: dict[str, Any] = {
            "request": {
                "system": system,
                "user": user,
                "model": response_model.__name__,
                "temperature": temperature,
            },
            "response": result.model_dump(mode="json"),
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
