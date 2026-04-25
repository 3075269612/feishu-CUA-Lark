from __future__ import annotations

from cua_lark.task.schema import Action, Verdict


class RecoveryPolicy:
    def plan(self, verdict: Verdict) -> Action | None:
        if verdict.status in {"pass", "blocked"}:
            return None
        return Action(type="noop_recovery", target="mock", metadata={"reason": verdict.reason})
