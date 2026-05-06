from pathlib import Path

import pytest

from cua_lark.eval.suite import load_eval_suite


def test_load_eval_suite(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
id: small_suite
description: "Small suite"
cases:
  - id: im_case
    task_path: testcases/im/send_text.yaml
    product: im
    profiles: [mock]
    tags: [im, smoke]
    expected_statuses: [pass]
""",
        encoding="utf-8",
    )

    suite = load_eval_suite(suite_path)

    assert suite.id == "small_suite"
    assert suite.cases[0].supports_profile("mock")
    assert suite.cases[0].expected_statuses == ["pass"]


def test_load_eval_suite_rejects_unknown_profile(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """
id: bad_suite
description: "Bad suite"
cases:
  - id: bad_case
    task_path: testcases/im/send_text.yaml
    product: im
    profiles: [desktop]
    tags: []
    expected_statuses: [pass]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported"):
        load_eval_suite(suite_path)
