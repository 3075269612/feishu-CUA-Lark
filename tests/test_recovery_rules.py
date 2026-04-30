from cua_lark.agent.recovery import RecoveryPolicy
from cua_lark.task.schema import Observation, Verdict


def test_recovery_dismisses_popup_from_ocr() -> None:
    observation = Observation(step_index=1, screen_summary="", ocr_texts=[{"text": "权限 弹窗"}])
    action = RecoveryPolicy().plan(Verdict(status="fail", reason="blocked"), observation)

    assert action is not None
    assert action.type == "press_key"
    assert action.target == "Escape"


def test_recovery_waits_for_loading() -> None:
    observation = Observation(step_index=1, screen_summary="loading")
    action = RecoveryPolicy().plan(Verdict(status="uncertain", reason="loading"), observation)

    assert action is not None
    assert action.type == "wait"
    assert action.metadata["seconds"] == 3


def test_recovery_retry_respects_max_retries() -> None:
    policy = RecoveryPolicy(max_retries=1)
    verdict = Verdict(status="fail", reason="click_failed")
    observation = Observation(step_index=2, screen_summary="ready")

    assert policy.plan(verdict, observation).type == "retry"
    assert policy.plan(verdict, observation) is None
