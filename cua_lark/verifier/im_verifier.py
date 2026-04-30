from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from cua_lark.config import ModelConfig
from cua_lark.task.schema import TaskSpec, Trace, Verdict

VerifierSubStatus = Literal["pass", "fail", "skipped", "error"]

EVIDENCE_SCHEMA_VERSION = "im_verification.v2"
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
            self._verify_ocr_placeholder(message, trace),
            self._verify_vlm_placeholder(message, trace),
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

        enabled = bool(self.config.get("api_oracle_enabled", True))
        if not enabled:
            return VerificationEvidence(
                source="api_oracle",
                status="skipped",
                reason="verify_api_skipped_disabled",
                confidence=0.0,
                details={},
            )

        try:
            from cua_lark.feishu.im_api import ImApi

            chat_name = str(task.slots.get("chat_name", ""))
            result = ImApi().latest_message_contains(chat_name, message)
        except Exception as exc:
            return VerificationEvidence(
                source="api_oracle",
                status="error",
                reason="verify_api_error",
                confidence=0.0,
                details={"error": str(exc), "chat_name": task.slots.get("chat_name")},
            )

        status = result.get("status")
        if status == "pass":
            return VerificationEvidence(
                source="api_oracle",
                status="pass",
                reason=_api_reason(result, fallback="verify_api_message_found"),
                confidence=0.9,
                details=result,
            )
        if status == "fail":
            return VerificationEvidence(
                source="api_oracle",
                status="fail",
                reason=_api_reason(result, fallback="verify_api_failed"),
                confidence=0.9,
                details=result,
            )
        if status == "disabled":
            return VerificationEvidence(
                source="api_oracle",
                status="skipped",
                reason=_api_reason(result, fallback="verify_api_skipped_disabled"),
                confidence=0.0,
                details=result,
            )
        return VerificationEvidence(
            source="api_oracle",
            status="error",
            reason="verify_api_unexpected_result",
            confidence=0.0,
            details=result,
        )

    def _verify_ocr_placeholder(self, message: str, trace: Trace | None = None) -> VerificationEvidence:
        if not self.config.get("ocr_enabled", False):
            return VerificationEvidence(
                source="ocr",
                status="skipped",
                reason="verify_ocr_skipped_disabled",
                confidence=0.0,
                details={},
            )

        if trace is None:
            return VerificationEvidence(
                source="ocr",
                status="error",
                reason="verify_ocr_no_trace",
                confidence=0.0,
                details={"expected_text": message},
            )

        # Find the after_final_send screenshot
        final_send_events = [
            event
            for event in trace.events
            if event.event_type == "step"
            and event.action is not None
            and event.action.type == "send_final"
            and event.verdict is not None
        ]

        if not final_send_events:
            return VerificationEvidence(
                source="ocr",
                status="error",
                reason="verify_ocr_no_final_send",
                confidence=0.0,
                details={"expected_text": message},
            )

        event = final_send_events[-1]
        screenshot_path = None
        if event.verdict:
            screenshot_path = event.verdict.evidence.get("after_screenshot")

        if not screenshot_path or not Path(str(screenshot_path)).exists():
            return VerificationEvidence(
                source="ocr",
                status="error",
                reason="verify_ocr_no_screenshot",
                confidence=0.0,
                details={"expected_text": message, "after_screenshot": screenshot_path},
            )

        try:
            from cua_lark.perception.ocr import OcrClient
            ocr = OcrClient()
            ocr_results = ocr.extract(str(screenshot_path))
            ocr_texts = [item.get("text", "") for item in ocr_results]

            # Check if message text appears in OCR results
            found = any(message in text for text in ocr_texts)

            if found:
                return VerificationEvidence(
                    source="ocr",
                    status="pass",
                    reason="verify_ocr_text_found",
                    confidence=0.65,
                    details={
                        "expected_text": message,
                        "after_screenshot": screenshot_path,
                        "ocr_texts": ocr_texts[:20],  # Limit to first 20 for brevity
                    },
                )
            else:
                return VerificationEvidence(
                    source="ocr",
                    status="fail",
                    reason="verify_ocr_text_not_found",
                    confidence=0.65,
                    details={
                        "expected_text": message,
                        "after_screenshot": screenshot_path,
                        "ocr_texts": ocr_texts[:20],
                    },
                )
        except Exception as exc:
            return VerificationEvidence(
                source="ocr",
                status="error",
                reason="verify_ocr_error",
                confidence=0.0,
                details={"expected_text": message, "error": str(exc)},
            )

    def _verify_vlm_placeholder(self, message: str, trace: Trace | None = None) -> VerificationEvidence:
        if not self.config.get("vlm_enabled", False):
            return VerificationEvidence(
                source="vlm",
                status="skipped",
                reason="verify_vlm_skipped_disabled",
                confidence=0.0,
                details={},
            )

        if trace is None:
            return VerificationEvidence(
                source="vlm",
                status="error",
                reason="verify_vlm_no_trace",
                confidence=0.0,
                details={"expected_text": message},
            )

        # Find the after_final_send screenshot
        final_send_events = [
            event
            for event in trace.events
            if event.event_type == "step"
            and event.action is not None
            and event.action.type == "send_final"
            and event.verdict is not None
        ]

        if not final_send_events:
            return VerificationEvidence(
                source="vlm",
                status="error",
                reason="verify_vlm_no_final_send",
                confidence=0.0,
                details={"expected_text": message},
            )

        event = final_send_events[-1]
        screenshot_path = None
        if event.verdict:
            screenshot_path = event.verdict.evidence.get("after_screenshot")

        if not screenshot_path or not Path(str(screenshot_path)).exists():
            return VerificationEvidence(
                source="vlm",
                status="error",
                reason="verify_vlm_no_screenshot",
                confidence=0.0,
                details={"expected_text": message, "after_screenshot": screenshot_path},
            )

        try:
            from cua_lark.perception.vlm import VlmClient

            model_config = _load_model_config()
            vlm = VlmClient(
                model=self.config.get("vlm_model") or (model_config.vlm_model if model_config else None),
                api_key=model_config.dashscope_api_key() if model_config else None,
                timeout=int(self.config.get("timeout_sec") or (model_config.timeout_sec if model_config else 30)),
            )

            prompt = f"""Look at this screenshot of a chat application.
Does the latest visible message in the chat contain the text: "{message}"?
Answer with Yes or No, followed by a brief explanation."""

            response = vlm.summarize(str(screenshot_path), prompt)

            # Check if VLM is disabled (API key not set)
            if "VLM disabled" in response or "API_KEY not set" in response:
                return VerificationEvidence(
                    source="vlm",
                    status="skipped",
                    reason="verify_vlm_skipped_no_api_key",
                    confidence=0.0,
                    details={"expected_text": message, "response": response},
                )

            # Simple heuristic: if response starts with "Yes" or contains affirmative language
            response_lower = response.lower()
            found = response_lower.startswith("yes") or "yes," in response_lower or "yes." in response_lower

            if found:
                return VerificationEvidence(
                    source="vlm",
                    status="pass",
                    reason="verify_vlm_text_found",
                    confidence=0.6,
                    details={
                        "expected_text": message,
                        "after_screenshot": screenshot_path,
                        "response": response,
                    },
                )
            else:
                return VerificationEvidence(
                    source="vlm",
                    status="fail",
                    reason="verify_vlm_text_not_found",
                    confidence=0.6,
                    details={
                        "expected_text": message,
                        "after_screenshot": screenshot_path,
                        "response": response,
                    },
                )
        except Exception as exc:
            return VerificationEvidence(
                source="vlm",
                status="error",
                reason="verify_vlm_error",
                confidence=0.0,
                details={"expected_text": message, "error": str(exc)},
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


def _api_reason(result: dict[str, Any], fallback: str) -> str:
    reason = str(result.get("reason") or "")
    if not reason:
        return fallback
    if reason.startswith("verify_api_"):
        return reason
    if result.get("status") == "disabled":
        return f"verify_api_skipped_{reason}"
    return f"verify_api_{reason}"


def _load_model_config() -> ModelConfig | None:
    try:
        return ModelConfig.from_yaml()
    except Exception:
        return None
