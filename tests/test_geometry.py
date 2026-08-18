from youtube_scroll_blocker.geometry import (
    Rect,
    comments_overlay_rect_for_monitor,
    overlay_rect_for_monitor,
    watch_overlay_rect_for_monitor,
)


def test_primary_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(260, 171, 1631, 852)


def test_secondary_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(2180, 171, 1631, 852)


def test_negative_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((-1920, -200, 0, 880)) == Rect(-1660, -29, 1631, 852)


def test_primary_monitor_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(1360, 170, 536, 860)


def test_secondary_monitor_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(3280, 170, 536, 860)


def test_negative_monitor_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((-1920, -200, 0, 880)) == Rect(-560, -30, 536, 860)


def test_primary_monitor_comments_geometry() -> None:
    assert comments_overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(0, 170, 1360, 910)


def test_comments_geometry_is_relative_to_secondary_monitor() -> None:
    assert comments_overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(1920, 170, 1360, 910)
