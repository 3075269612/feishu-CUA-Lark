from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OcrClient:
    """OCR client backed by RapidOCR (lazy-loaded)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._engine: Any = None

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise RuntimeError("rapidocr_onnxruntime not installed") from exc
            self._engine = RapidOCR()
        return self._engine

    def extract(self, screenshot_path: str | None) -> list[dict]:
        """Extract text from a screenshot.

        Returns list of {"text": str, "bbox": [x1, y1, x2, y2], "confidence": float}.
        """
        if screenshot_path is None:
            return []
        try:
            engine = self._get_engine()
        except RuntimeError:
            logger.warning("RapidOCR unavailable – returning empty OCR result")
            return []

        try:
            result, _ = engine(screenshot_path)
        except Exception:
            logger.exception("OCR extraction failed")
            return []

        if not result:
            return []

        return [
            {
                "text": item[1],
                "bbox": _polygon_to_xyxy(item[0]),
                "confidence": float(item[2]),
            }
            for item in result
        ]


def _polygon_to_xyxy(polygon: list) -> list[float]:
    """Convert RapidOCR 4-point polygon to axis-aligned [x1, y1, x2, y2]."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]
