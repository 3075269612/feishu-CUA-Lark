from __future__ import annotations

from cua_lark.task.schema import Action


def press(key: str, mock: bool = True) -> Action:
    return Action(type="press_key", target=key, mock=mock)
