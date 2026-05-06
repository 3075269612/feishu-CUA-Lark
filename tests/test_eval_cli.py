import json
from pathlib import Path

from cua_lark.main import main


def test_eval_cli_runs_mock_suite_and_writes_summary(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
id: cli_eval_suite
description: "CLI eval suite"
cases:
  - id: im_case
    task_path: testcases/im/send_text.yaml
    product: im
    profiles: [mock]
    tags: [im]
    expected_statuses: [pass]
  - id: docs_case
    task_path: testcases/docs/create_blank_doc.yaml
    product: docs
    profiles: [mock]
    tags: [docs]
    expected_statuses: [pass]
""",
        encoding="utf-8",
    )

    code = main(["eval", str(suite_path), "--profile", "mock", "--runs-dir", str(tmp_path / "runs")])

    assert code == 0
    summary_json = next((tmp_path / "runs").glob("cli_eval_suite_mock_*/summary.json"))
    summary_md = summary_json.with_name("summary.md")
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary_md.exists()
    assert summary["suite_id"] == "cli_eval_suite"
    assert summary["metrics"]["total_cases"] == 2
    assert summary["metrics"]["success_cases"] == 2
    assert summary["metrics"]["task_success_rate"] == 1.0
