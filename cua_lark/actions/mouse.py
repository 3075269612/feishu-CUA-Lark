from __future__ import annotations

from cua_lark.task.schema import Action


def click(target: str, coordinates: tuple[int, int] | None = None, mock: bool = True) -> Action:
    return Action(type="click", target=target, coordinates=coordinates, mock=mock)
