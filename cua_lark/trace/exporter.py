from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from cua_lark.tool_registry import build_tool_registry, write_mcp_manifest


DEFAULT_STATUSES = ("pass",)


def export_trace_datasets(
    runs_dir: str | Path,
    output_dir: str | Path,
    statuses: tuple[str, ...] = DEFAULT_STATUSES,
    include_products: tuple[str, ...] | None = None,
    max_runs: int | None = None,
) -> dict[str, Any]:
    """Export trace-derived datasets for Phase 8 tooling.

    The exporter records screenshot paths and metadata only. It intentionally does
    not copy screenshots or other real-run binary artifacts.
    """
    runs_path = Path(runs_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    status_filter = {status.strip() for status in statuses if status.strip()}
    product_filter = {product.strip() for product in include_products or () if product.strip()}
    eval_index = _load_eval_index(runs_path)

    trace_records: list[dict[str, Any]] = []
    grounding_records: list[dict[str, Any]] = []
    fewshot_records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    product_counts: Counter[str] = Counter()
    skipped = 0

    trace_paths = discover_trace_files(runs_path)
    for trace_path in trace_paths:
        parsed = parse_trace_run(trace_path, eval_index=eval_index)
        status = str(parsed.get("status") or "unknown")
        product = str(parsed.get("product") or "unknown")
        status_counts[status] += 1

        if status_filter and status not in status_filter:
            skipped += 1
            continue
        if product_filter and product not in product_filter:
            skipped += 1
            continue
        if max_runs is not None and len(trace_records) >= max_runs:
            skipped += 1
            continue

        trace_records.append(_trace_dataset_record(parsed))
        product_counts[product] += 1
        grounding_records.extend(_grounding_records(parsed))
        fewshot = _fewshot_record(parsed)
        if fewshot is not None:
            fewshot_records.append(fewshot)

    traces_path = out_dir / "traces.jsonl"
    grounding_path = out_dir / "grounding_eval.jsonl"
    fewshot_path = out_dir / "fewshot_examples.jsonl"
    summary_json_path = out_dir / "export_summary.json"
    summary_md_path = out_dir / "export_summary.md"
    manifest_path = out_dir / "mcp_manifest.json"

    _write_jsonl(traces_path, trace_records)
    _write_jsonl(grounding_path, grounding_records)
    _write_jsonl(fewshot_path, fewshot_records)
    registry = build_tool_registry()
    write_mcp_manifest(registry, manifest_path)

    summary = {
        "runs_dir": str(runs_path),
        "output_dir": str(out_dir),
        "statuses": sorted(status_filter),
        "include_products": sorted(product_filter) if product_filter else None,
        "total_trace_files": len(trace_paths),
        "exported_runs": len(trace_records),
        "skipped_runs": skipped,
        "status_counts": dict(sorted(status_counts.items())),
        "product_counts": dict(sorted(product_counts.items())),
        "grounding_examples": len(grounding_records),
        "fewshot_examples": len(fewshot_records),
        "tool_registry_tools": sorted(registry.tools.keys()),
        "generated_files": {
            "traces": str(traces_path),
            "grounding_eval": str(grounding_path),
            "fewshot_examples": str(fewshot_path),
            "export_summary_json": str(summary_json_path),
            "export_summary_md": str(summary_md_path),
            "mcp_manifest": str(manifest_path),
        },
    }
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md_path.write_text(_build_summary_markdown(summary), encoding="utf-8")
    return summary


def discover_trace_files(runs_dir: str | Path) -> list[Path]:
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        return []
    return sorted(path for path in runs_path.rglob("trace.jsonl") if path.is_file())


def parse_trace_run(trace_path: str | Path, eval_index: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    trace_file = Path(trace_path)
    trace_dir = trace_file.parent
    events = _read_jsonl(trace_file)
    task = _read_task(trace_dir / "task.yaml")
    status = _final_status(events)
    steps = [event for event in events if event.get("event_type") == "step"]
    report_path = trace_dir / "report.md"
    eval_case = (eval_index or {}).get(_norm_path(trace_dir))
    return {
        "trace_path": str(trace_file),
        "trace_dir": str(trace_dir),
        "task": task,
        "task_id": task.get("id"),
        "run_id": _run_id(events, trace_dir),
        "product": task.get("product"),
        "instruction": task.get("instruction"),
        "status": status,
        "events": events,
        "steps": steps,
        "report_path": str(report_path) if report_path.exists() else None,
        "eval": eval_case,
        "verification_evidence": _verification_evidence(steps),
    }


def _trace_dataset_record(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": parsed.get("task_id"),
        "run_id": parsed.get("run_id"),
        "product": parsed.get("product"),
        "instruction": parsed.get("instruction"),
        "status": parsed.get("status"),
        "trace_dir": parsed.get("trace_dir"),
        "report_path": parsed.get("report_path"),
        "eval": parsed.get("eval"),
        "verification_evidence": parsed.get("verification_evidence"),
        "steps": [_step_summary(step) for step in parsed.get("steps", [])],
    }


def _step_summary(step: dict[str, Any]) -> dict[str, Any]:
    observation = step.get("observation") if isinstance(step.get("observation"), dict) else {}
    action = step.get("action") if isinstance(step.get("action"), dict) else {}
    verdict = step.get("verdict") if isinstance(step.get("verdict"), dict) else {}
    action_metadata = action.get("metadata") if isinstance(action.get("metadata"), dict) else {}
    return {
        "step_index": step.get("step_index"),
        "screen_summary": observation.get("screen_summary"),
        "screenshot_path": observation.get("screenshot_path"),
        "action": {
            "type": action.get("type"),
            "target": action.get("target"),
            "coordinates": action.get("coordinates"),
            "coordinate_source": action_metadata.get("coordinate_source"),
            "stage": action_metadata.get("stage"),
        },
        "verdict": {
            "status": verdict.get("status"),
            "reason": verdict.get("reason"),
        },
    }


def _grounding_records(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for step in parsed.get("steps", []):
        action = step.get("action") if isinstance(step.get("action"), dict) else {}
        if action.get("type") != "click" or action.get("coordinates") is None:
            continue
        observation = step.get("observation") if isinstance(step.get("observation"), dict) else {}
        verdict = step.get("verdict") if isinstance(step.get("verdict"), dict) else {}
        metadata = action.get("metadata") if isinstance(action.get("metadata"), dict) else {}
        records.append(
            {
                "task_id": parsed.get("task_id"),
                "run_id": parsed.get("run_id"),
                "product": parsed.get("product"),
                "trace_dir": parsed.get("trace_dir"),
                "step_index": step.get("step_index"),
                "instruction": parsed.get("instruction"),
                "screenshot_path": observation.get("screenshot_path"),
                "target": action.get("target"),
                "action": {"type": action.get("type"), "coordinates": action.get("coordinates")},
                "target_bbox": metadata.get("final_bbox") or metadata.get("ocr_bbox") or metadata.get("raw_vlm_bbox"),
                "coordinate_source": metadata.get("coordinate_source"),
                "stage": metadata.get("stage"),
                "verdict": {"status": verdict.get("status"), "reason": verdict.get("reason")},
            }
        )
    return records


def _fewshot_record(parsed: dict[str, Any]) -> dict[str, Any] | None:
    product = parsed.get("product")
    if product not in {"im", "docs"}:
        return None
    successful_actions = [
        step_summary["action"]
        for step_summary in (_step_summary(step) for step in parsed.get("steps", []))
        if step_summary["verdict"]["status"] == "pass" and step_summary["action"]["type"] not in {None, "observe"}
    ]
    if not successful_actions:
        return None
    return {
        "task_id": parsed.get("task_id"),
        "run_id": parsed.get("run_id"),
        "product": product,
        "instruction": parsed.get("instruction"),
        "trace_dir": parsed.get("trace_dir"),
        "messages": [
            {"role": "user", "content": str(parsed.get("instruction") or "")},
            {"role": "assistant", "content": _fewshot_assistant_text(parsed, successful_actions)},
        ],
        "successful_actions": successful_actions,
    }


def _fewshot_assistant_text(parsed: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    lines = [f"Use the {parsed.get('product')} skill state machine and verify each step."]
    for index, action in enumerate(actions, 1):
        target = action.get("target") or ""
        action_type = action.get("type") or "action"
        lines.append(f"{index}. {action_type}: {target}")
    return "\n".join(lines)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_task(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _final_status(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        if event.get("event_type") == "run_finished":
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            status = metadata.get("status")
            return str(status) if status is not None else None
    return None


def _run_id(events: list[dict[str, Any]], trace_dir: Path) -> str | None:
    for event in events:
        if event.get("event_type") == "run_started":
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            run_id = metadata.get("run_id")
            if run_id:
                return str(run_id)
    parts = trace_dir.name.split("_")
    return "_".join(parts[-3:]) if len(parts) >= 3 else None


def _verification_evidence(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for step in reversed(steps):
        verdict = step.get("verdict") if isinstance(step.get("verdict"), dict) else {}
        evidence = verdict.get("evidence") if isinstance(verdict.get("evidence"), dict) else {}
        evidences = evidence.get("evidences")
        if isinstance(evidences, list):
            return [item for item in evidences if isinstance(item, dict)]
    return []


def _load_eval_index(runs_dir: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for summary_path in runs_dir.rglob("summary.json"):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cases = summary.get("cases") if isinstance(summary, dict) else None
        if not isinstance(cases, list):
            continue
        for case in cases:
            if not isinstance(case, dict) or not case.get("trace_dir"):
                continue
            case_info = {
                "suite_id": summary.get("suite_id"),
                "profile": summary.get("profile"),
                "case_id": case.get("id"),
                "expected_met": case.get("expected_met"),
                "summary_path": str(summary_path),
            }
            for candidate in _trace_dir_candidates(summary_path, str(case.get("trace_dir"))):
                index[_norm_path(candidate)] = case_info
    return index


def _trace_dir_candidates(summary_path: Path, trace_dir: str) -> list[Path]:
    path = Path(trace_dir)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(summary_path.parent / path)
        candidates.append(Path.cwd() / path)
    return candidates


def _norm_path(path: str | Path) -> str:
    return str(Path(path).resolve(strict=False)).lower()


def _build_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase 8 Trace Export Summary",
        "",
        f"- Runs dir: `{summary.get('runs_dir')}`",
        f"- Output dir: `{summary.get('output_dir')}`",
        f"- Status filter: `{', '.join(summary.get('statuses') or [])}`",
        f"- Total trace files: `{summary.get('total_trace_files')}`",
        f"- Exported runs: `{summary.get('exported_runs')}`",
        f"- Skipped runs: `{summary.get('skipped_runs')}`",
        f"- Grounding examples: `{summary.get('grounding_examples')}`",
        f"- Few-shot examples: `{summary.get('fewshot_examples')}`",
        "",
        "## Product Counts",
        "",
    ]
    product_counts = summary.get("product_counts") if isinstance(summary.get("product_counts"), dict) else {}
    if product_counts:
        for key, value in product_counts.items():
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Generated Files", ""])
    for key, value in (summary.get("generated_files") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)
