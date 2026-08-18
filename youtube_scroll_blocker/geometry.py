from __future__ import annotations

from dataclasses import dataclass


OVERLAY_X = 260
OVERLAY_Y = 171
OVERLAY_WIDTH = 1631
OVERLAY_HEIGHT = 852
WATCH_OVERLAY_X = 1360
WATCH_OVERLAY_Y = 170
WATCH_OVERLAY_WIDTH = 536
WATCH_OVERLAY_HEIGHT = 860
COMMENTS_OVERLAY_X = 0
COMMENTS_OVERLAY_Y = 170
COMMENTS_OVERLAY_WIDTH = 1360


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int


def overlay_rect_for_monitor(monitor_rect: tuple[int, int, int, int]) -> Rect:
    left, top, _right, _bottom = monitor_rect
    return Rect(
        left=left + OVERLAY_X,
        top=top + OVERLAY_Y,
        width=OVERLAY_WIDTH,
        height=OVERLAY_HEIGHT,
    )


def watch_overlay_rect_for_monitor(monitor_rect: tuple[int, int, int, int]) -> Rect:
    left, top, _right, _bottom = monitor_rect
    return Rect(
        left=left + WATCH_OVERLAY_X,
        top=top + WATCH_OVERLAY_Y,
        width=WATCH_OVERLAY_WIDTH,
        height=WATCH_OVERLAY_HEIGHT,
    )


def comments_overlay_rect_for_monitor(
    monitor_rect: tuple[int, int, int, int],
) -> Rect:
    left, top, right, bottom = monitor_rect
    return Rect(
        left=left + COMMENTS_OVERLAY_X,
        top=top + COMMENTS_OVERLAY_Y,
        width=min(COMMENTS_OVERLAY_WIDTH, max(0, right - left)),
        height=max(0, bottom - top - COMMENTS_OVERLAY_Y),
    )
