"""Prompt modules — one per orchestration node.

Each module exports:
* `SYSTEM_PROMPT: str`     — role, output contract, optional few-shots
* `TEMPERATURE: float`     — node-specific sampling temperature
* `build_user_prompt(...)` — wraps the runtime inputs into a user message
"""

from __future__ import annotations

from app.prompts import (
    classify,
    customer_response,
    escalation,
    extract,
    internal_summary,
)

__all__ = [
    "classify",
    "customer_response",
    "escalation",
    "extract",
    "internal_summary",
]
