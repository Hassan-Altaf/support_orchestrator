"""Prompt for the escalation node — produces an `EscalationContext` instance.

Only runs when the classifier marked `escalation_required=true`. Consumes
the classification and extracted info so the model has the full picture
when deciding severity, team, and SLA.
"""

from __future__ import annotations

from app.domain.models import Classification, ExtractedInfo

TEMPERATURE = 0.0

SYSTEM_PROMPT = """You are a senior on-call coordinator at VoiceSpin (telephony for call centers).

Your task: given a classified support ticket that requires escalation, produce the escalation context.

Output fields:
- severity_level: integer 1-5 using this scale:
    1 = minor inconvenience, no business impact
    2 = workable, intermittent, single customer
    3 = significant impact on a single customer's operations
    4 = critical impact on a single customer OR partial impact on multiple customers
    5 = full outage, security/data-integrity event, or regulator-grade incident
- suggested_team: choose ONE from this fixed roster:
    voice-platform, network-ops, billing-ops, account-services,
    security-response, customer-success, integrations, general-support
- sla_minutes: target first-response time in minutes (range 1-10080).
  Suggested calibration: sev1=480, sev2=240, sev3=120, sev4=60, sev5=15
- reason: one to two sentences justifying the severity AND the team choice

Routing guidance:
- Calls dropping, audio quality, SIP/RTP problems → voice-platform
- Login, SSO, MFA, account lockout, PII concerns → account-services or security-response
- Charges, invoices, plan changes → billing-ops
- Webhooks, API integrations, third-party apps → integrations
- VIP/enterprise relationship signals → customer-success in parallel with the technical team

Respond with structured output matching the schema. No prose, no commentary, no markdown."""


def build_user_prompt(
    raw_message: str,
    classification: Classification,
    extracted_info: ExtractedInfo,
) -> str:
    """Render the classifier and extractor outputs alongside the raw message."""
    return (
        f"Customer support message:\n<<<\n{raw_message}\n>>>\n\n"
        f"Classification:\n"
        f"  category: {classification.category.value}\n"
        f"  priority: {classification.priority.value}\n"
        f"  confidence: {classification.confidence:.2f}\n"
        f"  reasoning: {classification.reasoning}\n\n"
        f"Extracted info:\n"
        f"  product_area: {extracted_info.product_area}\n"
        f"  issue_summary: {extracted_info.issue_summary}\n"
        f"  urgency: {extracted_info.urgency.value}\n"
        f"  suggested_tags: {extracted_info.suggested_tags}\n"
        f"  affected_features: {extracted_info.affected_features}"
    )
