from __future__ import annotations

from cua_lark.task.schema import Action


def click(target: str, coordinates: tuple[int, int] | None = None, mock: bool = True) -> Action:
    return Action(type="click", target=target, coordinates=coordinates, mock=mock)


def double_click(target: str, coordinates: tuple[int, int] | None = None, mock: bool = True) -> Action:
    return Action(type="double_click", target=target, coordinates=coordinates, mock=mock)


def right_click(target: str, coordinates: tuple[int, int] | None = None, mock: bool = True) -> Action:
    return Action(type="right_click", target=target, coordinates=coordinates, mock=mock)


def drag(
    target: str,
    start_coordinates: tuple[int, int],
    end_coordinates: tuple[int, int],
    duration: float = 0.2,
    mock: bool = True,
) -> Action:
    return Action(
        type="drag",
        target=target,
        coordinates=start_coordinates,
        mock=mock,
        metadata={
            "start_coordinates": start_coordinates,
            "end_coordinates": end_coordinates,
            "duration": duration,
        },
    )


def scroll(target: str, clicks: int, coordinates: tuple[int, int] | None = None, mock: bool = True) -> Action:
    return Action(
        type="scroll",
        target=target,
        coordinates=coordinates,
        mock=mock,
        metadata={"clicks": clicks},
    )
