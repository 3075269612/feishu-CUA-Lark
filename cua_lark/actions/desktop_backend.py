from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BackendResult:
    ok: bool
    reason: str = "ok"
    metadata: dict[str, Any] | None = None


class DryRunDesktopBackend:
    backend_name = "dry-run"

    def __init__(self, screen_size: tuple[int, int] = (1440, 900)) -> None:
        self._screen_size = screen_size
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def screen_size(self) -> tuple[int, int]:
        return self._screen_size

    def focus_window(self, title_candidates: list[str], assume_frontmost_window: bool = False) -> BackendResult:
        self.calls.append(("focus_window", {"title_candidates": title_candidates, "assume_frontmost_window": assume_frontmost_window}))
        return BackendResult(
            ok=True,
            reason="dry_run_focus_planned",
            metadata={
                "backend": self.backend_name,
                "assume_frontmost_window": assume_frontmost_window,
                "title_candidates": title_candidates,
                "planned_only": True,
            },
        )

    def screenshot(self, output_path: str | Path) -> BackendResult:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw

            image = Image.new("RGB", self._screen_size, "white")
            draw = ImageDraw.Draw(image)
            draw.text((20, 20), "CUA-Lark dry-run placeholder screenshot", fill="black")
            image.save(output)
        except Exception:
            output.write_bytes(b"")
        self.calls.append(("screenshot", {"output_path": str(output)}))
        return BackendResult(
            ok=True,
            reason="dry_run_placeholder_screenshot",
            metadata={
                "path": str(output),
                "screenshot_width": self._screen_size[0],
                "screenshot_height": self._screen_size[1],
                "backend": self.backend_name,
                "planned_only": True,
            },
        )

    def click(self, x: int, y: int, target: str) -> BackendResult:
        self.calls.append(("click", {"x": x, "y": y, "target": target}))
        return BackendResult(ok=True, reason="dry_run_click_planned", metadata={"x": x, "y": y, "target": target, "planned_only": True})

    def hotkey(self, *keys: str) -> BackendResult:
        self.calls.append(("hotkey", {"keys": keys}))
        return BackendResult(ok=True, reason="dry_run_hotkey_planned", metadata={"keys": list(keys), "planned_only": True})

    def press(self, key: str) -> BackendResult:
        self.calls.append(("press", {"key": key}))
        return BackendResult(ok=True, reason="dry_run_press_planned", metadata={"key": key, "planned_only": True})

    def paste_text(self, text: str) -> BackendResult:
        self.calls.append(("paste_text", {"text": text}))
        return BackendResult(ok=True, reason="dry_run_paste_planned", metadata={"text_length": len(text), "planned_only": True})


class PyAutoGuiBackend:
    backend_name = "pyautogui"

    def __init__(self) -> None:
        self._pyautogui = None
        self._pyperclip = None

    def _load_pyautogui(self):
        if self._pyautogui is None:
            try:
                import pyautogui
            except Exception as exc:
                raise RuntimeError(f"pyautogui_unavailable:{exc}") from exc
            self._pyautogui = pyautogui
        return self._pyautogui

    def _load_pyperclip(self):
        if self._pyperclip is None:
            try:
                import pyperclip
            except Exception as exc:
                raise RuntimeError(f"pyperclip_unavailable:{exc}") from exc
            self._pyperclip = pyperclip
        return self._pyperclip

    def screen_size(self) -> tuple[int, int]:
        pyautogui = self._load_pyautogui()
        size = pyautogui.size()
        return int(size.width), int(size.height)

    def focus_window(self, title_candidates: list[str], assume_frontmost_window: bool = False) -> BackendResult:
        if assume_frontmost_window:
            return BackendResult(
                ok=True,
                reason="assume_frontmost_window",
                metadata={"backend": self.backend_name, "assume_frontmost_window": True},
            )
        try:
            pyautogui = self._load_pyautogui()
        except RuntimeError as exc:
            return BackendResult(False, str(exc), {"backend": self.backend_name})

        for title in title_candidates:
            try:
                windows = pyautogui.getWindowsWithTitle(title)
            except Exception:
                windows = []
            for window in windows:
                try:
                    window.activate()
                    return BackendResult(
                        ok=True,
                        reason="window_focused",
                        metadata={"backend": self.backend_name, "matched_title": title, "window_title": getattr(window, "title", "")},
                    )
                except Exception as exc:
                    return BackendResult(False, f"window_focus_failed:{exc}", {"backend": self.backend_name, "matched_title": title})
        return BackendResult(False, "feishu_window_not_found", {"backend": self.backend_name, "title_candidates": title_candidates})

    def screenshot(self, output_path: str | Path) -> BackendResult:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            import mss
            from PIL import Image
        except Exception as exc:
            return BackendResult(False, f"screenshot_dependency_unavailable:{exc}", {"backend": self.backend_name})

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
                image.save(output)
            return BackendResult(
                ok=True,
                reason="screenshot_saved",
                metadata={
                    "path": str(output),
                    "screenshot_width": int(shot.size.width),
                    "screenshot_height": int(shot.size.height),
                    "backend": self.backend_name,
                },
            )
        except Exception as exc:
            return BackendResult(False, f"screenshot_failed:{exc}", {"backend": self.backend_name})

    def click(self, x: int, y: int, target: str) -> BackendResult:
        try:
            self._load_pyautogui().click(x, y)
            return BackendResult(True, "clicked", {"backend": self.backend_name, "x": x, "y": y, "target": target})
        except Exception as exc:
            return BackendResult(False, f"click_failed:{exc}", {"backend": self.backend_name, "x": x, "y": y, "target": target})

    def hotkey(self, *keys: str) -> BackendResult:
        try:
            self._load_pyautogui().hotkey(*keys)
            return BackendResult(True, "hotkey_pressed", {"backend": self.backend_name, "keys": list(keys)})
        except Exception as exc:
            return BackendResult(False, f"hotkey_failed:{exc}", {"backend": self.backend_name, "keys": list(keys)})

    def press(self, key: str) -> BackendResult:
        try:
            self._load_pyautogui().press(key)
            return BackendResult(True, "key_pressed", {"backend": self.backend_name, "key": key})
        except Exception as exc:
            return BackendResult(False, f"press_failed:{exc}", {"backend": self.backend_name, "key": key})

    def paste_text(self, text: str) -> BackendResult:
        try:
            self._load_pyperclip().copy(text)
            hotkey = self.hotkey("ctrl", "v")
            if not hotkey.ok:
                return hotkey
            return BackendResult(True, "text_pasted", {"backend": self.backend_name, "text_length": len(text)})
        except Exception as exc:
            return BackendResult(False, f"paste_failed:{exc}", {"backend": self.backend_name, "text_length": len(text)})
