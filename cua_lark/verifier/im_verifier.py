from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from cua_lark.task.schema import TaskSpec, Trace, Verdict

VerifierSubStatus = Literal["pass", "fail", "skipped", "error"]

EVIDENCE_SCHEMA_VERSION = "im_verification.v1"
AUTO_PASS_SOURCES = {"api_oracle", "ocr", "vlm"}


class VerificationEvidence(BaseModel):
    source: str
    status: VerifierSubStatus
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)


class ImVerificationSummary(BaseModel):
    evidence_schema_version: str = EVIDENCE_SCHEMA_VERSION
    evidences: list[VerificationEvidence]
    final_status: Literal["pass", "fail", "needs_manual_verification", "uncertain"]
    reason: str
    manual_checklist: list[str] = Field(default_factory=list)

    def as_verdict(self) -> Verdict:
        return Verdict(
            status=self.final_status,
            reason=self.reason,
            evidence=self.model_dump(mode="json"),
            extracted_state={"verification_final_status": self.final_status},
        )


ApiOracle = Callable[[TaskSpec, str, str], VerificationEvidence]


class ImVerifierChain:
    def __init__(self, config: dict[str, Any] | None = None, api_oracle: ApiOracle | None = None) -> None:
        self.config = config or {}
        self.api_oracle = api_oracle

    def verify(self, task: TaskSpec, trace: Trace, message: str, run_id: str, dry_run: bool = False) -> Verdict:
        if dry_run:
            summary = ImVerificationSummary(
                evidences=[
                    VerificationEvidence(
                        source="verification_chain",
                        status="skipped",
                        reason="verify_dry_run_skipped",
                        confidence=0.0,
                        details={"dry_run": True},
                    )
                ],
                final_status="uncertain",
                reason="verify_dry_run_not_upgraded",
                manual_checklist=self._manual_checklist(task, message, run_id),
            )
            return summary.as_verdict()

        evidences = [
            self._verify_screenshot_evidence(trace),
            self._verify_task_criteria(task),
            self._verify_api_oracle(task, message, run_id),
            self._verify_ocr_placeholder(message),
            self._verify_vlm_placeholder(message),
        ]
        summary = self._aggregate(task, message, run_id, evidences)
        return summary.as_verdict()

    def _verify_screenshot_evidence(self, trace: Trace) -> VerificationEvidence:
        final_send_events = [
            event
            for event in trace.events
            if event.event_type == "step"
            and event.action is not None
            and event.action.type == "send_final"
            and event.verdict is not None
            and event.verdict.status == "sent_with_screenshot_evidence"
        ]
        if not final_send_events:
            return VerificationEvidence(
                source="screenshot",
                status="fail",
                reason="verify_screenshot_missing_final_send",
                confidence=0.0,
                details={},
            )

        event = final_send_events[-1]
        screenshot_path = None
        if event.verdict:
            screenshot_path = event.verdict.evidence.get("after_screenshot")
        path_ok = bool(screenshot_path and Path(str(screenshot_path)).exists())
        if not path_ok:
            return VerificationEvidence(
                source="screenshot",
                status="fail",
                reason="verify_screenshot_missing",
                confidence=0.0,
                details={"after_screenshot": screenshot_path},
            )
        return VerificationEvidence(
            source="screenshot",
            status="pass",
            reason="verify_screenshot_pass",
            confidence=0.45,
            details={"after_screenshot": screenshot_path, "step_index": event.step_index},
        )

    def _verify_task_criteria(self, task: TaskSpec) -> VerificationEvidence:
        return VerificationEvidence(
            source="task_criteria",
            status="skipped",
            reason="verify_task_criteria_registered",
            confidence=0.0,
            details={"criteria": [criterion.model_dump(mode="json") for criterion in task.success_criteria]},
        )

    def _verify_api_oracle(self, task: TaskSpec, message: str, run_id: str) -> VerificationEvidence:
        if self.api_oracle is not None:
            try:
                return self.api_oracle(task, message, run_id)
            except Exception as exc:
                return VerificationEvidence(
                    source="api_oracle",
                    status="error",
                    reason="verify_api_error",
                    confidence=0.0,
                    details={"error": str(exc)},
                )

        token = os.environ.get("FEISHU_TENANT_ACCESS_TOKEN")
        enabled = bool(self.config.get("api_oracle_enabled", True))
        if not enabled:
            return VerificationEvidence(
                source="api_oracle",
                status="skipped",
                reason="verify_api_skipped_disabled",
                confidence=0.0,
                details={},
            )
        if not token:
            return VerificationEvidence(
                source="api_oracle",
                status="skipped",
                reason="verify_api_skipped_no_token",
                confidence=0.0,
                details={"chat_name": task.slots.get("chat_name")},
            )
        return VerificationEvidence(
            source="api_oracle",
            status="skipped",
            reason="verify_api_skipped_not_implemented",
            confidence=0.0,
            details={"chat_name": task.slots.get("chat_name"), "message_contains_run_id": run_id in message},
        )

    def _verify_ocr_placeholder(self, message: str) -> VerificationEvidence:
        if self.config.get("ocr_enabled", False):
            return VerificationEvidence(
                source="ocr",
                status="skipped",
                reason="verify_ocr_skipped_not_implemented",
                confidence=0.0,
                details={"expected_text": message},
            )
        return VerificationEvidence(
            source="ocr",
            status="skipped",
            reason="verify_ocr_skipped_disabled",
            confidence=0.0,
            details={},
        )

    def _verify_vlm_placeholder(self, message: str) -> VerificationEvidence:
        if self.config.get("vlm_enabled", False):
            return VerificationEvidence(
                source="vlm",
                status="skipped",
                reason="verify_vlm_skipped_not_implemented",
                confidence=0.0,
                details={"expected_text": message},
            )
        return VerificationEvidence(
            source="vlm",
            status="skipped",
            reason="verify_vlm_skipped_disabled",
            confidence=0.0,
            details={},
        )

    def _aggregate(
        self,
        task: TaskSpec,
        message: str,
        run_id: str,
        evidences: list[VerificationEvidence],
    ) -> ImVerificationSummary:
        if any(evidence.status == "fail" for evidence in evidences):
            return ImVerificationSummary(
                evidences=evidences,
                final_status="fail",
                reason="verify_failed",
                manual_checklist=self._manual_checklist(task, message, run_id),
            )

        has_auto_pass = any(
            evidence.source in AUTO_PASS_SOURCES and evidence.status == "pass"
            for evidence in evidences
        )
        if has_auto_pass:
            return ImVerificationSummary(
                evidences=evidences,
                final_status="pass",
                reason="verify_auto_pass",
                manual_checklist=[],
            )

        screenshot_pass = any(evidence.source == "screenshot" and evidence.status == "pass" for evidence in evidences)
        non_screenshot = [evidence for evidence in evidences if evidence.source != "screenshot"]
        if screenshot_pass and all(evidence.status in {"skipped", "error"} for evidence in non_screenshot):
            return ImVerificationSummary(
                evidences=evidences,
                final_status="needs_manual_verification",
                reason="verify_needs_manual_verification",
                manual_checklist=self._manual_checklist(task, message, run_id),
            )

        return ImVerificationSummary(
            evidences=evidences,
            final_status="uncertain",
            reason="verify_uncertain",
            manual_checklist=self._manual_checklist(task, message, run_id),
        )

    @staticmethod
    def _manual_checklist(task: TaskSpec, message: str, run_id: str) -> list[str]:
        return [
            f"确认群名为：{task.slots.get('chat_name')}",
            f"确认最新消息文本包含：{message}",
            f"确认发送时间对应 run_id：{run_id}",
            "确认最新消息位于聊天窗口底部且无发送失败标记",
        ]
