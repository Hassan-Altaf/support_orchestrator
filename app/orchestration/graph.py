"""Graph assembly: wires the 5 nodes into the spec topology.

::

    START -> classify -> extract -> [classification.escalation_required?]
                                          yes -> escalation -+
                                          no  ----------+    |
                                                        v    v
                                                customer_response
                                                        |
                                                        v
                                                internal_summary
                                                        |
                                                        v
                                                       END

Routing rationale
-----------------
`customer_response` comes AFTER `escalation` (on the yes branch) because
the reply copy should be able to reference escalation status ("we have
prioritised your ticket"). `internal_summary` runs last so it can
consume every upstream artifact for the handoff packet.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import Settings
from app.llm.provider import LLMProvider
from app.orchestration.nodes import (
    make_classifier_node,
    make_customer_response_node,
    make_escalation_node,
    make_extractor_node,
    make_internal_summary_node,
)
from app.orchestration.state import SupportState

# Node names — constants so tests/observability can reference without
# magic strings, and rename refactors find every callsite.
CLASSIFY = "classify"
EXTRACT = "extract"
ESCALATION = "escalation"
CUSTOMER_RESPONSE = "customer_response"
INTERNAL_SUMMARY = "internal_summary"

# Conditional-edge keys — kept distinct from node names so the routing
# decision ("escalate?") is decoupled from the destination ("escalation").
RouteAfterExtract = Literal["escalate", "skip_escalation"]


def route_after_extract(state: SupportState) -> RouteAfterExtract:
    """Decide whether the escalation node runs.

    Public (no leading underscore) so unit tests can exercise the
    routing decision in isolation from the compiled graph.
    """
    classification = state.get("classification")
    if classification is not None and classification.escalation_required:
        return "escalate"
    return "skip_escalation"


def compile_graph(provider: LLMProvider, settings: Settings) -> CompiledStateGraph:
    """Build and compile the support-orchestration graph.

    All five node factories are invoked with the supplied provider and
    `settings.max_retries`, so the compiled graph is fully self-contained
    and can be invoked any number of times without re-wiring.
    """
    max_retries = settings.max_retries

    builder: StateGraph = StateGraph(SupportState)

    # LangGraph's `add_node` stubs require the callable to return the full
    # state type, but at runtime it accepts partial-state dicts (which the
    # framework merges via the field reducers). Our nodes return deltas
    # like `{"classification": ..., "trace": [...]}` on purpose; the
    # `call-overload` ignore is the standard workaround for this typing gap.
    builder.add_node(CLASSIFY, make_classifier_node(provider, max_retries))  # type: ignore[call-overload]
    builder.add_node(EXTRACT, make_extractor_node(provider, max_retries))  # type: ignore[call-overload]
    builder.add_node(ESCALATION, make_escalation_node(provider, max_retries))  # type: ignore[call-overload]
    builder.add_node(CUSTOMER_RESPONSE, make_customer_response_node(provider, max_retries))  # type: ignore[call-overload]
    builder.add_node(INTERNAL_SUMMARY, make_internal_summary_node(provider, max_retries))  # type: ignore[call-overload]

    builder.add_edge(START, CLASSIFY)
    builder.add_edge(CLASSIFY, EXTRACT)
    builder.add_conditional_edges(
        EXTRACT,
        route_after_extract,
        {
            "escalate": ESCALATION,
            "skip_escalation": CUSTOMER_RESPONSE,
        },
    )
    builder.add_edge(ESCALATION, CUSTOMER_RESPONSE)
    builder.add_edge(CUSTOMER_RESPONSE, INTERNAL_SUMMARY)
    builder.add_edge(INTERNAL_SUMMARY, END)

    return builder.compile()
