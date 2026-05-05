"""Unit tests for DocsCreateSkill state machine and execution."""

from cua_lark.docs.creator import DocsCreateSkill, DocsCreateStage


class TestDocsCreateStage:
    def test_stage_order(self) -> None:
        assert DocsCreateStage.STAGE_CLICK_CLOUD_DOCS.value == 0
        assert DocsCreateStage.STAGE_CLICK_NEW.value == 1
        assert DocsCreateStage.STAGE_CLICK_DOC_TYPE.value == 2
        assert DocsCreateStage.STAGE_CLICK_NEW_BLANK.value == 3
        assert DocsCreateStage.STAGE_INPUT_TITLE.value == 4
        assert DocsCreateStage.STAGE_DONE.value == 5

    def test_stage_labels(self) -> None:
        assert DocsCreateStage.STAGE_CLICK_CLOUD_DOCS.label == "STAGE_CLICK_CLOUD_DOCS"
        assert DocsCreateStage.STAGE_DONE.label == "STAGE_DONE"


class TestDocsCreateSkillInit:
    def test_default_values(self) -> None:
        skill = DocsCreateSkill()
        assert skill.target_doc == ""
        assert skill.stage == DocsCreateStage.STAGE_CLICK_CLOUD_DOCS
        assert not skill.is_done

    def test_full_init(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        assert skill.target_doc == "CUA-Dark-Test-Doc"


class TestStageTransitions:
    def test_advance_through_all_stages(self) -> None:
        skill = DocsCreateSkill()
        stages = []
        while not skill.is_done:
            stages.append(skill.stage)
            skill.advance()
        stages.append(skill.stage)
        assert stages == [
            DocsCreateStage.STAGE_CLICK_CLOUD_DOCS,
            DocsCreateStage.STAGE_CLICK_NEW,
            DocsCreateStage.STAGE_CLICK_DOC_TYPE,
            DocsCreateStage.STAGE_CLICK_NEW_BLANK,
            DocsCreateStage.STAGE_INPUT_TITLE,
            DocsCreateStage.STAGE_DONE,
        ]

    def test_advance_past_done_stays_done(self) -> None:
        skill = DocsCreateSkill()
        for _ in range(10):
            skill.advance()
        assert skill.stage == DocsCreateStage.STAGE_DONE


class TestNeedsGrounding:
    def test_click_stages_need_grounding(self) -> None:
        skill = DocsCreateSkill()
        assert skill.needs_grounding  # Stage 0
        skill.advance()
        assert skill.needs_grounding  # Stage 1
        skill.advance()
        assert skill.needs_grounding  # Stage 2
        skill.advance()
        assert skill.needs_grounding  # Stage 3

    def test_input_title_does_not_need_grounding(self) -> None:
        skill = DocsCreateSkill()
        for _ in range(4):
            skill.advance()
        assert skill.stage == DocsCreateStage.STAGE_INPUT_TITLE
        assert not skill.needs_grounding

    def test_done_does_not_need_grounding(self) -> None:
        skill = DocsCreateSkill()
        for _ in range(5):
            skill.advance()
        assert not skill.needs_grounding


class TestGuidancePrompts:
    def test_all_stages_produce_prompts(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        while not skill.is_done:
            prompt = skill.guidance_prompt()
            assert len(prompt) > 20, f"Stage {skill.stage.label} prompt too short: {prompt}"
            skill.advance()

    def test_stage_0_prompt_mentions_cloud_docs(self) -> None:
        skill = DocsCreateSkill()
        prompt = skill.guidance_prompt()
        assert "云文档" in prompt

    def test_stage_4_prompt_contains_target_doc(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        for _ in range(4):
            skill.advance()
        prompt = skill.guidance_prompt()
        assert "CUA-Dark-Test-Doc" in prompt
        assert "请输入标题" in prompt


class TestStageStepGoals:
    def test_stage_0_goal_is_grounded_click(self) -> None:
        skill = DocsCreateSkill()
        goals = skill.stage_step_goals()
        assert len(goals) == 1
        assert goals[0].metadata.get("action_hint") == "click_grounded"
        assert goals[0].metadata.get("target_desc") == "云文档"

    def test_stage_4_has_two_sub_goals(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        for _ in range(4):
            skill.advance()
        goals = skill.stage_step_goals()
        assert len(goals) == 2
        assert goals[0].metadata.get("action_hint") == "click_ratio"
        assert goals[1].metadata.get("action_hint") == "paste_text"
        assert goals[1].metadata.get("text") == "CUA-Dark-Test-Doc"


class TestExecuteStageDryRun:
    def _make_fake_backend(self):
        class FakeBackend:
            def __init__(self):
                self.calls: list[str] = []

            def hotkey(self, *keys):
                self.calls.append(f"hotkey:{'+'.join(keys)}")
                return _FakeResult(True, "ok")

            def paste_text(self, text):
                self.calls.append(f"paste_text:{text[:30]}")
                return _FakeResult(True, "ok")

            def click(self, x, y, target=None):
                self.calls.append(f"click:{x},{y}")
                return _FakeResult(True, "ok")

        return FakeBackend()

    def _make_fake_grounder(self, point=(200, 300)):
        class FakeGrounder:
            def __init__(self):
                self.last_metadata: dict = {}

            def locate_target(self, target, screenshot_path, ocr_candidates, accessibility_candidates=None):
                self.last_metadata = {"target": target, "coordinate_source": "test"}
                return point

        return FakeGrounder()

    def test_first_stage_clicks_cloud_docs(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        backend = self._make_fake_backend()
        grounder = self._make_fake_grounder()
        action, verdict = skill.execute_stage(backend, grounder, None, [], [], dry_run=True)
        assert action.type == "click"
        assert verdict.status == "pass"
        assert "云文档" in action.target

    def test_input_title_stage(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        for _ in range(4):
            skill.advance()
        backend = self._make_fake_backend()
        grounder = self._make_fake_grounder()
        action, verdict = skill.execute_stage(backend, grounder, None, [], [], dry_run=True)
        assert action.type == "paste_text"
        assert action.text == "CUA-Dark-Test-Doc"
        assert verdict.status == "pass"
        assert any("click:" in c for c in backend.calls)

    def test_full_run(self) -> None:
        skill = DocsCreateSkill(target_doc="CUA-Dark-Test-Doc")
        backend = self._make_fake_backend()
        grounder = self._make_fake_grounder()
        while not skill.is_done:
            _, verdict = skill.execute_stage(backend, grounder, None, [], [], dry_run=True)
            assert verdict.status == "pass", f"Failed at {skill.stage.label}: {verdict.reason}"
            skill.advance()
        assert skill.is_done
        assert len(backend.calls) >= 5


class _FakeResult:
    def __init__(self, ok, reason="ok", metadata=None):
        self.ok = ok
        self.reason = reason
        self.metadata = metadata or {}
