"""Test message_module step in visual grounding mode."""

from unittest.mock import MagicMock, Mock

import pytest

from cua_lark.main import _execute_visual_message_module
from cua_lark.task.schema import Observation, StepGoal


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dry_run = True
    return args


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.click.return_value = Mock(ok=True, reason="click_ok", metadata={})
    return backend


@pytest.fixture
def mock_grounder():
    grounder = MagicMock()
    grounder.last_metadata = {}
    return grounder


@pytest.fixture
def mock_context():
    return {"planned_points": {}, "last_visual_grounding": {}}


@pytest.fixture
def mock_goal():
    return StepGoal(
        index=2,
        description="Open message module",
        target="message_module",
        expected="message module visible",
    )


def test_message_module_already_on_page_by_screen_summary(mock_args, mock_backend, mock_grounder, mock_context, mock_goal):
    """When screen_summary indicates already on message page, should skip click."""
    observation = Observation(
        step_index=2,
        screen_summary="Feishu conversation list with recent chats visible",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    action, verdict = _execute_visual_message_module(
        mock_args, mock_backend, mock_context, mock_grounder, mock_goal, observation
    )

    assert action.type == "observe"
    assert verdict.status == "pass"
    assert verdict.reason == "already_on_message_page"
    assert verdict.evidence.get("skip_click") is True
    mock_backend.click.assert_not_called()
    mock_grounder.locate_target.assert_not_called()


def test_message_module_already_on_page_by_ocr(mock_args, mock_backend, mock_grounder, mock_context, mock_goal):
    """When OCR detects conversation indicators, should skip click."""
    observation = Observation(
        step_index=2,
        screen_summary="Feishu window",
        screenshot_path="/tmp/test.png",
        ocr_texts=[
            {"text": "会话", "bbox": [50, 100, 100, 120]},
            {"text": "CUA-Lark-Test", "bbox": [50, 150, 200, 170]},
        ],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    action, verdict = _execute_visual_message_module(
        mock_args, mock_backend, mock_context, mock_grounder, mock_goal, observation
    )

    assert action.type == "observe"
    assert verdict.status == "pass"
    assert verdict.reason == "already_on_message_page"
    mock_backend.click.assert_not_called()


def test_message_module_vlm_locates_button(mock_args, mock_backend, mock_grounder, mock_context, mock_goal):
    """When not on message page, VLM should locate and click message button."""
    observation = Observation(
        step_index=2,
        screen_summary="Feishu window showing calendar view",
        screenshot_path="/tmp/test.png",
        ocr_texts=[{"text": "日历", "bbox": [50, 100, 100, 120]}],
        metadata={"origin": [100, 50], "screenshot_size": [1600, 1000]},
    )

    # VLM finds message button at screenshot coordinates (60, 200)
    mock_grounder.locate_target.return_value = (60, 200)

    action, verdict = _execute_visual_message_module(
        mock_args, mock_backend, mock_context, mock_grounder, mock_goal, observation
    )

    assert action.type == "click"
    assert action.target == "message_module"
    assert action.coordinates == (160, 250)  # (60+100, 200+50) screen coordinates
    assert verdict.status == "pass"
    mock_grounder.locate_target.assert_called_once_with(
        "left sidebar message button",
        "/tmp/test.png",
        observation.ocr_texts,
        accessibility_candidates=observation.accessibility_candidates,
    )
    mock_backend.click.assert_called_once_with(160, 250, "message_module")


def test_message_module_vlm_not_found_blocks(mock_args, mock_backend, mock_grounder, mock_context, mock_goal):
    """When VLM cannot locate message button, should block (no fallback to fixed coordinates)."""
    observation = Observation(
        step_index=2,
        screen_summary="Feishu window",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    # VLM cannot find message button
    mock_grounder.locate_target.return_value = None

    action, verdict = _execute_visual_message_module(
        mock_args, mock_backend, mock_context, mock_grounder, mock_goal, observation
    )

    assert action.type == "click"
    assert verdict.status == "blocked"
    assert verdict.reason == "message_module_button_not_found_by_vlm"
    assert verdict.evidence.get("no_fallback") is True
    mock_backend.click.assert_not_called()


def test_message_module_no_fallback_to_fixed_coordinates(mock_args, mock_backend, mock_grounder, mock_context, mock_goal):
    """Even with planned_points containing message_module, should not fallback - must use VLM."""
    # This test ensures the new logic doesn't accidentally use old fallback path
    context_with_old_anchor = {
        "planned_points": {"message_module": (52, 88)},  # Old dangerous coordinate
        "last_visual_grounding": {},
    }

    observation = Observation(
        step_index=2,
        screen_summary="Feishu window",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    # VLM cannot find it
    mock_grounder.locate_target.return_value = None

    action, verdict = _execute_visual_message_module(
        mock_args, mock_backend, context_with_old_anchor, mock_grounder, mock_goal, observation
    )

    # Should block, not use the dangerous (52, 88) coordinate
    assert verdict.status == "blocked"
    assert verdict.reason == "message_module_button_not_found_by_vlm"
    mock_backend.click.assert_not_called()
