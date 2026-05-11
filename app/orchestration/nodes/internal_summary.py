"""Internal-summary node — populates `state["internal_summary"]`.

Final node in the pipeline. Falls back to a templated structured handoff
that embeds the raw message in diagnostic_notes so the receiving team
still has the verbatim customer text even when the model failed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.models import InternalSummary
from app.llm.provider import LLMProvider
from app.orchestration.nodes._common import execute_node
from app.orchestration.state import SupportState
from app.prompts import internal_summary

NODE_NAME = "internal_summary"


def _fallback_for(raw_message: str) -> InternalSummary:
    """Templated handoff embedding the raw message so reviewers see ground truth."""
    snippet = raw_message.strip()[:800] or "no content provided"
    # Pad to min_length=5 on each constrained field.
    return InternalSummary(
        headline="auto-fallback: summary node could not validate output",
        customer_intent="Unable to determine — see raw message in diagnostic_notes.",
        diagnostic_notes=f"Raw customer message (verbatim): {snippet}",
        recommended_actions=["Triage manually using the raw customer message."],
        handoff_team="general-support",
    )


def make_internal_summary_node(
    provider: LLMProvider,
    max_retries: int = 2,
) -> Callable[[SupportState], Awaitable[dict[str, Any]]]:
    async def summarize(state: SupportState) -> dict[str, Any]:
        classification = state["classification"]
        extracted = state["extracted_info"]
        # `if/raise` rather than `assert` so `python -O` can't strip the guard.
        if classification is None or extracted is None:
            raise RuntimeError(
                "internal_summary node invoked without upstream classification / extracted_info"
            )

        result, trace_entry, err = await execute_node(
            node_name=NODE_NAME,
            state=state,
            provider=provider,
            max_retries=max_retries,
            system=internal_summary.SYSTEM_PROMPT,
            user=internal_summary.build_user_prompt(
                state["raw_message"],
                classification,
                extracted,
                state.get("escalation_context"),
            ),
            response_model=InternalSummary,
            temperature=internal_summary.TEMPERATURE,
            fallback=_fallback_for(state["raw_message"]),
        )
        update: dict[str, Any] = {"internal_summary": result, "trace": [trace_entry]}
        if err is not None:
            update["errors"] = [err]
        return update

    return summarize
