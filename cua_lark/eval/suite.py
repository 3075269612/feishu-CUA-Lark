from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VALID_PROFILES = {"mock", "real-smoke-dry-run", "real-smoke"}
VALID_STATUSES = {
    "pass",
    "fail",
    "blocked",
    "uncertain",
    "sent_with_screenshot_evidence",
    "needs_manual_verification",
}


@dataclass(frozen=True)
class EvalCase:
    id: str
    task_path: str
    product: str
    profiles: list[str]
    tags: list[str] = field(default_factory=list)
    expected_statuses: list[str] = field(default_factory=lambda: ["pass"])

    def supports_profile(self, profile: str) -> bool:
        return profile in self.profiles


@dataclass(frozen=True)
class EvalSuite:
    id: str
    description: str
    cases: list[EvalCase]

    def cases_for_profile(self, profile: str) -> list[EvalCase]:
        return [case for case in self.cases if case.supports_profile(profile)]


def load_eval_suite(path: str | Path) -> EvalSuite:
    suite_path = Path(path)
    with suite_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("eval suite must be a mapping")

    suite_id = _required_str(data, "id", "suite")
    description = _required_str(data, "description", suite_id)
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("eval suite requires a non-empty cases list")

    cases = [_parse_case(item, index) for index, item in enumerate(raw_cases)]
    return EvalSuite(id=suite_id, description=description, cases=cases)


def _parse_case(raw: Any, index: int) -> EvalCase:
    if not isinstance(raw, dict):
        raise ValueError(f"case[{index}] must be a mapping")
    case_id = _required_str(raw, "id", f"case[{index}]")
    task_path = _required_str(raw, "task_path", case_id)
    product = _required_str(raw, "product", case_id)
    profiles = _required_list(raw, "profiles", case_id)
    tags = _optional_list(raw, "tags")
    expected_statuses = _required_list(raw, "expected_statuses", case_id)

    invalid_profiles = sorted(set(profiles) - VALID_PROFILES)
    if invalid_profiles:
        raise ValueError(f"{case_id}.profiles contains unsupported values: {invalid_profiles}")
    invalid_statuses = sorted(set(expected_statuses) - VALID_STATUSES)
    if invalid_statuses:
        raise ValueError(f"{case_id}.expected_statuses contains unsupported values: {invalid_statuses}")

    return EvalCase(
        id=case_id,
        task_path=task_path,
        product=product,
        profiles=profiles,
        tags=tags,
        expected_statuses=expected_statuses,
    )


def _required_str(data: dict[str, Any], key: str, owner: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner}.{key} is required")
    return value.strip()


def _required_list(data: dict[str, Any], key: str, owner: str) -> list[str]:
    values = data.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"{owner}.{key} must be a non-empty list")
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError(f"{owner}.{key} must contain only strings")
    return [value.strip() for value in values]


def _optional_list(data: dict[str, Any], key: str) -> list[str]:
    values = data.get(key, [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{key} must be a list")
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError(f"{key} must contain only strings")
    return [value.strip() for value in values]
