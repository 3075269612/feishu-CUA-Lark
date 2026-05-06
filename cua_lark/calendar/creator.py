from __future__ import annotations

from enum import IntEnum
from typing import Any

from cua_lark.task.schema import Action, StepGoal, Verdict


class CalendarCreateStage(IntEnum):
    STAGE_NAVIGATE_TO_CALENDAR = 0
    STAGE_CLICK_CREATE_EVENT = 1
    STAGE_INPUT_TITLE = 2
    STAGE_CLICK_SAVE = 3
    STAGE_VERIFY = 4
    STAGE_DONE = 5

    @property
    def label(self) -> str:
        return {
            CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR: "STAGE_NAVIGATE_TO_CALENDAR",
            CalendarCreateStage.STAGE_CLICK_CREATE_EVENT: "STAGE_CLICK_CREATE_EVENT",
            CalendarCreateStage.STAGE_INPUT_TITLE: "STAGE_INPUT_TITLE",
            CalendarCreateStage.STAGE_CLICK_SAVE: "STAGE_CLICK_SAVE",
            CalendarCreateStage.STAGE_VERIFY: "STAGE_VERIFY",
            CalendarCreateStage.STAGE_DONE: "STAGE_DONE",
        }.get(self, "UNKNOWN")


STAGE_TARGET_DESCRIPTIONS: dict[CalendarCreateStage, str] = {
    CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR: "日历",
    CalendarCreateStage.STAGE_CLICK_CREATE_EVENT: "创建日程",
    CalendarCreateStage.STAGE_INPUT_TITLE: "日程标题输入框",
    CalendarCreateStage.STAGE_CLICK_SAVE: "保存",
}

STAGE_INPUT_TITLE_CLICK_RATIO = (0.35, 0.15)


class CalendarCreateSkill:
    """State-machine-driven skill for creating a Feishu calendar event.

    Flow: navigate to calendar → click create → input title → save → verify.
    """

    def __init__(self, event_title: str = "") -> None:
        self.event_title = event_title
        self.stage = CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR

    @property
    def is_done(self) -> bool:
        return self.stage == CalendarCreateStage.STAGE_DONE

    @property
    def needs_grounding(self) -> bool:
        return self.stage in (
            CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR,
            CalendarCreateStage.STAGE_CLICK_CREATE_EVENT,
            CalendarCreateStage.STAGE_CLICK_SAVE,
        )

    @property
    def grounding_target_description(self) -> str:
        return STAGE_TARGET_DESCRIPTIONS.get(self.stage, "")

    def guidance_prompt(self) -> str:
        prompts: dict[CalendarCreateStage, str] = {
            CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR: (
                '当前步骤：进入日历模块。\n'
                '在左侧导航栏中点击[日历]图标（通常在[消息]下方），或使用Ctrl+3快捷键切换。\n'
                '如果当前已在日历页面则跳过此步骤。'
            ),
            CalendarCreateStage.STAGE_CLICK_CREATE_EVENT: (
                '当前步骤：点击[创建日程]按钮。\n'
                '在日历页面右上角区域找到[创建日程]按钮并点击。\n'
                '点击后会弹出日程编辑弹窗。'
            ),
            CalendarCreateStage.STAGE_INPUT_TITLE: (
                f'当前步骤：输入日程标题。\n'
                '在弹窗顶部的标题输入框中点击，使其获得焦点，'
                f'然后粘贴标题"{self.event_title}"。\n'
                '标题必须包含CUA-Lark关键词。'
            ),
            CalendarCreateStage.STAGE_CLICK_SAVE: (
                '当前步骤：点击弹窗中的[保存]按钮。\n'
                '找到弹窗底部或右上角的[保存]按钮并点击，保存日程。'
            ),
            CalendarCreateStage.STAGE_VERIFY: (
                f'当前步骤：验证日程是否创建成功。\n'
                f'在日历视图中确认"{self.event_title}"出现在对应日期上。'
            ),
            CalendarCreateStage.STAGE_DONE: (
                f'日历日程创建流程完成。日程"{self.event_title}"已保存。'
            ),
        }
        return prompts.get(self.stage, '继续执行。')

    def stage_step_goals(self) -> list[StepGoal]:
        stage = self.stage

        if stage == CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR:
            return [
                StepGoal(
                    index=1,
                    description="进入日历模块",
                    target="calendar_module",
                    expected="日历页面可见",
                    metadata={"action_hint": "click_grounded_or_hotkey", "target_desc": "日历", "hotkey": "ctrl+3"},
                )
            ]

        if stage == CalendarCreateStage.STAGE_CLICK_CREATE_EVENT:
            return [
                StepGoal(
                    index=2,
                    description="点击创建日程按钮",
                    target="create_event_button",
                    expected="弹出日程编辑弹窗",
                    metadata={"action_hint": "click_grounded", "target_desc": "创建日程"},
                )
            ]

        if stage == CalendarCreateStage.STAGE_INPUT_TITLE:
            return [
                StepGoal(
                    index=3,
                    description="点击标题输入区",
                    target="event_title_input",
                    expected="标题输入区获得焦点",
                    metadata={"action_hint": "click_ratio", "x_ratio": STAGE_INPUT_TITLE_CLICK_RATIO[0], "y_ratio": STAGE_INPUT_TITLE_CLICK_RATIO[1]},
                ),
                StepGoal(
                    index=4,
                    description=f"输入日程标题'{self.event_title}'",
                    target=self.event_title,
                    expected="标题文字已填入",
                    metadata={"action_hint": "paste_text", "text": self.event_title},
                ),
            ]

        if stage == CalendarCreateStage.STAGE_CLICK_SAVE:
            return [
                StepGoal(
                    index=5,
                    description="点击保存按钮",
                    target="save_button",
                    expected="日程已保存，弹窗关闭",
                    metadata={"action_hint": "click_grounded", "target_desc": "保存"},
                )
            ]

        if stage == CalendarCreateStage.STAGE_VERIFY:
            return [
                StepGoal(
                    index=6,
                    description=f"验证日程\"{self.event_title}\"出现在日历中",
                    target="calendar_view",
                    expected=f"OCR文本中包含日程标题",
                    metadata={"action_hint": "verify_ocr", "expected_text": self.event_title},
                )
            ]

        return [
            StepGoal(
                index=99,
                description="创建日程任务完成",
                target="done",
                expected="日历日程已创建",
                metadata={"action_hint": "done"},
            )
        ]

    def advance(self) -> None:
        if self.stage < CalendarCreateStage.STAGE_DONE:
            self.stage = CalendarCreateStage(self.stage.value + 1)

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
        stage = self.stage

        if stage == CalendarCreateStage.STAGE_NAVIGATE_TO_CALENDAR:
            return self._execute_navigate(backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run)

        if stage == CalendarCreateStage.STAGE_INPUT_TITLE:
            return self._execute_input_title(backend, dry_run, screen_width, screen_height)

        if stage == CalendarCreateStage.STAGE_VERIFY:
            return self._execute_verify(ocr_texts)

        if stage == CalendarCreateStage.STAGE_DONE:
            return (
                Action(type="done", target="calendar_create", mock=dry_run, metadata={"stage": stage.label}),
                Verdict(status="pass", reason="calendar_create_all_stages_complete", evidence={"stage": stage.label}),
            )

        return self._execute_grounded_click(
            backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run
        )

    def _execute_navigate(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        target_desc = "日历"
        # First try Ctrl+3 hotkey
        hotkey_result = backend.hotkey("ctrl", "3")
        if hotkey_result.ok:
            metadata: dict[str, Any] = {
                "stage": self.stage.label,
                "target_desc": target_desc,
                "method": "hotkey_ctrl_3",
                "grounding": "hybrid",
            }
            return (
                Action(
                    type="hotkey",
                    target=target_desc,
                    mock=dry_run,
                    metadata={**metadata, **(hotkey_result.metadata or {})},
                ),
                Verdict(
                    status="pass",
                    reason="navigated_to_calendar_via_hotkey",
                    evidence=metadata,
                ),
            )

        # Fallback: visual grounding for sidebar icon
        return self._execute_grounded_click(
            backend, grounder, screenshot_path, ocr_texts, accessibility_candidates, dry_run
        )

    def _execute_grounded_click(
        self,
        backend: Any,
        grounder: Any,
        screenshot_path: str | None,
        ocr_texts: list[dict[str, Any]],
        accessibility_candidates: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[Action, Verdict]:
        target_desc = self.grounding_target_description
        point = grounder.locate_target(
            target_desc,
            screenshot_path,
            ocr_texts,
            accessibility_candidates=accessibility_candidates,
        )
        metadata: dict[str, Any] = dict(grounder.last_metadata or {})
        metadata.setdefault("grounding", "hybrid")
        metadata["stage"] = self.stage.label
        metadata["target_desc"] = target_desc

        if point is None:
            return (
                Action(type="click", target=target_desc, mock=dry_run, metadata=metadata),
                Verdict(
                    status="blocked",
                    reason=f"grounding_failed:{target_desc}",
                    evidence={**metadata, "target_desc": target_desc},
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

    def _execute_input_title(
        self,
        backend: Any,
        dry_run: bool,
        screen_width: int,
        screen_height: int,
    ) -> tuple[Action, Verdict]:
        x_ratio, y_ratio = STAGE_INPUT_TITLE_CLICK_RATIO
        click_x = int(screen_width * x_ratio)
        click_y = int(screen_height * y_ratio)

        click_result = backend.click(click_x, click_y, "event_title_input")
        if not click_result.ok:
            return (
                Action(
                    type="click",
                    target="event_title_input",
                    coordinates=(click_x, click_y),
                    mock=dry_run,
                    metadata={"stage": self.stage.label, "x_ratio": x_ratio, "y_ratio": y_ratio},
                ),
                Verdict(status="blocked", reason=click_result.reason,
                        evidence={"stage": self.stage.label, **(click_result.metadata or {})}),
            )

        paste_result = backend.paste_text(self.event_title)
        action = Action(
            type="paste_text",
            target="event_title_input",
            text=self.event_title,
            mock=dry_run,
            metadata={
                "stage": self.stage.label,
                "click_x": click_x,
                "click_y": click_y,
                "x_ratio": x_ratio,
                "y_ratio": y_ratio,
                **(click_result.metadata or {}),
                **(paste_result.metadata or {}),
            },
        )
        verdict = Verdict(
            status="pass" if paste_result.ok else "blocked",
            reason=paste_result.reason if not paste_result.ok else "event_title_input_complete",
            evidence={"stage": self.stage.label, "event_title": self.event_title, **(paste_result.metadata or {})},
        )
        return action, verdict

    def _execute_verify(self, ocr_texts: list[dict[str, Any]]) -> tuple[Action, Verdict]:
        visible_text = " ".join(str(item.get("text", "")) for item in ocr_texts)
        title_found = self.event_title in visible_text
        action = Action(
            type="observe",
            target="calendar_view",
            mock=False,
            metadata={"stage": self.stage.label, "event_title": self.event_title},
        )
        if title_found:
            verdict = Verdict(
                status="pass",
                reason="event_title_found_in_ocr",
                evidence={"stage": self.stage.label, "event_title": self.event_title, "ocr_text_snippet": visible_text[:200]},
            )
        else:
            verdict = Verdict(
                status="uncertain",
                reason="event_title_not_found_in_ocr",
                evidence={"stage": self.stage.label, "event_title": self.event_title, "ocr_text_snippet": visible_text[:200]},
            )
        return action, verdict
