from cua_lark.grounding.hybrid_grounder import HybridGrounder
from cua_lark.grounding.vlm_grounder import VlmGrounder
from cua_lark.main import _screenshot_point_to_screen


class FakeVlm:
    def locate_element(self, screenshot_path: str, target_description: str):
        return (10, 10, 50, 50)


def test_vlm_grounder_locates_center_from_screenshot() -> None:
    grounder = VlmGrounder(vlm_client=FakeVlm())

    assert grounder.locate("button", screenshot_path="screen.png") == (30, 30)


def test_hybrid_grounder_snaps_to_ocr_candidate_by_iou() -> None:
    grounder = HybridGrounder(VlmGrounder(vlm_client=FakeVlm()))
    candidates = [{"text": "Send", "bbox": [12, 12, 52, 52], "confidence": 0.9}]

    assert grounder.locate_target("Send", "screen.png", candidates) == (32, 32)


def test_hybrid_grounder_prefers_accessibility_match_over_ocr() -> None:
    grounder = HybridGrounder(VlmGrounder(vlm_client=FakeVlm()))
    ocr_candidates = [{"text": "Send", "bbox": [12, 12, 52, 52], "confidence": 0.9}]
    accessibility_candidates = [
        {
            "name": "Send message",
            "role": "button",
            "bbox": [16, 16, 56, 56],
            "enabled": True,
            "visible": True,
        }
    ]

    point = grounder.locate_target(
        "send button",
        "screen.png",
        ocr_candidates,
        accessibility_candidates=accessibility_candidates,
    )

    assert point == (36, 36)
    assert grounder.last_metadata["coordinate_source"] == "accessibility_tree"
    assert grounder.last_metadata["raw_vlm_bbox"] == [10, 10, 50, 50]
    assert grounder.last_metadata["final_bbox"] == [16, 16, 56, 56]
    assert grounder.last_metadata["screenshot_point"] == [36, 36]
    assert grounder.last_metadata["accessibility_match"]["role"] == "button"


def test_hybrid_grounder_rejects_accessibility_without_semantic_match() -> None:
    grounder = HybridGrounder(VlmGrounder(vlm_client=FakeVlm()))
    ocr_candidates = [{"text": "Send", "bbox": [12, 12, 52, 52], "confidence": 0.9}]
    accessibility_candidates = [
        {
            "name": "Calendar",
            "role": "button",
            "bbox": [20, 20, 80, 80],
            "enabled": True,
            "visible": True,
        }
    ]

    assert (
        grounder.locate_target(
            "send button",
            "screen.png",
            ocr_candidates,
            accessibility_candidates=accessibility_candidates,
        )
        == (32, 32)
    )
    assert grounder.last_metadata["coordinate_source"] == "ocr_match"
    assert "accessibility_match" not in grounder.last_metadata


def test_hybrid_grounder_scales_vlm_bbox_to_ocr_candidate_on_high_dpi_image(tmp_path) -> None:
    from PIL import Image

    image_path = tmp_path / "screen.png"
    Image.new("RGB", (3200, 1904), "white").save(image_path)
    grounder = HybridGrounder(VlmGrounder(vlm_client=FakeVlm()))
    candidates = [{"text": "Send", "bbox": [24, 24, 104, 104], "confidence": 0.9}]

    assert grounder.locate_target("Send", str(image_path), candidates) == (64, 64)
    assert grounder.last_metadata["vlm_coordinate_scale"] in {"2x", "logical_1600x900"}


def test_screenshot_point_to_screen_adds_capture_origin() -> None:
    assert _screenshot_point_to_screen((100, 200), {"origin": [300, 400]}) == (400, 600)


def test_hybrid_grounder_uses_bottom_geometry_for_message_input_when_vlm_is_too_high(tmp_path) -> None:
    from PIL import Image

    image_path = tmp_path / "screen.png"
    Image.new("RGB", (3200, 1904), "white").save(image_path)
    grounder = HybridGrounder(VlmGrounder(vlm_client=FakeVlm()))

    point = grounder.locate_target("message_input", str(image_path), [])

    assert point == (2144, 1785)
    assert grounder.last_metadata["vlm_coordinate_scale"] == "geometry_message_input"
