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
    assert _exit_code_for_status("needs_manual_verification") == 0
    assert _exit_code_for_status("blocked") == 1
    assert _exit_code_for_status("fail") == 1
    assert _exit_code_for_status("uncertain") == 1
    assert _exit_code_for_status("uncertain", dry_run=True) == 0
    assert _exit_code_for_status("needs_manual_verification", strict=True) == 1
    assert _exit_code_for_status("pass", strict=True) == 0


def test_dry_run_does_not_upgrade_to_pass(tmp_path) -> None:
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
    report = next(tmp_path.glob("*/report.md")).read_text(encoding="utf-8")
    assert "Status: `uncertain`" in report
    assert "verify_im_send" not in report


def test_allow_send_creates_verification_step_with_dry_backend(tmp_path, monkeypatch) -> None:
    from cua_lark import main as main_module

    class SendCapableDryBackend(main_module.DryRunDesktopBackend):
        def screenshot(self, output_path):
            result = super().screenshot(output_path)
            result.metadata["planned_only"] = False
            return result

        def press(self, key: str):
            result = super().press(key)
            result.metadata["planned_only"] = False
            return result

    monkeypatch.setattr(main_module, "PyAutoGuiBackend", SendCapableDryBackend)
    code = main(
        [
            "run",
            "testcases/im/send_text.yaml",
            "--real-ui",
            "--confirm-target",
            "CUA-Lark-Test",
            "--allow-send",
            "--assume-frontmost-window",
            "--runs-dir",
            str(tmp_path),
        ]
    )

    assert code == 0
    report = next(tmp_path.glob("*/report.md")).read_text(encoding="utf-8")
    assert "verify_im_send" in report
    assert "needs_manual_verification" in report


def test_strict_verification_returns_nonzero_for_manual_verification(tmp_path, monkeypatch) -> None:
    from cua_lark import main as main_module

    class SendCapableDryBackend(main_module.DryRunDesktopBackend):
        def screenshot(self, output_path):
            result = super().screenshot(output_path)
            result.metadata["planned_only"] = False
            return result

        def press(self, key: str):
            result = super().press(key)
            result.metadata["planned_only"] = False
            return result

    monkeypatch.setattr(main_module, "PyAutoGuiBackend", SendCapableDryBackend)
    code = main(
        [
            "run",
            "testcases/im/send_text.yaml",
            "--real-ui",
            "--confirm-target",
            "CUA-Lark-Test",
            "--allow-send",
            "--assume-frontmost-window",
            "--strict-verification",
            "--runs-dir",
            str(tmp_path),
        ]
    )

    assert code == 1
