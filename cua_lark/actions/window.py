from __future__ import annotations

from cua_lark.task.schema import Action


def focus_window(name: str = "Feishu", mock: bool = True) -> Action:
    return Action(type="focus_window", target=name, mock=mock)
