import pytest

from cua_lark.grounding.coordinate import (
    bbox_center,
    compute_scale,
    denormalize_point,
    ensure_point_in_bounds,
    iou,
    normalize_point,
    scale_point,
)


def test_bbox_center() -> None:
    assert bbox_center((10, 20, 30, 60)) == (20, 40)


def test_coordinate_normalization_roundtrip() -> None:
    normalized = normalize_point(720, 450, 1440, 900)
    assert normalized == (0.5, 0.5)
    assert denormalize_point(*normalized, width=1440, height=900) == (720, 450)


def test_iou_for_overlapping_boxes() -> None:
    assert round(iou((0, 0, 10, 10), (5, 5, 15, 15)), 4) == 0.1429


def test_coordinate_scaling_and_bounds() -> None:
    assert compute_scale((1440, 900), (2880, 1800)) == (2.0, 2.0)
    assert scale_point((100, 200), (1440, 900), (2880, 1800)) == (200, 400)
    assert ensure_point_in_bounds((200, 400), (2880, 1800)) == (200, 400)


def test_coordinate_bounds_reject_out_of_screen() -> None:
    with pytest.raises(ValueError, match="point_out_of_bounds"):
        ensure_point_in_bounds((1440, 900), (1440, 900))
