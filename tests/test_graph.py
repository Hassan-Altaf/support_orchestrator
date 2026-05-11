"""Full-graph integration tests using the 5 sample messages.

For each scenario we queue per-model mock responses that mirror the
expected fields, then invoke the compiled graph and assert end-to-end
behavior including routing (escalation vs skip) and trace ordering.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.models import IssueCategory, Priority, Urgency
from app.llm.mock_provider import MockProvider
from app.orchestration.state import initial_state


def _queue_for_scenario(
    provider: MockProvider,
    expected: dict[str, Any],
    *,
    good_classification,
    good_extracted_info,
    good_escalation_context,
    good_customer_response,
    good_internal_summary,
) -> None:
    """Queue per-model canned responses matching the scenario's expected fields."""
    escalate = bool(expected["escalation_required"])
    provider.queue_for(
        "Classification",
        good_classification(
            category=IssueCategory(expected["category"]),
            priority=Priority(expected["priority"]),
            escalation_required=escalate,
        ),
    )
    provider.queue_for(
        "ExtractedInfo",
        good_extracted_info(urgency=Urgency(expected["urgency"])),
    )
    if escalate:
        provider.queue_for("EscalationContext", good_escalation_context())
    provider.queue_for("CustomerResponseDraft", good_customer_response())
    provider.queue_for("InternalSummary", good_internal_summary())


@pytest.mark.integration
class TestGraphScenarios:
    async def test_critical_bug_takes_escalation_path(
        self,
        compiled_graph,
        mock_provider,
        sample_messages,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        scenario = next(m for m in sample_messages if m["id"] == "critical_bug_deadline")
        _queue_for_scenario(
            mock_provider,
            scenario["expected"],
            good_classification=good_classification,
            good_extracted_info=good_extracted_info,
            good_escalation_context=good_escalation_context,
            good_customer_response=good_customer_response,
            good_internal_summary=good_internal_summary,
        )
        final = await compiled_graph.ainvoke(initial_state(scenario["message"], "req-bug"))

        assert final["classification"].escalation_required is True
        assert final["escalation_context"] is not None
        trace_nodes = [t.node for t in final["trace"]]
        assert trace_nodes == [
            "classify",
            "extract",
            "escalation",
            "customer_response",
            "internal_summary",
        ]
        assert final["errors"] == []

    async def test_billing_question_skips_escalation(
        self,
        compiled_graph,
        mock_provider,
        sample_messages,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        scenario = next(m for m in sample_messages if m["id"] == "billing_question")
        _queue_for_scenario(
            mock_provider,
            scenario["expected"],
            good_classification=good_classification,
            good_extracted_info=good_extracted_info,
            good_escalation_context=good_escalation_context,
            good_customer_response=good_customer_response,
            good_internal_summary=good_internal_summary,
        )
        final = await compiled_graph.ainvoke(initial_state(scenario["message"], "req-billing"))

        assert final["classification"].escalation_required is False
        assert final["escalation_context"] is None
        trace_nodes = [t.node for t in final["trace"]]
        assert trace_nodes == ["classify", "extract", "customer_response", "internal_summary"]
        assert mock_provider.call_count == 4  # no escalation call

    async def test_howto_skips_escalation(
        self,
        compiled_graph,
        mock_provider,
        sample_messages,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        scenario = next(m for m in sample_messages if m["id"] == "howto_sip_trunk")
        _queue_for_scenario(
            mock_provider,
            scenario["expected"],
            good_classification=good_classification,
            good_extracted_info=good_extracted_info,
            good_escalation_context=good_escalation_context,
            good_customer_response=good_customer_response,
            good_internal_summary=good_internal_summary,
        )
        final = await compiled_graph.ainvoke(initial_state(scenario["message"], "req-howto"))
        assert final["escalation_context"] is None

    async def test_multi_tenant_outage_escalates(
        self,
        compiled_graph,
        mock_provider,
        sample_messages,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        scenario = next(m for m in sample_messages if m["id"] == "multi_tenant_outage")
        _queue_for_scenario(
            mock_provider,
            scenario["expected"],
            good_classification=good_classification,
            good_extracted_info=good_extracted_info,
            good_escalation_context=good_escalation_context,
            good_customer_response=good_customer_response,
            good_internal_summary=good_internal_summary,
        )
        final = await compiled_graph.ainvoke(initial_state(scenario["message"], "req-outage"))
        assert final["escalation_context"] is not None
        assert final["classification"].priority == Priority.CRITICAL

    async def test_feature_request_skips_escalation(
        self,
        compiled_graph,
        mock_provider,
        sample_messages,
        good_classification,
        good_extracted_info,
        good_escalation_context,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        scenario = next(m for m in sample_messages if m["id"] == "feature_request_slack")
        _queue_for_scenario(
            mock_provider,
            scenario["expected"],
            good_classification=good_classification,
            good_extracted_info=good_extracted_info,
            good_escalation_context=good_escalation_context,
            good_customer_response=good_customer_response,
            good_internal_summary=good_internal_summary,
        )
        final = await compiled_graph.ainvoke(initial_state(scenario["message"], "req-feature"))
        assert final["classification"].category == IssueCategory.FEATURE_REQUEST
        assert final["escalation_context"] is None


@pytest.mark.integration
class TestGraphFallbackRecovery:
    async def test_classifier_failure_does_not_abort_pipeline(
        self,
        compiled_graph,
        mock_provider,
        good_extracted_info,
        good_customer_response,
        good_internal_summary,
    ) -> None:
        # Classifier explodes -> fallback (escalation_required=False) -> skip branch
        mock_provider.queue_for("Classification", RuntimeError("simulate outage"))
        mock_provider.queue_for("ExtractedInfo", good_extracted_info())
        mock_provider.queue_for("CustomerResponseDraft", good_customer_response())
        mock_provider.queue_for("InternalSummary", good_internal_summary())

        final = await compiled_graph.ainvoke(initial_state("anything", "req-fb"))

        assert final["classification"].category == IssueCategory.OTHER  # fallback signature
        assert final["customer_response"] is not None
        assert final["internal_summary"] is not None
        assert len(final["errors"]) >= 1
        assert final["trace"][0].outcome == "fallback"
