from cua_lark.main import _docs_create_verdict


def test_docs_create_verdict_blocks_existing_list_item_false_positive() -> None:
    verdict = _docs_create_verdict(
        "CUA-Dark-Test-Doc 20260506_131327_829575",
        "当前页面为云文档主页，展示文档列表，未直接显示标题输入区。",
        [
            {"text": "标题"},
            {"text": "位置"},
            {"text": "所有者"},
            {"text": "CUA-Dark-Test-Doc 20260506_131327_829575"},
        ],
        {"path": "after.png"},
    )

    assert verdict.status == "blocked"
    assert verdict.reason == "docs_create_not_verified_postcondition"
    assert verdict.evidence["title_found"] is True
    assert "未直接显示标题输入区" in verdict.evidence["list_marker_hits"]


def test_docs_create_verdict_accepts_editor_with_unique_title() -> None:
    verdict = _docs_create_verdict(
        "CUA-Dark-Test-Doc 20260506_131327_829575",
        "当前是文档页面，标题输入区显示 CUA-Dark-Test-Doc 20260506_131327_829575，正文区域可编辑。",
        [],
        {"path": "after.png"},
    )

    assert verdict.status == "pass"
    assert verdict.reason == "docs_create_verified"
