"""User-input delimiter sanitization for prompt construction.

Every node's `build_user_prompt` wraps the customer's message between `<<<`
and `>>>` so the LLM can see a clear content/instruction boundary. A
customer (or an attacker) could embed `>>>` (or a leading `<<<`) in their
own message to break out of the envelope and inject pseudo-instructions
after it.

`sanitize_user_input` collapses those delimiters into visually-similar but
non-meaningful sequences (`>> >`, `<< <`) so the envelope can't be closed
prematurely. We deliberately keep this mechanical and minimal — the real
defense is structured-output validation downstream, not perfect string
escaping.
"""

from __future__ import annotations


def sanitize_user_input(text: str) -> str:
    """Neutralize the `<<<` / `>>>` envelope delimiters in customer text."""
    if not text:
        return text
    return text.replace(">>>", ">> >").replace("<<<", "<< <")
