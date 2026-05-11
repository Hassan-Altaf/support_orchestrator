"""Orchestration node factories.

Each `make_*_node(provider, max_retries)` returns an `async (state) -> dict`
callable suitable for `graph.add_node(...)` in Stage 7.
"""

from __future__ import annotations

from app.orchestration.nodes.classifier import make_classifier_node
from app.orchestration.nodes.customer_response import make_customer_response_node
from app.orchestration.nodes.escalation import make_escalation_node
from app.orchestration.nodes.extractor import make_extractor_node
from app.orchestration.nodes.internal_summary import make_internal_summary_node

__all__ = [
    "make_classifier_node",
    "make_customer_response_node",
    "make_escalation_node",
    "make_extractor_node",
    "make_internal_summary_node",
]
