from __future__ import annotations

from enum import IntEnum
from typing import Any

from cua_lark.calendar.creator import CalendarCreateSkill, CalendarCreateStage
from cua_lark.docs.creator import DocsCreateSkill, DocsCreateStage
from cua_lark.task.schema import Action, StepGoal, Verdict


class CrossProductStage(IntEnum):
    STAGE_CALENDAR = 0
    STAGE_DOCS = 1
    STAGE_IM = 2
    STAGE_DONE = 3

    @property
    def label(self) -> str:
        return {
            CrossProductStage.STAGE_CALENDAR: "STAGE_CALENDAR",
            CrossProductStage.STAGE_DOCS: "STAGE_DOCS",
            CrossProductStage.STAGE_IM: "STAGE_IM",
            CrossProductStage.STAGE_DONE: "STAGE_DONE",
        }.get(self, "UNKNOWN")


class ImSendSubStage(IntEnum):
    IM_NAVIGATE_TO_MESSAGE = 0
    IM_OPEN_CHAT = 1
    IM_PASTE_MESSAGE = 2
    IM_SEND = 3
    IM_DONE = 4

    @property
    def label(self) -> str:
        return {
            ImSendSubStage.IM_NAVIGATE_TO_MESSAGE: "IM_NAVIGATE_TO_MESSAGE",
            ImSendSubStage.IM_OPEN_CHAT: "IM_OPEN_CHAT",
            ImSendSubStage.IM_PASTE_MESSAGE: "IM_PASTE_MESSAGE",
            ImSendSubStage.IM_SEND: "IM_SEND",
            ImSendSubStage.IM_DONE: "IM_DONE",
        }.get(self, "UNKNOWN")


IM_TARGET_DESCRIPTIONS: dict[ImSendSubStage, str] = {
    ImSendSubStage.IM_NAVIGATE_TO_MESSAGE: "左侧消息按钮",
    ImSendSubStage.IM_OPEN_CHAT: "",  # filled dynamically with chat_name
    ImSendSubStage.IM_PASTE_MESSAGE: "消息输入框",
}


class CrossProductSkill:
    """Meta state machine orchestrating Calendar → Docs → IM cross-product flow.

    Each meta-stage delegates to a sub-skill state machine:
    - STAGE_CALENDAR → CalendarCreateSkill
    - STAGE_DOCS    → DocsCreateSkill
    - STAGE_IM      → inline ImSendSubStage

    The model never controls the long chain — all transitions are deterministic.
    """

    def __init__(
        self,
        event_title: str = "",
        folder_name: str = "",
        chat_name: str = "",
        run_id: str = "",
    ) -> None:
        self.stage = CrossProductStage.STAGE_CALENDAR
        self._calendar = CalendarCreateSkill(event_title=event_title)
        self._docs = DocsCreateSkill(target_doc=f"CUA-Lark Kickoff {run_id}")
        self._im_sub_stage = ImSendSubStage.IM_NAVIGATE_TO_MESSAGE
        self._chat_name = chat_name
        self._run_id = run_id
        self._event_title = event_title
        self._folder_name = folder_name

    @property
    def is_done(self) -> bool:
        return self.stage == CrossProductStage.STAGE_DONE

    @property
    def current_sub_task(self) -> str:
        if self.stage == CrossProductStage.STAGE_CALENDAR:
            return "calendar"
        if self.stage == CrossProductStage.STAGE_DOCS:
            return "docs"
        if self.stage == CrossProductStage.STAGE_IM:
            return "im"
        return "done"

    def guidance_prompt(self) -> str:
        if self.stage == CrossProductStage.STAGE_CALENDAR:
            return self._calendar.guidance_prompt()
        if self.stage == CrossProductStage.STAGE_DOCS:
            return self._docs.guidance_prompt()
        if self.stage == CrossProductStage.STAGE_IM:
            return self._im_guidance()
        return "跨产品链路全部完成。"

    def stage_step_goals(self) -> list[StepGoal]:
        if self.stage == CrossProductStage.STAGE_CALENDAR:
            return self._calendar.stage_step_goals()
        if self.stage == CrossProductStage.STAGE_DOCS:
            return self._docs.stage_step_goals()
        if self.stage == CrossProductStage.STAGE_IM:
            return self._im_step_goals()
        return [
            StepGoal(
                index=99,
                description="跨产品链路全部完成",
                target="done",
                expected="所有子任务已执行",
                metadata={"action_hint": "done"},
            )
        ]

    def execute_stage(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
        screen_width: int = 1440,
        screen_height: int = 900,
    ) -> tuple[Action, Verdict]:
        if self.stage == CrossProductStage.STAGE_CALENDAR:
            return self._calendar.execute_stage(
                backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run, screen_width, screen_height
            )
        if self.stage == CrossProductStage.STAGE_DOCS:
            return self._docs.execute_stage(
                backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run, screen_width, screen_height
            )
        if self.stage == CrossProductStage.STAGE_IM:
            return self._execute_im_stage(backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run)
        return (
            Action(type="done", target="cross_product", mock=dry_run, metadata={}),
            Verdict(status="pass", reason="cross_product_all_stages_complete", evidence={}),
        )

    def advance(self) -> None:
        if self.stage == CrossProductStage.STAGE_CALENDAR:
            self._calendar.advance()
            if self._calendar.is_done:
                self.stage = CrossProductStage.STAGE_DOCS
            return

        if self.stage == CrossProductStage.STAGE_DOCS:
            self._docs.advance()
            if self._docs.is_done:
                self.stage = CrossProductStage.STAGE_IM
            return

        if self.stage == CrossProductStage.STAGE_IM:
            self._im_sub_stage = ImSendSubStage(self._im_sub_stage.value + 1)
            if self._im_sub_stage == ImSendSubStage.IM_DONE:
                self.stage = CrossProductStage.STAGE_DONE
            return

    def _build_summary_message(self) -> str:
        return (
            f"CUA-Lark Kickoff {self._run_id} 完成:\n"
            f"- 日历日程: {self._event_title}\n"
            f"- 文档已创建: {self._folder_name}"
        )

    def _im_guidance(self) -> str:
        prompts: dict[ImSendSubStage, str] = {
            ImSendSubStage.IM_NAVIGATE_TO_MESSAGE: (
                '当前步骤：进入消息模块。\n'
                '在左侧导航栏中点击[消息]按钮，进入消息页面。\n'
                '如果当前已在消息页面（左侧会话列表可见），跳过此步骤。'
            ),
            ImSendSubStage.IM_OPEN_CHAT: (
                f'当前步骤：打开群聊"{self._chat_name}"。\n'
                f'在左侧会话列表中找到"{self._chat_name}"并点击打开。'
            ),
            ImSendSubStage.IM_PASTE_MESSAGE: (
                '当前步骤：粘贴跨产品链路汇总消息。\n'
                '点击底部消息输入框使其获得焦点，然后粘贴汇总消息。'
            ),
            ImSendSubStage.IM_SEND: (
                '当前步骤：按Enter发送汇总消息。\n'
                f'将向"{self._chat_name}"发送跨产品链路完成的汇总消息。'
            ),
            ImSendSubStage.IM_DONE: 'IM汇总消息已发送。',
        }
        return prompts.get(self._im_sub_stage, '继续执行。')

    def _im_step_goals(self) -> list[StepGoal]:
        sub_stage = self._im_sub_stage

        if sub_stage == ImSendSubStage.IM_NAVIGATE_TO_MESSAGE:
            return [
                StepGoal(
                    index=1,
                    description="进入消息模块",
                    target="message_module",
                    expected="消息页面可见",
                    metadata={"action_hint": "click_grounded_or_skip", "target_desc": "消息"},
                )
            ]
        if sub_stage == ImSendSubStage.IM_OPEN_CHAT:
            return [
                StepGoal(
                    index=2,
                    description=f"打开群聊{self._chat_name}",
                    target=self._chat_name,
                    expected="群聊已打开",
                    metadata={"action_hint": "click_grounded", "target_desc": self._chat_name},
                )
            ]
        if sub_stage == ImSendSubStage.IM_PASTE_MESSAGE:
            summary = self._build_summary_message()
            return [
                StepGoal(
                    index=3,
                    description="点击消息输入框并粘贴汇总消息",
                    target="message_input",
                    expected="汇总消息已粘贴",
                    metadata={"action_hint": "click_and_paste", "target_desc": "消息输入框", "text": summary},
                )
            ]
        if sub_stage == ImSendSubStage.IM_SEND:
            return [
                StepGoal(
                    index=4,
                    description="发送汇总消息",
                    target="send_button_or_enter",
                    expected="消息已发送",
                    metadata={"action_hint": "press_enter"},
                )
            ]
        return [
            StepGoal(
                index=5,
                description="IM汇总完成",
                target="done",
                expected="汇总消息已发送",
                metadata={"action_hint": "done"},
            )
        ]

    def _execute_im_stage(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        sub_stage = self._im_sub_stage

        if sub_stage == ImSendSubStage.IM_NAVIGATE_TO_MESSAGE:
            return self._execute_im_navigate(backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run)
        if sub_stage == ImSendSubStage.IM_OPEN_CHAT:
            return self._execute_im_open_chat(backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run)
        if sub_stage == ImSendSubStage.IM_PASTE_MESSAGE:
            return self._execute_im_paste(backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run)
        if sub_stage == ImSendSubStage.IM_SEND:
            return self._execute_im_send(backend, dry_run)
        return (
            Action(type="done", target="im_summary", mock=dry_run, metadata={"sub_stage": sub_stage.label}),
            Verdict(status="pass", reason="im_summary_complete", evidence={"sub_stage": sub_stage.label}),
        )

    def _execute_im_navigate(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        if _looks_like_message_page(ocr_texts):
            action = Action(
                type="observe",
                target="message_module",
                mock=dry_run,
                metadata={"skip_click": True, "grounding": "hybrid"},
            )
            verdict = Verdict(status="pass", reason="already_on_message_page", evidence={"skip_click": True})
            return action, verdict

        return self._grounded_click(grounder, "消息", backend, screenshot_path, ocr_texts, accessibility_candidates, dry_run)

    def _execute_im_open_chat(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        return self._grounded_click(grounder, self._chat_name, backend, screenshot_path, ocr_texts, accessibility_candidates, dry_run)

    def _execute_im_paste(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        target_desc = "消息输入框"
        point = grounder.locate_target(
            target_desc,
            screenshot_path,
            ocr_texts,
            accessibility_candidates=accessibility_candidates,
        )
        metadata: dict[str, Any] = dict(grounder.last_metadata or {})
        metadata.setdefault("grounding", "hybrid")
        metadata["im_sub_stage"] = self._im_sub_stage.label
        metadata["target_desc"] = target_desc

        if point is None:
            return (
                Action(type="paste_text", target="message_input", mock=dry_run, metadata=metadata),
                Verdict(status="blocked", reason="message_input_not_found", evidence={**metadata, "no_fallback": True}),
            )

        click_result = backend.click(point[0], point[1], "message_input")
        if not click_result.ok:
            return (
                Action(type="paste_text", target="message_input", coordinates=point, mock=dry_run, metadata=metadata),
                Verdict(status="blocked", reason=click_result.reason, evidence={**metadata, **(click_result.metadata or {})}),
            )

        summary = self._build_summary_message()
        paste_result = backend.paste_text(summary)
        action = Action(
            type="paste_text",
            target="message_input",
            text=summary,
            coordinates=point,
            mock=dry_run,
            metadata={**metadata, **(click_result.metadata or {}), **(paste_result.metadata or {})},
        )
        verdict = Verdict(
            status="pass" if paste_result.ok else "blocked",
            reason=paste_result.reason if not paste_result.ok else "summary_message_pasted",
            evidence={**metadata, "message_preview": summary[:80], **(paste_result.metadata or {})},
        )
        return action, verdict

    def _execute_im_send(self, backend: Any, dry_run: bool) -> tuple[Action, Verdict]:
        result = backend.press("enter")
        action = Action(
            type="send_final",
            target="Enter",
            mock=dry_run,
            metadata={"im_sub_stage": self._im_sub_stage.label, "summary_sent": True, **(result.metadata or {})},
        )
        verdict = Verdict(
            status="pass" if result.ok else "blocked",
            reason=result.reason if not result.ok else "im_summary_sent",
            evidence={"im_sub_stage": self._im_sub_stage.label, **(result.metadata or {})},
        )
        return action, verdict

    def _grounded_click(
        self,
        grounder: Any,
        target_desc: str,
        backend: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        point = grounder.locate_target(
            target_desc,
            screenshot_path,
            ocr_texts,
            accessibility_candidates=accessibility_candidates,
        )
        metadata: dict[str, Any] = dict(grounder.last_metadata or {})
        metadata.setdefault("grounding", "hybrid")
        metadata["im_sub_stage"] = self._im_sub_stage.label
        metadata["target_desc"] = target_desc

        if point is None:
            return (
                Action(type="click", target=target_desc, mock=dry_run, metadata=metadata),
                Verdict(
                    status="blocked",
                    reason=f"grounding_failed:{target_desc}",
                    evidence={**metadata, "no_fallback": True},
                ),
            )

        result = backend.click(point[0], point[1], target_desc)
        return (
            Action(
                type="click",
                target=target_desc,
                coordinates=point,
                mock=dry_run,
                metadata={**metadata, **(result.metadata or {})},
            ),
            Verdict(
                status="pass" if result.ok else "blocked",
                reason=result.reason,
                evidence={**metadata, **(result.metadata or {})},
            ),
        )


def _looks_like_message_page(ocr_texts: list[dict[str, Any]]) -> bool:
    visible = " ".join(str(item.get("text", "")) for item in ocr_texts)
    return any(marker in visible for marker in ["会话", "CUA-Lark-Test"])
