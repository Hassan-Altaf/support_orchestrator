"""Evaluation harness for the support classifier.

Runs every message in `tests/fixtures/eval_set.json` through the compiled
graph and reports:
* overall accuracy on category and priority
* per-category precision / recall / F1
* average confidence (overall + per-correct / per-incorrect)
* a confusion matrix (predicted vs expected category)

Outputs a human-readable markdown report at `samples/eval_report.md` and
prints a summary to the console.

Usage::

    python scripts/eval.py            # real LLM provider (requires API key)
    python scripts/eval.py --mock     # MockProvider returning the expected labels
                                       (use to verify harness mechanics)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

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
EVAL_SET_PATH = REPO_ROOT / "tests" / "fixtures" / "eval_set.json"
REPORT_PATH = REPO_ROOT / "samples" / "eval_report.md"

console = Console()
app = typer.Typer(help="Eval harness for the support classifier.")


def _build_provider(use_mock: bool, settings: Settings) -> LLMProvider:
    if use_mock:
        return MockProvider()
    return get_llm_provider(settings)


def _queue_mock_for_label(provider: MockProvider, expected: dict[str, str]) -> None:
    """Queue mock responses that produce the expected label (so --mock => 100% accuracy)."""
    category = IssueCategory(expected["category"])
    priority = Priority(expected["priority"])
    provider.queue_for(
        "Classification",
        Classification(
            category=category,
            priority=priority,
            escalation_required=priority == Priority.CRITICAL,
            confidence=0.9,
            reasoning="Mock prediction returns the labeled values for harness verification.",
        ),
    )
    provider.queue_for(
        "ExtractedInfo",
        ExtractedInfo(
            product_area="mock",
            issue_summary="mock extraction for eval harness verification.",
            urgency=Urgency.NORMAL,
            suggested_tags=["mock"],
        ),
    )
    if priority == Priority.CRITICAL:
        provider.queue_for(
            "EscalationContext",
            EscalationContext(
                severity_level=5,
                suggested_team="voice-platform",
                sla_minutes=15,
                reason="Mock escalation for harness verification of critical paths.",
            ),
        )
    provider.queue_for(
        "CustomerResponseDraft",
        CustomerResponseDraft(
            response="Thanks for reaching out. Our team is investigating. - the VoiceSpin team"
        ),
    )
    provider.queue_for(
        "InternalSummary",
        InternalSummary(
            headline="Mock summary for eval harness",
            customer_intent="N/A - harness run",
            diagnostic_notes="Mock run; no real diagnostic content.",
            recommended_actions=["N/A - mock"],
            handoff_team="general-support",
        ),
    )


async def _run_eval(use_mock: bool) -> dict[str, Any]:
    """Run the eval set and return aggregated metrics."""
    settings = Settings()  # reads .env if present (needed for real-provider API keys)
    eval_set: list[dict[str, Any]] = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    correct_category = 0
    correct_priority = 0
    confidences: list[float] = []
    confidences_correct: list[float] = []
    confidences_wrong: list[float] = []
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in eval_set:
        expected_cat = item["expected"]["category"]
        expected_pri = item["expected"]["priority"]

        provider = _build_provider(use_mock, settings)
        if use_mock and isinstance(provider, MockProvider):
            _queue_mock_for_label(provider, item["expected"])
        graph = compile_graph(provider, settings)

        final = await graph.ainvoke(initial_state(item["message"], item["id"]))
        classification: Classification = final["classification"]
        pred_cat = classification.category.value
        pred_pri = classification.priority.value

        cat_ok = pred_cat == expected_cat
        pri_ok = pred_pri == expected_pri
        correct_category += int(cat_ok)
        correct_priority += int(pri_ok)
        confidences.append(classification.confidence)
        (confidences_correct if cat_ok else confidences_wrong).append(classification.confidence)
        confusion[expected_cat][pred_cat] += 1

        rows.append(
            {
                "id": item["id"],
                "message_preview": item["message"][:80],
                "expected_category": expected_cat,
                "predicted_category": pred_cat,
                "category_ok": cat_ok,
                "expected_priority": expected_pri,
                "predicted_priority": pred_pri,
                "priority_ok": pri_ok,
                "confidence": classification.confidence,
            }
        )

    n = len(eval_set)
    # Per-category precision / recall / F1
    per_category = _compute_per_category(rows)

    return {
        "n": n,
        "accuracy_category": correct_category / n if n else 0.0,
        "accuracy_priority": correct_priority / n if n else 0.0,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "avg_confidence_correct": (
            sum(confidences_correct) / len(confidences_correct) if confidences_correct else 0.0
        ),
        "avg_confidence_wrong": (
            sum(confidences_wrong) / len(confidences_wrong) if confidences_wrong else 0.0
        ),
        "per_category": per_category,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "rows": rows,
    }


def _compute_per_category(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Compute precision / recall / F1 per category."""
    categories = {r["expected_category"] for r in rows} | {r["predicted_category"] for r in rows}
    result: dict[str, dict[str, float]] = {}
    for cat in sorted(categories):
        tp = sum(
            1 for r in rows if r["expected_category"] == cat and r["predicted_category"] == cat
        )
        fp = sum(
            1 for r in rows if r["expected_category"] != cat and r["predicted_category"] == cat
        )
        fn = sum(
            1 for r in rows if r["expected_category"] == cat and r["predicted_category"] != cat
        )
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        result[cat] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn,
        }
    return result


def _render_report_md(metrics: dict[str, Any], use_mock: bool) -> str:
    """Build the markdown report body."""
    lines: list[str] = []
    lines.append("# Support Classifier - Eval Report")
    lines.append("")
    lines.append(f"- Generated: `{datetime.now(UTC).isoformat()}`")
    lines.append(f"- Provider: `{'mock' if use_mock else 'real'}`")
    lines.append(f"- Eval set size: **{metrics['n']}**")
    lines.append("")

    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- Category accuracy: **{metrics['accuracy_category']:.1%}**")
    lines.append(f"- Priority accuracy: **{metrics['accuracy_priority']:.1%}**")
    lines.append(f"- Average confidence (overall): {metrics['avg_confidence']:.2f}")
    lines.append(f"- Average confidence on correct: {metrics['avg_confidence_correct']:.2f}")
    lines.append(f"- Average confidence on wrong: {metrics['avg_confidence_wrong']:.2f}")
    lines.append("")

    lines.append("## Per-category precision / recall / F1")
    lines.append("")
    lines.append("| category | precision | recall | F1 | support |")
    lines.append("|---|---:|---:|---:|---:|")
    for cat, m in metrics["per_category"].items():
        lines.append(
            f"| {cat} | {m['precision']:.2f} | {m['recall']:.2f} | "
            f"{m['f1']:.2f} | {int(m['support'])} |"
        )
    lines.append("")

    lines.append("## Confusion matrix (expected -> predicted)")
    lines.append("")
    cats = sorted(set(metrics["confusion"]) | {p for d in metrics["confusion"].values() for p in d})
    header = "| expected \\ predicted | " + " | ".join(cats) + " |"
    sep = "|---|" + "|".join(["---:"] * len(cats)) + "|"
    lines.append(header)
    lines.append(sep)
    for exp in cats:
        row = [exp] + [str(metrics["confusion"].get(exp, {}).get(pred, 0)) for pred in cats]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## Per-message detail")
    lines.append("")
    lines.append(
        "| id | expected cat | predicted cat | ok | expected pri | predicted pri | ok | conf |"
    )
    lines.append("|---|---|---|:-:|---|---|:-:|---:|")
    for r in metrics["rows"]:
        lines.append(
            f"| {r['id']} | {r['expected_category']} | {r['predicted_category']} | "
            f"{'OK' if r['category_ok'] else 'NO'} | {r['expected_priority']} | {r['predicted_priority']} | "
            f"{'OK' if r['priority_ok'] else 'NO'} | {r['confidence']:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_summary_console(metrics: dict[str, Any], use_mock: bool) -> None:
    console.rule(f"[bold]Eval summary[/] (provider={'mock' if use_mock else 'real'})")
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("eval set size", str(metrics["n"]))
    summary.add_row("category accuracy", f"{metrics['accuracy_category']:.1%}")
    summary.add_row("priority accuracy", f"{metrics['accuracy_priority']:.1%}")
    summary.add_row("avg confidence (overall)", f"{metrics['avg_confidence']:.2f}")
    summary.add_row("avg confidence (correct)", f"{metrics['avg_confidence_correct']:.2f}")
    summary.add_row("avg confidence (wrong)", f"{metrics['avg_confidence_wrong']:.2f}")
    console.print(summary)


@app.command()
def run(
    mock: bool = typer.Option(
        False, "--mock", help="Use MockProvider (verifies harness mechanics)."
    ),
) -> None:
    """Run the eval set and write samples/eval_report.md."""
    metrics = asyncio.run(_run_eval(use_mock=mock))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render_report_md(metrics, mock), encoding="utf-8")
    _render_summary_console(metrics, mock)
    console.print(f"\n[green]report written to[/] [bold]{REPORT_PATH.relative_to(REPO_ROOT)}[/]")


if __name__ == "__main__":
    app()
