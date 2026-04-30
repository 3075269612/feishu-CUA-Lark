from __future__ import annotations

import logging
import os
import re
from typing import Any

from cua_lark.config import ModelConfig

logger = logging.getLogger(__name__)


class VlmClient:
    """Vision-Language Model client backed by DashScope Qwen-VL (lazy-loaded)."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> None:
        config = _load_model_config()
        self._model = model or (config.vlm_model if config else "qwen-vl-max")
        if api_key is None:
            api_key = config.dashscope_api_key() if config else os.environ.get("DASHSCOPE_API_KEY")
        self._api_key = api_key
        self._timeout = timeout or (config.timeout_sec if config else 30)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(self, screenshot_path: str | None, prompt: str | None = None) -> str:
        """Send a screenshot (optional) + text prompt to Qwen-VL and return the text response."""
        if not self._api_key:
            return "VLM disabled: DASHSCOPE_API_KEY not set."

        prompt = prompt or "Describe what you see on this screen in detail."
        content: list[dict[str, Any]] = []
        if screenshot_path:
            content.append({"image": f"file://{os.path.abspath(screenshot_path)}"})
        content.append({"text": prompt})

        return self._call(content)

    def locate_element(
        self,
        screenshot_path: str,
        target_description: str,
    ) -> tuple[int, int, int, int] | None:
        """Ask VLM to locate a UI element and return its bbox (x1, y1, x2, y2)."""
        if not self._api_key:
            return None

        size_hint = _image_size_hint(screenshot_path)
        prompt = (
            f"在这张截图中找到以下 UI 元素：'{target_description}'。\n"
            f"{size_hint}"
            f"请返回它的边界框坐标，格式为四个整数：x1 y1 x2 y2，"
            f"分别代表左上角和右下角的像素坐标。\n"
            f"只输出四个数字，用空格分隔，不要输出其他内容。"
        )
        content = [
            {"image": f"file://{os.path.abspath(screenshot_path)}"},
            {"text": prompt},
        ]
        response = self._call(content)
        return _parse_bbox(response)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call(self, content: list[dict[str, Any]]) -> str:
        try:
            from dashscope import MultiModalConversation
        except ImportError:
            return "VLM disabled: dashscope package not installed."

        messages = [{"role": "user", "content": content}]
        try:
            response = MultiModalConversation.call(
                model=self._model,
                messages=messages,
                api_key=self._api_key,
            )
        except Exception:
            logger.exception("DashScope API call failed")
            return "VLM error: API call failed."

        if response.status_code != 200:
            return f"VLM error: {response.code} {response.message}"

        try:
            return response.output.choices[0].message.content[0]["text"]
        except (IndexError, KeyError, TypeError):
            return str(response.output)


def _parse_bbox(text: str) -> tuple[int, int, int, int] | None:
    """Parse four integers from VLM response text."""
    numbers = re.findall(r"\d+", text)
    if len(numbers) >= 4:
        return (int(numbers[0]), int(numbers[1]), int(numbers[2]), int(numbers[3]))
    return None


def _image_size_hint(screenshot_path: str) -> str:
    try:
        from PIL import Image

        with Image.open(screenshot_path) as image:
            return f"截图原始分辨率是 {image.width}x{image.height}，请使用这个原始像素坐标系。\n"
    except Exception:
        return ""


def _load_model_config() -> ModelConfig | None:
    try:
        return ModelConfig.from_yaml()
    except Exception:
        logger.exception("Failed to load model config; falling back to environment-only VLM config")
        return None
