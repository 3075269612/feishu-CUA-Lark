from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_eval_reports(summary: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_summary(summary), encoding="utf-8")
    return json_path, md_path


def build_markdown_summary(summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    lines = [
        f"# FeishuWorld Eval Report: {summary.get('suite_id')}",
        "",
        f"- Profile: `{summary.get('profile')}`",
        f"- Started: `{summary.get('started_at')}`",
        f"- Finished: `{summary.get('finished_at')}`",
        f"- Output dir: `{summary.get('output_dir')}`",
        "",
        "## Metrics",
        "",
        f"- total_cases: `{metrics.get('total_cases')}`",
        f"- success_cases: `{metrics.get('success_cases')}`",
        f"- manual_cases: `{metrics.get('manual_cases')}`",
        f"- failed_cases: `{metrics.get('failed_cases')}`",
        f"- task_success_rate: `{metrics.get('task_success_rate')}`",
        f"- step_success_rate: `{metrics.get('step_success_rate')}`",
        f"- mean_steps: `{metrics.get('mean_steps')}`",
        f"- mean_time: `{metrics.get('mean_time')}`",
        f"- recovery_count: `{metrics.get('recovery_count')}`",
        "",
        "## Failure Categories",
        "",
    ]
    failure_category = metrics.get("failure_category") if isinstance(metrics.get("failure_category"), dict) else {}
    if failure_category:
        for key, value in sorted(failure_category.items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- none")

    agreement = metrics.get("visual_api_agreement")
    if isinstance(agreement, dict):
        lines.extend(
            [
                "",
                "## Visual/API Agreement",
                "",
                f"- comparable_cases: `{agreement.get('comparable_cases')}`",
                f"- agreement_cases: `{agreement.get('agreement_cases')}`",
                f"- rate: `{agreement.get('rate')}`",
            ]
        )

    lines.extend(["", "## Cases", ""])
    for case in summary.get("cases", []):
        if not isinstance(case, dict):
            continue
        lines.append(
            "- "
            f"`{case.get('id')}` "
            f"product `{case.get('product')}`, "
            f"status `{case.get('status')}`, "
            f"steps `{case.get('steps')}`, "
            f"duration `{case.get('duration_sec')}`, "
            f"expected `{case.get('expected_met')}`"
        )
    lines.append("")
    return "\n".join(lines)
