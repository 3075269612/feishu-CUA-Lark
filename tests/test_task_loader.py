from cua_lark.task.loader import load_task


def test_load_send_text_task() -> None:
    task = load_task("testcases/im/send_text.yaml")

    assert task.id == "im_send_text_001"
    assert task.product == "im"
    assert task.slots["chat_name"] == "CUA-Lark-Test"
    assert task.limits.max_steps == 30
    assert task.success_criteria[0].type == "visual_text_exists"
