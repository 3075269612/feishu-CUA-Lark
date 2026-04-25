from __future__ import annotations

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
