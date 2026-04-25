from __future__ import annotations

from cua_lark.task.schema import StepGoal, TaskSpec


class MockPlanner:
    """Deterministic planner for Phase 1 mock runs."""

    def plan(self, task: TaskSpec) -> list[StepGoal]:
        if task.product == "im":
            chat_name = str(task.slots.get("chat_name", ""))
            return [
                StepGoal(index=1, description="Confirm Feishu window context", target="feishu_window", expected="window available"),
                StepGoal(index=2, description="Open message module", target="message_module", expected="message module visible"),
                StepGoal(index=3, description=f"Open chat {chat_name}", target=chat_name, expected="target chat opened"),
                StepGoal(index=4, description="Fill message input", target="message_input", expected="message text visible"),
                StepGoal(index=5, description="Send and verify message", target="send_button_or_enter", expected="latest message visible"),
            ]
        return [
            StepGoal(index=1, description=f"Mock plan for {task.product}", target=task.product, expected="mock step passes"),
        ]
