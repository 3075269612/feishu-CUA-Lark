from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from cua_lark.task.schema import Action, TaskSpec


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str = "allowed"


@dataclass
class SafetyGuard:
    allowed_chats: set[str] = field(default_factory=set)
    allowed_contacts: set[str] = field(default_factory=set)
    allowed_doc_folders: set[str] = field(default_factory=set)
    allowed_calendar_keywords: set[str] = field(default_factory=set)
    forbidden_actions: set[str] = field(default_factory=set)
    require_run_id_in_message: bool = True
    real_ui_requires_confirm_target: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SafetyGuard":
        with Path(path).open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(
            allowed_chats=set(data.get("allowed_chats", [])),
            allowed_contacts=set(data.get("allowed_contacts", [])),
            allowed_doc_folders=set(data.get("allowed_doc_folders", [])),
            allowed_calendar_keywords=set(data.get("allowed_calendar_keywords", [])),
            forbidden_actions=set(data.get("forbidden_actions", [])),
            require_run_id_in_message=bool(data.get("require_run_id_in_message", True)),
            real_ui_requires_confirm_target=bool(data.get("real_ui_requires_confirm_target", True)),
        )

    def check_task(self, task: TaskSpec) -> SafetyDecision:
        slots = task.slots
        chat = slots.get("chat_name")
        if chat and chat not in self.allowed_chats:
            return SafetyDecision(False, f"chat_not_allowed:{chat}")

        for contact in self._iter_slot_values(slots, ("contact_name", "contact_names", "attendees", "invitees")):
            if contact not in self.allowed_contacts:
                return SafetyDecision(False, f"contact_not_allowed:{contact}")

        folder = slots.get("folder_name") or slots.get("doc_folder") or slots.get("doc_folder_name")
        if folder and folder not in self.allowed_doc_folders:
            return SafetyDecision(False, f"doc_folder_not_allowed:{folder}")

        if task.product == "calendar" or any(key in slots for key in ("event_title", "title")):
            title = str(slots.get("event_title") or slots.get("title") or "")
            if title and self.allowed_calendar_keywords:
                if not any(keyword in title for keyword in self.allowed_calendar_keywords):
                    return SafetyDecision(False, f"calendar_keyword_not_allowed:{title}")

        return SafetyDecision(True)

    def check_action(self, action: Action, task: TaskSpec | None = None) -> SafetyDecision:
        candidates = {action.type}
        for key in ("risk", "forbidden_action", "action_name"):
            value = action.metadata.get(key)
            if isinstance(value, str):
                candidates.add(value)
        blocked = candidates & self.forbidden_actions
        if blocked:
            return SafetyDecision(False, f"forbidden_action:{sorted(blocked)[0]}")
        if task is not None:
            return self.check_task(task)
        return SafetyDecision(True)

    def check_real_ui_run(
        self,
        task: TaskSpec,
        confirm_target: str | None,
        rendered_message: str,
        run_id: str,
    ) -> SafetyDecision:
        if task.product not in ("im", "docs"):
            return SafetyDecision(False, f"real_ui_product_not_allowed:{task.product}")
        if task.risk_level != "low":
            return SafetyDecision(False, f"risk_level_not_allowed:{task.risk_level}")

        task_decision = self.check_task(task)
        if not task_decision.allowed:
            return task_decision

        if task.product == "docs":
            target_doc = str(task.slots.get("target_doc", ""))
            if self.real_ui_requires_confirm_target and not confirm_target:
                return SafetyDecision(False, "confirm_target_required")
            if confirm_target and target_doc and "CUA" not in target_doc:
                return SafetyDecision(False, f"docs_title_missing_cua_marker:{target_doc}")
            return SafetyDecision(True)

        chat_name = task.slots.get("chat_name")
        if self.real_ui_requires_confirm_target and not confirm_target:
            return SafetyDecision(False, "confirm_target_required")
        if confirm_target != chat_name:
            return SafetyDecision(False, f"confirm_target_mismatch:{confirm_target}!={chat_name}")

        if "CUA-Lark" not in rendered_message:
            return SafetyDecision(False, "message_missing_cua_lark_marker")
        if self.require_run_id_in_message and run_id not in rendered_message:
            return SafetyDecision(False, "message_missing_run_id")

        return SafetyDecision(True)

    def allow_task(self, task: TaskSpec) -> bool:
        return self.check_task(task).allowed

    def allow_action(self, action: Action, task: TaskSpec | None = None) -> bool:
        return self.check_action(action, task).allowed

    @staticmethod
    def _iter_slot_values(slots: dict[str, Any], keys: Iterable[str]) -> Iterable[str]:
        for key in keys:
            value = slots.get(key)
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield item
