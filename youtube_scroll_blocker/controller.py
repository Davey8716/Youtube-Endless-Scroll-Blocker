from __future__ import annotations

from typing import Protocol

from .browser_detection import DetectionResult
from .geometry import (
    Rect,
    comments_overlay_rect_for_monitor,
    overlay_rect_for_monitor,
    watch_overlay_rect_for_monitor,
)
from .url_rules import OverlayMode


class OverlayView(Protocol):
    def show_at(self, rect: Rect, owner_hwnd: int) -> bool: ...

    def hide_overlay(self) -> None: ...


class OverlayController:
    def __init__(self, overlay: OverlayView, comments_overlay: OverlayView) -> None:
        self._overlay = overlay
        self._comments_overlay = comments_overlay
        self.enabled = True
        self.menu_open = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hide()

    def set_menu_open(self, open_: bool) -> None:
        self.menu_open = open_
        if open_:
            self.hide()

    def handle_detection(self, result: DetectionResult) -> None:
        if (
            not self.enabled
            or self.menu_open
            or not result.should_show
            or result.monitor_rect is None
            or result.browser_hwnd is None
        ):
            self.hide()
            return
        if result.mode is OverlayMode.WATCH:
            rect = watch_overlay_rect_for_monitor(result.monitor_rect)
            if result.player_visible is False:
                comments_rect = comments_overlay_rect_for_monitor(result.monitor_rect)
                self._comments_overlay.show_at(comments_rect, result.browser_hwnd)
            else:
                self._comments_overlay.hide_overlay()
        else:
            rect = overlay_rect_for_monitor(result.monitor_rect)
            self._comments_overlay.hide_overlay()
        self._overlay.show_at(rect, result.browser_hwnd)

    def hide(self) -> None:
        self._overlay.hide_overlay()
        self._comments_overlay.hide_overlay()
