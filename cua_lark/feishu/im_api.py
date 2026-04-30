from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from cua_lark.feishu.auth import FeishuAuth


class ImApi:
    def __init__(self, auth: FeishuAuth | None = None, page_size: int = 20) -> None:
        self.auth = auth or FeishuAuth.from_env()
        self.page_size = page_size

    def latest_message_contains(self, chat_name: str, text: str) -> dict:
        token = self.auth.get_tenant_access_token()
        if not token:
            return {"status": "disabled", "reason": "missing_tenant_access_token", "chat_name": chat_name}

        chat_id = self._find_chat_id(chat_name, token)
        if not chat_id:
            return {"status": "fail", "reason": "chat_not_found", "chat_name": chat_name}

        messages = self._get_recent_messages(chat_id, token)
        extracted = [self._extract_text_content(message) for message in messages]
        matched = [message for message in extracted if text in message]
        if matched:
            return {
                "status": "pass",
                "reason": "latest_message_contains_text",
                "chat_name": chat_name,
                "chat_id": chat_id,
                "matched_count": len(matched),
                "recent_texts": extracted[:5],
            }
        return {
            "status": "fail",
            "reason": "message_text_not_found",
            "chat_name": chat_name,
            "chat_id": chat_id,
            "recent_texts": extracted[:5],
        }

    def _find_chat_id(self, chat_name: str, token: str) -> str | None:
        data = self._get(
            "/im/v1/chats",
            token,
            params={"page_size": 100},
        )
        for chat in data.get("items", []):
            if str(chat.get("name", "")).strip() == chat_name:
                return str(chat.get("chat_id"))
        return None

    def _get_recent_messages(self, chat_id: str, token: str) -> list[dict[str, Any]]:
        data = self._get(
            "/im/v1/messages",
            token,
            params={
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": self.page_size,
                "sort_type": "ByCreateTimeDesc",
            },
        )
        return list(data.get("items", []))

    def _get(self, path: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.auth.api_base_url}{path}"
        try:
            import httpx
        except ImportError:
            query = parse.urlencode(params)
            req = request.Request(f"{url}?{query}", headers={"Authorization": f"Bearer {token}"}, method="GET")
            with request.urlopen(req, timeout=self.auth.timeout) as resp:
                payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        else:
            response = httpx.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=self.auth.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"feishu_api_failed:{path}:{payload.get('code')}:{payload.get('msg')}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return {}
        return data

    def _extract_text_content(self, message: dict[str, Any]) -> str:
        body = message.get("body") or {}
        content = body.get("content", "")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return content
        return _flatten_text(content)


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("text", "name", "content"):
            if key in value:
                parts.append(_flatten_text(value[key]))
        if parts:
            return "".join(parts)
        return "".join(_flatten_text(item) for item in value.values())
    return str(value)
