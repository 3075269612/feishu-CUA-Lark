from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from cua_lark.eval.metrics import compute_metrics
from cua_lark.eval.report import write_eval_reports
from cua_lark.eval.suite import EvalCase, VALID_PROFILES, load_eval_suite
from cua_lark.task.loader import load_task


RunCommand = Callable[[list[str]], int]


def run_eval_suite(
    suite_path: str | Path,
    profile: str,
    runs_dir: str | Path,
    run_command: RunCommand,
) -> tuple[int, dict[str, Any], Path, Path]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"unsupported eval profile: {profile}")
    suite = load_eval_suite(suite_path)
    selected_cases = suite.cases_for_profile(profile)
    if not selected_cases:
        raise ValueError(f"suite {suite.id} has no cases for profile {profile}")

    started_at = datetime.now().isoformat(timespec="seconds")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_dir = Path(runs_dir) / f"{suite.id}_{profile}_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)

    case_results = []
    for case in selected_cases:
        case_results.append(_run_case(case, profile, output_dir, run_command))

    finished_at = datetime.now().isoformat(timespec="seconds")
    summary = {
        "suite_id": suite.id,
        "description": suite.description,
        "profile": profile,
        "started_at": started_at,
        "finished_at": finished_at,
        "output_dir": str(output_dir),
        "metrics": compute_metrics(case_results),
        "cases": case_results,
    }
    json_path, md_path = write_eval_reports(summary, output_dir)
    return _exit_code(summary), summary, json_path, md_path


def _run_case(case: EvalCase, profile: str, output_dir: Path, run_command: RunCommand) -> dict[str, Any]:
    case_runs_dir = output_dir / case.id
    case_runs_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    argv = _build_run_argv(case, profile, case_runs_dir)
    started_perf = perf_counter()
    exit_code = run_command(argv)
    elapsed_sec = round(perf_counter() - started_perf, 4)
    finished_at = datetime.now().isoformat(timespec="seconds")

    trace_dir = _latest_trace_dir(case_runs_dir)
    parsed = _parse_trace(trace_dir) if trace_dir else {}
    status = parsed.get("status")
    return {
        "id": case.id,
        "product": case.product,
        "task_path": case.task_path,
        "profile": profile,
        "tags": case.tags,
        "expected_statuses": case.expected_statuses,
        "expected_met": status in case.expected_statuses,
        "status": status,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": elapsed_sec,
        "trace_duration_sec": parsed.get("duration_sec"),
        "steps": parsed.get("steps", 0),
        "passed_steps": parsed.get("passed_steps", 0),
        "recovery_count": parsed.get("recovery_count", 0),
        "failure_category": parsed.get("failure_category"),
        "verification_evidence": parsed.get("verification_evidence", []),
        "screenshot_paths": parsed.get("screenshot_paths", []),
        "trace_dir": str(trace_dir) if trace_dir else None,
        "report_path": str(trace_dir / "report.md") if trace_dir and (trace_dir / "report.md").exists() else None,
        "argv": argv,
    }


def _build_run_argv(case: EvalCase, profile: str, case_runs_dir: Path) -> list[str]:
    argv = ["run", case.task_path, "--runs-dir", str(case_runs_dir)]
    if profile == "mock":
        return [*argv, "--mock"]

    confirm_target = _infer_confirm_target(case.task_path)
    argv.extend(["--real-ui", "--confirm-target", confirm_target])
    if profile == "real-smoke-dry-run":
        argv.append("--dry-run")
    elif profile == "real-smoke":
        argv.append("--allow-send")
    return argv


def _infer_confirm_target(task_path: str) -> str:
    task = load_task(task_path)
    slots = task.slots
    for key in ("chat_name", "target_doc", "title", "folder_name"):
        value = slots.get(key)
        if isinstance(value, str) and value:
            return value
    return "CUA-Lark-Test"


def _latest_trace_dir(case_runs_dir: Path) -> Path | None:
    candidates = [path for path in case_runs_dir.iterdir() if path.is_dir() and (path / "trace.jsonl").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _parse_trace(trace_dir: Path) -> dict[str, Any]:
    events = []
    trace_path = trace_dir / "trace.jsonl"
    with trace_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    step_events = [event for event in events if event.get("event_type") == "step"]
    status = _final_status(events)
    failure_category = _failure_category(step_events, status)
    started = _event_time(events, "run_started")
    finished = _event_time(events, "run_finished")
    duration = (finished - started).total_seconds() if started and finished else None
    return {
        "status": status,
        "duration_sec": round(duration, 4) if duration is not None else None,
        "steps": len(step_events),
        "passed_steps": _passed_steps(step_events),
        "recovery_count": sum(1 for event in events if event.get("event_type") == "recovery"),
        "failure_category": failure_category,
        "verification_evidence": _verification_evidence(step_events),
        "screenshot_paths": _screenshot_paths(step_events),
    }


def _final_status(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        if event.get("event_type") == "run_finished":
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            status = metadata.get("status")
            return str(status) if status is not None else None
    return None


def _event_time(events: list[dict[str, Any]], event_type: str) -> datetime | None:
    for event in events:
        if event.get("event_type") == event_type:
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str):
                return datetime.fromisoformat(timestamp)
    return None


def _passed_steps(step_events: list[dict[str, Any]]) -> int:
    total = 0
    for event in step_events:
        verdict = event.get("verdict") if isinstance(event.get("verdict"), dict) else {}
        if verdict.get("status") == "pass":
            total += 1
    return total


def _failure_category(step_events: list[dict[str, Any]], status: str | None) -> str | None:
    if status == "pass" or status in {"needs_manual_verification", "sent_with_screenshot_evidence"}:
        return None
    for event in step_events:
        verdict = event.get("verdict") if isinstance(event.get("verdict"), dict) else {}
        verdict_status = verdict.get("status")
        if verdict_status != "pass":
            return str(verdict.get("reason") or verdict_status or status or "unknown")
    return status


def _verification_evidence(step_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for event in reversed(step_events):
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        if action.get("type") != "verify_im_send":
            continue
        verdict = event.get("verdict") if isinstance(event.get("verdict"), dict) else {}
        evidence = verdict.get("evidence") if isinstance(verdict.get("evidence"), dict) else {}
        evidences = evidence.get("evidences")
        if isinstance(evidences, list):
            return [item for item in evidences if isinstance(item, dict)]
    return []


def _screenshot_paths(step_events: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for event in step_events:
        observation = event.get("observation") if isinstance(event.get("observation"), dict) else {}
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        candidates = [
            observation.get("screenshot_path"),
            metadata.get("before_screenshot"),
            metadata.get("after_screenshot"),
        ]
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate or candidate in seen:
                continue
            paths.append(candidate)
            seen.add(candidate)
    return paths


def _exit_code(summary: dict[str, Any]) -> int:
    cases = summary.get("cases") if isinstance(summary.get("cases"), list) else []
    return 0 if all(isinstance(case, dict) and case.get("expected_met") for case in cases) else 1
