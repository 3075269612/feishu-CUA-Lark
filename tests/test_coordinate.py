from cua_lark.grounding.coordinate import bbox_center, denormalize_point, iou, normalize_point


def test_bbox_center() -> None:
    assert bbox_center((10, 20, 30, 60)) == (20, 40)


def test_coordinate_normalization_roundtrip() -> None:
    normalized = normalize_point(720, 450, 1440, 900)
    assert normalized == (0.5, 0.5)
    assert denormalize_point(*normalized, width=1440, height=900) == (720, 450)


def test_iou_for_overlapping_boxes() -> None:
    assert round(iou((0, 0, 10, 10), (5, 5, 15, 15)), 4) == 0.1429
