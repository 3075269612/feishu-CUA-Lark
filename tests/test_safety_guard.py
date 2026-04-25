from cua_lark.agent.safety_guard import SafetyGuard
from cua_lark.task.schema import Action, TaskSpec


def test_safety_guard_allows_configured_chat() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(
        id="safe",
        product="im",
        instruction="send",
        slots={"chat_name": "CUA-Lark-Test"},
    )

    decision = guard.check_task(task)

    assert decision.allowed


def test_safety_guard_blocks_unknown_chat() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(
        id="unsafe",
        product="im",
        instruction="send",
        slots={"chat_name": "Real Customer Group"},
    )

    decision = guard.check_task(task)

    assert not decision.allowed
    assert decision.reason.startswith("chat_not_allowed")


def test_safety_guard_blocks_forbidden_action() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    action = Action(type="share_public_link", target="doc", mock=True)

    decision = guard.check_action(action)

    assert not decision.allowed
    assert decision.reason == "forbidden_action:share_public_link"
