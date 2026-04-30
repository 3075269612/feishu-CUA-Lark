from pathlib import Path

from cua_lark.task.schema import Action, Observation, TaskSpec, Trace, TraceEvent, Verdict
from cua_lark.verifier.im_verifier import ImVerifierChain, VerificationEvidence


def _task() -> TaskSpec:
    return TaskSpec(
        id="im_send_text_001",
        product="im",
        instruction="send",
        slots={"chat_name": "CUA-Lark-Test"},
        success_criteria=[{"type": "visual_text_exists", "text": "Hello from CUA-Lark"}],
    )


def _trace(tmp_path: Path, screenshot: bool = True) -> Trace:
    screenshot_path = tmp_path / "after_final_send.png"
    if screenshot:
        screenshot_path.write_text("fake", encoding="utf-8")
    trace = Trace(task_id="im_send_text_001", run_id="run_001", trace_dir=str(tmp_path))
    trace.events.append(
        TraceEvent(
            timestamp="2026-04-26T00:00:00",
            event_type="step",
            step_index=10,
            observation=Observation(step_index=10, screen_summary="final send"),
            action=Action(type="send_final", target="Enter"),
            verdict=Verdict(
                status="sent_with_screenshot_evidence",
                reason="key_pressed",
                evidence={"after_screenshot": str(screenshot_path)},
            ),
        )
    )
    return trace


def test_im_verifier_needs_manual_when_only_screenshot_passes(tmp_path: Path) -> None:
    config = {"api_oracle_enabled": False, "ocr_enabled": False, "vlm_enabled": False}
    verdict = ImVerifierChain(config=config).verify(_task(), _trace(tmp_path), "Hello from CUA-Lark run_001", "run_001")

    assert verdict.status == "needs_manual_verification"
    assert verdict.evidence["evidence_schema_version"] == "im_verification.v2"
    assert verdict.evidence["evidences"][0]["reason"] == "verify_screenshot_pass"
    assert any("确认群名" in item for item in verdict.evidence["manual_checklist"])


def test_im_verifier_fails_when_screenshot_missing(tmp_path: Path) -> None:
    config = {"api_oracle_enabled": False, "ocr_enabled": False, "vlm_enabled": False}
    verdict = ImVerifierChain(config=config).verify(_task(), _trace(tmp_path, screenshot=False), "Hello from CUA-Lark run_001", "run_001")

    assert verdict.status == "fail"
    assert verdict.evidence["evidences"][0]["reason"] == "verify_screenshot_missing"


def test_im_verifier_api_ocr_vlm_skip_when_disabled(tmp_path: Path) -> None:
    config = {"api_oracle_enabled": False, "ocr_enabled": False, "vlm_enabled": False}
    verdict = ImVerifierChain(config=config).verify(_task(), _trace(tmp_path), "Hello from CUA-Lark run_001", "run_001")
    reasons = {evidence["reason"] for evidence in verdict.evidence["evidences"]}

    assert "verify_api_skipped_disabled" in reasons
    assert "verify_ocr_skipped_disabled" in reasons
    assert "verify_vlm_skipped_disabled" in reasons


def test_im_verifier_auto_pass_when_api_oracle_passes(tmp_path: Path) -> None:
    def api_oracle(task: TaskSpec, message: str, run_id: str) -> VerificationEvidence:
        return VerificationEvidence(
            source="api_oracle",
            status="pass",
            reason="verify_api_pass",
            confidence=0.95,
            details={"run_id": run_id, "message": message},
        )

    verdict = ImVerifierChain(api_oracle=api_oracle).verify(_task(), _trace(tmp_path), "Hello from CUA-Lark run_001", "run_001")

    assert verdict.status == "pass"
    assert verdict.reason == "verify_auto_pass"


def test_im_verifier_fail_wins_over_auto_pass(tmp_path: Path) -> None:
    def api_oracle(task: TaskSpec, message: str, run_id: str) -> VerificationEvidence:
        return VerificationEvidence(
            source="api_oracle",
            status="fail",
            reason="verify_api_message_not_found",
            confidence=0.9,
            details={},
        )

    verdict = ImVerifierChain(api_oracle=api_oracle).verify(_task(), _trace(tmp_path), "Hello from CUA-Lark run_001", "run_001")

    assert verdict.status == "fail"


def test_im_verifier_dry_run_stays_uncertain(tmp_path: Path) -> None:
    verdict = ImVerifierChain().verify(_task(), _trace(tmp_path), "Hello from CUA-Lark run_001", "run_001", dry_run=True)

    assert verdict.status == "uncertain"
    assert verdict.reason == "verify_dry_run_not_upgraded"


def test_im_verifier_uses_im_api_for_api_oracle(tmp_path: Path, monkeypatch) -> None:
    class FakeImApi:
        def latest_message_contains(self, chat_name: str, text: str) -> dict:
            return {
                "status": "pass",
                "reason": "latest_message_contains_text",
                "chat_name": chat_name,
                "matched_count": 1,
                "recent_texts": [text],
            }

    import cua_lark.feishu.im_api as im_api_module

    monkeypatch.setattr(im_api_module, "ImApi", lambda: FakeImApi())

    verdict = ImVerifierChain(config={"api_oracle_enabled": True}).verify(
        _task(),
        _trace(tmp_path),
        "Hello from CUA-Lark run_001",
        "run_001",
    )

    assert verdict.status == "pass"
    api_evidence = next(evidence for evidence in verdict.evidence["evidences"] if evidence["source"] == "api_oracle")
    assert api_evidence["status"] == "pass"
    assert api_evidence["reason"] == "verify_api_latest_message_contains_text"


def test_im_verifier_maps_missing_api_credentials_to_skip(tmp_path: Path, monkeypatch) -> None:
    class FakeImApi:
        def latest_message_contains(self, chat_name: str, text: str) -> dict:
            return {"status": "disabled", "reason": "missing_tenant_access_token", "chat_name": chat_name}

    import cua_lark.feishu.im_api as im_api_module

    monkeypatch.setattr(im_api_module, "ImApi", lambda: FakeImApi())

    verdict = ImVerifierChain(config={"api_oracle_enabled": True}).verify(
        _task(),
        _trace(tmp_path),
        "Hello from CUA-Lark run_001",
        "run_001",
    )

    api_evidence = next(evidence for evidence in verdict.evidence["evidences"] if evidence["source"] == "api_oracle")
    assert api_evidence["status"] == "skipped"
    assert api_evidence["reason"] == "verify_api_skipped_missing_tenant_access_token"
