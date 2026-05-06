from __future__ import annotations

from statistics import mean
from typing import Any


SUCCESS_STATUS = "pass"
MANUAL_STATUSES = {"needs_manual_verification", "sent_with_screenshot_evidence"}
FAILURE_STATUSES = {"blocked", "fail", "uncertain"}


def compute_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    success_cases = [case for case in cases if case.get("status") == SUCCESS_STATUS]
    manual_cases = [case for case in cases if case.get("status") in MANUAL_STATUSES]
    failed_cases = [case for case in cases if case.get("status") in FAILURE_STATUSES or case.get("status") is None]
    total_steps = sum(int(case.get("steps") or 0) for case in cases)
    passed_steps = sum(int(case.get("passed_steps") or 0) for case in cases)

    comparable, agreement = _visual_api_agreement(cases)
    return {
        "total_cases": total,
        "success_cases": len(success_cases),
        "manual_cases": len(manual_cases),
        "failed_cases": len(failed_cases),
        "task_success_rate": _rate(len(success_cases), total),
        "manual_rate": _rate(len(manual_cases), total),
        "step_success_rate": _rate(passed_steps, total_steps),
        "mean_steps": _mean([case.get("steps") for case in cases]),
        "mean_time": _mean([case.get("duration_sec") for case in cases]),
        "recovery_count": sum(int(case.get("recovery_count") or 0) for case in cases),
        "failure_category": _failure_categories(cases),
        "visual_api_agreement": {
            "comparable_cases": comparable,
            "agreement_cases": agreement,
            "rate": _rate(agreement, comparable),
        },
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _mean(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return round(mean(numeric), 4)


def _failure_categories(cases: list[dict[str, Any]]) -> dict[str, int]:
    categories: dict[str, int] = {}
    for case in cases:
        status = case.get("status")
        if status == SUCCESS_STATUS or status in MANUAL_STATUSES:
            continue
        category = str(case.get("failure_category") or status or "missing_trace")
        categories[category] = categories.get(category, 0) + 1
    return categories


def _visual_api_agreement(cases: list[dict[str, Any]]) -> tuple[int, int]:
    comparable = 0
    agreement = 0
    for case in cases:
        evidence = case.get("verification_evidence")
        if not isinstance(evidence, list):
            continue
        api_status = _source_status(evidence, {"api", "api_oracle", "feishu_api"})
        visual_status = _source_status(evidence, {"visual", "vlm", "ocr"})
        if api_status is None or visual_status is None:
            continue
        comparable += 1
        if api_status == visual_status:
            agreement += 1
    return comparable, agreement


def _source_status(evidence: list[Any], source_names: set[str]) -> str | None:
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").lower()
        if source in source_names:
            status = item.get("status")
            return str(status) if status is not None else None
    return None
