from __future__ import annotations

from cua_lark.grounding.coordinate import bbox_center, iou
from cua_lark.grounding.vlm_grounder import VlmGrounder

BBox = tuple[float, float, float, float]


class HybridGrounder:
    def __init__(self, vlm_grounder: VlmGrounder | None = None) -> None:
        self.vlm_grounder = vlm_grounder or VlmGrounder()
        self.last_metadata: dict = {}

    def choose_bbox(
        self,
        visual_bbox: BBox,
        candidates: list[dict],
        min_iou: float = 0.3,
    ) -> BBox:
        for candidate in candidates:
            bbox = candidate.get("bbox")
            if bbox and iou(visual_bbox, tuple(bbox)) >= min_iou:
                return tuple(bbox)
        return visual_bbox

    def center(self, bbox: BBox) -> tuple[float, float]:
        return bbox_center(bbox)

    def locate_target(
        self,
        target: str,
        screenshot_path: str | None,
        ocr_candidates: list[dict],
        accessibility_candidates: list[dict] | None = None,
        min_iou: float = 0.3,
        min_semantic_score: float = 0.5,
    ) -> tuple[int, int] | None:
        """Locate target using hybrid approach: VLM + OCR + Accessibility Tree.

        Priority order:
        1. VLM bbox + Accessibility Tree match (semantic + IoU)
        2. VLM bbox + OCR match (text + IoU)
        3. VLM bbox only (fallback)

        Args:
            target: Target description (e.g., "message input box")
            screenshot_path: Path to screenshot
            ocr_candidates: OCR text candidates with bbox
            accessibility_candidates: Accessibility Tree elements with name, role, bbox
            min_iou: Minimum IoU threshold for bbox matching
            min_semantic_score: Minimum semantic similarity for accessibility matching

        Returns:
            (x, y) point in screenshot coordinates, or None if not found
        """
        self.last_metadata = {"target": target, "screenshot_path": screenshot_path}

        # Step 1: Get VLM bbox
        visual_bbox = self.vlm_grounder.locate_bbox(target, screenshot_path)
        if visual_bbox is None:
            self.last_metadata["reason"] = "vlm_bbox_missing"
            return None

        # Step 2: Calibrate VLM bbox using OCR
        calibrated_bbox = self._calibrate_visual_bbox(target, visual_bbox, screenshot_path, ocr_candidates)

        # Step 3: Try Accessibility Tree match first (highest priority)
        if accessibility_candidates:
            accessibility_match = self._match_accessibility_candidate(
                target, calibrated_bbox, accessibility_candidates, min_iou, min_semantic_score
            )
            if accessibility_match is not None:
                final_bbox = accessibility_match["bbox"]
                x, y = self.center(tuple(final_bbox))
                self.last_metadata.update(
                    {
                        "raw_vlm_bbox": list(visual_bbox),
                        "calibrated_vlm_bbox": list(calibrated_bbox),
                        "final_bbox": list(final_bbox),
                        "screenshot_point": [int(x), int(y)],
                        "coordinate_source": "accessibility_tree",
                        "accessibility_match": {
                            "name": accessibility_match.get("name"),
                            "role": accessibility_match.get("role"),
                            "iou": accessibility_match.get("iou"),
                            "semantic_score": accessibility_match.get("semantic_score"),
                        },
                    }
                )
                return int(x), int(y)

        # Step 4: Fallback to OCR match
        final_bbox = self.choose_bbox(calibrated_bbox, ocr_candidates, min_iou=min_iou)
        x, y = self.center(final_bbox)
        coordinate_source = "ocr_match" if final_bbox != calibrated_bbox else "vlm_only"
        self.last_metadata.update(
            {
                "raw_vlm_bbox": list(visual_bbox),
                "calibrated_vlm_bbox": list(calibrated_bbox),
                "final_bbox": list(final_bbox),
                "screenshot_point": [int(x), int(y)],
                "coordinate_source": coordinate_source,
            }
        )
        return int(x), int(y)

    def _calibrate_visual_bbox(
        self,
        target: str,
        visual_bbox: BBox,
        screenshot_path: str | None,
        ocr_candidates: list[dict],
    ) -> BBox:
        image_size = _image_size(screenshot_path)
        if image_size is None:
            return visual_bbox

        variants = _scaled_bbox_variants(visual_bbox, image_size)
        best_bbox = variants[0][1]
        best_score = -1.0
        target_tokens = _target_tokens(target)

        for label, bbox in variants:
            score = _ocr_alignment_score(bbox, ocr_candidates, target_tokens)
            if score > best_score:
                best_score = score
                best_bbox = bbox
                self.last_metadata["vlm_coordinate_scale"] = label

        if best_score <= 0:
            best_bbox = _default_scaled_bbox(visual_bbox, image_size)
            self.last_metadata["vlm_coordinate_scale"] = "default_high_dpi" if best_bbox != visual_bbox else "native"

        geometry_bbox = _target_geometry_bbox(target, best_bbox, image_size)
        if geometry_bbox is not None:
            best_bbox = geometry_bbox
            self.last_metadata["vlm_coordinate_scale"] = "geometry_message_input"

        return _clamp_bbox(best_bbox, image_size)

    def _match_accessibility_candidate(
        self,
        target: str,
        vlm_bbox: BBox,
        accessibility_candidates: list[dict],
        min_iou: float = 0.3,
        min_semantic_score: float = 0.5,
    ) -> dict | None:
        """Match VLM bbox with Accessibility Tree candidates using IoU + semantic similarity.

        Args:
            target: Target description
            vlm_bbox: VLM-detected bounding box
            accessibility_candidates: List of accessibility elements
            min_iou: Minimum IoU threshold
            min_semantic_score: Minimum semantic similarity threshold

        Returns:
            Best matching accessibility element with added 'iou' and 'semantic_score' fields,
            or None if no good match found.
        """
        best_match: dict | None = None
        best_combined_score = 0.0

        for candidate in accessibility_candidates:
            candidate_bbox = candidate.get("bbox")
            if not candidate_bbox or len(candidate_bbox) != 4:
                continue

            # Calculate IoU
            overlap = iou(vlm_bbox, tuple(candidate_bbox))
            if overlap < min_iou:
                continue

            # Calculate semantic similarity
            semantic_score = self._semantic_similarity(target, candidate)
            if semantic_score < min_semantic_score:
                continue

            # Combined score: weighted average (IoU 40%, semantic 60%)
            combined_score = 0.4 * overlap + 0.6 * semantic_score

            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_match = {
                    **candidate,
                    "iou": overlap,
                    "semantic_score": semantic_score,
                    "combined_score": combined_score,
                }

        return best_match

    def _semantic_similarity(self, target: str, accessibility_element: dict) -> float:
        """Calculate semantic similarity between target description and accessibility element.

        Args:
            target: Target description (e.g., "message input box")
            accessibility_element: Accessibility element with 'name', 'role', 'automation_id'

        Returns:
            Similarity score between 0.0 and 1.0
        """
        target_lower = target.lower()
        name = str(accessibility_element.get("name", "")).lower()
        role = str(accessibility_element.get("role", "")).lower()
        automation_id = str(accessibility_element.get("automation_id", "")).lower()

        score = 0.0

        # Role matching (high weight)
        role_keywords = {
            "button": ["button", "按钮", "btn"],
            "edit": ["input", "edit", "text", "输入框", "编辑框"],
            "text": ["text", "label", "文本"],
            "list_item": ["item", "list", "列表", "项"],
            "menu_item": ["menu", "菜单"],
            "checkbox": ["check", "复选"],
            "combobox": ["combo", "dropdown", "下拉"],
        }

        for role_key, keywords in role_keywords.items():
            if role == role_key or role_key in role:
                if any(kw in target_lower for kw in keywords):
                    score += 0.4
                    break

        # Name matching (medium weight)
        target_tokens = set(_target_tokens(target))
        name_tokens = set(name.replace("_", " ").replace("-", " ").split())

        if target_tokens and name_tokens:
            common_tokens = target_tokens & name_tokens
            if common_tokens:
                score += 0.3 * (len(common_tokens) / max(len(target_tokens), len(name_tokens)))

        # Exact substring match in name (high weight)
        if name and any(token in name for token in target_tokens if len(token) >= 3):
            score += 0.3

        # Automation ID matching (low weight)
        if automation_id and any(token in automation_id for token in target_tokens if len(token) >= 3):
            score += 0.1

        # Special case: message input
        if "input" in target_lower or "输入" in target_lower:
            if role in ("edit", "text") and ("message" in name or "消息" in name or "send" in name or "发送" in name):
                score = max(score, 0.9)

        # Special case: message module / sidebar button
        if "message" in target_lower and "module" in target_lower:
            if role == "button" and ("message" in name or "消息" in name):
                score = max(score, 0.9)

        return min(1.0, score)


def _image_size(screenshot_path: str | None) -> tuple[int, int] | None:
    if not screenshot_path:
        return None
    try:
        from PIL import Image

        with Image.open(screenshot_path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return None


def _scaled_bbox_variants(bbox: BBox, image_size: tuple[int, int]) -> list[tuple[str, BBox]]:
    width, height = image_size
    candidates = [("native", 1.0, 1.0)]
    if width >= 1800 or height >= 1200:
        candidates.extend(
            [
                ("2x", 2.0, 2.0),
                ("logical_1600x900", width / 1600.0, height / 900.0),
                ("logical_1600x1000", width / 1600.0, height / 1000.0),
            ]
        )

    variants: list[tuple[str, BBox]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for label, sx, sy in candidates:
        scaled = _clamp_bbox((bbox[0] * sx, bbox[1] * sy, bbox[2] * sx, bbox[3] * sy), image_size)
        key = tuple(int(round(v)) for v in scaled)
        if key not in seen:
            seen.add(key)
            variants.append((label, scaled))
    return variants


def _default_scaled_bbox(bbox: BBox, image_size: tuple[int, int]) -> BBox:
    width, height = image_size
    x1, y1, x2, y2 = bbox

    # For high-DPI screens, VLM sometimes returns coordinates in logical resolution (1600x1000)
    # that need to be scaled up to physical resolution (3200x2000).
    # Heuristic: if all coordinates fit within 1600x1000, assume logical coordinates.
    # If any coordinate exceeds these bounds, assume physical coordinates.
    if (width >= 1800 or height >= 1200) and x2 <= 1600 and y2 <= 1000:
        # Scale from logical 1600x1000 to physical resolution
        return _clamp_bbox((bbox[0] * (width / 1600.0), bbox[1] * (height / 1000.0), bbox[2] * (width / 1600.0), bbox[3] * (height / 1000.0)), image_size)
    return bbox


def _ocr_alignment_score(bbox: BBox, candidates: list[dict], target_tokens: list[str]) -> float:
    best = 0.0
    for candidate in candidates:
        candidate_bbox = candidate.get("bbox")
        if not candidate_bbox:
            continue
        overlap = iou(bbox, tuple(candidate_bbox))
        if overlap <= 0:
            continue
        text = str(candidate.get("text", "")).lower()
        text_bonus = 1.0 if any(token and token in text for token in target_tokens) else 0.0
        if target_tokens and text_bonus <= 0 and overlap < 0.5:
            continue
        best = max(best, overlap + text_bonus)
    return best


def _target_tokens(target: str) -> list[str]:
    lowered = target.lower()
    tokens = [part for part in lowered.replace("_", " ").replace("-", " ").split() if len(part) >= 2]
    if "cua" in lowered and "lark" in lowered:
        tokens.extend(["cua", "lark", "cua-lark-test"])
    if "search" in lowered:
        tokens.extend(["search", "搜索"])
    if "input" in lowered:
        tokens.extend(["发送", "send"])
    return tokens


def _clamp_bbox(bbox: BBox, image_size: tuple[int, int]) -> BBox:
    width, height = image_size
    x1, y1, x2, y2 = bbox
    return (
        max(0.0, min(float(width - 1), x1)),
        max(0.0, min(float(height - 1), y1)),
        max(0.0, min(float(width - 1), x2)),
        max(0.0, min(float(height - 1), y2)),
    )


def _target_geometry_bbox(target: str, bbox: BBox, image_size: tuple[int, int]) -> BBox | None:
    lowered = target.lower()
    if "input" not in lowered and "输入" not in lowered and "消息输入" not in lowered:
        return None
    width, height = image_size
    _, center_y = bbox_center(bbox)
    if center_y >= height * 0.70:
        return None
    return (
        width * 0.36,
        height * 0.89,
        width * 0.98,
        height * 0.985,
    )
