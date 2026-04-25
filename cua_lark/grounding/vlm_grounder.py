from __future__ import annotations

from cua_lark.grounding.coordinate import bbox_center


class VlmGrounder:
    def locate(self, target: str, bbox: tuple[int, int, int, int] | None = None) -> tuple[int, int] | None:
        if bbox is None:
            return None
        x, y = bbox_center(bbox)
        return int(x), int(y)
