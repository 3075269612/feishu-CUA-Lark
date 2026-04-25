from __future__ import annotations

from cua_lark.task.schema import Observation, StepGoal, Verdict


class MockVerifier:
    def verify_step(self, goal: StepGoal, observation: Observation) -> Verdict:
        return Verdict(
            status="pass",
            reason=f"Mock verification passed for: {goal.description}",
            evidence={"screen_summary": observation.screen_summary, "target": goal.target},
            extracted_state={"last_completed_goal": goal.description},
        )
