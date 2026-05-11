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


def _classify_failure(exc: BaseException) -> str:
    """Map a node-level exception to a coarse, leak-safe client summary.

    The full exception goes to server-side logs; this string is what we
    expose in API responses. We never include the original message text
    because provider error bodies have been observed to include partial
    API keys, rate-limit URIs, and internal hostnames.
    """
    name_lower = type(exc).__name__.lower()
    # We DO inspect the message text — but only to bucket it into one of
    # the fixed labels below; the raw message itself never leaves this fn.
    msg_lower = str(exc).lower()

    if "validation" in name_lower:
        # ValidationError after retry budget exhaustion — schema deviation.
        return "model output failed validation after retries"
    if (
        "rate" in name_lower
        or "ratelimit" in name_lower
        or " 429" in msg_lower
        or "429 " in msg_lower
        or "quota" in msg_lower
        or "exhausted" in msg_lower
        or "resource_exhausted" in msg_lower
        or "too many requests" in msg_lower
    ):
        return "provider rate-limited or quota exhausted"
    if (
        "timeout" in name_lower
        or "timed out" in msg_lower
        or " 504" in msg_lower
        or "504 " in msg_lower
    ):
        return "provider timeout"
    if (
        "auth" in name_lower
        or "permission" in name_lower
        or " 401" in msg_lower
        or "401 " in msg_lower
        or " 403" in msg_lower
        or "403 " in msg_lower
        or "unauthorized" in msg_lower
        or "permission_denied" in msg_lower
        or "invalid api key" in msg_lower
    ):
        return "provider authentication failed"
    if "providererror" in name_lower:
        return "provider error"
    return "provider unavailable"


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
        # Two strings, by design:
        #  * `internal_detail` — full exception type + message; sent only to
        #    server-side structured logs (provider error bodies may contain
        #    partial API keys, internal URLs, rate-limit URIs, etc.)
        #  * `client_summary` — coarse, leak-safe; this is what we expose to
        #    the API caller via `recovered_errors` and the trace's `detail`.
        internal_detail = f"{type(e).__name__}: {str(e)[:500]}"
        client_summary = _classify_failure(e)
        log.warning(
            "node_fallback",
            duration_ms=duration_ms,
            error=internal_detail,
            client_summary=client_summary,
        )
        return (
            fallback,
            TraceEntry(
                node=node_name,
                duration_ms=duration_ms,
                outcome="fallback",
                detail=client_summary,
            ),
            f"{node_name}: {client_summary}",
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
