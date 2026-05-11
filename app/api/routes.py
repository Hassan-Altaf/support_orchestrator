"""HTTP route handlers.

The router is mounted under `/api/v1` in `app/main.py`. The compiled
graph is shared across requests via `app.state.graph`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.api.schemas import HealthResponse, ProcessRequest, VersionResponse
from app.config import Settings
from app.domain.models import TicketProcessingResult
from app.orchestration.state import initial_state
from app.utils.logging import get_logger, get_request_id

router = APIRouter(prefix="/api/v1")


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(request: Request) -> HealthResponse:
    """Liveness check. Returns 200 if the service is reachable."""
    return HealthResponse(version=_settings(request).app_version)


@router.get("/version", response_model=VersionResponse, tags=["meta"])
async def version(request: Request) -> VersionResponse:
    """Version + build info for debugging mismatched deploys."""
    s = _settings(request)
    return VersionResponse(version=s.app_version, build=None)


@router.post(
    "/support/process",
    response_model=TicketProcessingResult,
    status_code=status.HTTP_200_OK,
    tags=["support"],
)
async def process_support_message(
    payload: ProcessRequest,
    request: Request,
) -> TicketProcessingResult:
    """Run the support orchestration graph against an inbound message.

    Returns the full processing result, including a per-node trace and any
    recovered errors. Validation failures on the request body produce 422
    automatically (see exception handler in app/main.py).
    """
    log = get_logger(__name__)
    request_id = get_request_id() or "unknown"
    graph = request.app.state.graph

    log.info(
        "process_request_start",
        message_length=len(payload.message),
        has_metadata=payload.metadata is not None,
    )

    state = initial_state(raw_message=payload.message, request_id=request_id)

    # Graph-level timeout = generous bound on the WHOLE pipeline, distinct
    # from `request_timeout_seconds` (which bounds a single LLM call).
    # Worst-case without this: 5 nodes * (1 + max_retries) * per-call-timeout.
    settings = _settings(request)
    graph_budget = max(settings.request_timeout_seconds * 4, 60)
    try:
        final: dict[str, Any] = await asyncio.wait_for(graph.ainvoke(state), timeout=graph_budget)
    except TimeoutError as exc:
        log.error("graph_timeout", graph_budget_s=graph_budget)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"orchestration exceeded the {graph_budget}s budget",
        ) from exc

    # Every node in the graph populates its field with either a real or
    # fallback value, so these should not be None after a normal run.
    missing = [
        k
        for k in (
            "classification",
            "extracted_info",
            "customer_response",
            "internal_summary",
        )
        if final.get(k) is None
    ]
    if missing:
        log.error("graph_incomplete_state", missing_fields=missing)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"orchestration produced incomplete state: missing {missing}",
        )

    result = TicketProcessingResult(
        request_id=request_id,
        processed_at=datetime.now(UTC),
        classification=final["classification"],
        extracted_info=final["extracted_info"],
        escalation_context=final.get("escalation_context"),
        customer_response=final["customer_response"],
        internal_summary=final["internal_summary"],
        processing_trace=final.get("trace", []),
        recovered_errors=final.get("errors", []),
    )

    log.info(
        "process_request_complete",
        category=result.classification.category.value,
        priority=result.classification.priority.value,
        escalated=result.escalation_context is not None,
        recovered_errors=len(result.recovered_errors),
        trace_length=len(result.processing_trace),
    )
    return result
