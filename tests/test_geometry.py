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
    assert watch_overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(1360, 170, 536, 858)


def test_secondary_monitor_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(3280, 170, 536, 858)


def test_negative_monitor_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((-1920, -200, 0, 880)) == Rect(-560, -30, 536, 858)


def test_portrait_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((0, 0, 1080, 1920)) == Rect(722, 177, 336, 1694)


def test_portrait_watch_geometry_is_relative_to_monitor_origin() -> None:
    assert watch_overlay_rect_for_monitor((3840, 0, 4920, 1920)) == Rect(
        4562,
        177,
        336,
        1694,
    )


def test_unsupported_portrait_size_has_no_watch_geometry() -> None:
    assert watch_overlay_rect_for_monitor((0, 0, 1200, 1920)) is None


def test_primary_monitor_comments_geometry() -> None:
    assert comments_overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(10, 170, 1360, 910)


def test_comments_geometry_is_relative_to_secondary_monitor() -> None:
    assert comments_overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(1930, 170, 1360, 910)


def test_portrait_comments_geometry() -> None:
    assert comments_overlay_rect_for_monitor((0, 0, 1080, 1920)) == Rect(
        6,
        177,
        717,
        1694,
    )


def test_portrait_comments_geometry_is_relative_to_monitor_origin() -> None:
    monitor = (3840, 0, 4920, 1920)
    assert comments_overlay_rect_for_monitor(monitor) == Rect(3846, 177, 717, 1694)


def test_portrait_feed_geometry_is_not_supported() -> None:
    monitor = (3840, 0, 4920, 1920)
    assert overlay_rect_for_monitor(monitor) is None


def test_unsupported_portrait_size_has_no_comments_geometry() -> None:
    assert comments_overlay_rect_for_monitor((0, 0, 1200, 1920)) is None
