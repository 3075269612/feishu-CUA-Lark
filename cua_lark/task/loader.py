from __future__ import annotations

from pathlib import Path

import yaml

from cua_lark.task.schema import TaskSpec


def load_task(path: str | Path) -> TaskSpec:
    task_path = Path(path)
    with task_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return TaskSpec.model_validate(data)


def dump_task(task: TaskSpec, path: str | Path) -> None:
    task_path = Path(path)
    task_path.parent.mkdir(parents=True, exist_ok=True)
    with task_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(task.model_dump(mode="json"), fh, allow_unicode=True, sort_keys=False)
