"""MockProvider — canned-response provider for tests and `demo --mock`.

Supports three queueing modes that can be combined:
* `queue(*responses)`     — global FIFO queue (returned in order)
* `queue_for(name, ...)`  — per-model-name FIFO queue (preferred when set)
* Queue entries may be `BaseModel` instances (returned) OR `Exception`
  instances (raised) — the latter is how tests simulate validation failures.

Resolution order on each call: per-model queue → global queue → error.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# A queued entry is either a model instance to return or an exception to raise.
QueueEntry = BaseModel | Exception


class MockProvider:
    """In-memory provider returning canned outputs."""

    def __init__(self) -> None:
        self._global: list[QueueEntry] = []
        self._by_model: dict[str, list[QueueEntry]] = {}
        self._call_count = 0
        self._calls_by_model: dict[str, int] = {}

    # ------------------------------------------------------------------ queue
    def queue(self, *entries: QueueEntry) -> MockProvider:
        """Append entries to the global FIFO queue. Returns self for chaining."""
        self._global.extend(entries)
        return self

    def queue_for(self, model_name: str, *entries: QueueEntry) -> MockProvider:
        """Append entries to the per-model FIFO queue."""
        self._by_model.setdefault(model_name, []).extend(entries)
        return self

    # ---------------------------------------------------------- introspection
    @property
    def call_count(self) -> int:
        return self._call_count

    def calls_for(self, model_name: str) -> int:
        return self._calls_by_model.get(model_name, 0)

    # ------------------------------------------------------------------- API
    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        del system, user, temperature  # MockProvider is content-agnostic by design
        self._call_count += 1
        name = response_model.__name__
        self._calls_by_model[name] = self._calls_by_model.get(name, 0) + 1

        bucket = self._by_model.get(name) or self._global
        if not bucket:
            raise RuntimeError(
                f"MockProvider has no queued response for {name!r} "
                f"(total calls so far: {self._call_count})."
            )
        entry = bucket.pop(0)

        if isinstance(entry, Exception):
            raise entry
        if not isinstance(entry, response_model):
            raise TypeError(
                f"MockProvider: queued entry is {type(entry).__name__}, caller asked for {name}."
            )
        return entry
