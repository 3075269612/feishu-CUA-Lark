from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any
from urllib import request

from cua_lark.config.model_config import load_local_secrets


@dataclass
class FeishuAuth:
    app_id: str | None = None
    app_secret: str | None = None
    api_base_url: str = "https://open.feishu.cn/open-apis"
    timeout: float = 10.0
    _tenant_access_token: str | None = None
    _expires_at: float = 0.0

    def status(self) -> dict[str, str]:
        if self._env_token():
            return {"status": "enabled", "reason": "tenant_access_token_from_env"}
        if self.app_id and self.app_secret:
            return {"status": "enabled", "reason": "app_credentials_configured"}
        return {"status": "disabled", "reason": "feishu_credentials_missing"}

    @classmethod
    def from_env(cls, api_base_url: str | None = None, timeout: float = 10.0) -> FeishuAuth:
        secrets = load_local_secrets().get("feishu") or {}
        return cls(
            app_id=os.environ.get("FEISHU_APP_ID") or os.environ.get("LARK_APP_ID") or secrets.get("app_id"),
            app_secret=os.environ.get("FEISHU_APP_SECRET") or os.environ.get("LARK_APP_SECRET") or secrets.get("app_secret"),
            api_base_url=api_base_url
            or os.environ.get("FEISHU_API_BASE_URL")
            or secrets.get("api_base_url")
            or "https://open.feishu.cn/open-apis",
            timeout=timeout,
        )

    def get_tenant_access_token(self) -> str | None:
        env_token = self._env_token()
        if env_token:
            return env_token

        now = time.time()
        if self._tenant_access_token and now < self._expires_at - 60:
            return self._tenant_access_token
        if not self.app_id or not self.app_secret:
            return None

        payload = self._post_json(
            f"{self.api_base_url}/auth/v3/tenant_access_token/internal",
            {"app_id": self.app_id, "app_secret": self.app_secret},
        )
        if payload.get("code") != 0:
            raise RuntimeError(f"feishu_auth_failed:{payload.get('code')}:{payload.get('msg')}")

        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("feishu_auth_failed:missing_tenant_access_token")
        self._tenant_access_token = str(token)
        self._expires_at = now + int(payload.get("expire", 7200))
        return self._tenant_access_token

    @staticmethod
    def _env_token() -> str | None:
        return os.environ.get("FEISHU_TENANT_ACCESS_TOKEN") or os.environ.get("LARK_TENANT_ACCESS_TOKEN")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            import httpx
        except ImportError:
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        response = httpx.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
