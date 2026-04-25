from __future__ import annotations

from pathlib import Path

from cua_lark.task.schema import Trace


def build_markdown_report(trace: Trace) -> str:
    step_events = [event for event in trace.events if event.event_type == "step"]
    lines = [
        f"# CUA-Lark Run Report: {trace.task_id}",
        "",
        f"- Run ID: `{trace.run_id}`",
        f"- Status: `{trace.status}`",
        f"- Trace dir: `{trace.trace_dir}`",
        f"- Steps: `{len(step_events)}`",
        "",
        "## Steps",
        "",
    ]
    for event in step_events:
        action = event.action.type if event.action else "none"
        verdict = event.verdict.status if event.verdict else "none"
        reason = event.verdict.reason if event.verdict else ""
        lines.append(f"- Step {event.step_index}: action `{action}`, verdict `{verdict}`. {reason}")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(trace: Trace, path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_markdown_report(trace), encoding="utf-8")
    return report_path
