from __future__ import annotations

from enum import IntEnum
from typing import Any

from cua_lark.task.schema import Action, StepGoal, Verdict


class DocsCreateStage(IntEnum):
    STAGE_CLICK_CLOUD_DOCS = 0
    STAGE_CLICK_NEW = 1
    STAGE_CLICK_DOC_TYPE = 2
    STAGE_CLICK_NEW_BLANK = 3
    STAGE_INPUT_TITLE = 4
    STAGE_DONE = 5

    @property
    def label(self) -> str:
        return {
            DocsCreateStage.STAGE_CLICK_CLOUD_DOCS: "STAGE_CLICK_CLOUD_DOCS",
            DocsCreateStage.STAGE_CLICK_NEW: "STAGE_CLICK_NEW",
            DocsCreateStage.STAGE_CLICK_DOC_TYPE: "STAGE_CLICK_DOC_TYPE",
            DocsCreateStage.STAGE_CLICK_NEW_BLANK: "STAGE_CLICK_NEW_BLANK",
            DocsCreateStage.STAGE_INPUT_TITLE: "STAGE_INPUT_TITLE",
            DocsCreateStage.STAGE_DONE: "STAGE_DONE",
        }.get(self, "UNKNOWN")


# Mapping each stage to the grounding target description for the VLM.
STAGE_TARGET_DESCRIPTIONS: dict[DocsCreateStage, str] = {
    DocsCreateStage.STAGE_CLICK_CLOUD_DOCS: "云文档",
    DocsCreateStage.STAGE_CLICK_NEW: "新建",
    DocsCreateStage.STAGE_CLICK_DOC_TYPE: "文档",
    DocsCreateStage.STAGE_CLICK_NEW_BLANK: "新建空白文档",
    DocsCreateStage.STAGE_INPUT_TITLE: "请输入标题",
}

# Stage 4 (title input) uses a center-click heuristic instead of grounding.
STAGE_INPUT_TITLE_CLICK_RATIO = (0.35, 0.18)


class DocsCreateSkill:
    """State-machine-driven skill for creating a blank Feishu document.

    Click path: 云文档 → 新建 → 文档 → 新建空白文档 → 输入标题.
    """

    def __init__(self, target_doc: str = "") -> None:
        self.target_doc = target_doc
        self.stage = DocsCreateStage.STAGE_CLICK_CLOUD_DOCS

    @property
    def is_done(self) -> bool:
        return self.stage == DocsCreateStage.STAGE_DONE

    @property
    def needs_grounding(self) -> bool:
        """Whether the current stage requires VLM hybrid grounding to locate a UI element."""
        return self.stage in (
            DocsCreateStage.STAGE_CLICK_CLOUD_DOCS,
            DocsCreateStage.STAGE_CLICK_NEW,
            DocsCreateStage.STAGE_CLICK_DOC_TYPE,
            DocsCreateStage.STAGE_CLICK_NEW_BLANK,
        )

    @property
    def grounding_target_description(self) -> str:
        """The natural-language description for the VLM to locate the current target."""
        return STAGE_TARGET_DESCRIPTIONS.get(self.stage, "")

    def guidance_prompt(self) -> str:
        """Generate stage-specific guidance for the VLM/actor."""
        prompts: dict[DocsCreateStage, str] = {
            DocsCreateStage.STAGE_CLICK_CLOUD_DOCS: (
                '当前步骤：点击左侧栏的[云文档]图标进入云文档页面。\n'
                '在左侧导航栏中寻找[云文档]入口（通常在[消息]下方），点击进入。\n'
                '如果当前已在云文档页面则跳过此步骤。'
            ),
            DocsCreateStage.STAGE_CLICK_NEW: (
                '当前步骤：点击页面右上角的[新建]按钮。\n'
                '在云文档页面右侧找到[新建]按钮并点击，点击后会弹出文档类型选择菜单。'
            ),
            DocsCreateStage.STAGE_CLICK_DOC_TYPE: (
                '当前步骤：在弹出的菜单中点击[文档]选项。\n'
                '注意：是点击[文档]，不要误点[电子表格]、[多维表格]或[思维笔记]。'
            ),
            DocsCreateStage.STAGE_CLICK_NEW_BLANK: (
                '当前步骤：在弹窗中点击[新建空白文档]按钮。\n'
                '弹窗中应有[新建空白文档]选项，点击后浏览器会自动打开并跳转到文档编辑页。'
            ),
            DocsCreateStage.STAGE_INPUT_TITLE: (
                '当前步骤：在浏览器文档页面中输入标题。\n'
                '页面左上角应有[请输入标题]的提示文字。点击该输入区域使其获得焦点，'
                f"然后粘贴标题'{self.target_doc}'。"
            ),
            DocsCreateStage.STAGE_DONE: (
                f"创建文档流程完成。文档标题'{self.target_doc}'已输入，文档会自动保存。"
            ),
        }
        return prompts.get(self.stage, '继续执行。')

    def stage_step_goals(self) -> list[StepGoal]:
        """Generate StepGoal list for the current stage."""
        stage = self.stage

        if stage == DocsCreateStage.STAGE_CLICK_CLOUD_DOCS:
            return [
                StepGoal(
                    index=1,
                    description="点击左侧栏云文档入口",
                    target="cloud_docs_entry",
                    expected="进入云文档页面",
                    metadata={"action_hint": "click_grounded", "target_desc": "云文档"},
                )
            ]

        if stage == DocsCreateStage.STAGE_CLICK_NEW:
            return [
                StepGoal(
                    index=2,
                    description="点击新建按钮",
                    target="new_button",
                    expected="弹出文档类型菜单",
                    metadata={"action_hint": "click_grounded", "target_desc": "新建"},
                )
            ]

        if stage == DocsCreateStage.STAGE_CLICK_DOC_TYPE:
            return [
                StepGoal(
                    index=3,
                    description="在弹出菜单中点击文档选项",
                    target="doc_type_option",
                    expected="弹出新建文档弹窗",
                    metadata={"action_hint": "click_grounded", "target_desc": "文档"},
                )
            ]

        if stage == DocsCreateStage.STAGE_CLICK_NEW_BLANK:
            return [
                StepGoal(
                    index=4,
                    description="点击新建空白文档",
                    target="new_blank_doc_button",
                    expected="浏览器打开文档编辑页",
                    metadata={"action_hint": "click_grounded", "target_desc": "新建空白文档"},
                )
            ]

        if stage == DocsCreateStage.STAGE_INPUT_TITLE:
            return [
                StepGoal(
                    index=5,
                    description="点击标题输入区",
                    target="doc_title_input",
                    expected="标题输入区获得焦点",
                    metadata={"action_hint": "click_ratio", "x_ratio": 0.35, "y_ratio": 0.18},
                ),
                StepGoal(
                    index=6,
                    description=f"输入标题'{self.target_doc}'",
                    target=self.target_doc,
                    expected="标题文字已显示",
                    metadata={"action_hint": "paste_text", "text": self.target_doc},
                ),
            ]

        return [
            StepGoal(
                index=99,
                description="创建文档任务完成",
                target="done",
                expected="文档已创建且标题正确",
                metadata={"action_hint": "done"},
            )
        ]

    def advance(self) -> None:
        if self.stage < DocsCreateStage.STAGE_DONE:
            self.stage = DocsCreateStage(self.stage.value + 1)

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
        """Execute the current stage and return (action, verdict)."""
        stage = self.stage

        if stage == DocsCreateStage.STAGE_INPUT_TITLE:
            return self._execute_input_title(backend, dry_run, screen_width, screen_height)

        if stage == DocsCreateStage.STAGE_DONE:
            return (
                Action(type="done", target="docs_create", mock=dry_run, metadata={"stage": stage.label}),
                Verdict(status="pass", reason="docs_create_all_stages_complete", evidence={"stage": stage.label}),
            )

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

        click_result = backend.click(click_x, click_y, "doc_title_input")
        if not click_result.ok:
            return (
                Action(
                    type="click",
                    target="doc_title_input",
                    coordinates=(click_x, click_y),
                    mock=dry_run,
                    metadata={"stage": self.stage.label, "x_ratio": x_ratio, "y_ratio": y_ratio},
                ),
                Verdict(status="blocked", reason=click_result.reason,
                        evidence={"stage": self.stage.label, **(click_result.metadata or {})}),
            )

        paste_result = backend.paste_text(self.target_doc)
        action = Action(
            type="paste_text",
            target="doc_title_input",
            text=self.target_doc,
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
            reason=paste_result.reason if not paste_result.ok else "title_input_complete",
            evidence={"stage": self.stage.label, "target_doc": self.target_doc, **(paste_result.metadata or {})},
        )
        return action, verdict
