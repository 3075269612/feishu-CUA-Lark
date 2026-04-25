from __future__ import annotations

from cua_lark.grounding.coordinate import bbox_center, iou


class HybridGrounder:
    def choose_bbox(
        self,
        visual_bbox: tuple[float, float, float, float],
        candidates: list[dict],
        min_iou: float = 0.3,
    ) -> tuple[float, float, float, float]:
        for candidate in candidates:
            bbox = candidate.get("bbox")
            if bbox and iou(visual_bbox, tuple(bbox)) >= min_iou:
                return tuple(bbox)
        return visual_bbox

    def center(self, bbox: tuple[float, float, float, float]) -> tuple[float, float]:
        return bbox_center(bbox)
