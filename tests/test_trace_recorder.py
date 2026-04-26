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


def test_trace_recorder_keeps_real_ui_metadata(tmp_path: Path) -> None:
    task = TaskSpec(id="trace_real", product="im", instruction="mock", slots={"chat_name": "CUA-Lark-Test"})
    recorder = TraceRecorder(base_dir=tmp_path)
    trace = recorder.start(task, run_id="run_001")
    observation = Observation(
        step_index=1,
        screen_summary="coordinate plan",
        screenshot_path="before.png",
        metadata={
            "coordinate_source": "config_fixed_anchor",
            "base_resolution": [1440, 900],
            "actual_resolution": [1440, 900],
            "scale_x": 1.0,
            "scale_y": 1.0,
        },
    )
    action = Action(type="coordinate_plan", target="im_anchors", metadata=observation.metadata)
    verdict = Verdict(status="pass", reason="coordinates_planned", evidence=observation.metadata)

    recorder.record_step(trace, observation, action, verdict)

    payload = (tmp_path / "trace_real_run_001" / "step_001.json").read_text(encoding="utf-8")
    assert "config_fixed_anchor" in payload
    assert "scale_x" in payload


def test_observation_screenshot_path_can_be_none() -> None:
    observation = Observation(step_index=1, screen_summary="no screenshot", screenshot_path=None)

    assert observation.screenshot_path is None


def test_report_renders_verification_summary(tmp_path: Path) -> None:
    task = TaskSpec(id="trace_verify", product="im", instruction="mock", slots={"chat_name": "CUA-Lark-Test"})
    recorder = TraceRecorder(base_dir=tmp_path)
    trace = recorder.start(task, run_id="run_001")
    trace.status = "needs_manual_verification"
    trace.metadata["verification_summary"] = {
        "evidence_schema_version": "im_verification.v1",
        "final_status": "needs_manual_verification",
        "reason": "verify_needs_manual_verification",
        "evidences": [
            {
                "source": "screenshot",
                "status": "pass",
                "reason": "verify_screenshot_pass",
                "confidence": 0.45,
                "details": {"after_screenshot": "after.png"},
            }
        ],
        "manual_checklist": ["确认群名为：CUA-Lark-Test"],
    }

    report_path = write_markdown_report(trace, Path(trace.trace_dir) / "report.md")
    report = report_path.read_text(encoding="utf-8")

    assert "## Verification Summary" in report
    assert "im_verification.v1" in report
    assert "确认群名为：CUA-Lark-Test" in report
