"""Pytest fixtures shared across the test suite.

Provides:
* `settings` / `mock_provider` / `compiled_graph` / `client` for wiring
* `sample_messages` / `eval_set` loaded from JSON fixtures
* Builder fixtures (`good_classification`, `good_extracted_info`, etc.)
  returning factory callables so tests can vary fields per scenario.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

# Force the LLM provider to "mock" BEFORE importing app modules so the
# module-level `app = create_app()` in app/main.py doesn't trip the
# Settings validator looking for OPENAI_API_KEY (even if a developer has
# LLM_PROVIDER=openai set in their shell without a key present).
os.environ["LLM_PROVIDER"] = "mock"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.models import (
    Classification,
    CustomerResponseDraft,
    EscalationContext,
    ExtractedInfo,
    InternalSummary,
    IssueCategory,
    Priority,
    Urgency,
)
from app.llm.mock_provider import MockProvider
from app.main import create_app
from app.orchestration.graph import compile_graph

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Core wiring fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def settings() -> Settings:
    return Settings(llm_provider="mock", _env_file=None)


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def compiled_graph(mock_provider: MockProvider, settings: Settings):  # type: ignore[no-untyped-def]
    return compile_graph(mock_provider, settings)


@pytest.fixture
def app(settings: Settings, mock_provider: MockProvider) -> FastAPI:
    return create_app(settings, provider=mock_provider)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# JSON fixture loaders
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    return json.loads((FIXTURES_DIR / "sample_messages.json").read_text(encoding="utf-8"))


@pytest.fixture
def eval_set() -> list[dict[str, Any]]:
    return json.loads((FIXTURES_DIR / "eval_set.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Canned-response builders (factories — call with overrides per test)
# ---------------------------------------------------------------------------
@pytest.fixture
def good_classification() -> Callable[..., Classification]:
    def _build(
        *,
        category: IssueCategory = IssueCategory.TECHNICAL_BUG,
        priority: Priority = Priority.MEDIUM,
        escalation_required: bool = False,
        confidence: float = 0.88,
        reasoning: str = "Customer reports a software issue with operational impact.",
    ) -> Classification:
        return Classification(
            category=category,
            priority=priority,
            escalation_required=escalation_required,
            confidence=confidence,
            reasoning=reasoning,
        )

    return _build


@pytest.fixture
def good_extracted_info() -> Callable[..., ExtractedInfo]:
    def _build(
        *,
        product_area: str = "outbound_dialer",
        issue_summary: str = "Outbound calls drop shortly after connect on the dialer.",
        urgency: Urgency = Urgency.URGENT,
        suggested_tags: list[str] | None = None,
        affected_features: list[str] | None = None,
    ) -> ExtractedInfo:
        return ExtractedInfo(
            product_area=product_area,
            issue_summary=issue_summary,
            urgency=urgency,
            suggested_tags=suggested_tags or ["sip", "outbound"],
            affected_features=affected_features or [],
        )

    return _build


@pytest.fixture
def good_escalation_context() -> Callable[..., EscalationContext]:
    def _build(
        *,
        severity_level: int = 4,
        suggested_team: str = "voice-platform",
        sla_minutes: int = 60,
        reason: str = "Symptoms align with a SIP/RTP fault on the voice platform path.",
    ) -> EscalationContext:
        return EscalationContext(
            severity_level=severity_level,
            suggested_team=suggested_team,
            sla_minutes=sla_minutes,
            reason=reason,
        )

    return _build


@pytest.fixture
def good_customer_response() -> Callable[..., CustomerResponseDraft]:
    def _build(text: str | None = None) -> CustomerResponseDraft:
        return CustomerResponseDraft(
            response=text
            or (
                "Thanks for letting us know. Our team is looking into it and "
                "we will follow up shortly with an update. "
                "- the VoiceSpin team"
            )
        )

    return _build


@pytest.fixture
def good_internal_summary() -> Callable[..., InternalSummary]:
    def _build(
        *,
        headline: str = "Outbound dialer dropping calls for SIP-trunk customer",
        customer_intent: str = "Resolve call-drop regression on outbound campaigns",
        diagnostic_notes: str = "Calls connect then drop shortly after; symptom started today.",
        recommended_actions: list[str] | None = None,
        handoff_team: str = "voice-platform",
    ) -> InternalSummary:
        return InternalSummary(
            headline=headline,
            customer_intent=customer_intent,
            diagnostic_notes=diagnostic_notes,
            recommended_actions=recommended_actions
            or ["Check SIP trunk auth and RTP timeouts", "Page voice-platform on-call"],
            handoff_team=handoff_team,
        )

    return _build


# ---------------------------------------------------------------------------
# Cross-cutting: a pre-built ValidationError instance for retry tests.
# ---------------------------------------------------------------------------
@pytest.fixture
def validation_error_instance():  # type: ignore[no-untyped-def]
    """Returns a `pydantic.ValidationError` that retry tests can re-raise."""
    from pydantic import ValidationError

    try:
        Classification(
            category="not_a_real_category",  # type: ignore[arg-type]
            priority=Priority.LOW,
            escalation_required=False,
            confidence=0.5,
            reasoning="some valid reasoning text here for the error fixture",
        )
    except ValidationError as e:
        return e
    raise RuntimeError("expected ValidationError")
