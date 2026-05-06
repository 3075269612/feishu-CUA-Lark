from cua_lark.eval.report import build_markdown_summary


def test_build_markdown_summary_contains_metrics_and_cases() -> None:
    markdown = build_markdown_summary(
        {
            "suite_id": "suite",
            "profile": "mock",
            "started_at": "2026-05-06T10:00:00",
            "finished_at": "2026-05-06T10:00:01",
            "output_dir": "runs/suite",
            "metrics": {
                "total_cases": 1,
                "success_cases": 1,
                "manual_cases": 0,
                "failed_cases": 0,
                "task_success_rate": 1.0,
                "step_success_rate": 1.0,
                "mean_steps": 1.0,
                "mean_time": 1.0,
                "recovery_count": 0,
                "failure_category": {},
                "visual_api_agreement": {"comparable_cases": 0, "agreement_cases": 0, "rate": None},
            },
            "cases": [{"id": "im_case", "product": "im", "status": "pass", "steps": 1, "duration_sec": 1.0, "expected_met": True}],
        }
    )

    assert "# FeishuWorld Eval Report: suite" in markdown
    assert "task_success_rate" in markdown
    assert "`im_case`" in markdown
