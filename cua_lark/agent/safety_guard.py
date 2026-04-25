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
