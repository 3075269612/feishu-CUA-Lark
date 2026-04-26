from __future__ import annotations


BBox = tuple[float, float, float, float]


def bbox_center(bbox: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def normalize_point(x: float, y: float, width: float, height: float) -> tuple[float, float]:
    return (x / width, y / height)


def denormalize_point(nx: float, ny: float, width: float, height: float) -> tuple[float, float]:
    return (nx * width, ny * height)


def scale_point(
    point: tuple[float, float],
    base_resolution: tuple[float, float],
    actual_resolution: tuple[float, float],
) -> tuple[float, float]:
    base_width, base_height = base_resolution
    actual_width, actual_height = actual_resolution
    return (point[0] * actual_width / base_width, point[1] * actual_height / base_height)


def compute_scale(
    base_resolution: tuple[float, float],
    actual_resolution: tuple[float, float],
) -> tuple[float, float]:
    base_width, base_height = base_resolution
    actual_width, actual_height = actual_resolution
    return (actual_width / base_width, actual_height / base_height)


def ensure_point_in_bounds(point: tuple[float, float], screen_size: tuple[float, float]) -> tuple[int, int]:
    x, y = point
    width, height = screen_size
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError(f"point_out_of_bounds:{point} screen={screen_size}")
    return int(round(x)), int(round(y))


def iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return 0.0 if union == 0 else intersection / union
