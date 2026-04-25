from __future__ import annotations

from cua_lark.task.schema import Verdict


def ocr_text_exists(text: str) -> Verdict:
    return Verdict(status="uncertain", reason="ocr verifier disabled in mock mode", evidence={"text": text})
