from __future__ import annotations

from cua_lark.task.schema import Action


def paste_text(text: str, target: str = "clipboard", mock: bool = True) -> Action:
    return Action(type="paste_text", target=target, text=text, mock=mock)
