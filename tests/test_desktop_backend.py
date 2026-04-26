from cua_lark.actions.desktop_backend import DryRunDesktopBackend


def test_dry_run_backend_records_plans_without_real_input(tmp_path) -> None:
    backend = DryRunDesktopBackend(screen_size=(1440, 900))

    focus = backend.focus_window(["Feishu", "飞书"])
    screenshot = backend.screenshot(tmp_path / "screen.png")
    click = backend.click(10, 20, "message_input")
    paste = backend.paste_text("Hello from CUA-Lark run_001")
    press = backend.press("enter")

    assert focus.ok
    assert screenshot.ok
    assert click.metadata["planned_only"]
    assert paste.metadata["planned_only"]
    assert press.metadata["planned_only"]
    assert [name for name, _ in backend.calls] == ["focus_window", "screenshot", "click", "paste_text", "press"]
