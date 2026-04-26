from cua_lark.main import main
from cua_lark.main import _exit_code_for_status


def test_mock_cli_still_runs(tmp_path) -> None:
    code = main(["run", "testcases/im/send_text.yaml", "--mock", "--runs-dir", str(tmp_path)])

    assert code == 0


def test_real_ui_requires_confirm_target(tmp_path) -> None:
    code = main(["run", "testcases/im/send_text.yaml", "--real-ui", "--dry-run", "--runs-dir", str(tmp_path)])

    assert code == 2


def test_real_ui_rejects_dry_run_allow_send_conflict(tmp_path) -> None:
    code = main(
        [
            "run",
            "testcases/im/send_text.yaml",
            "--real-ui",
            "--confirm-target",
            "CUA-Lark-Test",
            "--dry-run",
            "--allow-send",
            "--runs-dir",
            str(tmp_path),
        ]
    )

    assert code == 2


def test_real_ui_dry_run_does_not_require_desktop_dependencies(tmp_path) -> None:
    code = main(
        [
            "run",
            "testcases/im/send_text.yaml",
            "--real-ui",
            "--confirm-target",
            "CUA-Lark-Test",
            "--dry-run",
            "--runs-dir",
            str(tmp_path),
        ]
    )

    assert code == 0
    report_paths = list(tmp_path.glob("*/report.md"))
    assert report_paths
    assert "dry-run" in report_paths[0].read_text(encoding="utf-8")


def test_real_ui_final_status_maps_to_exit_code() -> None:
    assert _exit_code_for_status("sent_with_screenshot_evidence") == 0
    assert _exit_code_for_status("blocked") == 1
    assert _exit_code_for_status("fail") == 1
    assert _exit_code_for_status("uncertain") == 1
    assert _exit_code_for_status("uncertain", dry_run=True) == 0
