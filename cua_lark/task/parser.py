from __future__ import annotations

from typing import Any

from cua_lark.task.schema import TaskSpec


def render_slots(slots: dict[str, Any], run_id: str) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    for key, value in slots.items():
        if isinstance(value, str):
            rendered[key] = value.replace("{{run_id}}", run_id)
        else:
            rendered[key] = value
    return rendered


def render_task(task: TaskSpec, run_id: str) -> TaskSpec:
    return task.model_copy(update={"slots": render_slots(task.slots, run_id)}, deep=True)
