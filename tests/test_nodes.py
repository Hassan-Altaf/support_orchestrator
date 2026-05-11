"""Per-node unit tests: happy path, validation retry, exhausted-retry fallback.

Each node is exercised in isolation by calling its factory with a
fresh MockProvider and invoking the returned async callable against a
prepared SupportState.
"""

from __future__ import annotations

import pytest

from app.domain.models import (
    Classification,
    EscalationContext,
    ExtractedInfo,
    InternalSummary,
    IssueCategory,
    Priority,
    Urgency,
)
from app.llm.mock_provider import MockProvider
from app.orchestration.nodes import (
    make_classifier_node,
    make_customer_response_node,
    make_escalation_node,
    make_extractor_node,
    make_internal_summary_node,
)
from app.orchestration.state import initial_state


# =============================================================================
# Classifier
# =============================================================================
class TestClassifierNode:
    async def test_happy_path_marks_trace_ok(
        self, mock_provider: MockProvider, good_classification
    ) -> None:
        mock_provider.queue(good_classification(escalation_required=True))
        node = make_classifier_node(mock_provider, max_retries=2)
        update = await node(initial_state("any message", "req-1"))

        assert isinstance(update["classification"], Classification)
        assert update["classification"].escalation_required is True
        assert len(update["trace"]) == 1
        assert update["trace"][0].node == "classify"
        assert update["trace"][0].outcome == "ok"
        assert "errors" not in update

    async def test_retry_then_success(
        self, mock_provider: MockProvider, good_classification, validation_error_instance
    ) -> None:
        mock_provider.queue(validation_error_instance, good_classification())
        node = make_classifier_node(mock_provider, max_retries=2)
        update = await node(initial_state("msg", "req-2"))

        assert update["trace"][0].outcome == "retry"
        assert update["trace"][0].detail == "retries=1"
        assert "errors" not in update

    async def test_exhausted_retries_engages_safe_fallback(
        self, mock_provider: MockProvider, validation_error_instance
    ) -> None:
        for _ in range(3):
            mock_provider.queue(validation_error_instance)
        node = make_classifier_node(mock_provider, max_retries=2)
        update = await node(initial_state("msg", "req-3"))

        fb = update["classification"]
        assert fb.category == IssueCategory.OTHER
        assert fb.priority == Priority.MEDIUM
        assert fb.escalation_required is False
        assert fb.confidence == 0.0
        assert update["trace"][0].outcome == "fallback"
        assert len(update["errors"]) == 1
        assert update["errors"][0].startswith("classify:")

    async def test_provider_exception_engages_fallback(self, mock_provider: MockProvider) -> None:
        mock_provider.queue(RuntimeError("simulated upstream outage"))
        node = make_classifier_node(mock_provider, max_retries=2)
        update = await node(initial_state("msg", "req-4"))

        assert update["trace"][0].outcome == "fallback"
        assert "RuntimeError" in update["errors"][0]


# =============================================================================
# Extractor
# =============================================================================
class TestExtractorNode:
    async def test_happy_path(
        self, mock_provider: MockProvider, good_classification, good_extracted_info
    ) -> None:
        state = initial_state("msg", "req-1")
        state["classification"] = good_classification()
        mock_provider.queue(good_extracted_info())

        update = await make_extractor_node(mock_provider)(state)

        assert isinstance(update["extracted_info"], ExtractedInfo)
        assert update["trace"][0].outcome == "ok"

    async def test_fallback_preserves_message_snippet(
        self, mock_provider: MockProvider, good_classification
    ) -> None:
        raw = "Outbound calls are dropping for our team every single time we dial out."
        state = initial_state(raw, "req-2")
        state["classification"] = good_classification()
        mock_provider.queue(RuntimeError("provider down"))

        update = await make_extractor_node(mock_provider)(state)

        ei = update["extracted_info"]
        assert ei.product_area == "unknown"
        assert ei.urgency == Urgency.NORMAL
        assert ei.suggested_tags == ["unclassified"]
        assert "Outbound" in ei.issue_summary

    async def test_fallback_pads_short_message(
        self, mock_provider: MockProvider, good_classification
    ) -> None:
        # raw too short for issue_summary's min_length=10; fallback must still validate.
        state = initial_state("hi", "req-3")
        state["classification"] = good_classification()
        mock_provider.queue(RuntimeError("down"))

        update = await make_extractor_node(mock_provider)(state)
        assert len(update["extracted_info"].issue_summary) >= 10

    async def test_works_without_classification(
        self, mock_provider: MockProvider, good_extracted_info
    ) -> None:
        # Defensive: extractor should still produce output if classification is None.
        state = initial_state("msg", "req-4")
        mock_provider.queue(good_extracted_info())
        update = await make_extractor_node(mock_provider)(state)
        assert isinstance(update["extracted_info"], ExtractedInfo)


# =============================================================================
# Escalation
# =============================================================================
class TestEscalationNode:
    async def test_happy_path(
        self,
        mock_provider: MockProvider,
        good_classification,
        good_extracted_info,
        good_escalation_context,
    ) -> None:
        state = initial_state("msg", "req-1")
        state["classification"] = good_classification(escalation_required=True)
        state["extracted_info"] = good_extracted_info()
        mock_provider.queue(good_escalation_context())

        update = await make_escalation_node(mock_provider)(state)

        assert isinstance(update["escalation_context"], EscalationContext)
        assert update["escalation_context"].suggested_team == "voice-platform"

    async def test_fallback_matches_spec(
        self, mock_provider: MockProvider, good_classification, good_extracted_info
    ) -> None:
        state = initial_state("msg", "req-2")
        state["classification"] = good_classification(escalation_required=True)
        state["extracted_info"] = good_extracted_info()
        mock_provider.queue(RuntimeError("boom"))

        update = await make_escalation_node(mock_provider)(state)

        ec = update["escalation_context"]
        assert ec.severity_level == 3
        assert ec.suggested_team == "general_support"
        assert ec.sla_minutes == 240


# =============================================================================
# Customer response
# =============================================================================
class TestCustomerResponseNode:
    async def test_unwraps_response_to_string(
        self,
        mock_provider: MockProvider,
        good_classification,
        good_extracted_info,
        good_customer_response,
    ) -> None:
        state = initial_state("msg", "req-1")
        state["classification"] = good_classification()
        state["extracted_info"] = good_extracted_info()
        mock_provider.queue(good_customer_response())

        update = await make_customer_response_node(mock_provider)(state)

        assert isinstance(update["customer_response"], str)
        assert "VoiceSpin team" in update["customer_response"]

    async def test_fallback_uses_templated_message(
        self,
        mock_provider: MockProvider,
        good_classification,
        good_extracted_info,
    ) -> None:
        state = initial_state("msg", "req-2")
        state["classification"] = good_classification()
        state["extracted_info"] = good_extracted_info()
        mock_provider.queue(RuntimeError("openai down"))

        update = await make_customer_response_node(mock_provider)(state)
        assert isinstance(update["customer_response"], str)
        assert len(update["customer_response"]) >= 20
        assert "VoiceSpin team" in update["customer_response"]
        assert update["trace"][0].outcome == "fallback"


# =============================================================================
# Internal summary
# =============================================================================
class TestInternalSummaryNode:
    async def test_happy_path(
        self,
        mock_provider: MockProvider,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_internal_summary,
    ) -> None:
        state = initial_state("msg", "req-1")
        state["classification"] = good_classification(escalation_required=True)
        state["extracted_info"] = good_extracted_info()
        state["escalation_context"] = good_escalation_context()
        mock_provider.queue(good_internal_summary())

        update = await make_internal_summary_node(mock_provider)(state)

        assert isinstance(update["internal_summary"], InternalSummary)
        assert update["internal_summary"].handoff_team == "voice-platform"

    async def test_fallback_embeds_raw_message(
        self,
        mock_provider: MockProvider,
        good_classification,
        good_extracted_info,
    ) -> None:
        raw = "Inbound calls failing for all our tenants since 9am; help."
        state = initial_state(raw, "req-2")
        state["classification"] = good_classification(escalation_required=True)
        state["extracted_info"] = good_extracted_info()
        mock_provider.queue(RuntimeError("model down"))

        update = await make_internal_summary_node(mock_provider)(state)

        assert "Inbound calls failing" in update["internal_summary"].diagnostic_notes
        assert update["internal_summary"].handoff_team == "general-support"


# =============================================================================
# Negative case: missing upstream state triggers defensive assert
# =============================================================================
class TestPreconditionAsserts:
    async def test_escalation_requires_classification(
        self, mock_provider: MockProvider, good_extracted_info
    ) -> None:
        state = initial_state("msg", "req-1")
        state["extracted_info"] = good_extracted_info()
        with pytest.raises(AssertionError):
            await make_escalation_node(mock_provider)(state)
