"""HTTP request / response DTOs.

These are intentionally separated from `app/domain/models.py`:
* Domain models = LLM contract and internal data
* API schemas = wire format

Even when the wire and domain models look similar, keeping them in
separate modules lets the API evolve (versioned endpoints, additive
fields, deprecation aliases) without touching the orchestration logic.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProcessRequest(BaseModel):
    """POST /api/v1/support/process — request body."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=5,
        max_length=10_000,
        description="The raw customer support message to triage and respond to.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional caller-supplied metadata (tenant id, channel, …); echoed in logs.",
    )


class HealthResponse(BaseModel):
    """GET /api/v1/health — liveness + version."""

    status: str = Field(default="ok", description="Always 'ok' when the service is reachable.")
    version: str


class VersionResponse(BaseModel):
    """GET /api/v1/version — version and build info."""

    version: str
    build: str | None = None


class ErrorResponse(BaseModel):
    """Uniform error envelope used by exception handlers."""

    error: str = Field(description="Short machine-readable error code (e.g. 'validation_error').")
    detail: str | None = Field(default=None, description="Human-readable explanation.")
    request_id: str | None = Field(
        default=None,
        description="Correlates with X-Request-ID; copy this into bug reports.",
    )
