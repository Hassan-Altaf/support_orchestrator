"""Customer-response node — populates `state["customer_response"]`.

Unwraps `CustomerResponseDraft.response` into the plain string the API
returns. Falls back to a templated empathetic message on validation
failure so the customer always gets a reply.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.models import CustomerResponseDraft
from app.llm.provider import LLMProvider
from app.orchestration.nodes._common import execute_node
from app.orchestration.state import SupportState
from app.prompts import customer_response

NODE_NAME = "customer_response"

# Spec §5: templated empathetic message. Must satisfy the 20-char min.
_FALLBACK_TEXT = (
    "Thank you for reaching out. We have received your message and our team is "
    "reviewing the details. We will follow up shortly with more information. "
    "- the VoiceSpin team"
)
_FALLBACK = CustomerResponseDraft(response=_FALLBACK_TEXT)


def make_customer_response_node(
    provider: LLMProvider,
    max_retries: int = 2,
) -> Callable[[SupportState], Awaitable[dict]]:
    async def respond(state: SupportState) -> dict:
        classification = state["classification"]
        extracted = state["extracted_info"]
        assert classification is not None, "customer_response invoked without classification"
        assert extracted is not None, "customer_response invoked without extracted_info"

        result, trace_entry, err = await execute_node(
            node_name=NODE_NAME,
            state=state,
            provider=provider,
            max_retries=max_retries,
            system=customer_response.SYSTEM_PROMPT,
            user=customer_response.build_user_prompt(
                state["raw_message"],
                classification,
                extracted,
                state.get("escalation_context"),
            ),
            response_model=CustomerResponseDraft,
            temperature=customer_response.TEMPERATURE,
            fallback=_FALLBACK,
        )
        update: dict = {"customer_response": result.response, "trace": [trace_entry]}
        if err is not None:
            update["errors"] = [err]
        return update

    return respond
