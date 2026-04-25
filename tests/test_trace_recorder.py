from pathlib import Path

from cua_lark.report.markdown_report import write_markdown_report
from cua_lark.task.schema import Action, Observation, TaskSpec, Verdict
from cua_lark.trace.recorder import TraceRecorder


def test_trace_recorder_writes_run_artifacts(tmp_path: Path) -> None:
    task = TaskSpec(
        id="trace_test",
        product="im",
        instruction="mock",
        slots={"chat_name": "CUA-Lark-Test"},
    )
    recorder = TraceRecorder(base_dir=tmp_path)
    trace = recorder.start(task, run_id="run_001")
    observation = Observation(step_index=1, screen_summary="mock screen")
    action = Action(type="mock_click", target="message_module")
    verdict = Verdict(status="pass", reason="ok")

    recorder.record_step(trace, observation, action, verdict)
    recorder.finalize(trace, "pass")
    report_path = write_markdown_report(trace, Path(trace.trace_dir) / "report.md")

    trace_dir = tmp_path / "trace_test_run_001"
    assert trace_dir.exists()
    assert (trace_dir / "task.yaml").exists()
    assert (trace_dir / "trace.jsonl").exists()
    assert (trace_dir / "step_001.json").exists()
    assert report_path.exists()
    assert "Status: `pass`" in report_path.read_text(encoding="utf-8")
