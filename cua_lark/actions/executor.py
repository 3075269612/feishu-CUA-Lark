from __future__ import annotations

from cua_lark.task.schema import Action, StepGoal, TaskSpec


class MockActionExecutor:
    def build_action(self, task: TaskSpec, goal: StepGoal) -> Action:
        if goal.target == "message_input":
            return Action(type="paste_text", target=goal.target, text=str(task.slots.get("message", "")), mock=True)
        if goal.target == "send_button_or_enter":
            return Action(type="press_key", target="Enter", mock=True)
        return Action(type="mock_click", target=goal.target, mock=True, metadata={"description": goal.description})

    def execute(self, action: Action) -> Action:
        return action.model_copy(update={"metadata": {**action.metadata, "executed": "mock"}})
