"""Test target name normalization for Chinese/English compatibility."""

from cua_lark.main import _normalize_target_name


def test_normalize_feishu_window():
    """Test feishu_window normalization."""
    assert _normalize_target_name("feishu_window", "CUA-Lark-Test") == "feishu_window"
    assert _normalize_target_name("飞书窗口", "CUA-Lark-Test") == "feishu_window"
    assert _normalize_target_name("飞书主窗口", "CUA-Lark-Test") == "feishu_window"
    assert _normalize_target_name("飞书桌面应用窗口", "CUA-Lark-Test") == "feishu_window"


def test_normalize_message_module():
    """Test message_module normalization."""
    assert _normalize_target_name("message_module", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("消息入口", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("消息按钮", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("左侧栏消息入口", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("左侧导航栏的消息按钮", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("left sidebar message button", "CUA-Lark-Test") == "message_module"


def test_normalize_message_input():
    """Test message_input normalization."""
    assert _normalize_target_name("message_input", "CUA-Lark-Test") == "message_input"
    assert _normalize_target_name("消息输入框", "CUA-Lark-Test") == "message_input"
    assert _normalize_target_name("输入框", "CUA-Lark-Test") == "message_input"
    assert _normalize_target_name("聊天窗口底部输入框", "CUA-Lark-Test") == "message_input"
    assert _normalize_target_name("message input box", "CUA-Lark-Test") == "message_input"


def test_normalize_send_button():
    """Test send_button_or_enter normalization."""
    assert _normalize_target_name("send_button_or_enter", "CUA-Lark-Test") == "send_button_or_enter"
    assert _normalize_target_name("发送按钮", "CUA-Lark-Test") == "send_button_or_enter"
    assert _normalize_target_name("键盘 Enter 键", "CUA-Lark-Test") == "send_button_or_enter"
    assert _normalize_target_name("send button", "CUA-Lark-Test") == "send_button_or_enter"


def test_normalize_chat_name():
    """Test chat name normalization."""
    assert _normalize_target_name("CUA-Lark-Test", "CUA-Lark-Test") == "CUA-Lark-Test"
    assert _normalize_target_name("左侧会话列表中的CUA-Lark-Test群聊", "CUA-Lark-Test") == "CUA-Lark-Test"
    assert _normalize_target_name("CUA-Lark-Test群聊列表项", "CUA-Lark-Test") == "CUA-Lark-Test"
    assert _normalize_target_name("left conversation list item named CUA-Lark-Test", "CUA-Lark-Test") == "CUA-Lark-Test"
    # IMPORTANT: Handle literal placeholders from LLM planner
    assert _normalize_target_name("chat_name", "CUA-Lark-Test") == "CUA-Lark-Test"
    assert _normalize_target_name("chat_list_item", "CUA-Lark-Test") == "CUA-Lark-Test"


def test_normalize_unknown_target():
    """Test that unknown targets are returned as-is."""
    assert _normalize_target_name("unknown_target", "CUA-Lark-Test") == "unknown_target"
    assert _normalize_target_name("随机目标", "CUA-Lark-Test") == "随机目标"
    assert _normalize_target_name("当前页面UI", "CUA-Lark-Test") == "当前页面UI"


def test_normalize_case_insensitive():
    """Test that normalization is case-insensitive for English."""
    assert _normalize_target_name("Message_Module", "CUA-Lark-Test") == "message_module"
    assert _normalize_target_name("MESSAGE_INPUT", "CUA-Lark-Test") == "message_input"
    assert _normalize_target_name("SEND_BUTTON_OR_ENTER", "CUA-Lark-Test") == "send_button_or_enter"
