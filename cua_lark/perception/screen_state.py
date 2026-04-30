from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from cua_lark.perception.ocr import OcrClient
from cua_lark.perception.screenshot import capture_screenshot, capture_screenshot_with_metadata
from cua_lark.perception.vlm import VlmClient
from cua_lark.perception.accessibility import AccessibilityExtractor, MockAccessibilityExtractor
from cua_lark.task.schema import Observation, StepGoal


class MockPerceptor:
    def observe(self, goal: StepGoal) -> Observation:
        return Observation(
            step_index=goal.index,
            screen_summary=f"Mock screen state for: {goal.description}",
            screenshot_path=None,
            ocr_texts=[],
            accessibility_candidates=[],
            metadata={"target": goal.target, "mock": True},
        )


class RealPerceptor:
    """Visual-first perception chain: screenshot, OCR, Accessibility Tree, then VLM summary."""

    def __init__(
        self,
        ocr_client: OcrClient | None = None,
        vlm_client: VlmClient | None = None,
        accessibility_extractor: AccessibilityExtractor | None = None,
        window_title: str | None = "Feishu",
        screenshot_func: Callable[[str | None, str], str | None] | None = None,
        enable_accessibility: bool = True,
    ) -> None:
        self.ocr_client = ocr_client or OcrClient()
        self.vlm_client = vlm_client or VlmClient()
        self.accessibility_extractor = accessibility_extractor or (AccessibilityExtractor() if enable_accessibility else MockAccessibilityExtractor())
        self.window_title = window_title
        self.screenshot_func = screenshot_func or capture_screenshot
        self.enable_accessibility = enable_accessibility

    def observe(self, goal: StepGoal, trace_dir: str | Path) -> Observation:
        trace_path = Path(trace_dir)
        trace_path.mkdir(parents=True, exist_ok=True)
        screenshot_meta: dict[str, Any] = {}
        if self.screenshot_func is capture_screenshot:
            capture = capture_screenshot_with_metadata(
                window_title=self.window_title,
                output_path=str(trace_path / f"step_{goal.index:03d}_observe.png"),
            )
            screenshot_path = str(capture.get("path")) if capture else None
            screenshot_meta = capture or {}
        else:
            screenshot_path = self.screenshot_func(
                window_title=self.window_title,
                output_path=str(trace_path / f"step_{goal.index:03d}_observe.png"),
            )

        # Extract OCR texts
        ocr_texts = self.ocr_client.extract(screenshot_path)

        # Extract Accessibility Tree elements
        accessibility_candidates: list[dict[str, Any]] = []
        if self.enable_accessibility:
            try:
                accessibility_candidates = self.accessibility_extractor.extract_elements(
                    window_title=self.window_title,
                    max_depth=2,  # Limit depth to avoid performance issues (depth 3 = 2263 elements, depth 8 = too many)
                    include_invisible=False,
                )
            except Exception:
                # Silently fall back to empty list if extraction fails
                pass

        # Generate VLM summary
        screen_summary = self._summarize(goal, screenshot_path, ocr_texts)

        return Observation(
            step_index=goal.index,
            screen_summary=screen_summary,
            screenshot_path=screenshot_path,
            ocr_texts=ocr_texts,
            accessibility_candidates=accessibility_candidates,
            metadata={
                "target": goal.target,
                "mock": False,
                "window_title": self.window_title,
                "ocr_count": len(ocr_texts),
                "accessibility_count": len(accessibility_candidates),
                "screenshot_captured": screenshot_path is not None,
                **screenshot_meta,
            },
        )

    def _summarize(
        self,
        goal: StepGoal,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
    ) -> str:
        prompt = (
            "Summarize the current Feishu/Lark screen for a UI automation agent.\n"
            f"Current step: {goal.description}\n"
            f"Target element: {goal.target}\n"
            f"Expected state: {goal.expected}\n"
            "Mention visible UI state, likely blockers, and whether the target appears."
        )
        if screenshot_path:
            summary = self.vlm_client.summarize(screenshot_path, prompt)
            if summary:
                return summary

        visible_text = ", ".join(str(item.get("text", "")) for item in ocr_texts if item.get("text"))
        if visible_text:
            return f"OCR-only screen state: {visible_text}"
        return "No screenshot or OCR text available for real perception."
