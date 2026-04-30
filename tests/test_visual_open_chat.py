from types import SimpleNamespace

from cua_lark.actions.desktop_backend import BackendResult
from cua_lark.main import _execute_visual_open_chat, _fallback_anchor_for_target
from cua_lark.task.schema import Observation, StepGoal


class FakeBackend:
    def __init__(self) -> None:
        self.clicks = []
        self.pastes = []
        self.presses = []

    def click(self, x: int, y: int, target: str) -> BackendResult:
        self.clicks.append((x, y, target))
        return BackendResult(True, "dry_run_click_planned", {"x": x, "y": y, "target": target, "planned_only": True})

    def paste_text(self, text: str) -> BackendResult:
        self.pastes.append(text)
        return BackendResult(True, "unexpected_paste", {})

    def press(self, key: str) -> BackendResult:
        self.presses.append(key)
        return BackendResult(True, "unexpected_press", {})


class FakeGrounder:
    def __init__(self) -> None:
        self.targets = []
        self.last_metadata = {}

    def locate_target(self, target: str, screenshot_path: str | None, ocr_candidates: list[dict], accessibility_candidates: list[dict] | None = None):
        self.targets.append(target)
        self.last_metadata = {
            "target": target,
            "screenshot_point": [100, 200],
            "coordinate_source": "test",
        }
        if target == "left conversation list item named CUA-Lark-Test":
            return (100, 200)
        return None


def test_visual_open_chat_clicks_visible_conversation_item_without_global_search() -> None:
    backend = FakeBackend()
    grounder = FakeGrounder()
    context = {"planned_points": {}}
    goal = StepGoal(index=3, description="Open chat CUA-Lark-Test", target="CUA-Lark-Test", expected="chat opened")
    observation = Observation(step_index=3, screen_summary="screen", screenshot_path="screen.png")

    action, verdict = _execute_visual_open_chat(
        SimpleNamespace(dry_run=True),
        backend,
        context,
        grounder,
        goal,
        observation,
        "CUA-Lark-Test",
    )

    assert verdict.status == "pass"
    assert action.coordinates == (100, 200)
    assert grounder.targets == ["left conversation list item named CUA-Lark-Test"]
    assert backend.clicks == [(100, 200, "CUA-Lark-Test")]
    assert backend.pastes == []
    assert backend.presses == []
    assert "search_point" not in action.metadata
    assert "paste" not in action.metadata
    assert "enter" not in action.metadata


def test_fallback_anchor_does_not_route_arbitrary_chat_name_to_search_result() -> None:
    assert _fallback_anchor_for_target("CUA-Lark-Test", {"first_search_result": (300, 165)}) is None
