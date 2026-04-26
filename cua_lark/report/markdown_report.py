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
    ]
    if trace.metadata:
        lines.extend(["", "## Run Metadata", ""])
        for key, value in trace.metadata.items():
            if key == "verification_summary":
                continue
            lines.append(f"- {key}: `{value}`")
    verification_summary = trace.metadata.get("verification_summary")
    if isinstance(verification_summary, dict):
        lines.extend(["", "## Verification Summary", ""])
        lines.append(f"- evidence_schema_version: `{verification_summary.get('evidence_schema_version')}`")
        lines.append(f"- final_status: `{verification_summary.get('final_status')}`")
        lines.append(f"- reason: `{verification_summary.get('reason')}`")
        lines.extend(["", "### Verifier Evidence", ""])
        for evidence in verification_summary.get("evidences", []):
            if not isinstance(evidence, dict):
                continue
            source = evidence.get("source")
            status = evidence.get("status")
            reason = evidence.get("reason")
            confidence = evidence.get("confidence")
            lines.append(f"- `{source}`: `{status}` ({reason}), confidence `{confidence}`")
        checklist = verification_summary.get("manual_checklist") or []
        if checklist:
            lines.extend(["", "### Manual Verification Checklist", ""])
            for item in checklist:
                lines.append(f"- {item}")
    lines.extend(["", "## Steps", ""])
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
