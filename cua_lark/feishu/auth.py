from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeishuAuth:
    app_id: str | None = None
    app_secret: str | None = None

    def status(self) -> dict[str, str]:
        return {"status": "disabled", "reason": "Feishu API auth is not used in Phase 1 mock mode"}
