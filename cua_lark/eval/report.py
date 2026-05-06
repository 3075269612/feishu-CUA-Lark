from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


def write_eval_reports(summary: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "summary.md"
    html_path = out_dir / "summary.html"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_summary(summary), encoding="utf-8")
    html_path.write_text(build_html_summary(summary), encoding="utf-8")
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


def build_html_summary(summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    rows = []
    for case in summary.get("cases", []):
        if not isinstance(case, dict):
            continue
        status = escape(str(case.get("status")))
        expected = "yes" if case.get("expected_met") else "no"
        trace_dir = escape(str(case.get("trace_dir") or ""))
        report_path = escape(str(case.get("report_path") or ""))
        screenshots = case.get("screenshot_paths") if isinstance(case.get("screenshot_paths"), list) else []
        screenshot_preview = _screenshot_preview(screenshots)
        rows.append(
            "<tr>"
            f"<td>{escape(str(case.get('id')))}</td>"
            f"<td>{escape(str(case.get('product')))}</td>"
            f"<td><span class=\"status status-{status}\">{status}</span></td>"
            f"<td>{escape(str(case.get('steps')))}</td>"
            f"<td>{escape(str(case.get('duration_sec')))}</td>"
            f"<td>{expected}</td>"
            f"<td><code>{trace_dir}</code></td>"
            f"<td><code>{report_path}</code></td>"
            f"<td>{screenshot_preview}</td>"
            "</tr>"
        )
    case_rows = "\n".join(rows) if rows else "<tr><td colspan=\"9\">No cases</td></tr>"
    failure_category = metrics.get("failure_category") if isinstance(metrics.get("failure_category"), dict) else {}
    failure_items = "".join(
        f"<li><code>{escape(str(key))}</code>: {escape(str(value))}</li>"
        for key, value in sorted(failure_category.items())
    ) or "<li>none</li>"
    agreement = metrics.get("visual_api_agreement") if isinstance(metrics.get("visual_api_agreement"), dict) else {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>FeishuWorld Eval Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2937; }}
    h1 {{ margin-bottom: 4px; }}
    .meta {{ color: #6b7280; margin-top: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; }}
    .metric strong {{ display: block; font-size: 22px; margin-top: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    code {{ font-size: 12px; white-space: pre-wrap; }}
    .status {{ font-weight: 600; }}
    .status-pass {{ color: #047857; }}
    .status-fail, .status-blocked {{ color: #b91c1c; }}
  </style>
</head>
<body>
  <h1>FeishuWorld Eval Report: {escape(str(summary.get("suite_id")))}</h1>
  <p class="meta">Profile: <code>{escape(str(summary.get("profile")))}</code> · Started: <code>{escape(str(summary.get("started_at")))}</code> · Finished: <code>{escape(str(summary.get("finished_at")))}</code></p>
  <p>Output dir: <code>{escape(str(summary.get("output_dir")))}</code></p>
  <section class="metrics">
    {_metric_card("total_cases", metrics.get("total_cases"))}
    {_metric_card("success_cases", metrics.get("success_cases"))}
    {_metric_card("failed_cases", metrics.get("failed_cases"))}
    {_metric_card("task_success_rate", metrics.get("task_success_rate"))}
    {_metric_card("step_success_rate", metrics.get("step_success_rate"))}
    {_metric_card("visual_api_agreement", agreement.get("rate"))}
  </section>
  <h2>Failure Categories</h2>
  <ul>{failure_items}</ul>
  <h2>Cases</h2>
  <table>
    <thead><tr><th>Case</th><th>Product</th><th>Status</th><th>Steps</th><th>Duration</th><th>Expected</th><th>Trace</th><th>Report</th><th>Screenshots</th></tr></thead>
    <tbody>{case_rows}</tbody>
  </table>
</body>
</html>
"""


def _metric_card(label: str, value: Any) -> str:
    return f"<div class=\"metric\"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>"


def _screenshot_preview(screenshots: list[Any]) -> str:
    paths = [str(path) for path in screenshots if isinstance(path, str) and path]
    if not paths:
        return ""
    first = escape(paths[0])
    extra = len(paths) - 1
    suffix = f"<br><span class=\"meta\">+{extra} more</span>" if extra > 0 else ""
    return f"<code>{first}</code>{suffix}"
