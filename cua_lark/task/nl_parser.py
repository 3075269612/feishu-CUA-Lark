from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime

from cua_lark.task.schema import TaskSpec, TaskLimits, SuccessCriterion
from cua_lark.perception.vlm import VlmClient


def parse_natural_language(
    nl_text: str,
    vlm: VlmClient | None = None,
    skills_dir: str | Path = "skills",
) -> TaskSpec:
    """Convert a natural language instruction into a structured TaskSpec.

    Uses the configured VLM to understand the user's intent and extract
    product type, slots, success criteria, and instruction text.
    """
    vlm = vlm or VlmClient()
    skills_context = _load_skill_context(skills_dir)
    prompt = _build_parse_prompt(nl_text, skills_context)

    response = vlm.summarize(None, prompt)

    if response.startswith("VLM disabled") or response.startswith("VLM error"):
        raise RuntimeError(f"NL parser requires a configured VLM: {response}")

    task_spec = _parse_vlm_response(response, nl_text)
    return task_spec


def _build_parse_prompt(nl_text: str, skills_context: str) -> str:
    """Build the VLM prompt for NL→TaskSpec conversion."""
    return (
        "你是一个飞书/Lark桌面端自动化测试的任务解析器。\n"
        "用户会用自然语言描述一个飞书操作任务，你需要将其转换为结构化的测试规格（TaskSpec JSON）。\n\n"

        "## 可用的飞书产品类型（product字段）\n"
        "- im: 即时消息（发送消息、搜索聊天、@提及等）\n"
        "- calendar: 日历（创建日程、修改日程、删除日程等）\n"
        "- docs: 云文档（创建文档、编辑文档等）\n"
        "- cross_product: 跨产品联动（涉及多个产品的组合任务）\n\n"

        "## 各产品的槽位（slots字段）\n"
        "IM: chat_name（群聊名称）, message（消息内容）, mention_user（可选，@的用户）\n"
        "Calendar: event_title（日程标题，必须包含CUA-Lark）, event_time（日程时间描述）\n"
        "Docs: target_doc（文档标题，必须包含CUA或CUA-Lark）, folder_name（文件夹名称）\n"
        "CrossProduct: chat_name, event_title, folder_name\n\n"

        "## 成功标准（success_criteria字段）\n"
        "每个任务至少包含一个 type=visual_text_exists 的成功标准，text为任务中应出现的文本。\n\n"

        "## 输出要求\n"
        "只输出一个合法的JSON对象，不要包含```json```代码块标记，不要包含任何解释文字。\n"
        "JSON格式：\n"
        "{\n"
        '  "product": "im|calendar|docs|cross_product",\n'
        '  "instruction": "用自然语言重述的任务描述",\n'
        '  "slots": { ... 产品相关的槽位键值对 ... },\n'
        '  "success_criteria": [{"type": "visual_text_exists", "text": "..."}]\n'
        "}\n\n"

        f"## 飞书操作技能参考\n{skills_context}\n\n"
        f"## 用户指令\n{nl_text}\n\n"
        "请解析为JSON："
    )


def _load_skill_context(skills_dir: str | Path) -> str:
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return ""
    chunks: list[str] = []
    for path in sorted(skills_path.glob("*.md")):
        try:
            chunks.append(f"# {path.name}\n{path.read_text(encoding='utf-8')}")
        except OSError:
            continue
    return "\n\n".join(chunks)


def _parse_vlm_response(response: str, nl_text: str) -> TaskSpec:
    """Parse VLM response text into a TaskSpec, filling in defaults."""
    payload = _extract_json_payload(response)
    if payload is None:
        raise ValueError(f"VLM did not return valid JSON: {response[:300]}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise ValueError(f"VLM returned invalid JSON: {payload[:300]}")

    product = str(data.get("product", "im"))
    instruction = str(data.get("instruction", nl_text))
    slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
    slots = _inject_run_id_marker(product, slots)

    success_criteria: list[SuccessCriterion] = []
    raw_criteria = data.get("success_criteria", [])
    if isinstance(raw_criteria, list):
        for c in raw_criteria:
            if isinstance(c, dict) and c.get("type"):
                success_criteria.append(SuccessCriterion(**c))

    task_id = _generate_task_id(product)

    return TaskSpec(
        id=task_id,
        product=product,
        instruction=instruction,
        slots=slots,
        success_criteria=success_criteria,
        limits=TaskLimits(max_steps=30, timeout_sec=120),
        risk_level="low",
    )


def _generate_task_id(product: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"nl_{product}_{ts}"


def _inject_run_id_marker(product: str, slots: dict) -> dict:
    """Ensure slots contain {{run_id}} marker required by SafetyGuard."""
    slots = dict(slots)
    if product == "im":
        message = str(slots.get("message", ""))
        if "{{run_id}}" not in message:
            slots["message"] = f"{message} {{{{run_id}}}}".strip()
    if product == "calendar":
        title = str(slots.get("event_title", ""))
        if "{{run_id}}" not in title:
            slots["event_title"] = f"{title} {{{{run_id}}}}".strip()
    if product == "cross_product":
        title = str(slots.get("event_title", ""))
        if "{{run_id}}" not in title:
            slots["event_title"] = f"{title} {{{{run_id}}}}".strip()
    return slots


def _extract_json_payload(text: str) -> str | None:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    obj_start = stripped.find("{")
    obj_end = stripped.rfind("}")
    if 0 <= obj_start < obj_end:
        return stripped[obj_start: obj_end + 1]
    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if 0 <= array_start < array_end:
        return stripped[array_start: array_end + 1]
    return None
