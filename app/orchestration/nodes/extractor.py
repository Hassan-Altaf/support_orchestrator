"""Extractor node — populates `state["extracted_info"]`.

Consumes `state["classification"].category` as soft context to focus the
extraction. Falls back gracefully if classification is somehow missing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.models import ExtractedInfo, Urgency
from app.llm.provider import LLMProvider
from app.orchestration.nodes._common import execute_node
from app.orchestration.state import SupportState
from app.prompts import extract

NODE_NAME = "extract"


def _fallback_for(raw_message: str) -> ExtractedInfo:
    # Spec §5: unknown product_area, raw message truncated to 200 chars
    # as issue_summary, normal urgency, single 'unclassified' tag.
    snippet = raw_message.strip()[:200] if raw_message.strip() else "no content provided"
    if len(snippet) < 10:
        # ExtractedInfo.issue_summary requires min_length=10; pad gracefully.
        snippet = (snippet + " (auto-fallback)").ljust(10)
    return ExtractedInfo(
        product_area="unknown",
        issue_summary=snippet,
        urgency=Urgency.NORMAL,
        suggested_tags=["unclassified"],
    )


def make_extractor_node(
    provider: LLMProvider,
    max_retries: int = 2,
) -> Callable[[SupportState], Awaitable[dict[str, Any]]]:
    async def extractor(state: SupportState) -> dict[str, Any]:
        classification = state.get("classification")
        category = classification.category if classification is not None else None

        result, trace_entry, err = await execute_node(
            node_name=NODE_NAME,
            state=state,
            provider=provider,
            max_retries=max_retries,
            system=extract.SYSTEM_PROMPT,
            user=extract.build_user_prompt(state["raw_message"], category),
            response_model=ExtractedInfo,
            temperature=extract.TEMPERATURE,
            fallback=_fallback_for(state["raw_message"]),
        )
        update: dict[str, Any] = {"extracted_info": result, "trace": [trace_entry]}
        if err is not None:
            update["errors"] = [err]
        return update

    return extractor
