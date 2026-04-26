from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from cua_lark.actions import DryRunDesktopBackend, MockActionExecutor, PyAutoGuiBackend
from cua_lark.agent import MockPlanner, SafetyGuard
from cua_lark.grounding.coordinate import compute_scale, ensure_point_in_bounds, scale_point
from cua_lark.perception import MockPerceptor
from cua_lark.task.loader import load_task
from cua_lark.task.parser import render_task
from cua_lark.task.schema import Action, Observation, StepGoal, TaskSpec, Trace, Verdict
from cua_lark.trace import TraceRecorder
from cua_lark.verifier import MockVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cua-lark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a testcase")
    run.add_argument("task_path")
    run.add_argument("--mock", action="store_true", help="Use the safe mock execution loop")
    run.add_argument("--real-ui", action="store_true", help="Use the real desktop UI backend")
    run.add_argument("--safety-config", default="configs/safety.yaml")
    run.add_argument("--desktop-config", default="configs/desktop.yaml")
    run.add_argument("--runs-dir", default="runs")
    run.add_argument("--confirm-target")
    run.add_argument("--allow-send", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--assume-frontmost-window", action="store_true")
    return parser


def run_mock_task(args: argparse.Namespace) -> int:
    if not args.mock:
        print("Only --mock execution is enabled in Phase 1 mock runner.")
        return 2

    raw_task = load_task(args.task_path)
    run_id = _new_run_id()
    task = render_task(raw_task, run_id)
    recorder = TraceRecorder(args.runs_dir)
    trace = recorder.start(task, run_id=run_id)

    safety = SafetyGuard.from_yaml(args.safety_config)
    decision = safety.check_task(task)
    if not decision.allowed:
        recorder.finalize(trace, "blocked")
        recorder.write_report(trace)
        print(f"Blocked by safety guard: {decision.reason}")
        print(f"Trace dir: {trace.trace_dir}")
        return 1

    planner = MockPlanner()
    perceptor = MockPerceptor()
    executor = MockActionExecutor()
    verifier = MockVerifier()

    for goal in planner.plan(task):
        observation = perceptor.observe(goal)
        action = executor.build_action(task, goal)
        action_decision = safety.check_action(action, task)
        if not action_decision.allowed:
            verdict = Verdict(status="blocked", reason=action_decision.reason)
            recorder.record_step(trace, observation, action, verdict, metadata={"goal": goal.model_dump(mode="json")})
            recorder.finalize(trace, "blocked")
            report_path = recorder.write_report(trace)
            print(f"Blocked by safety guard: {action_decision.reason}")
            print(f"Trace dir: {trace.trace_dir}")
            print(f"Report: {report_path}")
            return 1

        executed = executor.execute(action)
        verdict = verifier.verify_step(goal, observation)
        recorder.record_step(trace, observation, executed, verdict, metadata={"goal": goal.model_dump(mode="json")})

    recorder.finalize(trace, "pass")
    report_path = recorder.write_report(trace)
    print("Mock run completed.")
    print(f"Status: {trace.status}")
    print(f"Trace dir: {trace.trace_dir}")
    print(f"Report: {report_path}")
    return 0


def run_real_ui_task(args: argparse.Namespace) -> int:
    if args.dry_run and args.allow_send:
        print("--dry-run and --allow-send are mutually exclusive.")
        return 2
    if not args.confirm_target:
        print("--confirm-target is required for --real-ui.")
        return 2

    raw_task = load_task(args.task_path)
    run_id = _new_run_id()
    task = render_task(raw_task, run_id)
    message = str(task.slots.get("message", ""))
    recorder = TraceRecorder(args.runs_dir)
    trace = recorder.start(task, run_id=run_id)
    execution_mode = "dry-run" if args.dry_run else ("real-ui-allow-send" if args.allow_send else "real-ui-without-send")
    trace.metadata.update(
        {
            "execution_mode": execution_mode,
            "allow_send": args.allow_send,
            "dry_run": args.dry_run,
            "assume_frontmost_window": args.assume_frontmost_window,
        }
    )

    safety = SafetyGuard.from_yaml(args.safety_config)
    preflight = safety.check_real_ui_run(task, args.confirm_target, message, run_id)
    if not preflight.allowed:
        observation = Observation(step_index=0, screen_summary="Real UI preflight safety check failed")
        action = Action(type="real_ui_preflight", target=args.confirm_target, mock=False)
        verdict = Verdict(status="blocked", reason=preflight.reason, evidence={"execution_mode": execution_mode})
        recorder.record_step(trace, observation, action, verdict)
        recorder.finalize(trace, "blocked")
        report_path = recorder.write_report(trace)
        print(f"Blocked by safety guard: {preflight.reason}")
        print(f"Trace dir: {trace.trace_dir}")
        print(f"Report: {report_path}")
        return 1

    desktop_config = load_desktop_config(args.desktop_config)
    backend = DryRunDesktopBackend(_config_screen_size(desktop_config)) if args.dry_run else PyAutoGuiBackend()
    context: dict[str, Any] = {
        "desktop_config": desktop_config,
        "execution_mode": execution_mode,
        "coordinate_info": {},
        "planned_points": {},
    }

    status = _real_ui_prepare_and_act(args, task, trace, recorder, backend, context)
    if status != "pass":
        recorder.finalize(trace, status)
        report_path = recorder.write_report(trace)
        print(f"Real UI run ended with status: {status}")
        print(f"Trace dir: {trace.trace_dir}")
        print(f"Report: {report_path}")
        return 0 if args.dry_run and status in {"uncertain", "needs_manual_verification"} else 1

    final_status = _real_ui_final_send(args, task, trace, recorder, backend, safety, message, run_id, context)
    recorder.finalize(trace, final_status)
    report_path = recorder.write_report(trace)
    print("Real UI run completed.")
    print(f"Status: {trace.status}")
    print(f"Trace dir: {trace.trace_dir}")
    print(f"Report: {report_path}")
    return _exit_code_for_status(final_status, dry_run=args.dry_run)


def _real_ui_prepare_and_act(
    args: argparse.Namespace,
    task: TaskSpec,
    trace: Trace,
    recorder: TraceRecorder,
    backend: Any,
    context: dict[str, Any],
) -> str:
    desktop_config = context["desktop_config"]
    title_candidates = list(desktop_config.get("window_title_candidates", ["Feishu", "飞书"]))
    step_index = 1

    focus = backend.focus_window(title_candidates, assume_frontmost_window=args.assume_frontmost_window)
    focus_status = "pass" if focus.ok else "blocked"
    _record_real_step(
        recorder,
        trace,
        step_index,
        "Focus Feishu window",
        Action(type="focus_window", target="Feishu", mock=args.dry_run, metadata=focus.metadata or {}),
        Verdict(status=focus_status, reason=focus.reason, evidence=focus.metadata or {}),
    )
    if not focus.ok:
        return "blocked"

    step_index += 1
    screenshot = backend.screenshot(Path(trace.trace_dir) / "before_coordinate_plan.png")
    screenshot_status = "pass" if screenshot.ok else "blocked"
    _record_real_step(
        recorder,
        trace,
        step_index,
        "Capture screenshot before coordinate planning",
        Action(type="screenshot", target="screen", mock=args.dry_run, metadata=screenshot.metadata or {}),
        Verdict(status=screenshot_status, reason=screenshot.reason, evidence=screenshot.metadata or {}),
    )
    if not screenshot.ok:
        return "blocked"

    step_index += 1
    coordinate_result = _plan_coordinates(desktop_config, backend, screenshot.metadata or {})
    context["coordinate_info"] = coordinate_result["coordinate_info"]
    context["planned_points"] = coordinate_result["planned_points"]
    coordinate_status = "pass" if coordinate_result["ok"] else "blocked"
    _record_real_step(
        recorder,
        trace,
        step_index,
        "Plan fixed IM coordinates with scaling",
        Action(type="coordinate_plan", target="im_anchors", mock=args.dry_run, metadata=coordinate_result),
        Verdict(status=coordinate_status, reason=coordinate_result["reason"], evidence=coordinate_result),
    )
    if not coordinate_result["ok"]:
        return "blocked"

    actions: list[tuple[str, str, Any]] = [
        ("click", "message_module", None),
        ("click", "search_box", None),
        ("paste_text", "search_box", str(task.slots.get("chat_name", ""))),
        ("press", "enter", "enter"),
        ("click", "message_input", None),
        ("paste_text", "message_input", str(task.slots.get("message", ""))),
    ]
    for action_type, target, payload in actions:
        step_index += 1
        result = _execute_pre_send_action(
            backend,
            context["planned_points"],
            context["coordinate_info"],
            action_type,
            target,
            payload,
            args.dry_run,
        )
        status = "pass" if result.ok else "blocked"
        _record_real_step(
            recorder,
            trace,
            step_index,
            f"Pre-send action: {action_type} {target}",
            Action(type=action_type, target=target, text=payload if action_type == "paste_text" else None, mock=args.dry_run, metadata=result.metadata or {}),
            Verdict(status=status, reason=result.reason, evidence=result.metadata or {}),
        )
        if not result.ok:
            return "blocked"
    return "pass"


def _real_ui_final_send(
    args: argparse.Namespace,
    task: TaskSpec,
    trace: Trace,
    recorder: TraceRecorder,
    backend: Any,
    safety: SafetyGuard,
    message: str,
    run_id: str,
    context: dict[str, Any],
) -> str:
    step_index = max((event.step_index or 0 for event in trace.events), default=0) + 1
    unsafe_prior = [
        event
        for event in trace.events
        if event.event_type == "step"
        and event.verdict is not None
        and event.verdict.status in {"blocked", "fail", "uncertain"}
    ]
    if unsafe_prior:
        verdict = Verdict(status="blocked", reason="prior_step_not_clean", evidence={"prior_step_count": len(unsafe_prior)})
        _record_real_step(
            recorder,
            trace,
            step_index,
            "Final send skipped because a prior step was not clean",
            Action(type="send_final", target="Enter", mock=args.dry_run, metadata={"allow_send": args.allow_send}),
            verdict,
        )
        return "blocked"

    final_check = safety.check_real_ui_run(task, args.confirm_target, message, run_id)
    if not final_check.allowed:
        verdict = Verdict(status="blocked", reason=final_check.reason, evidence={"final_safety_check": False})
        _record_real_step(
            recorder,
            trace,
            step_index,
            "Final send safety check",
            Action(type="send_final", target="Enter", mock=args.dry_run, metadata={"allow_send": args.allow_send}),
            verdict,
        )
        return "blocked"

    if not args.allow_send:
        status = "uncertain" if args.dry_run else "needs_manual_verification"
        reason = "dry_run_final_send_not_executed" if args.dry_run else "allow_send_not_provided_final_send_skipped"
        _record_real_step(
            recorder,
            trace,
            step_index,
            "Final send skipped by safety switch",
            Action(type="send_final", target="Enter", mock=args.dry_run, metadata={"allow_send": False, "planned_only": True}),
            Verdict(status=status, reason=reason, evidence={"message_contains_run_id": run_id in message}),
        )
        return status

    result = backend.press("enter")
    status = "sent_with_screenshot_evidence" if result.ok else "blocked"
    after = backend.screenshot(Path(trace.trace_dir) / "after_final_send.png")
    evidence = {**(result.metadata or {}), "after_screenshot": (after.metadata or {}).get("path"), "after_screenshot_status": after.reason}
    _record_real_step(
        recorder,
        trace,
        step_index,
        "Final send action",
        Action(type="send_final", target="Enter", mock=False, metadata={"allow_send": True, **(result.metadata or {})}),
        Verdict(status=status, reason=result.reason, evidence=evidence),
    )
    return status


def _execute_pre_send_action(
    backend: Any,
    planned_points: dict[str, tuple[int, int]],
    coordinate_info: dict[str, Any],
    action_type: str,
    target: str,
    payload: Any,
    dry_run: bool,
):
    if action_type == "click":
        x, y = planned_points[target]
        result = backend.click(x, y, target)
        result.metadata = {
            **(result.metadata or {}),
            **coordinate_info,
            "coordinate_source": coordinate_info.get("coordinate_source", "config_fixed_anchor"),
        }
        return result
    if action_type == "paste_text":
        return backend.paste_text(str(payload))
    if action_type == "press":
        return backend.press(str(payload))
    return backend.click(0, 0, target)


def _record_real_step(
    recorder: TraceRecorder,
    trace: Trace,
    step_index: int,
    summary: str,
    action: Action,
    verdict: Verdict,
) -> None:
    observation = Observation(
        step_index=step_index,
        screen_summary=summary,
        screenshot_path=action.metadata.get("path") if action.metadata else None,
        metadata={"real_ui": True, **(action.metadata or {})},
    )
    recorder.record_step(trace, observation, action, verdict)


def _exit_code_for_status(status: str, dry_run: bool = False) -> int:
    if status in {"pass", "sent_with_screenshot_evidence"}:
        return 0
    if dry_run and status in {"uncertain", "needs_manual_verification"}:
        return 0
    return 1


def _plan_coordinates(desktop_config: dict[str, Any], backend: Any, screenshot_metadata: dict[str, Any]) -> dict[str, Any]:
    base = desktop_config.get("base_resolution") or desktop_config.get("resolution") or {"width": 1440, "height": 900}
    base_resolution = (float(base["width"]), float(base["height"]))
    screen_size = backend.screen_size()
    screenshot_resolution = (
        float(screenshot_metadata.get("screenshot_width") or screen_size[0]),
        float(screenshot_metadata.get("screenshot_height") or screen_size[1]),
    )
    scale_x, scale_y = compute_scale(base_resolution, screen_size)
    anchors = desktop_config.get("im_anchors", {})
    planned_points: dict[str, tuple[int, int]] = {}
    try:
        for name, spec in anchors.items():
            point = tuple(spec["point"])
            scaled = scale_point((float(point[0]), float(point[1])), base_resolution, screen_size)
            planned_points[name] = ensure_point_in_bounds(scaled, screen_size)
    except Exception as exc:
        return {
            "ok": False,
            "reason": str(exc),
            "coordinate_source": "config_fixed_anchor",
            "base_resolution": base_resolution,
            "actual_resolution": screen_size,
            "pyautogui_size": screen_size,
            "screenshot_resolution": screenshot_resolution,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "planned_points": planned_points,
        }
    return {
        "ok": True,
        "reason": "coordinates_planned",
        "coordinate_info": {
            "coordinate_source": "config_fixed_anchor",
            "base_resolution": base_resolution,
            "actual_resolution": screen_size,
            "pyautogui_size": screen_size,
            "screenshot_resolution": screenshot_resolution,
            "scale_x": scale_x,
            "scale_y": scale_y,
        },
        "planned_points": planned_points,
        "coordinate_source": "config_fixed_anchor",
        "base_resolution": base_resolution,
        "actual_resolution": screen_size,
        "pyautogui_size": screen_size,
        "screenshot_resolution": screenshot_resolution,
        "scale_x": scale_x,
        "scale_y": scale_y,
    }


def load_desktop_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _config_screen_size(config: dict[str, Any]) -> tuple[int, int]:
    resolution = config.get("resolution") or config.get("base_resolution") or {"width": 1440, "height": 900}
    return int(resolution["width"]), int(resolution["height"])


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def run_task(args: argparse.Namespace) -> int:
    if args.mock and args.real_ui:
        print("--mock and --real-ui are mutually exclusive.")
        return 2
    if args.mock:
        return run_mock_task(args)
    if args.real_ui:
        return run_real_ui_task(args)
    print("Specify --mock or --real-ui.")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_task(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
