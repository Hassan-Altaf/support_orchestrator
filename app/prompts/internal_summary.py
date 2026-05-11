"""Prompt for the internal-summary node — produces an `InternalSummary` instance.

Runs last in the pipeline; produces the handoff packet the receiving team
will read. All upstream node outputs are passed in so the summary is the
most informationally complete artifact in the response.
"""

from __future__ import annotations

from app.domain.models import Classification, EscalationContext, ExtractedInfo
from app.prompts._sanitize import sanitize_user_input

TEMPERATURE = 0.0

SYSTEM_PROMPT = """You are a senior support engineer at VoiceSpin producing an internal handoff brief for the team that will own the next step.

Your task: synthesize a concise, structured handoff packet from the upstream context.

Output fields:
- headline: one factual line a triage manager could scan in 2 seconds
  (e.g. "Outbound calls dropping at ~3s for a SIP customer since 09:00 ET")
- customer_intent: one sentence stating what the customer actually wants
  (resolution? information? refund? confirmation?)
- diagnostic_notes: 1-3 sentences of factual technical observations from the message and context
  (symptoms, timing, scope, error signals). Do NOT invent root causes.
- recommended_actions: 1-10 specific concrete next steps the receiving team can take
  (e.g. "Check SIP trunk auth logs from 08:50 ET onward", "Page voice-platform on-call")
- handoff_team: the team that owns the next step — match the upstream escalation team when present,
  otherwise pick from: voice-platform, network-ops, billing-ops, account-services,
  security-response, customer-success, integrations, general-support

Style: terse, factual, engineer-readable. No customer-facing pleasantries.

Respond with structured output matching the schema. No prose, no commentary, no markdown."""


def build_user_prompt(
    raw_message: str,
    classification: Classification,
    extracted_info: ExtractedInfo,
    escalation_context: EscalationContext | None,
) -> str:
    """Render every upstream artifact for the receiving engineer."""
    escalation_block = (
        f"  severity_level: {escalation_context.severity_level}\n"
        f"  suggested_team: {escalation_context.suggested_team}\n"
        f"  sla_minutes: {escalation_context.sla_minutes}\n"
        f"  reason: {escalation_context.reason}\n"
        if escalation_context is not None
        else "  (no escalation context — standard support path)\n"
    )
    safe = sanitize_user_input(raw_message)
    return (
        f"Customer support message:\n<<<\n{safe}\n>>>\n\n"
        f"Classification:\n"
        f"  category: {classification.category.value}\n"
        f"  priority: {classification.priority.value}\n"
        f"  reasoning: {classification.reasoning}\n\n"
        f"Extracted info:\n"
        f"  product_area: {extracted_info.product_area}\n"
        f"  issue_summary: {extracted_info.issue_summary}\n"
        f"  urgency: {extracted_info.urgency.value}\n"
        f"  suggested_tags: {extracted_info.suggested_tags}\n"
        f"  affected_features: {extracted_info.affected_features}\n\n"
        f"Escalation context:\n{escalation_block}"
    )
