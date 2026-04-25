from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from cua_lark.actions import MockActionExecutor
from cua_lark.agent import MockPlanner, SafetyGuard
from cua_lark.perception import MockPerceptor
from cua_lark.task.loader import load_task
from cua_lark.task.parser import render_task
from cua_lark.task.schema import Verdict
from cua_lark.trace import TraceRecorder
from cua_lark.verifier import MockVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cua-lark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a testcase")
    run.add_argument("task_path")
    run.add_argument("--mock", action="store_true", help="Use the safe mock execution loop")
    run.add_argument("--safety-config", default="configs/safety.yaml")
    run.add_argument("--runs-dir", default="runs")
    return parser


def run_task(args: argparse.Namespace) -> int:
    if not args.mock:
        print("Only --mock execution is enabled in Phase 1.")
        return 2

    raw_task = load_task(args.task_path)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_task(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
