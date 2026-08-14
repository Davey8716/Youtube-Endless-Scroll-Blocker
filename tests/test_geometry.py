from youtube_scroll_blocker.geometry import Rect, overlay_rect_for_monitor


def test_primary_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((0, 0, 1920, 1080)) == Rect(260, 171, 1631, 852)


def test_secondary_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((1920, 0, 3840, 1080)) == Rect(2180, 171, 1631, 852)


def test_negative_monitor_geometry() -> None:
    assert overlay_rect_for_monitor((-1920, -200, 0, 880)) == Rect(-1660, -29, 1631, 852)
