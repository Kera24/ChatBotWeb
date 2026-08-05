"""Shared terminal/JSON rendering for a completed evaluation run, used by both
`eval:report` (an existing run) and `eval:launch` (a fresh run it just executed).
"""

from __future__ import annotations

from app.db.models import EvaluationRun
from app.evaluation.gate import GateVerdict
from app.evaluation.metrics.aggregate import RunSummary


def render_json_report(run: EvaluationRun, summary: RunSummary, gate: GateVerdict) -> dict:
    return {
        "run_id": run.id,
        "status": run.status,
        "mode": run.mode,
        "dataset_id": run.dataset_id,
        "dataset_version": run.dataset_version,
        "provider_key": run.provider_key,
        "model_key": run.model_key,
        "prompt_key": run.prompt_key,
        "prompt_version": run.prompt_version,
        "policy": run.policy_snapshot_json,
        "summary": summary.as_dict(),
        "gate": gate.as_dict(),
    }


def render_text_report(run: EvaluationRun, summary: RunSummary, gate: GateVerdict) -> str:
    lines = [
        f"Evaluation run {run.id} ({run.status}, mode={run.mode})",
        f"Dataset {run.dataset_id} @ version {run.dataset_version}",
        f"Model: {run.model_key or '-'} / Provider: {run.provider_key or '-'} / Prompt: {run.prompt_key or '-'}@{run.prompt_version or '-'}",
        "",
        f"Cases:            {summary.total_cases}",
        f"Passed:           {summary.passed_cases}",
        f"Failed:           {summary.failed_cases}",
        f"Hard failures:    {summary.hard_failure_cases}",
        f"Pass rate:        {summary.pass_rate:.1%}",
        "",
        f"Retrieval hit rate:                    {_fmt_pct(summary.retrieval_hit_rate)}",
        f"Citation coverage:                      {_fmt_pct(summary.citation_coverage)}",
        f"Fallback rate on answerable cases:       {_fmt_pct(summary.fallback_rate_on_answerable)}",
        f"Correct fallback on unanswerable cases:  {_fmt_pct(summary.correct_fallback_rate_on_unanswerable)}",
        f"Average precision@k:                     {_fmt_pct(summary.average_precision_at_k)}",
        f"Average duplicate-context rate:           {_fmt_pct(summary.average_duplicate_context_rate)}",
        f"Unauthorised-source rate:                {_fmt_pct(summary.unauthorised_source_rate)}",
        f"Invalid-citation rate:                    {_fmt_pct(summary.invalid_citation_rate)}",
        f"Latency p50 / p95 (ms):                  {_fmt_ms(summary.latency_p50_ms)} / {_fmt_ms(summary.latency_p95_ms)}",
        f"Total tokens (prompt/completion/total):  {summary.total_prompt_tokens}/{summary.total_completion_tokens}/{summary.total_tokens}",
        "",
        "Category breakdown:",
    ]
    for category, counts in sorted(summary.category_breakdown.items()):
        lines.append(f"  {category:<28} total={counts['total']:<3} passed={counts['passed']:<3} failed={counts['failed']:<3} hard_failure={counts['hard_failure']}")

    if summary.failed_cases_list:
        lines.append("")
        lines.append("Failed cases:")
        for case in summary.failed_cases_list:
            marker = "HARD FAILURE" if case.hard_failure else "failed"
            lines.append(f"  [{marker}] ({case.category}) {case.question!r}")
            lines.append(f"      reasons: {', '.join(case.failure_reasons) or '-'}")

    lines.append("")
    lines.append(f"Gate: {'PASSED' if gate.passed else 'FAILED'}")
    for reason in gate.reasons:
        lines.append(f"  - {reason}")

    return "\n".join(lines)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _fmt_ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"
