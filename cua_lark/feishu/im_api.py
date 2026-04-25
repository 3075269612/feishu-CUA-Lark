from __future__ import annotations


class ImApi:
    def latest_message_contains(self, chat_name: str, text: str) -> dict:
        return {"status": "disabled", "chat_name": chat_name, "text": text}
