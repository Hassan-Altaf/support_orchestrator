"""Shared `_execute_node` helper used by every orchestration node.

Each node's variation is mechanical (different prompt module, response
model, fallback, and field unwrap). The retry / fallback / trace / log
boilerplate is captured here once.
"""

from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel

from app.domain.models import TraceEntry, TraceOutcome
from app.llm.provider import LLMProvider, call_with_retry
from app.orchestration.state import SupportState
from app.utils.logging import get_logger

T = TypeVar("T", bound=BaseModel)


async def execute_node(
    *,
    node_name: str,
    state: SupportState,
    provider: LLMProvider,
    max_retries: int,
    system: str,
    user: str,
    response_model: type[T],
    temperature: float,
    fallback: T,
) -> tuple[T, TraceEntry, str | None]:
    """Run one LLM-backed node with retry-with-feedback and safe fallback.

    Returns ``(result, trace_entry, error_message_or_None)``.

    On success, `result` is the validated model; `outcome` is "ok" (no
    retries) or "retry" (one or more retries). On failure (validation
    exhausted, transport error, refusal, …), `result` is `fallback`,
    `outcome` is "fallback", and `error_message_or_None` is populated so
    the caller can append it to `state["errors"]`.
    """
    log = get_logger(__name__).bind(node=node_name, request_id=state.get("request_id", "?"))
    start = time.perf_counter()
    try:
        result, retries = await call_with_retry(
            provider,
            system=system,
            user=user,
            response_model=response_model,
            max_retries=max_retries,
            temperature=temperature,
        )
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        err_summary = f"{type(e).__name__}: {str(e)[:200]}"
        log.warning("node_fallback", duration_ms=duration_ms, error=err_summary)
        return (
            fallback,
            TraceEntry(
                node=node_name,
                duration_ms=duration_ms,
                outcome="fallback",
                detail=err_summary[:200],
            ),
            f"{node_name}: {err_summary}",
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    outcome: TraceOutcome = "retry" if retries > 0 else "ok"
    log.info(
        "node_complete",
        duration_ms=duration_ms,
        outcome=outcome,
        retries=retries,
    )
    return (
        result,
        TraceEntry(
            node=node_name,
            duration_ms=duration_ms,
            outcome=outcome,
            detail=f"retries={retries}" if retries > 0 else None,
        ),
        None,
    )
