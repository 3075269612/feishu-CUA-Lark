"""CLI integration tests for docs create."""

from cua_lark.main import main


def _apply_common_monkeypatches(monkeypatch, main_module):
    class FakeGrounder:
        def __init__(self):
            self.last_metadata: dict = {}

        def locate_target(self, target, screenshot_path, ocr_candidates, accessibility_candidates=None, **kwargs):
            self.last_metadata = {
                "target": target,
                "coordinate_source": "test_hybrid_grounding",
                "screenshot_point": [100, 100],
            }
            return (100, 100)

    class FakeBackend(main_module.DryRunDesktopBackend):
        def screenshot(self, output_path):
            result = super().screenshot(output_path)
            result.metadata["planned_only"] = False
            return result

    class FakeVlmClient:
        def summarize(self, screenshot_path, prompt=None):
            return "docs target appears"

    class FakeOcrClient:
        def extract(self, screenshot_path):
            return [{"text": "云文档", "bbox": [0, 0, 100, 20], "confidence": 0.95}]

    class FakeAccessibility:
        def extract_elements(self, window_title=None, max_depth=4, include_invisible=False):
            return []

    monkeypatch.setattr(
        "cua_lark.actions.feishu_launcher.ensure_feishu_frontmost",
        lambda window_title_candidates: main_module.BackendResult(True, "feishu_frontmost", {"backend": "test"}),
    )
    monkeypatch.setattr(main_module, "PyAutoGuiBackend", FakeBackend)
    monkeypatch.setattr(main_module, "HybridGrounder", FakeGrounder)
    monkeypatch.setattr(main_module, "VlmClient", FakeVlmClient)
    monkeypatch.setattr(main_module, "OcrClient", FakeOcrClient)
    monkeypatch.setattr(main_module, "AccessibilityExtractor", FakeAccessibility)
    monkeypatch.setattr(
        main_module,
        "load_feishu_verification_config",
        lambda args: {"api_oracle_enabled": False, "ocr_enabled": False, "vlm_enabled": False},
    )


def test_docs_create_loads_in_mock_mode(tmp_path) -> None:
    code = main([
        "run",
        "testcases/docs/create_blank_doc.yaml",
        "--mock",
        "--runs-dir",
        str(tmp_path),
    ])
    assert code == 0


def test_docs_create_dry_run_returns_uncertain(tmp_path, monkeypatch) -> None:
    from cua_lark import main as main_module

    _apply_common_monkeypatches(monkeypatch, main_module)

    code = main([
        "run",
        "testcases/docs/create_blank_doc.yaml",
        "--real-ui",
        "--confirm-target",
        "CUA-Dark",
        "--dry-run",
        "--runs-dir",
        str(tmp_path),
    ])

    assert code == 0


def test_docs_create_with_allow_send_runs_all_stages(tmp_path, monkeypatch) -> None:
    from cua_lark import main as main_module

    _apply_common_monkeypatches(monkeypatch, main_module)

    code = main([
        "run",
        "testcases/docs/create_blank_doc.yaml",
        "--real-ui",
        "--confirm-target",
        "CUA-Dark",
        "--allow-send",
        "--runs-dir",
        str(tmp_path),
    ])

    assert code == 0
