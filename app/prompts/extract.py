"""Prompt for the extractor node — produces an `ExtractedInfo` instance.

Receives the already-determined category as soft context so the extractor
focuses on category-relevant facts. `category` is optional to keep the
prompt usable in unit tests that exercise this node in isolation.
"""

from __future__ import annotations

from app.domain.models import IssueCategory
from app.prompts._sanitize import sanitize_user_input

TEMPERATURE = 0.0

SYSTEM_PROMPT = """You are a senior support data analyst at VoiceSpin (telephony for call centers).

Your task: extract structured facts from the customer message.

Output fields:
- product_area: short snake_case tag for the affected product surface
  (e.g. outbound_dialer, inbound_ivr, sip_trunk, call_recording, agent_desktop,
   reporting, billing, account_management, integrations, mobile_app)
- issue_summary: one to two sentence canonical description of what is wrong or asked
  (rewrite — do NOT copy the customer's wording verbatim)
- urgency: not_urgent | normal | urgent | immediate — based on the customer's stated
  time pressure (deadlines, "asap", "right now"); ignore tone or politeness
- suggested_tags: 1-8 short kebab-case tags useful for routing and search
  (e.g. ["sip", "outbound", "dropped-call"])
- affected_features: optional list of specific feature names mentioned
  (omit when none clearly named)

Examples:

[Message] "Calls dropping ~3 seconds after connect on our outbound campaigns. Started today around 9am Eastern. We're a SIP-trunk customer."
[Output] product_area=outbound_dialer, issue_summary="Outbound calls disconnect approximately 3 seconds after connect, starting 09:00 ET today.", urgency=urgent, suggested_tags=["sip", "outbound", "dropped-call", "call-quality"], affected_features=["outbound campaigns", "SIP trunk"]

[Message] "Can someone send me the invoice for last month? I think we got billed twice."
[Output] product_area=billing, issue_summary="Customer requests last month's invoice and suspects a double charge.", urgency=normal, suggested_tags=["billing", "invoice", "double-charge"], affected_features=[]

Respond with structured output matching the schema. No prose, no commentary, no markdown."""


def build_user_prompt(raw_message: str, category: IssueCategory | None = None) -> str:
    """Wrap the message and (optionally) the already-decided category."""
    category_hint = (
        f"Pre-classified category (for context only — extract independently): {category.value}\n\n"
        if category is not None
        else ""
    )
    safe = sanitize_user_input(raw_message)
    return f"{category_hint}Customer support message:\n<<<\n{safe}\n>>>"
