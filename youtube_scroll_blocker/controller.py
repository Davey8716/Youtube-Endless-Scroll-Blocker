from __future__ import annotations

from typing import Protocol

from .browser_detection import DetectionResult
from .geometry import Rect, overlay_rect_for_monitor, watch_overlay_rect_for_monitor
from .url_rules import OverlayMode


class OverlayView(Protocol):
    def show_at(self, rect: Rect, owner_hwnd: int) -> bool: ...

    def hide_overlay(self) -> None: ...


class OverlayController:
    def __init__(self, overlay: OverlayView) -> None:
        self._overlay = overlay
        self.enabled = True
        self.menu_open = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self._overlay.hide_overlay()

    def set_menu_open(self, open_: bool) -> None:
        self.menu_open = open_
        if open_:
            self._overlay.hide_overlay()

    def handle_detection(self, result: DetectionResult) -> None:
        if (
            not self.enabled
            or self.menu_open
            or not result.should_show
            or result.monitor_rect is None
            or result.browser_hwnd is None
        ):
            self._overlay.hide_overlay()
            return
        if result.mode is OverlayMode.WATCH:
            rect = watch_overlay_rect_for_monitor(result.monitor_rect)
        else:
            rect = overlay_rect_for_monitor(result.monitor_rect)
        self._overlay.show_at(rect, result.browser_hwnd)

    def hide(self) -> None:
        self._overlay.hide_overlay()
