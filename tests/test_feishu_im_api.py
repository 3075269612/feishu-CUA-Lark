from types import SimpleNamespace

import httpx

from cua_lark.feishu.auth import FeishuAuth
from cua_lark.feishu.im_api import ImApi


def test_im_api_latest_message_contains(monkeypatch) -> None:
    def fake_get(url, headers, params, timeout):
        if url.endswith("/im/v1/chats"):
            payload = {"code": 0, "data": {"items": [{"name": "CUA-Lark-Test", "chat_id": "chat_1"}]}}
        else:
            payload = {
                "code": 0,
                "data": {
                    "items": [
                        {"body": {"content": "{\"text\":\"Hello from CUA-Lark run_001\"}"}},
                    ]
                },
            }
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr(httpx, "get", fake_get)
    auth = FeishuAuth(api_base_url="https://example.test", _tenant_access_token="token", _expires_at=9999999999)

    result = ImApi(auth=auth).latest_message_contains("CUA-Lark-Test", "Hello from CUA-Lark")

    assert result["status"] == "pass"
    assert result["chat_id"] == "chat_1"
