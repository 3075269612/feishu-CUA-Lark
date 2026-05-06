from cua_lark.actions.desktop_backend import DryRunDesktopBackend
from cua_lark.actions.mouse import click, double_click, drag, right_click, scroll


def test_dry_run_backend_records_plans_without_real_input(tmp_path) -> None:
    backend = DryRunDesktopBackend(screen_size=(1440, 900))

    focus = backend.focus_window(["Feishu", "飞书"])
    screenshot = backend.screenshot(tmp_path / "screen.png")
    click = backend.click(10, 20, "message_input")
    double_click = backend.double_click(12, 22, "doc_title")
    right_click = backend.right_click(14, 24, "context_target")
    drag = backend.drag(1, 2, 30, 40, "selection", duration=0.3)
    scroll = backend.scroll(-5, x=100, y=200, target="list")
    paste = backend.paste_text("Hello from CUA-Lark run_001")
    press = backend.press("enter")

    assert focus.ok
    assert screenshot.ok
    assert click.metadata["planned_only"]
    assert double_click.metadata["planned_only"]
    assert right_click.metadata["planned_only"]
    assert drag.metadata["planned_only"]
    assert drag.metadata["end_x"] == 30
    assert scroll.metadata["planned_only"]
    assert scroll.metadata["clicks"] == -5
    assert paste.metadata["planned_only"]
    assert press.metadata["planned_only"]
    assert [name for name, _ in backend.calls] == [
        "focus_window",
        "screenshot",
        "click",
        "double_click",
        "right_click",
        "drag",
        "scroll",
        "paste_text",
        "press",
    ]


def test_mouse_action_helpers_have_stable_action_types() -> None:
    assert click("button", (1, 2)).type == "click"

    double = double_click("file", (3, 4), mock=False)
    assert double.type == "double_click"
    assert double.target == "file"
    assert double.coordinates == (3, 4)
    assert not double.mock

    right = right_click("row", (5, 6))
    assert right.type == "right_click"
    assert right.coordinates == (5, 6)

    drag_action = drag("range", (1, 1), (9, 9), duration=0.4)
    assert drag_action.type == "drag"
    assert drag_action.coordinates == (1, 1)
    assert drag_action.metadata["start_coordinates"] == (1, 1)
    assert drag_action.metadata["end_coordinates"] == (9, 9)
    assert drag_action.metadata["duration"] == 0.4

    scroll_action = scroll("list", -3, coordinates=(10, 20))
    assert scroll_action.type == "scroll"
    assert scroll_action.coordinates == (10, 20)
    assert scroll_action.metadata["clicks"] == -3
