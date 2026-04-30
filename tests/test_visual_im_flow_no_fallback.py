"""Integration test: visual IM flow must not fallback to dangerous fixed coordinates."""

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from cua_lark.grounding.hybrid_grounder import HybridGrounder
from cua_lark.main import _execute_visual_goal, _fallback_anchor_for_target
from cua_lark.task.schema import Observation, StepGoal, TaskSpec


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dry_run = True
    return args


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.click.return_value = Mock(ok=True, reason="click_ok", metadata={})
    backend.paste_text.return_value = Mock(ok=True, reason="paste_ok", metadata={})
    return backend


@pytest.fixture
def mock_grounder():
    grounder = MagicMock(spec=HybridGrounder)
    grounder.last_metadata = {}
    grounder.locate_target.return_value = None  # Default: VLM cannot find target
    return grounder


@pytest.fixture
def mock_task():
    return TaskSpec(
        id="test_visual_im",
        product="im",
        action="send_text",
        instruction="Send test message to CUA-Lark-Test",
        slots={"chat_name": "CUA-Lark-Test", "message": "test message"},
    )


@pytest.fixture
def context_with_legacy_anchors():
    """Context with old dangerous coordinates that visual mode must NOT use."""
    return {
        "planned_points": {
            "message_module": (52, 88),  # Dangerous: hits search box
            "search_box": (300, 70),
            "first_search_result": (300, 165),
            "message_input": (760, 820),
        },
        "last_visual_grounding": {},
    }


def test_fallback_blocks_message_module(context_with_legacy_anchors):
    """_fallback_anchor_for_target must return None for message_module."""
    result = _fallback_anchor_for_target("message_module", context_with_legacy_anchors["planned_points"])
    assert result is None, "message_module must not fallback to fixed coordinates"


def test_fallback_blocks_search_box(context_with_legacy_anchors):
    """_fallback_anchor_for_target must return None for search_box."""
    result = _fallback_anchor_for_target("search_box", context_with_legacy_anchors["planned_points"])
    assert result is None, "search_box must not fallback in IM send flow"


def test_fallback_blocks_chat_list_items(context_with_legacy_anchors):
    """_fallback_anchor_for_target must return None for conversation list items."""
    result = _fallback_anchor_for_target(
        "left conversation list item named CUA-Lark-Test",
        context_with_legacy_anchors["planned_points"],
    )
    assert result is None, "chat list items must not fallback to search"


def test_fallback_allows_message_input(context_with_legacy_anchors):
    """_fallback_anchor_for_target allows message_input (safe geometry)."""
    result = _fallback_anchor_for_target("message_input", context_with_legacy_anchors["planned_points"])
    assert result == "message_input", "message_input has safe geometry and can fallback"


def test_visual_message_module_blocks_when_vlm_fails(
    mock_args, mock_backend, mock_grounder, mock_task, context_with_legacy_anchors
):
    """When VLM cannot find message button, visual mode must block (not use legacy [52,88])."""
    goal = StepGoal(index=2, description="Open message module", target="message_module", expected="visible")
    observation = Observation(
        step_index=2,
        screen_summary="Feishu window",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    # VLM cannot find message button
    mock_grounder.locate_target.return_value = None

    action, verdict = _execute_visual_goal(
        mock_args, mock_task, mock_backend, context_with_legacy_anchors, mock_grounder, goal, observation
    )

    # Must block, not click the dangerous (52, 88)
    assert verdict.status == "blocked"
    assert verdict.reason == "message_module_button_not_found_by_vlm"
    mock_backend.click.assert_not_called()


def test_visual_open_chat_blocks_when_vlm_fails(
    mock_args, mock_backend, mock_grounder, mock_task, context_with_legacy_anchors
):
    """When VLM cannot find chat list item, visual mode must block (not use search_box)."""
    goal = StepGoal(index=3, description="Open chat", target="CUA-Lark-Test", expected="chat opened")
    observation = Observation(
        step_index=3,
        screen_summary="Feishu message page",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    # VLM cannot find chat list item
    mock_grounder.locate_target.return_value = None

    action, verdict = _execute_visual_goal(
        mock_args, mock_task, mock_backend, context_with_legacy_anchors, mock_grounder, goal, observation
    )

    # Must block, not fallback to search_box
    assert verdict.status == "blocked"
    assert verdict.reason == "visual_chat_list_item_not_found"
    mock_backend.click.assert_not_called()


def test_visual_message_input_can_use_geometry_fallback(
    mock_args, mock_backend, mock_grounder, mock_task, context_with_legacy_anchors
):
    """message_input has safe geometry and can fallback when VLM fails."""
    goal = StepGoal(index=4, description="Fill message input", target="message_input", expected="text visible")
    observation = Observation(
        step_index=4,
        screen_summary="Chat opened",
        screenshot_path="/tmp/test.png",
        ocr_texts=[],
        metadata={"origin": [0, 0], "screenshot_size": [1600, 1000]},
    )

    # VLM cannot find message_input
    mock_grounder.locate_target.return_value = None

    action, verdict = _execute_visual_goal(
        mock_args, mock_task, mock_backend, context_with_legacy_anchors, mock_grounder, goal, observation
    )

    # Should use geometry fallback (760, 820) and succeed
    assert action.type == "paste_text"
    assert verdict.status == "pass"
    assert action.coordinates == (760, 820)
    mock_backend.click.assert_called_once_with(760, 820, "message_input")
    mock_backend.paste_text.assert_called_once_with("test message")
