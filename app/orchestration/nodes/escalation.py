"""Escalation node — populates `state["escalation_context"]`.

Only invoked when the classifier set `escalation_required=true` (the
conditional edge in `graph.py` enforces this). Consumes the upstream
classification + extracted_info as context for severity/team/SLA.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.models import EscalationContext
from app.llm.provider import LLMProvider
from app.orchestration.nodes._common import execute_node
from app.orchestration.state import SupportState
from app.prompts import escalation

NODE_NAME = "escalation"

# Spec §5: severity=3, team="general_support", sla=240, reason="auto-fallback"
_FALLBACK = EscalationContext(
    severity_level=3,
    suggested_team="general_support",
    sla_minutes=240,
    reason="auto-fallback: escalation node could not produce a validated output",
)


def make_escalation_node(
    provider: LLMProvider,
    max_retries: int = 2,
) -> Callable[[SupportState], Awaitable[dict]]:
    async def escalation_handler(state: SupportState) -> dict:
        classification = state["classification"]
        extracted = state["extracted_info"]
        # Defensive: if upstream nodes catastrophically failed, those would
        # still be populated by fallbacks. The conditional edge wouldn't
        # have routed us here without a classification, but assert in case.
        assert classification is not None, "escalation invoked without classification"
        assert extracted is not None, "escalation invoked without extracted_info"

        result, trace_entry, err = await execute_node(
            node_name=NODE_NAME,
            state=state,
            provider=provider,
            max_retries=max_retries,
            system=escalation.SYSTEM_PROMPT,
            user=escalation.build_user_prompt(state["raw_message"], classification, extracted),
            response_model=EscalationContext,
            temperature=escalation.TEMPERATURE,
            fallback=_FALLBACK,
        )
        update: dict = {"escalation_context": result, "trace": [trace_entry]}
        if err is not None:
            update["errors"] = [err]
        return update

    return escalation_handler
