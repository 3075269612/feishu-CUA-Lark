from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from cua_lark.actions import BackendResult, DryRunDesktopBackend, MockActionExecutor, PyAutoGuiBackend
from cua_lark.agent import MockPlanner, SafetyGuard
from cua_lark.grounding.hybrid_grounder import HybridGrounder
from cua_lark.perception import MockPerceptor
from cua_lark.perception.accessibility import AccessibilityExtractor
from cua_lark.perception.ocr import OcrClient
from cua_lark.perception.vlm import VlmClient
from cua_lark.task.loader import load_task
from cua_lark.task.parser import render_task
from cua_lark.task.schema import Action, Observation, StepGoal, TaskSpec, Trace, Verdict
from cua_lark.trace import TraceRecorder
from cua_lark.verifier import ImVerifierChain, MockVerifier


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
    run.add_argument("--strict-verification", action="store_true")
    run.add_argument("--grounding", default="hybrid", choices=["hybrid"], help="Use VLM + OCR + Accessibility hybrid grounding")
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
            "grounding": args.grounding,
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
        "grounding": args.grounding,
        "last_visual_grounding": {},
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
    if final_status == "sent_with_screenshot_evidence":
        final_status = _real_ui_verify_after_send(args, task, trace, recorder, message, run_id)
    recorder.finalize(trace, final_status)
    report_path = recorder.write_report(trace)
    print("Real UI run completed.")
    print(f"Status: {trace.status}")
    print(f"Trace dir: {trace.trace_dir}")
    print(f"Report: {report_path}")
    return _exit_code_for_status(final_status, dry_run=args.dry_run, strict=args.strict_verification)


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

    grounder = HybridGrounder()
    goals = [
        StepGoal(index=step_index + 1, description="Open message module", target="message_module", expected="message page visible"),
        StepGoal(index=step_index + 2, description="Open target chat", target=str(task.slots.get("chat_name", "")), expected="chat opened"),
        StepGoal(index=step_index + 3, description="Paste message into input", target="message_input", expected="message text visible"),
    ]

    for goal in goals:
        observation = _observe_for_visual_goal(
            backend,
            trace,
            goal,
            desktop_config,
        )
        action, verdict = _execute_visual_goal(args, task, backend, context, grounder, goal, observation)
        recorder.record_step(trace, observation, action, verdict, metadata={"goal": goal.model_dump(mode="json")})
        if verdict.status != "pass":
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


def _real_ui_verify_after_send(
    args: argparse.Namespace,
    task: TaskSpec,
    trace: Trace,
    recorder: TraceRecorder,
    message: str,
    run_id: str,
) -> str:
    step_index = max((event.step_index or 0 for event in trace.events), default=0) + 1
    verifier = ImVerifierChain(config=load_feishu_verification_config(args))
    verdict = verifier.verify(task, trace, message, run_id, dry_run=args.dry_run)
    trace.metadata["verification_summary"] = verdict.evidence
    trace.metadata["verification_final_status"] = verdict.status
    _record_real_step(
        recorder,
        trace,
        step_index,
        "Verify IM send result",
        Action(type="verify_im_send", target=task.slots.get("chat_name"), mock=args.dry_run, metadata={"verification": verdict.evidence}),
        verdict,
    )
    return verdict.status


def _observe_for_visual_goal(
    backend: Any,
    trace: Trace,
    goal: StepGoal,
    desktop_config: dict[str, Any],
) -> Observation:
    screenshot = backend.screenshot(Path(trace.trace_dir) / f"step_{goal.index:03d}_observe.png")
    screenshot_path = (screenshot.metadata or {}).get("path") if screenshot.ok else None
    ocr_texts: list[dict[str, Any]] = []
    accessibility_candidates: list[dict[str, Any]] = []

    if screenshot_path:
        ocr_texts = OcrClient().extract(str(screenshot_path))
        accessibility_candidates = _extract_accessibility_candidates(desktop_config)

    summary = _summarize_visual_goal(
        goal,
        screenshot_path,
        ocr_texts,
        allow_vlm=not bool((screenshot.metadata or {}).get("planned_only")),
    )
    return Observation(
        step_index=goal.index,
        screen_summary=summary,
        screenshot_path=str(screenshot_path) if screenshot_path else None,
        ocr_texts=ocr_texts,
        accessibility_candidates=accessibility_candidates,
        metadata={
            "real_ui": True,
            "grounding": "hybrid",
            "ocr_count": len(ocr_texts),
            "accessibility_count": len(accessibility_candidates),
            **(screenshot.metadata or {}),
        },
    )


def _extract_accessibility_candidates(desktop_config: dict[str, Any]) -> list[dict[str, Any]]:
    title_candidates = list(desktop_config.get("window_title_candidates", ["Feishu", "飞书"]))
    max_depth = int(desktop_config.get("accessibility_max_depth", 4))
    extractor = AccessibilityExtractor()
    for title in title_candidates:
        candidates = extractor.extract_elements(window_title=title, max_depth=max_depth, include_invisible=False)
        if candidates:
            return candidates
    return []


def _summarize_visual_goal(
    goal: StepGoal,
    screenshot_path: str | None,
    ocr_texts: list[dict[str, Any]],
    allow_vlm: bool = True,
) -> str:
    if screenshot_path and allow_vlm:
        prompt = (
            "Summarize the current Feishu/Lark UI for a desktop automation step.\n"
            f"Step: {goal.description}\n"
            f"Target: {goal.target}\n"
            "Mention whether the target appears and any active page context."
        )
        summary = VlmClient().summarize(screenshot_path, prompt)
        if summary and not summary.startswith("VLM disabled") and not summary.startswith("VLM error"):
            return summary
    visible_text = ", ".join(str(item.get("text", "")) for item in ocr_texts if item.get("text"))
    if visible_text:
        return f"OCR-visible UI text: {visible_text}"
    return "Hybrid observation captured no OCR text."


def _execute_visual_goal(
    args: argparse.Namespace,
    task: TaskSpec,
    backend: Any,
    context: dict[str, Any],
    grounder: HybridGrounder,
    goal: StepGoal,
    observation: Observation,
) -> tuple[Action, Verdict]:
    chat_name = str(task.slots.get("chat_name", ""))
    target = _normalize_target_name(goal.target, chat_name)
    normalized_goal = goal.model_copy(update={"target": target})

    if target == "message_module":
        return _execute_visual_message_module(args, backend, context, grounder, normalized_goal, observation)
    if target == chat_name:
        return _execute_visual_open_chat(args, backend, context, grounder, normalized_goal, observation, chat_name)
    if target == "message_input":
        return _execute_visual_message_input(args, task, backend, context, grounder, normalized_goal, observation)

    return (
        Action(type="unknown_visual_goal", target=target, mock=args.dry_run),
        Verdict(status="blocked", reason="unsupported_visual_goal", evidence={"target": target}),
    )


def _execute_visual_message_module(
    args: argparse.Namespace,
    backend: Any,
    context: dict[str, Any],
    grounder: HybridGrounder,
    goal: StepGoal,
    observation: Observation,
) -> tuple[Action, Verdict]:
    if _looks_like_message_page(observation):
        action = Action(
            type="observe",
            target="message_module",
            mock=args.dry_run,
            metadata={"skip_click": True, "grounding": "hybrid"},
        )
        verdict = Verdict(status="pass", reason="already_on_message_page", evidence={"skip_click": True})
        return action, verdict

    point = grounder.locate_target(
        "left sidebar message button",
        observation.screenshot_path,
        observation.ocr_texts,
        accessibility_candidates=observation.accessibility_candidates,
    )
    metadata = _grounding_metadata(grounder)
    context["last_visual_grounding"] = metadata
    if point is None:
        action = Action(type="click", target="message_module", mock=args.dry_run, metadata=metadata)
        verdict = Verdict(
            status="blocked",
            reason="message_module_button_not_found_by_vlm",
            evidence={**metadata, "no_fallback": True},
        )
        return action, verdict

    screen_point = _screenshot_point_to_screen(point, observation.metadata)
    result = backend.click(screen_point[0], screen_point[1], "message_module")
    return _action_verdict_from_backend(
        action_type="click",
        target="message_module",
        coordinates=screen_point,
        result=result,
        dry_run=args.dry_run,
        metadata=metadata,
    )


def _execute_visual_open_chat(
    args: argparse.Namespace,
    backend: Any,
    context: dict[str, Any],
    grounder: HybridGrounder,
    goal: StepGoal,
    observation: Observation,
    chat_name: str,
) -> tuple[Action, Verdict]:
    target_description = f"left conversation list item named {chat_name}"
    point = grounder.locate_target(
        target_description,
        observation.screenshot_path,
        observation.ocr_texts,
        accessibility_candidates=observation.accessibility_candidates,
    )
    metadata = _grounding_metadata(grounder)
    context["last_visual_grounding"] = metadata
    if point is None:
        action = Action(type="click", target=chat_name, mock=args.dry_run, metadata=metadata)
        verdict = Verdict(status="blocked", reason="visual_chat_list_item_not_found", evidence={**metadata, "no_fallback": True})
        return action, verdict

    screen_point = _screenshot_point_to_screen(point, observation.metadata)
    result = backend.click(screen_point[0], screen_point[1], chat_name)
    return _action_verdict_from_backend(
        action_type="click",
        target=chat_name,
        coordinates=screen_point,
        result=result,
        dry_run=args.dry_run,
        metadata=metadata,
    )


def _execute_visual_message_input(
    args: argparse.Namespace,
    task: TaskSpec,
    backend: Any,
    context: dict[str, Any],
    grounder: HybridGrounder,
    goal: StepGoal,
    observation: Observation,
) -> tuple[Action, Verdict]:
    point = grounder.locate_target(
        "message input box at bottom of chat",
        observation.screenshot_path,
        observation.ocr_texts,
        accessibility_candidates=observation.accessibility_candidates,
    )
    metadata = _grounding_metadata(grounder)
    context["last_visual_grounding"] = metadata

    if point is None:
        fallback_name = _fallback_anchor_for_target("message_input", context.get("planned_points", {}))
        if fallback_name:
            point = context["planned_points"][fallback_name]
            metadata = {**metadata, "coordinate_source": "explicit_test_geometry_fallback", "fallback_anchor": fallback_name}
        else:
            action = Action(type="paste_text", target="message_input", mock=args.dry_run, metadata=metadata)
            verdict = Verdict(status="blocked", reason="message_input_not_found_by_hybrid_grounding", evidence={**metadata, "no_fixed_coordinate_fallback": True})
            return action, verdict

    screen_point = _screenshot_point_to_screen(point, observation.metadata)
    click = backend.click(screen_point[0], screen_point[1], "message_input")
    if not click.ok:
        return _action_verdict_from_backend(
            action_type="paste_text",
            target="message_input",
            coordinates=screen_point,
            result=click,
            dry_run=args.dry_run,
            metadata=metadata,
        )

    text = str(task.slots.get("message", ""))
    paste = backend.paste_text(text)
    combined_metadata = {
        **metadata,
        **(click.metadata or {}),
        "paste": paste.metadata or {},
    }
    action = Action(
        type="paste_text",
        target="message_input",
        text=text,
        coordinates=screen_point,
        mock=args.dry_run,
        metadata=combined_metadata,
    )
    verdict = Verdict(
        status="pass" if paste.ok else "blocked",
        reason=paste.reason,
        evidence=combined_metadata,
    )
    return action, verdict


def _action_verdict_from_backend(
    action_type: str,
    target: str,
    coordinates: tuple[int, int],
    result: BackendResult,
    dry_run: bool,
    metadata: dict[str, Any],
) -> tuple[Action, Verdict]:
    combined_metadata = {**metadata, **(result.metadata or {})}
    action = Action(
        type=action_type,
        target=target,
        coordinates=coordinates,
        mock=dry_run,
        metadata=combined_metadata,
    )
    verdict = Verdict(
        status="pass" if result.ok else "blocked",
        reason=result.reason,
        evidence=combined_metadata,
    )
    return action, verdict


def _grounding_metadata(grounder: HybridGrounder) -> dict[str, Any]:
    metadata = dict(grounder.last_metadata or {})
    metadata.setdefault("grounding", "hybrid")
    return metadata


def _looks_like_message_page(observation: Observation) -> bool:
    summary = observation.screen_summary.lower()
    if "conversation list" in summary or "recent chats" in summary or "message page" in summary:
        return True
    visible = " ".join(str(item.get("text", "")) for item in observation.ocr_texts)
    return any(marker in visible for marker in ["会话", "CUA-Lark-Test"])


def _normalize_target_name(target: str, chat_name: str) -> str:
    lowered = target.lower()
    if lowered in {"feishu_window"} or "飞书" in target and "窗口" in target:
        return "feishu_window"
    if lowered in {"message_module"} or "消息入口" in target or "消息按钮" in target or "message button" in lowered:
        return "message_module"
    if lowered in {"message_input"} or "输入框" in target or "message input" in lowered:
        return "message_input"
    if lowered in {"send_button_or_enter"} or "发送按钮" in target or "enter" in lowered or "send button" in lowered:
        return "send_button_or_enter"
    if target == chat_name or lowered in {"chat_name", "chat_list_item"} or chat_name.lower() in lowered:
        return chat_name
    return target


def _screenshot_point_to_screen(point: tuple[int, int], metadata: dict[str, Any]) -> tuple[int, int]:
    origin = metadata.get("origin") or metadata.get("screenshot_origin") or [0, 0]
    return int(point[0] + int(origin[0])), int(point[1] + int(origin[1]))


def _fallback_anchor_for_target(target: str, planned_points: dict[str, tuple[int, int]]) -> str | None:
    if target == "message_input" and "message_input" in planned_points:
        return "message_input"
    return None


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


def _exit_code_for_status(status: str, dry_run: bool = False, strict: bool = False) -> int:
    if strict:
        return 0 if status == "pass" else 1
    if status in {"pass", "sent_with_screenshot_evidence", "needs_manual_verification"}:
        return 0
    if dry_run and status in {"uncertain", "needs_manual_verification"}:
        return 0
    return 1


def load_desktop_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_feishu_verification_config(args: argparse.Namespace) -> dict[str, Any]:
    try:
        with Path("configs/feishu.yaml").open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        data = {}
    verification = data.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    return verification


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
