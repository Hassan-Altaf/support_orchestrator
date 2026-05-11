"""Prompt for the customer-response node — produces a `CustomerResponseDraft`.

Temperature is 0.3 (the only non-zero in the pipeline) for natural-language
variation. The single-field `CustomerResponseDraft` wrapper exists so this
node fits the LLM provider's structured-output Protocol; the node unwraps
`.response` into the API result.
"""

from __future__ import annotations

from app.domain.models import Classification, EscalationContext, ExtractedInfo
from app.prompts._sanitize import sanitize_user_input

TEMPERATURE = 0.3

SYSTEM_PROMPT = """You are an empathetic, professional senior support agent at VoiceSpin (telephony for call centers).

Your task: draft the customer-facing reply for this support ticket.

Tone and content rules — these are non-negotiable:
- Open by acknowledging the customer's situation in your own words (do NOT parrot back their exact phrasing).
- DO NOT promise specific timelines, fixes, refunds, or causes — you are not the engineer or the billing team.
- DO NOT speculate on root cause.
- Reference the relevant internal team in soft terms ("our voice platform team", "our billing team") without naming individuals.
- If the ticket is escalated, reassure the customer that it has been prioritised; if not, set neutral expectations.
- Sign off warmly and professionally. Do NOT include a placeholder name; end with "the VoiceSpin team".
- Length: 3 to 5 sentences. No bullet points, no markdown, no headings.

Output field:
- response: the customer-facing reply text matching the rules above.

Respond with structured output matching the schema. No prose, no commentary, no markdown."""


def build_user_prompt(
    raw_message: str,
    classification: Classification,
    extracted_info: ExtractedInfo,
    escalation_context: EscalationContext | None,
) -> str:
    """Render full context for an empathetic, well-targeted reply."""
    escalation_block = (
        f"\nEscalation: yes — severity {escalation_context.severity_level}, "
        f"routed to {escalation_context.suggested_team}.\n"
        if escalation_context is not None
        else "\nEscalation: not required — standard support path.\n"
    )
    safe = sanitize_user_input(raw_message)
    return (
        f"Customer support message:\n<<<\n{safe}\n>>>\n\n"
        f"Internal context for the agent (do NOT echo verbatim):\n"
        f"  category: {classification.category.value}\n"
        f"  priority: {classification.priority.value}\n"
        f"  product_area: {extracted_info.product_area}\n"
        f"  issue_summary: {extracted_info.issue_summary}\n"
        f"  urgency: {extracted_info.urgency.value}"
        f"{escalation_block}"
    )
