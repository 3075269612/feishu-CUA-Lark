"""Accessibility Tree extraction for UI automation.

Extracts UI element information from Windows applications using UI Automation API.
Provides structured element data (name, role, bbox, state) to enhance visual grounding.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AccessibilityExtractor:
    """Extract UI elements from Windows applications via UI Automation."""

    def __init__(self) -> None:
        self._uia = None
        self._initialized = False

    def _initialize(self) -> bool:
        """Lazy initialization of UI Automation."""
        if self._initialized:
            return True

        try:
            import comtypes.client

            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen.UIAutomationClient import (
                CUIAutomation,
                IUIAutomation,
                TreeScope_Descendants,
            )

            self._uia: IUIAutomation = comtypes.client.CreateObject(
                CUIAutomation, interface=IUIAutomation
            )
            self._TreeScope_Descendants = TreeScope_Descendants
            self._initialized = True
            return True
        except Exception:
            logger.exception("Failed to initialize UI Automation")
            return False

    def extract_elements(
        self,
        window_title: str | None = None,
        hwnd: int | None = None,
        max_depth: int = 10,
        include_invisible: bool = False,
    ) -> list[dict[str, Any]]:
        """Extract UI elements from a window.

        Args:
            window_title: Window title to search for (partial match).
            hwnd: Window handle. If provided, takes precedence over window_title.
            max_depth: Maximum tree depth to traverse.
            include_invisible: Whether to include invisible elements.

        Returns:
            List of element dictionaries with keys:
            - name: Element name/label
            - role: Control type (button, text_area, etc.)
            - bbox: [left, top, right, bottom] in screen coordinates
            - enabled: Whether element is enabled
            - visible: Whether element is visible
            - control_type: Raw control type ID
            - automation_id: Automation ID if available
        """
        if not self._initialize():
            logger.warning("UI Automation not available, returning empty list")
            return []

        if hwnd is None and window_title is not None:
            hwnd = self._find_window_hwnd(window_title)

        if hwnd is None:
            logger.warning("No window found, cannot extract accessibility tree")
            return []

        try:
            root_element = self._uia.ElementFromHandle(hwnd)
            if root_element is None:
                logger.warning(f"Could not get UI element for hwnd={hwnd}")
                return []

            elements: list[dict[str, Any]] = []
            self._traverse_element(
                root_element,
                elements,
                depth=0,
                max_depth=max_depth,
                include_invisible=include_invisible,
            )
            logger.info(f"Extracted {len(elements)} accessibility elements from hwnd={hwnd}")
            return elements
        except Exception:
            logger.exception(f"Failed to extract accessibility tree from hwnd={hwnd}")
            return []

    def _find_window_hwnd(self, window_title: str) -> int | None:
        """Find window handle by title."""
        try:
            import win32gui

            result: list[int] = []

            def _enum_callback(hwnd: int, _: Any) -> None:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                text = win32gui.GetWindowText(hwnd)
                if window_title.lower() in text.lower():
                    result.append(hwnd)

            win32gui.EnumWindows(_enum_callback, None)
            return result[0] if result else None
        except Exception:
            logger.exception(f"Failed to find window with title '{window_title}'")
            return None

    def _traverse_element(
        self,
        element: Any,
        result: list[dict[str, Any]],
        depth: int,
        max_depth: int,
        include_invisible: bool,
    ) -> None:
        """Recursively traverse UI element tree."""
        if depth > max_depth:
            return

        try:
            # Extract element properties
            elem_data = self._extract_element_data(element)

            # Skip invisible elements if requested
            if not include_invisible and not elem_data.get("visible", False):
                return

            # Skip elements without valid bounding box
            bbox = elem_data.get("bbox")
            if not bbox or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                return

            result.append(elem_data)

            # Traverse children
            try:
                condition = self._uia.CreateTrueCondition()
                children = element.FindAll(self._TreeScope_Descendants, condition)
                if children:
                    for i in range(children.Length):
                        child = children.GetElement(i)
                        if child:
                            self._traverse_element(
                                child,
                                result,
                                depth + 1,
                                max_depth,
                                include_invisible,
                            )
            except Exception:
                pass  # Some elements don't support children

        except Exception:
            logger.debug(f"Failed to process element at depth {depth}", exc_info=True)

    def _extract_element_data(self, element: Any) -> dict[str, Any]:
        """Extract properties from a single UI element."""
        data: dict[str, Any] = {
            "name": "",
            "role": "unknown",
            "bbox": [0, 0, 0, 0],
            "enabled": False,
            "visible": False,
            "control_type": 0,
            "automation_id": "",
        }

        try:
            # Name
            try:
                data["name"] = element.CurrentName or ""
            except Exception:
                pass

            # Control type
            try:
                control_type = element.CurrentControlType
                data["control_type"] = control_type
                data["role"] = self._control_type_to_role(control_type)
            except Exception:
                pass

            # Bounding rectangle
            try:
                rect = element.CurrentBoundingRectangle
                data["bbox"] = [
                    int(rect.left),
                    int(rect.top),
                    int(rect.right),
                    int(rect.bottom),
                ]
            except Exception:
                pass

            # Enabled state
            try:
                data["enabled"] = bool(element.CurrentIsEnabled)
            except Exception:
                pass

            # Visible state (offscreen check)
            try:
                data["visible"] = not bool(element.CurrentIsOffscreen)
            except Exception:
                pass

            # Automation ID
            try:
                data["automation_id"] = element.CurrentAutomationId or ""
            except Exception:
                pass

        except Exception:
            logger.debug("Failed to extract some element properties", exc_info=True)

        return data

    def _control_type_to_role(self, control_type: int) -> str:
        """Map UI Automation control type ID to semantic role name."""
        # UI Automation control type constants
        # Reference: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-controltype-ids
        control_type_map = {
            50000: "button",
            50001: "calendar",
            50002: "checkbox",
            50003: "combobox",
            50004: "edit",  # text input
            50005: "hyperlink",
            50006: "image",
            50007: "list_item",
            50008: "list",
            50009: "menu",
            50010: "menu_bar",
            50011: "menu_item",
            50012: "progress_bar",
            50013: "radio_button",
            50014: "scroll_bar",
            50015: "slider",
            50016: "spinner",
            50017: "status_bar",
            50018: "tab",
            50019: "tab_item",
            50020: "text",
            50021: "toolbar",
            50022: "tooltip",
            50023: "tree",
            50024: "tree_item",
            50025: "custom",
            50026: "group",
            50027: "thumb",
            50028: "data_grid",
            50029: "data_item",
            50030: "document",
            50031: "split_button",
            50032: "window",
            50033: "pane",
            50034: "header",
            50035: "header_item",
            50036: "table",
            50037: "title_bar",
            50038: "separator",
        }
        return control_type_map.get(control_type, f"unknown_{control_type}")


class MockAccessibilityExtractor:
    """Mock extractor for testing without UI Automation."""

    def extract_elements(
        self,
        window_title: str | None = None,
        hwnd: int | None = None,
        max_depth: int = 10,
        include_invisible: bool = False,
    ) -> list[dict[str, Any]]:
        """Return empty list for mock mode."""
        return []


# Legacy compatibility
class AccessibilityClient:
    def snapshot(self) -> list[dict]:
        return []
