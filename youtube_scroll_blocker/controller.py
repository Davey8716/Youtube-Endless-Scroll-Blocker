from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .browser_detection import DetectionResult
from .geometry import (
    Rect,
    comments_overlay_rect_for_monitor,
    is_portrait_monitor,
    overlay_rect_for_monitor,
    watch_overlay_rect_for_monitor,
)
from .url_rules import OverlayMode


class OverlayView(Protocol):
    def show_at(self, rect: Rect, owner_hwnd: int) -> bool: ...

    def hide_overlay(self) -> None: ...


@dataclass
class _OverlayPair:
    recommendations: OverlayView
    comments: OverlayView


class OverlayController:
    def __init__(
        self,
        overlay_or_factory: OverlayView | Callable[[], OverlayView],
        comments_overlay: OverlayView | None = None,
        *,
        feed_recommendations_enabled: bool = True,
        watch_recommendations_enabled: bool = True,
        comments_enabled: bool = True,
    ) -> None:
        self._overlay_factory: Callable[[], OverlayView] | None
        self._unassigned_pair: _OverlayPair | None
        if comments_overlay is None and callable(overlay_or_factory):
            self._overlay_factory = overlay_or_factory
            self._unassigned_pair = None
        elif comments_overlay is not None:
            self._overlay_factory = None
            self._unassigned_pair = _OverlayPair(overlay_or_factory, comments_overlay)  # type: ignore[arg-type]
        else:
            raise TypeError("An overlay factory or two overlay views are required")
        self._overlay_pairs: dict[int, _OverlayPair] = {}
        self.enabled = True
        self.feed_recommendations_enabled = feed_recommendations_enabled
        self.watch_recommendations_enabled = watch_recommendations_enabled
        self.comments_enabled = comments_enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hide()

    def set_feed_recommendations_enabled(self, enabled: bool) -> None:
        self.feed_recommendations_enabled = enabled
        if not enabled:
            self._hide_recommendations()

    def set_watch_recommendations_enabled(self, enabled: bool) -> None:
        self.watch_recommendations_enabled = enabled
        if not enabled:
            self._hide_recommendations()

    def set_comments_enabled(self, enabled: bool) -> None:
        self.comments_enabled = enabled
        if not enabled:
            for pair in self._all_pairs():
                pair.comments.hide_overlay()

    def handle_detection(self, result: DetectionResult) -> None:
        self.handle_detections((result,))

    def handle_detections(self, results: Iterable[DetectionResult]) -> None:
        eligible = {
            result.browser_hwnd: result
            for result in results
            if result.should_show
            and result.monitor_rect is not None
            and result.browser_hwnd is not None
        }
        self._remove_stale_pairs(set(eligible))
        if not eligible:
            self.hide()
            return
        if not self.enabled:
            self.hide()
            return
        for hwnd, result in eligible.items():
            self._render(self._pair_for(hwnd), result)

    def _render(self, pair: _OverlayPair, result: DetectionResult) -> None:
        assert result.monitor_rect is not None
        assert result.browser_hwnd is not None
        if result.mode is OverlayMode.WATCH:
            portrait = is_portrait_monitor(result.monitor_rect)
            regular_mode = (
                result.theatre_mode is False if portrait else result.theatre_mode is not True
            )
            rect = watch_overlay_rect_for_monitor(result.monitor_rect)
            if self.watch_recommendations_enabled and regular_mode and rect is not None:
                pair.recommendations.show_at(rect, result.browser_hwnd)
            else:
                pair.recommendations.hide_overlay()
            comments_mode_supported = not portrait or result.theatre_mode is False
            if (
                self.comments_enabled
                and comments_mode_supported
                and result.player_visible is False
            ):
                comments_rect = comments_overlay_rect_for_monitor(result.monitor_rect)
                if comments_rect is not None:
                    pair.comments.show_at(comments_rect, result.browser_hwnd)
                else:
                    pair.comments.hide_overlay()
            else:
                pair.comments.hide_overlay()
        else:
            pair.comments.hide_overlay()
            if self.feed_recommendations_enabled:
                rect = overlay_rect_for_monitor(result.monitor_rect)
                if rect is not None:
                    pair.recommendations.show_at(rect, result.browser_hwnd)
                else:
                    pair.recommendations.hide_overlay()
            else:
                pair.recommendations.hide_overlay()

    def _pair_for(self, hwnd: int) -> _OverlayPair:
        pair = self._overlay_pairs.get(hwnd)
        if pair is not None:
            return pair
        if self._unassigned_pair is not None:
            pair = self._unassigned_pair
            self._unassigned_pair = None
        elif self._overlay_factory is not None:
            pair = _OverlayPair(self._overlay_factory(), self._overlay_factory())
        else:
            raise RuntimeError("No overlay factory is available for another browser window")
        self._overlay_pairs[hwnd] = pair
        return pair

    def _all_pairs(self) -> tuple[_OverlayPair, ...]:
        assigned = tuple(self._overlay_pairs.values())
        if self._unassigned_pair is None:
            return assigned
        return (*assigned, self._unassigned_pair)

    def _hide_recommendations(self) -> None:
        for pair in self._all_pairs():
            pair.recommendations.hide_overlay()

    def _remove_stale_pairs(self, active_hwnds: set[int]) -> None:
        for hwnd in tuple(self._overlay_pairs):
            if hwnd in active_hwnds:
                continue
            pair = self._overlay_pairs.pop(hwnd)
            self._dispose_pair(pair)

    @staticmethod
    def _dispose_view(view: OverlayView) -> None:
        view.hide_overlay()
        close = getattr(view, "close", None)
        if callable(close):
            close()

    def _dispose_pair(self, pair: _OverlayPair) -> None:
        self._dispose_view(pair.recommendations)
        self._dispose_view(pair.comments)

    def hide(self) -> None:
        for pair in self._all_pairs():
            pair.recommendations.hide_overlay()
            pair.comments.hide_overlay()

    def close(self) -> None:
        for pair in self._all_pairs():
            self._dispose_pair(pair)
        self._overlay_pairs.clear()
        self._unassigned_pair = None
