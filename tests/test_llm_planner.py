from pathlib import Path

from cua_lark.agent.planner import LlmPlanner
from cua_lark.task.schema import Observation, TaskSpec


class FakeVlm:
    def __init__(self, response: str) -> None:
        self.response = response

    def summarize(self, screenshot_path: str | None, prompt: str | None = None) -> str:
        return self.response


def test_llm_planner_parses_json_plan(tmp_path: Path) -> None:
    (tmp_path / "im.md").write_text("IM skill", encoding="utf-8")
    response = '[{"index": 1, "description": "Open IM", "target": "message_module", "expected": "visible"}]'
    planner = LlmPlanner(vlm_client=FakeVlm(response), skills_dir=tmp_path)
    task = TaskSpec(id="t", product="im", instruction="send", slots={"chat_name": "CUA-Lark-Test"})

    steps = planner.plan(task)

    assert steps[0].target == "message_module"
    assert steps[0].metadata["source"] == "llm"


def test_llm_planner_replan_step_uses_requested_index() -> None:
    response = '[{"description": "Click input", "target": "message_input", "expected": "focused"}]'
    planner = LlmPlanner(vlm_client=FakeVlm(response))
    task = TaskSpec(id="t", product="im", instruction="send")
    observation = Observation(step_index=7, screen_summary="input visible")

    step = planner.replan_step(task, observation, 7)

    assert step.index == 7
    assert step.target == "message_input"
