from cua_lark.eval.metrics import compute_metrics


def test_compute_metrics_separates_success_manual_and_failures() -> None:
    metrics = compute_metrics(
        [
            {"status": "pass", "steps": 3, "passed_steps": 3, "duration_sec": 2.0},
            {"status": "needs_manual_verification", "steps": 2, "passed_steps": 1, "duration_sec": 4.0},
            {"status": "blocked", "steps": 1, "passed_steps": 0, "failure_category": "blocked_by_safety"},
        ]
    )

    assert metrics["total_cases"] == 3
    assert metrics["success_cases"] == 1
    assert metrics["manual_cases"] == 1
    assert metrics["failed_cases"] == 1
    assert metrics["task_success_rate"] == 0.3333
    assert metrics["step_success_rate"] == 0.6667
    assert metrics["mean_steps"] == 2.0
    assert metrics["mean_time"] == 3.0
    assert metrics["failure_category"] == {"blocked_by_safety": 1}


def test_compute_metrics_visual_api_agreement() -> None:
    metrics = compute_metrics(
        [
            {
                "status": "pass",
                "steps": 1,
                "passed_steps": 1,
                "verification_evidence": [
                    {"source": "api_oracle", "status": "pass"},
                    {"source": "ocr", "status": "pass"},
                ],
            },
            {
                "status": "fail",
                "steps": 1,
                "passed_steps": 0,
                "verification_evidence": [
                    {"source": "api_oracle", "status": "fail"},
                    {"source": "vlm", "status": "pass"},
                ],
            },
        ]
    )

    assert metrics["visual_api_agreement"] == {
        "comparable_cases": 2,
        "agreement_cases": 1,
        "rate": 0.5,
    }
