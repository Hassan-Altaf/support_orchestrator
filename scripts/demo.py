"""CLI demo for the support orchestration pipeline.

Usage::

    python scripts/demo.py                          # real LLM, runs all 5 samples
    python scripts/demo.py --mock                   # MockProvider, no API key needed
    python scripts/demo.py --mock --save            # also write samples/outputs/*.json
    python scripts/demo.py --message "..."          # single ad-hoc message
    python scripts/demo.py --mock --message "..."   # ad-hoc message with mock

When `--mock` is used with a known sample (matched by id or message), the
MockProvider is pre-queued with hand-crafted responses that match the
sample's expected fields — so the reviewer sees a realistic-looking
pipeline run end-to-end without spending API tokens.

For ad-hoc messages under `--mock`, a single generic canned response is
used so the pipeline still completes.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Force mock provider BEFORE importing app modules in case the user runs
# `--mock` without an OPENAI_API_KEY in env.
if "--mock" in sys.argv:
    os.environ["LLM_PROVIDER"] = "mock"

from app.config import Settings
from app.domain.models import (
    Classification,
    CustomerResponseDraft,
    EscalationContext,
    ExtractedInfo,
    InternalSummary,
    IssueCategory,
    Priority,
    Urgency,
)
from app.llm import get_llm_provider
from app.llm.mock_provider import MockProvider
from app.llm.provider import LLMProvider
from app.orchestration.graph import compile_graph
from app.orchestration.state import initial_state

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_PATH = REPO_ROOT / "tests" / "fixtures" / "sample_messages.json"
OUTPUTS_DIR = REPO_ROOT / "samples" / "outputs"

console = Console()
app = typer.Typer(help="Support orchestrator demo runner.", no_args_is_help=False)


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:max_len] or "message"


def _load_samples() -> list[dict[str, Any]]:
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


def _queue_mock_for_scenario(provider: MockProvider, expected: dict[str, Any]) -> None:
    """Hand-craft a realistic canned response set matching a scenario's labels."""
    escalate = bool(expected.get("escalation_required", False))
    category = IssueCategory(expected.get("category", "other"))
    priority = Priority(expected.get("priority", "medium"))
    urgency = Urgency(expected.get("urgency", "normal"))

    provider.queue_for(
        "Classification",
        Classification(
            category=category,
            priority=priority,
            escalation_required=escalate,
            confidence=0.9,
            reasoning=f"Demo classification for category={category.value}, priority={priority.value}.",
        ),
    )
    provider.queue_for(
        "ExtractedInfo",
        ExtractedInfo(
            product_area=_product_area_for(category),
            issue_summary=(
                "Demo extraction. In a real run this would summarize the customer message "
                "in 1-2 canonical sentences."
            ),
            urgency=urgency,
            suggested_tags=[category.value, urgency.value],
        ),
    )
    if escalate:
        provider.queue_for(
            "EscalationContext",
            EscalationContext(
                severity_level=5 if priority == Priority.CRITICAL else 4,
                suggested_team=_team_for(category),
                sla_minutes=15 if priority == Priority.CRITICAL else 60,
                reason=f"Escalation justified: priority={priority.value}, category={category.value}.",
            ),
        )
    provider.queue_for(
        "CustomerResponseDraft",
        CustomerResponseDraft(
            response=(
                "Thanks for letting us know. We have received your message and our team is "
                "looking into it. We will follow up shortly with more information. "
                "- the VoiceSpin team"
            )
        ),
    )
    provider.queue_for(
        "InternalSummary",
        InternalSummary(
            headline=f"Demo handoff for {category.value} ({priority.value})",
            customer_intent=f"Resolve a {category.value} issue.",
            diagnostic_notes="Demo run with mocked LLM outputs - no real diagnostic content.",
            recommended_actions=["Triage with on-call agent", "Review related tickets"],
            handoff_team=_team_for(category),
        ),
    )


def _product_area_for(category: IssueCategory) -> str:
    return {
        IssueCategory.TECHNICAL_BUG: "agent_desktop",
        IssueCategory.OUTAGE: "sip_trunk",
        IssueCategory.BILLING: "billing",
        IssueCategory.ACCOUNT_ACCESS: "account_management",
        IssueCategory.HOW_TO: "agent_desktop",
        IssueCategory.FEATURE_REQUEST: "reporting",
        IssueCategory.OTHER: "unknown",
    }[category]


def _team_for(category: IssueCategory) -> str:
    return {
        IssueCategory.TECHNICAL_BUG: "voice-platform",
        IssueCategory.OUTAGE: "voice-platform",
        IssueCategory.BILLING: "billing-ops",
        IssueCategory.ACCOUNT_ACCESS: "account-services",
        IssueCategory.HOW_TO: "general-support",
        IssueCategory.FEATURE_REQUEST: "general-support",
        IssueCategory.OTHER: "general-support",
    }[category]


def _build_provider(use_mock: bool, settings: Settings) -> LLMProvider:
    if use_mock:
        return MockProvider()
    return get_llm_provider(settings)


def _render_result(scenario_id: str, raw_message: str, final: dict[str, Any]) -> None:
    """Pretty-print one orchestration result to the console."""
    classification = final["classification"]
    extracted = final["extracted_info"]
    esc = final.get("escalation_context")
    summary = final["internal_summary"]

    console.print(
        Panel(raw_message, title=f"[bold]{scenario_id}[/] - customer message", border_style="cyan")
    )

    facts = Table.grid(padding=(0, 2))
    facts.add_column(style="bold")
    facts.add_column()
    facts.add_row("category", classification.category.value)
    facts.add_row("priority", classification.priority.value)
    facts.add_row("confidence", f"{classification.confidence:.2f}")
    facts.add_row("escalation_required", str(classification.escalation_required))
    facts.add_row("product_area", extracted.product_area)
    facts.add_row("urgency", extracted.urgency.value)
    facts.add_row("suggested_tags", ", ".join(extracted.suggested_tags))
    if esc is not None:
        facts.add_row("escalation_team", esc.suggested_team)
        facts.add_row("severity", str(esc.severity_level))
        facts.add_row("sla_minutes", str(esc.sla_minutes))
    console.print(Panel(facts, title="classification + extraction", border_style="green"))

    console.print(Panel(final["customer_response"], title="customer reply", border_style="magenta"))

    handoff = Table.grid(padding=(0, 2))
    handoff.add_column(style="bold")
    handoff.add_column()
    handoff.add_row("headline", summary.headline)
    handoff.add_row("intent", summary.customer_intent)
    handoff.add_row("team", summary.handoff_team)
    handoff.add_row("actions", "\n".join(f"- {a}" for a in summary.recommended_actions))
    console.print(Panel(handoff, title="internal handoff", border_style="yellow"))

    trace_tbl = Table(title="processing_trace", show_header=True)
    trace_tbl.add_column("node")
    trace_tbl.add_column("outcome")
    trace_tbl.add_column("duration_ms", justify="right")
    trace_tbl.add_column("detail")
    for entry in final["trace"]:
        trace_tbl.add_row(entry.node, entry.outcome, str(entry.duration_ms), entry.detail or "")
    console.print(trace_tbl)

    if final["errors"]:
        console.print(
            Panel("\n".join(final["errors"]), title="recovered_errors", border_style="red")
        )
    console.print()


def _save_output(slug: str, scenario_id: str, message: str, final: dict[str, Any]) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "scenario_id": scenario_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "raw_message": message,
        "classification": final["classification"].model_dump(mode="json"),
        "extracted_info": final["extracted_info"].model_dump(mode="json"),
        "escalation_context": (
            final["escalation_context"].model_dump(mode="json")
            if final.get("escalation_context") is not None
            else None
        ),
        "customer_response": final["customer_response"],
        "internal_summary": final["internal_summary"].model_dump(mode="json"),
        "processing_trace": [t.model_dump(mode="json") for t in final["trace"]],
        "recovered_errors": final["errors"],
    }
    path = OUTPUTS_DIR / f"{slug}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


async def _run_scenario(
    settings: Settings,
    use_mock: bool,
    scenario_id: str,
    message: str,
    expected: dict[str, Any] | None,
    save: bool,
) -> None:
    provider = _build_provider(use_mock, settings)
    if use_mock and isinstance(provider, MockProvider):
        if expected is not None:
            _queue_mock_for_scenario(provider, expected)
        else:
            # ad-hoc message: produce generic canned responses
            _queue_mock_for_scenario(
                provider,
                {
                    "category": "other",
                    "priority": "medium",
                    "escalation_required": False,
                    "urgency": "normal",
                },
            )

    graph = compile_graph(provider, settings)
    final = await graph.ainvoke(initial_state(message, scenario_id))
    _render_result(scenario_id, message, final)

    if save:
        path = _save_output(_slugify(scenario_id), scenario_id, message, final)
        console.print(f"  [dim]saved -> {path.relative_to(REPO_ROOT)}[/]\n")


@app.command()
def run(
    mock: bool = typer.Option(False, "--mock", help="Use MockProvider (no API key needed)."),
    save: bool = typer.Option(False, "--save", help="Write JSON outputs to samples/outputs/."),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Process a single ad-hoc message instead of the samples."
    ),
) -> None:
    """Run the demo. Defaults to all 5 bundled sample messages."""
    settings = Settings()  # reads .env if present (needed for real-provider API keys)

    if message is not None:
        console.rule("[bold]Ad-hoc message[/]")
        asyncio.run(
            _run_scenario(
                settings=settings,
                use_mock=mock,
                scenario_id="ad_hoc",
                message=message,
                expected=None,
                save=save,
            )
        )
        return

    samples = _load_samples()
    console.rule(f"[bold]Demo - {len(samples)} sample messages[/]" + (" (MOCK)" if mock else ""))
    for sample in samples:
        asyncio.run(
            _run_scenario(
                settings=settings,
                use_mock=mock,
                scenario_id=sample["id"],
                message=sample["message"],
                expected=sample.get("expected"),
                save=save,
            )
        )


if __name__ == "__main__":
    app()
