from pathlib import Path

from cua_lark.perception.screen_state import RealPerceptor
from cua_lark.task.schema import StepGoal


class FakeOcr:
    def extract(self, screenshot_path: str | None):
        return [{"text": "CUA-Lark-Test", "bbox": [1, 2, 3, 4], "confidence": 0.9}]


class FakeVlm:
    def summarize(self, screenshot_path: str | None, prompt: str | None = None) -> str:
        return "target appears"


def test_real_perceptor_observe_chains_screenshot_ocr_vlm(tmp_path: Path) -> None:
    def screenshot_func(window_title: str | None, output_path: str) -> str:
        Path(output_path).write_text("fake", encoding="utf-8")
        return output_path

    perceptor = RealPerceptor(ocr_client=FakeOcr(), vlm_client=FakeVlm(), screenshot_func=screenshot_func)
    goal = StepGoal(index=3, description="Open chat", target="CUA-Lark-Test", expected="chat opened")

    observation = perceptor.observe(goal, tmp_path)

    assert observation.step_index == 3
    assert observation.screen_summary == "target appears"
    assert observation.screenshot_path is not None
    assert observation.ocr_texts[0]["text"] == "CUA-Lark-Test"
    assert observation.metadata["mock"] is False
