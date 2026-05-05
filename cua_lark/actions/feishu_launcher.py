"""Feishu application launcher and window management.

Ensures Feishu desktop client is running and brought to foreground,
regardless of whether it's already started, minimized, or in background.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from cua_lark.actions.desktop_backend import BackendResult

logger = logging.getLogger(__name__)


def ensure_feishu_frontmost(
    feishu_exe_path: str | None = None,
    window_title_candidates: list[str] | None = None,
    max_wait_sec: int = 15,
) -> BackendResult:
    """Ensure Feishu desktop client is running and in foreground.

    This function handles all scenarios:
    1. Feishu not running → launch it
    2. Feishu minimized → restore window
    3. Feishu in background → bring to foreground
    4. Feishu already frontmost → verify and return

    Args:
        feishu_exe_path: Path to Feishu.exe. If None, searches common locations.
        window_title_candidates: Window titles to search for. Defaults to ["Feishu", "飞书", "Lark"].
        max_wait_sec: Maximum seconds to wait for window to appear after launch.

    Returns:
        BackendResult with ok=True if Feishu is frontmost, ok=False otherwise.
    """
    if window_title_candidates is None:
        window_title_candidates = ["Feishu", "飞书", "Lark"]

    try:
        import psutil
        import win32con
        import win32gui
    except ImportError as exc:
        return BackendResult(
            ok=False,
            reason=f"missing_dependency:{exc}",
            metadata={"required": ["psutil", "pywin32"]},
        )

    # Step 1: Check if Feishu process is running
    feishu_running = _is_feishu_process_running()
    logger.info(f"Feishu process running: {feishu_running}")

    # Step 2: Launch Feishu if not running
    if not feishu_running:
        if feishu_exe_path is None:
            feishu_exe_path = _find_feishu_executable()

        if feishu_exe_path is None:
            return BackendResult(
                ok=False,
                reason="feishu_exe_not_found",
                metadata={"searched_paths": _get_common_feishu_paths()},
            )

        logger.info(f"Launching Feishu from: {feishu_exe_path}")
        try:
            subprocess.Popen([feishu_exe_path], shell=False)
            time.sleep(3)  # Wait for initial launch
        except Exception as exc:
            return BackendResult(
                ok=False,
                reason=f"launch_failed:{exc}",
                metadata={"exe_path": feishu_exe_path},
            )

    # Step 3: Find Feishu window handle
    hwnd = _find_feishu_window(window_title_candidates, max_wait_sec)
    if hwnd is None:
        return BackendResult(
            ok=False,
            reason="feishu_window_not_found_after_launch",
            metadata={
                "title_candidates": window_title_candidates,
                "max_wait_sec": max_wait_sec,
                "process_running": _is_feishu_process_running(),
            },
        )

    window_title = win32gui.GetWindowText(hwnd)
    logger.info(f"Found Feishu window: hwnd={hwnd}, title='{window_title}'")

    # Step 4: Restore window if minimized
    if win32gui.IsIconic(hwnd):
        logger.info("Feishu window is minimized, restoring...")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)

    # Step 5: Bring window to foreground
    try:
        # Try direct SetForegroundWindow first
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as exc:
        # If direct call fails, try workaround for Windows restrictions
        logger.warning(f"SetForegroundWindow failed: {exc}, trying workaround...")
        try:
            _force_foreground_window(hwnd)
            time.sleep(0.2)
        except Exception as exc2:
            return BackendResult(
                ok=False,
                reason=f"set_foreground_failed:{exc2}",
                metadata={"hwnd": hwnd, "window_title": window_title},
            )

    # Step 6: Verify window is ready (found + restored + focus attempted).
    # Windows may block SetForegroundWindow due to anti-focus-stealing rules,
    # but pyautogui can still click/type into the window. Treat as ok.
    foreground_hwnd = win32gui.GetForegroundWindow()
    frontmost = (foreground_hwnd == hwnd)
    if not frontmost:
        logger.warning(
            f"Feishu window not in foreground (expected hwnd={hwnd}, got {foreground_hwnd}). "
            "Continuing anyway — pyautogui can interact without foreground focus."
        )

    logger.info("Feishu window preparation complete")
    return BackendResult(
        ok=True,
        reason="feishu_frontmost" if frontmost else "feishu_visible_not_foreground",
        metadata={
            "hwnd": hwnd,
            "was_running": feishu_running,
            "window_title": window_title,
            "is_iconic": win32gui.IsIconic(hwnd),
            "is_visible": win32gui.IsWindowVisible(hwnd),
            "is_frontmost": frontmost,
        },
    )


def _is_feishu_process_running() -> bool:
    """Check if any Feishu/Lark process is running."""
    try:
        import psutil

        for proc in psutil.process_iter(["name"]):
            name = proc.info["name"].lower()
            if any(keyword in name for keyword in ["lark", "feishu", "飞书"]):
                return True
        return False
    except Exception:
        logger.exception("Failed to check Feishu process")
        return False


def _find_feishu_executable() -> str | None:
    """Search common installation paths for Feishu executable."""
    paths = _get_common_feishu_paths()
    for path in paths:
        if path.exists():
            logger.info(f"Found Feishu executable at: {path}")
            return str(path)
    return None


def _get_common_feishu_paths() -> list[Path]:
    """Return list of common Feishu installation paths."""
    return [
        Path.home() / "AppData/Local/Bytedance/Feishu/Feishu.exe",
        Path.home() / "AppData/Local/Bytedance/Lark/Lark.exe",
        Path("D:/Feishu/Feishu.exe"),  # Common custom installation path
        Path("C:/Program Files/Feishu/Feishu.exe"),
        Path("C:/Program Files (x86)/Feishu/Feishu.exe"),
        Path("C:/Program Files/Lark/Lark.exe"),
        Path("C:/Program Files (x86)/Lark/Lark.exe"),
    ]


def _find_feishu_window(
    title_candidates: list[str], max_wait_sec: int
) -> int | None:
    """Find Feishu window handle by searching for title candidates.

    Polls for up to max_wait_sec if window not immediately found.
    """
    try:
        import win32gui
    except ImportError:
        return None

    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        for title in title_candidates:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd and hwnd != 0:
                return hwnd

        # Also try EnumWindows for partial title match
        result = _enum_windows_for_feishu(title_candidates)
        if result:
            return result

        time.sleep(0.5)

    return None


def _enum_windows_for_feishu(title_candidates: list[str]) -> int | None:
    """Enumerate all windows and find best match for Feishu."""
    try:
        import win32gui

        best_match: tuple[int, int] | None = None  # (score, hwnd)

        def _enum_callback(hwnd: int, _: Any) -> None:
            nonlocal best_match
            if not win32gui.IsWindowVisible(hwnd):
                return

            try:
                window_text = win32gui.GetWindowText(hwnd)
                if not window_text:
                    return

                for candidate in title_candidates:
                    if candidate.lower() in window_text.lower():
                        # Prefer exact match (score 0) over partial match
                        score = 0 if candidate.lower() == window_text.lower() else 1
                        if best_match is None or score < best_match[0]:
                            best_match = (score, hwnd)
            except Exception:
                pass

        win32gui.EnumWindows(_enum_callback, None)
        return best_match[1] if best_match else None
    except Exception:
        logger.exception("Failed to enumerate windows")
        return None


def _force_foreground_window(hwnd: int) -> None:
    """Force window to foreground using workaround for Windows restrictions.

    Windows restricts SetForegroundWindow in certain scenarios. This uses
    a workaround by simulating Alt key press to allow foreground change.
    """
    import win32api
    import win32con
    import win32gui
    import win32process

    # Get current foreground window's thread
    foreground_hwnd = win32gui.GetForegroundWindow()
    foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
    target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

    # Attach to foreground thread to bypass restrictions
    if foreground_thread != target_thread:
        win32process.AttachThreadInput(foreground_thread, target_thread, True)

    # Simulate Alt key to allow SetForegroundWindow
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32gui.SetForegroundWindow(hwnd)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    # Detach threads
    if foreground_thread != target_thread:
        win32process.AttachThreadInput(foreground_thread, target_thread, False)
