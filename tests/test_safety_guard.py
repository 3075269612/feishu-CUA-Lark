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


def test_real_ui_guard_requires_im_low_risk_confirmed_chat_and_message_markers() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(
        id="safe_real",
        product="im",
        instruction="send",
        slots={"chat_name": "CUA-Lark-Test", "message": "Hello from CUA-Lark run_001"},
        risk_level="low",
    )

    decision = guard.check_real_ui_run(task, "CUA-Lark-Test", "Hello from CUA-Lark run_001", "run_001")

    assert decision.allowed


def test_real_ui_guard_blocks_non_im_product() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(id="calendar", product="calendar", instruction="create", slots={"title": "CUA-Lark run_001"})

    decision = guard.check_real_ui_run(task, "CUA-Lark-Test", "Hello from CUA-Lark run_001", "run_001")

    assert not decision.allowed
    assert decision.reason.startswith("real_ui_product_not_allowed")


def test_real_ui_guard_blocks_confirm_target_mismatch() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(id="unsafe", product="im", instruction="send", slots={"chat_name": "CUA-Lark-Test"})

    decision = guard.check_real_ui_run(task, "Other", "Hello from CUA-Lark run_001", "run_001")

    assert not decision.allowed
    assert decision.reason.startswith("confirm_target_mismatch")


def test_real_ui_guard_blocks_missing_message_markers() -> None:
    guard = SafetyGuard.from_yaml("configs/safety.yaml")
    task = TaskSpec(id="unsafe", product="im", instruction="send", slots={"chat_name": "CUA-Lark-Test"})

    missing_marker = guard.check_real_ui_run(task, "CUA-Lark-Test", "Hello run_001", "run_001")
    missing_run_id = guard.check_real_ui_run(task, "CUA-Lark-Test", "Hello from CUA-Lark", "run_001")

    assert not missing_marker.allowed
    assert missing_marker.reason == "message_missing_cua_lark_marker"
    assert not missing_run_id.allowed
    assert missing_run_id.reason == "message_missing_run_id"
