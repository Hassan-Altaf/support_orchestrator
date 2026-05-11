"""Classifier node — populates `state["classification"]`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.models import Classification, IssueCategory, Priority
from app.llm.provider import LLMProvider
from app.orchestration.nodes._common import execute_node
from app.orchestration.state import SupportState
from app.prompts import classify

NODE_NAME = "classify"

# Spec safe fallback (§5): OTHER / MEDIUM / no escalation / 0 confidence
_FALLBACK = Classification(
    category=IssueCategory.OTHER,
    priority=Priority.MEDIUM,
    escalation_required=False,
    confidence=0.0,
    reasoning="auto-fallback: classifier could not produce a validated output",
)


def make_classifier_node(
    provider: LLMProvider,
    max_retries: int = 2,
) -> Callable[[SupportState], Awaitable[dict]]:
    """Build the classifier node with provider + retry budget bound."""

    async def classifier(state: SupportState) -> dict:
        result, trace_entry, err = await execute_node(
            node_name=NODE_NAME,
            state=state,
            provider=provider,
            max_retries=max_retries,
            system=classify.SYSTEM_PROMPT,
            user=classify.build_user_prompt(state["raw_message"]),
            response_model=Classification,
            temperature=classify.TEMPERATURE,
            fallback=_FALLBACK,
        )
        update: dict = {"classification": result, "trace": [trace_entry]}
        if err is not None:
            update["errors"] = [err]
        return update

    return classifier
