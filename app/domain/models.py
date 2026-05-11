"""Pydantic domain models for the support orchestration pipeline.

Every model used as LLM structured output declares `extra="forbid"` so
hallucinated keys are rejected at parse time — belt-and-suspenders to the
provider-level schema constraints.

Field bounds (`min_length`, `max_length`, `ge`, `le`) are intentional and
double as the contract communicated to the LLM in the prompt; they let the
retry-with-feedback loop give the model a concrete error to correct.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================
class IssueCategory(StrEnum):
    """Top-level classification of an inbound support message."""

    TECHNICAL_BUG = "technical_bug"
    ACCOUNT_ACCESS = "account_access"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    HOW_TO = "how_to"
    OUTAGE = "outage"
    OTHER = "other"


class Priority(StrEnum):
    """Business-impact priority assigned at classification time."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Urgency(StrEnum):
    """Customer-stated time pressure independent of priority."""

    NOT_URGENT = "not_urgent"
    NORMAL = "normal"
    URGENT = "urgent"
    IMMEDIATE = "immediate"


# Outcome strings for trace entries — Literal keeps the contract in the type
# system so a typo in a node ("retried" instead of "retry") is caught by mypy.
TraceOutcome = Literal["ok", "retry", "fallback", "error"]


# =============================================================================
# LLM-structured outputs (one per node)
# =============================================================================
class Classification(BaseModel):
    """Classifier-node output: category, priority, escalation decision."""

    model_config = ConfigDict(extra="forbid")

    category: IssueCategory
    priority: Priority
    escalation_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=10, max_length=500)


class ExtractedInfo(BaseModel):
    """Extractor-node output: structured facts mined from the raw message."""

    model_config = ConfigDict(extra="forbid")

    product_area: str = Field(min_length=2, max_length=100)
    issue_summary: str = Field(min_length=10, max_length=500)
    urgency: Urgency
    suggested_tags: list[str] = Field(min_length=1, max_length=8)
    affected_features: list[str] = Field(default_factory=list, max_length=10)


class EscalationContext(BaseModel):
    """Escalation-node output: severity, target team, SLA, justification."""

    model_config = ConfigDict(extra="forbid")

    severity_level: int = Field(ge=1, le=5)
    suggested_team: str = Field(min_length=2, max_length=80)
    sla_minutes: int = Field(ge=1, le=10_080)  # 1 minute .. 1 week
    reason: str = Field(min_length=10, max_length=500)


class InternalSummary(BaseModel):
    """Internal-summary-node output: structured handoff packet for the team."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=5, max_length=200)
    customer_intent: str = Field(min_length=5, max_length=300)
    diagnostic_notes: str = Field(min_length=5, max_length=1000)
    recommended_actions: list[str] = Field(min_length=1, max_length=10)
    handoff_team: str = Field(min_length=2, max_length=80)


# =============================================================================
# Internal observability
# =============================================================================
class TraceEntry(BaseModel):
    """One row of the per-request orchestration trace surfaced in the API response."""

    model_config = ConfigDict(extra="forbid")

    node: str
    duration_ms: int = Field(ge=0)
    outcome: TraceOutcome
    detail: str | None = None


# =============================================================================
# Public API response
# =============================================================================
class TicketProcessingResult(BaseModel):
    """Top-level response returned by POST /api/v1/support/process."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    processed_at: datetime
    classification: Classification
    extracted_info: ExtractedInfo
    escalation_context: EscalationContext | None
    customer_response: str = Field(min_length=1, max_length=2000)
    internal_summary: InternalSummary
    processing_trace: list[TraceEntry]
    recovered_errors: list[str] = Field(default_factory=list)
