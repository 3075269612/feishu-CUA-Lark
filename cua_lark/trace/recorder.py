from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from cua_lark.report.markdown_report import write_markdown_report
from cua_lark.task.loader import dump_task
from cua_lark.task.schema import Action, Observation, TaskSpec, Trace, TraceEvent, Verdict


class TraceRecorder:
    def __init__(self, base_dir: str | Path = "runs") -> None:
        self.base_dir = Path(base_dir)

    def start(self, task: TaskSpec, run_id: str | None = None) -> Trace:
        run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        trace_dir = self._unique_trace_dir(task.id, run_id)
        trace_dir.mkdir(parents=True, exist_ok=False)
        dump_task(task, trace_dir / "task.yaml")
        trace = Trace(task_id=task.id, run_id=run_id, trace_dir=str(trace_dir))
        self._append_event(trace, "run_started", metadata={"task_id": task.id})
        return trace

    def record_step(
        self,
        trace: Trace,
        observation: Observation,
        action: Action,
        verdict: Verdict,
        metadata: dict[str, Any] | None = None,
        before_screenshot: str | None = None,
        after_screenshot: str | None = None,
    ) -> TraceEvent:
        step_metadata = metadata or {}
        if before_screenshot or after_screenshot:
            step_metadata = {
                **step_metadata,
                "before_screenshot": before_screenshot,
                "after_screenshot": after_screenshot,
            }
        event = self._append_event(
            trace,
            "step",
            step_index=observation.step_index,
            observation=observation,
            action=action,
            verdict=verdict,
            metadata=step_metadata,
        )
        step_path = Path(trace.trace_dir) / f"step_{observation.step_index:03d}.json"
        step_path.write_text(json.dumps(event.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        action_path = Path(trace.trace_dir) / f"step_{observation.step_index:03d}_action.json"
        action_path.write_text(json.dumps(action.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        verdict_path = Path(trace.trace_dir) / f"step_{observation.step_index:03d}_verdict.json"
        verdict_path.write_text(json.dumps(verdict.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        return event

    def finalize(self, trace: Trace, status: str) -> Trace:
        trace.status = status  # type: ignore[assignment]
        self._append_event(trace, "run_finished", metadata={"status": status})
        return trace

    def write_report(self, trace: Trace) -> Path:
        report_path = write_markdown_report(trace, Path(trace.trace_dir) / "report.md")
        self._append_event(trace, "report_written", metadata={"path": str(report_path)})
        return report_path

    def _append_event(
        self,
        trace: Trace,
        event_type: str,
        step_index: int | None = None,
        observation: Observation | None = None,
        action: Action | None = None,
        verdict: Verdict | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            event_type=event_type,
            step_index=step_index,
            observation=observation,
            action=action,
            verdict=verdict,
            metadata=metadata or {},
        )
        trace.events.append(event)
        trace_path = Path(trace.trace_dir) / "trace.jsonl"
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return event

    def _unique_trace_dir(self, task_id: str, run_id: str) -> Path:
        base = self.base_dir / f"{task_id}_{run_id}"
        if not base.exists():
            return base
        index = 1
        while True:
            candidate = self.base_dir / f"{task_id}_{run_id}_{index}"
            if not candidate.exists():
                return candidate
            index += 1
