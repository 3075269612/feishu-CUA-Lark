from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def capture_screenshot(
    window_title: str | None = None,
    output_path: str | None = None,
) -> str | None:
    """Capture a screenshot, optionally cropped to a specific window.

    Returns the saved file path, or *None* on failure.
    """
    result = capture_screenshot_with_metadata(window_title=window_title, output_path=output_path)
    return result.get("path") if result else None


def capture_screenshot_with_metadata(
    window_title: str | None = None,
    output_path: str | None = None,
) -> dict | None:
    """Capture a screenshot and return path plus coordinate metadata."""
    if output_path is None:
        return None
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        import mss
        from PIL import Image
    except ImportError:
        logger.warning("mss or Pillow not installed – screenshot skipped")
        return None

    _enable_dpi_awareness()

    # Try window-level capture on Windows
    rect = _find_window_rect(window_title) if window_title else None

    try:
        with mss.mss() as sct:
            if rect:
                rect = _rect_to_mss_coordinates(rect, sct.monitors[0])
                left, top, right, bottom = rect
                monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
            else:
                monitor = sct.monitors[1]  # primary monitor fallback
            if monitor["width"] <= 0 or monitor["height"] <= 0:
                logger.warning("screenshot skipped due to empty monitor area: %s", monitor)
                return None
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(out)
        return {
            "path": str(out),
            "origin": [int(monitor["left"]), int(monitor["top"])],
            "screenshot_size": [int(monitor["width"]), int(monitor["height"])],
            "window_rect": [int(monitor["left"]), int(monitor["top"]), int(monitor["left"] + monitor["width"]), int(monitor["top"] + monitor["height"])],
            "coordinate_space": "physical_screen_pixels",
        }
    except Exception:
        logger.exception("screenshot capture failed")
        return None


def _enable_dpi_awareness() -> None:
    """Make Win32 window coordinates line up with physical screenshot pixels."""
    try:
        # Per-monitor v2, available on modern Windows. Ignore failures because
        # DPI awareness may already be fixed by the host process.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                logger.debug("could not set process DPI awareness", exc_info=True)


def _find_window_rect(title: str) -> tuple[int, int, int, int] | None:
    """Find a window by partial title match and return (left, top, right, bottom)."""
    try:
        import win32gui  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("pywin32 not available – falling back to full-screen capture")
        return None

    result: list[tuple[int, tuple[int, int, int, int]]] = []

    def _enum_cb(hwnd: int, _extra: object) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        wtext = win32gui.GetWindowText(hwnd)
        score = _window_title_match_score(title, wtext)
        if score is not None:
            rect = _extended_frame_bounds(hwnd) or win32gui.GetWindowRect(hwnd)
            if rect[2] - rect[0] > 100 and rect[3] - rect[1] > 100:
                result.append((score, rect))

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        logger.exception("window enumeration failed – falling back to full-screen capture")
        return None
    if not result:
        return None
    result.sort(key=lambda item: item[0])
    return result[0][1]


def _window_title_match_score(query: str, title: str) -> int | None:
    """Prefer exact app window titles over browser tabs or document titles."""
    q = query.strip().lower()
    t = title.strip().lower()
    if not q or not t or q not in t:
        return None
    if t == q:
        return 0
    if t.startswith(q):
        return 1
    return 2


def _extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return the visible window bounds when DWM can provide them."""
    rect = wintypes.RECT()

    try:
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_EXTENDED_FRAME_BOUNDS excludes the invisible resize border.
        result = dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(9),
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
    except Exception:
        return None
    if result != 0:
        return None
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _rect_to_mss_coordinates(
    rect: tuple[int, int, int, int],
    virtual_monitor: dict,
) -> tuple[int, int, int, int]:
    """Convert a Win32 rect to mss' physical-pixel coordinate space."""
    left, top, right, bottom = rect
    screen_w, screen_h = _system_metrics()
    monitor_w = int(virtual_monitor.get("width") or 0)
    monitor_h = int(virtual_monitor.get("height") or 0)

    if screen_w > 0 and screen_h > 0 and monitor_w > 0 and monitor_h > 0:
        scale_x = monitor_w / screen_w
        scale_y = monitor_h / screen_h
        if scale_x > 1.01 or scale_y > 1.01:
            left = round(left * scale_x)
            right = round(right * scale_x)
            top = round(top * scale_y)
            bottom = round(bottom * scale_y)

    mon_left = int(virtual_monitor.get("left") or 0)
    mon_top = int(virtual_monitor.get("top") or 0)
    mon_right = mon_left + monitor_w
    mon_bottom = mon_top + monitor_h
    return (
        max(mon_left, left),
        max(mon_top, top),
        min(mon_right, right),
        min(mon_bottom, bottom),
    )


def _system_metrics() -> tuple[int, int]:
    try:
        return (
            int(ctypes.windll.user32.GetSystemMetrics(0)),
            int(ctypes.windll.user32.GetSystemMetrics(1)),
        )
    except Exception:
        return (0, 0)
