from types import SimpleNamespace

import httpx

from cua_lark.feishu.auth import FeishuAuth


def test_feishu_auth_gets_and_caches_tenant_token(monkeypatch) -> None:
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"code": 0, "tenant_access_token": "tenant-token", "expire": 7200},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    auth = FeishuAuth(app_id="app", app_secret="secret", api_base_url="https://example.test", timeout=3)

    assert auth.get_tenant_access_token() == "tenant-token"
    assert auth.get_tenant_access_token() == "tenant-token"
    assert len(calls) == 1


def test_feishu_auth_from_env_prefers_tenant_token(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_TENANT_ACCESS_TOKEN", "env-token")

    auth = FeishuAuth.from_env()

    assert auth.get_tenant_access_token() == "env-token"
