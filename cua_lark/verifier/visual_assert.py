from __future__ import annotations

from cua_lark.task.schema import Verdict


def visual_text_exists(text: str) -> Verdict:
    return Verdict(status="uncertain", reason="visual verifier disabled in mock mode", evidence={"text": text})
