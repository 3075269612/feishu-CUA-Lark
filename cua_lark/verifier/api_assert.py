from __future__ import annotations

from cua_lark.task.schema import Verdict


def api_assert_disabled(assertion_type: str) -> Verdict:
    return Verdict(status="uncertain", reason="Feishu API verifier disabled in Phase 1", evidence={"type": assertion_type})
