"""SupportState — the LangGraph TypedDict carried across all nodes.

Design notes
------------
* Most fields use REPLACE semantics (LangGraph's default for TypedDict):
  the latest node's value wins. Optional fields start as `None`.
* `errors` and `trace` use ACCUMULATE semantics via `Annotated[..., add]`.
  Each node returns `{"trace": [entry]}` and LangGraph concatenates rather
  than overwriting. Same for `errors` populated by safe-fallback paths.
* TypedDict is chosen over a Pydantic model because LangGraph's reducer
  system was designed against TypedDicts. The trade-off is that runtime
  validation happens at field boundaries (we use Pydantic models for the
  payload fields themselves).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from app.domain.models import (
    Classification,
    EscalationContext,
    ExtractedInfo,
    InternalSummary,
    TraceEntry,
)


class SupportState(TypedDict):
    """Mutable state threaded through the orchestration graph."""

    # ---- Inputs (set once by the route handler) ----------------------------
    raw_message: str
    request_id: str

    # ---- Node outputs (each populated by exactly one node) -----------------
    classification: Classification | None
    extracted_info: ExtractedInfo | None
    escalation_context: EscalationContext | None
    customer_response: str | None
    internal_summary: InternalSummary | None

    # ---- Accumulators (every node may append) ------------------------------
    errors: Annotated[list[str], add]
    trace: Annotated[list[TraceEntry], add]


def initial_state(raw_message: str, request_id: str) -> SupportState:
    """Build a fresh SupportState with all node-output fields set to None."""
    return SupportState(
        raw_message=raw_message,
        request_id=request_id,
        classification=None,
        extracted_info=None,
        escalation_context=None,
        customer_response=None,
        internal_summary=None,
        errors=[],
        trace=[],
    )
