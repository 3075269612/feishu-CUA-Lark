import sys
from types import SimpleNamespace

from cua_lark.perception.ocr import OcrClient


def test_ocr_client_extracts_text_and_axis_aligned_bbox(monkeypatch) -> None:
    class FakeEngine:
        def __call__(self, screenshot_path: str):
            assert screenshot_path == "screen.png"
            return [
                (
                    [[10, 20], [30, 18], [32, 40], [8, 42]],
                    "hello",
                    0.98,
                )
            ], None

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", SimpleNamespace(RapidOCR=lambda: FakeEngine()))

    result = OcrClient().extract("screen.png")

    assert result == [{"text": "hello", "bbox": [8, 18, 32, 42], "confidence": 0.98}]


def test_ocr_client_mock_mode_without_screenshot_returns_empty() -> None:
    assert OcrClient().extract(None) == []
