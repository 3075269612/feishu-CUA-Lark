import sys
from types import SimpleNamespace

from cua_lark.perception.vlm import VlmClient


def _dashscope_module(text: str):
    message = SimpleNamespace(content=[{"text": text}])
    choice = SimpleNamespace(message=message)
    output = SimpleNamespace(choices=[choice])
    response = SimpleNamespace(status_code=200, output=output)
    return SimpleNamespace(MultiModalConversation=SimpleNamespace(call=lambda **kwargs: response))


def test_vlm_client_summarize_calls_dashscope(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "dashscope", _dashscope_module("screen summary"))

    result = VlmClient(api_key="key").summarize("screen.png", "describe")

    assert result == "screen summary"


def test_vlm_client_locate_element_parses_bbox(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "dashscope", _dashscope_module("10 20 30 40"))

    result = VlmClient(api_key="key").locate_element("screen.png", "send button")

    assert result == (10, 20, 30, 40)


def test_vlm_client_without_api_key_degrades() -> None:
    client = VlmClient(api_key="")

    assert client.locate_element("screen.png", "target") is None
    assert "VLM disabled" in client.summarize("screen.png", "prompt")


def test_vlm_client_loads_model_config_by_default(monkeypatch) -> None:
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content=[{"text": "configured"}])
        choice = SimpleNamespace(message=message)
        output = SimpleNamespace(choices=[choice])
        return SimpleNamespace(status_code=200, output=output)

    fake_dashscope = SimpleNamespace(MultiModalConversation=SimpleNamespace(call=fake_call))
    monkeypatch.setitem(sys.modules, "dashscope", fake_dashscope)

    class FakeModelConfig:
        vlm_model = "configured-model"
        timeout_sec = 12

        def dashscope_api_key(self) -> str:
            return "configured-key"

    monkeypatch.setattr("cua_lark.perception.vlm.ModelConfig.from_yaml", lambda: FakeModelConfig())

    result = VlmClient().summarize("screen.png", "describe")

    assert result == "configured"
    assert calls[0]["model"] == "configured-model"
    assert calls[0]["api_key"] == "configured-key"
