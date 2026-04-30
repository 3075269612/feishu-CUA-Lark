from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cua_lark.perception.vlm import VlmClient
from cua_lark.task.schema import Observation, StepGoal, TaskSpec


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


class LlmPlanner:
    """Planner that asks the configured VLM/LLM for task-specific UI steps."""

    def __init__(
        self,
        vlm_client: VlmClient | None = None,
        skills_dir: str | Path = "skills",
        fallback_planner: MockPlanner | None = None,
    ) -> None:
        self.vlm_client = vlm_client or VlmClient()
        self.skills_dir = Path(skills_dir)
        self.fallback_planner = fallback_planner or MockPlanner()

    def plan(self, task: TaskSpec) -> list[StepGoal]:
        prompt = self._build_plan_prompt(task)
        response = self.vlm_client.summarize(None, prompt)
        steps = _parse_step_goals(response)
        if steps:
            return steps
        return self.fallback_planner.plan(task)

    def replan_step(self, task: TaskSpec, observation: Observation, step_index: int) -> StepGoal:
        prompt = self._build_replan_prompt(task, observation, step_index)
        response = self.vlm_client.summarize(observation.screenshot_path, prompt)
        steps = _parse_step_goals(response)
        if steps:
            step = steps[0]
            return step.model_copy(update={"index": step_index})

        for fallback in self.fallback_planner.plan(task):
            if fallback.index >= step_index:
                return fallback.model_copy(update={"index": step_index})
        return StepGoal(
            index=step_index,
            description="Recover by reassessing the current screen",
            target=task.product,
            expected="next actionable UI target identified",
            metadata={"source": "fallback_replan"},
        )

    def _build_plan_prompt(self, task: TaskSpec) -> str:
        return (
            "You are planning a Feishu/Lark desktop UI automation task.\n"
            "Use the skill notes as operational context, then return only JSON.\n"
            "JSON schema: [{\"index\": 1, \"description\": \"...\", \"target\": \"...\", \"expected\": \"...\"}]\n"
            f"Task JSON:\n{json.dumps(task.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"Skill notes:\n{self._load_skill_context()}"
        )

    def _build_replan_prompt(self, task: TaskSpec, observation: Observation, step_index: int) -> str:
        return (
            "Decide the next single UI automation step from the current screen.\n"
            "Return only a JSON array with one object using keys: index, description, target, expected.\n"
            f"Use index {step_index}.\n"
            f"Task JSON:\n{json.dumps(task.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"Observation JSON:\n{json.dumps(observation.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"Skill notes:\n{self._load_skill_context()}"
        )

    def _load_skill_context(self) -> str:
        if not self.skills_dir.exists():
            return ""
        chunks: list[str] = []
        for path in sorted(self.skills_dir.glob("*.md")):
            try:
                chunks.append(f"# {path.name}\n{path.read_text(encoding='utf-8')}")
            except OSError:
                continue
        return "\n\n".join(chunks)


def _parse_step_goals(text: str) -> list[StepGoal]:
    payload = _extract_json_payload(text)
    if payload is None:
        return []
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict):
        raw = raw.get("steps") or raw.get("plan") or [raw]
    if not isinstance(raw, list):
        return []

    steps: list[StepGoal] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        try:
            steps.append(_step_from_dict(item, default_index=index))
        except (TypeError, ValueError):
            continue
    return steps


def _extract_json_payload(text: str) -> str | None:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return stripped

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if 0 <= array_start < array_end:
        return stripped[array_start : array_end + 1]

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if 0 <= object_start < object_end:
        return stripped[object_start : object_end + 1]
    return None


def _step_from_dict(item: dict[str, Any], default_index: int) -> StepGoal:
    description = str(item.get("description") or item.get("goal") or item.get("step") or "").strip()
    target = str(item.get("target") or item.get("element") or description or "screen").strip()
    expected = str(item.get("expected") or item.get("success") or item.get("expected_state") or "").strip()
    return StepGoal(
        index=int(item.get("index") or default_index),
        description=description or f"Execute step {default_index}",
        target=target,
        expected=expected or "step completed",
        metadata={"source": "llm", **(item.get("metadata") if isinstance(item.get("metadata"), dict) else {})},
    )
