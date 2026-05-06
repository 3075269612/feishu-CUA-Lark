import json
from pathlib import Path

from cua_lark.main import main
from cua_lark.task.schema import Action, Observation, TaskSpec, Verdict
from cua_lark.trace.exporter import discover_trace_files, export_trace_datasets, parse_trace_run
from cua_lark.trace.recorder import TraceRecorder


def test_discover_trace_files_finds_nested_suite_cases(tmp_path: Path) -> None:
    trace_dir = _write_trace(tmp_path / "runs" / "suite" / "case", status="pass")

    traces = discover_trace_files(tmp_path / "runs")

    assert traces == [trace_dir / "trace.jsonl"]


def test_parse_trace_run_reads_task_steps_and_status(tmp_path: Path) -> None:
    trace_dir = _write_trace(tmp_path / "runs", status="pass", product="docs")

    parsed = parse_trace_run(trace_dir / "trace.jsonl")

    assert parsed["task_id"] == "docs_trace"
    assert parsed["product"] == "docs"
    assert parsed["status"] == "pass"
    assert len(parsed["steps"]) == 1
    assert parsed["steps"][0]["action"]["metadata"]["coordinate_source"] == "ocr_match"


def test_export_trace_datasets_defaults_to_pass_only(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_trace(runs_dir / "pass_case", status="pass", product="im", task_id="im_trace")
    _write_trace(runs_dir / "manual_case", status="needs_manual_verification", product="docs", task_id="docs_trace")

    summary = export_trace_datasets(runs_dir, tmp_path / "out")

    assert summary["exported_runs"] == 1
    assert summary["skipped_runs"] == 1
    assert summary["grounding_examples"] == 1
    traces = _read_jsonl(tmp_path / "out" / "traces.jsonl")
    grounding = _read_jsonl(tmp_path / "out" / "grounding_eval.jsonl")
    fewshot = _read_jsonl(tmp_path / "out" / "fewshot_examples.jsonl")
    assert traces[0]["task_id"] == "im_trace"
    assert grounding[0]["coordinate_source"] == "ocr_match"
    assert fewshot[0]["product"] == "im"
    assert (tmp_path / "out" / "export_summary.md").exists()
    assert (tmp_path / "out" / "mcp_manifest.json").exists()


def test_export_trace_datasets_can_include_manual_bucket(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_trace(runs_dir / "manual_case", status="needs_manual_verification", product="docs", task_id="docs_trace")

    summary = export_trace_datasets(runs_dir, tmp_path / "out", statuses=("pass", "needs_manual_verification"))

    assert summary["exported_runs"] == 1
    assert summary["product_counts"] == {"docs": 1}
    traces = _read_jsonl(tmp_path / "out" / "traces.jsonl")
    assert traces[0]["status"] == "needs_manual_verification"


def test_export_traces_cli_writes_phase8_outputs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_trace(runs_dir, status="pass", product="im", task_id="im_trace")
    out_dir = tmp_path / "datasets" / "generated"

    code = main(["export-traces", str(runs_dir), "--out", str(out_dir)])

    assert code == 0
    summary = json.loads((out_dir / "export_summary.json").read_text(encoding="utf-8"))
    assert summary["exported_runs"] == 1
    assert (out_dir / "traces.jsonl").exists()
    assert (out_dir / "grounding_eval.jsonl").exists()
    assert (out_dir / "fewshot_examples.jsonl").exists()


def _write_trace(
    base_dir: Path,
    status: str,
    product: str = "im",
    task_id: str | None = None,
) -> Path:
    task = TaskSpec(
        id=task_id or f"{product}_trace",
        product=product,
        instruction=f"Run {product} trace",
        slots={"chat_name": "CUA-Lark-Test"},
    )
    recorder = TraceRecorder(base_dir=base_dir)
    trace = recorder.start(task, run_id="run_001")
    observation = Observation(
        step_index=1,
        screen_summary="screen with target",
        screenshot_path="step_001_observe.png",
    )
    action = Action(
        type="click",
        target="target button",
        coordinates=(120, 240),
        mock=False,
        metadata={
            "coordinate_source": "ocr_match",
            "final_bbox": [100, 220, 140, 260],
            "stage": "STAGE_TEST",
        },
    )
    verdict = Verdict(status="pass", reason="clicked")
    recorder.record_step(trace, observation, action, verdict)
    recorder.finalize(trace, status)
    recorder.write_report(trace)
    return Path(trace.trace_dir)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
