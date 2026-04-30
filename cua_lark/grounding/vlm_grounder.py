from __future__ import annotations

from cua_lark.grounding.coordinate import bbox_center
from cua_lark.perception.vlm import VlmClient


class VlmGrounder:
    def __init__(self, vlm_client: VlmClient | None = None) -> None:
        self.vlm_client = vlm_client or VlmClient()

    def locate(
        self,
        target: str,
        bbox: tuple[int, int, int, int] | None = None,
        screenshot_path: str | None = None,
    ) -> tuple[int, int] | None:
        if bbox is None:
            bbox = self.locate_bbox(target, screenshot_path)
        if bbox is None:
            return None
        x, y = bbox_center(bbox)
        return int(x), int(y)

    def locate_bbox(
        self,
        target: str,
        screenshot_path: str | None = None,
    ) -> tuple[int, int, int, int] | None:
        if not screenshot_path or self.vlm_client is None:
            return None
        return self.vlm_client.locate_element(screenshot_path, target)
