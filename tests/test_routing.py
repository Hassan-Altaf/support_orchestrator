"""Focused conditional-edge tests for `route_after_extract`.

Kept separate from the full-graph tests so a routing bug is identified
to the exact predicate without running the whole pipeline.
"""

from __future__ import annotations

from app.orchestration.graph import route_after_extract
from app.orchestration.state import initial_state


class TestRouteAfterExtract:
    def test_escalation_required_true_routes_to_escalate(self, good_classification) -> None:
        state = initial_state("msg", "req-1")
        state["classification"] = good_classification(escalation_required=True)
        assert route_after_extract(state) == "escalate"

    def test_escalation_required_false_routes_to_skip(self, good_classification) -> None:
        state = initial_state("msg", "req-2")
        state["classification"] = good_classification(escalation_required=False)
        assert route_after_extract(state) == "skip_escalation"

    def test_missing_classification_defaults_to_skip(self) -> None:
        # Defensive: should not crash if upstream catastrophically failed.
        state = initial_state("msg", "req-3")
        assert state["classification"] is None
        assert route_after_extract(state) == "skip_escalation"
