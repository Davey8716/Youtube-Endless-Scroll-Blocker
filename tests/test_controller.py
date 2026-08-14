from youtube_scroll_blocker.browser_detection import DetectionResult
from youtube_scroll_blocker.controller import OverlayController
from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.url_rules import OverlayMode


class FakeOverlay:
    def __init__(self) -> None:
        self.shown_at: list[Rect] = []
        self.hide_count = 0

    def show_at(self, rect: Rect) -> None:
        self.shown_at.append(rect)

    def hide_overlay(self) -> None:
        self.hide_count += 1


def test_eligible_detection_shows_at_monitor_relative_bounds() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (1920, 0, 3840, 1080)))
    assert overlay.shown_at == [Rect(2180, 171, 1631, 852)]


def test_watch_detection_uses_watch_bounds() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.handle_detection(DetectionResult(OverlayMode.WATCH, (1920, 0, 3840, 1080)))
    assert overlay.shown_at == [Rect(3143, 176, 677, 852)]


def test_ineligible_detection_hides_overlay() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.handle_detection(DetectionResult())
    assert overlay.hide_count == 1


def test_disabled_controller_ignores_eligible_detection() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.set_enabled(False)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080)))
    assert not overlay.shown_at
    assert overlay.hide_count == 2


def test_open_menu_hides_and_suppresses_overlay() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.set_menu_open(True)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080)))
    assert not overlay.shown_at
    assert overlay.hide_count == 2


def test_detection_without_monitor_bounds_hides_overlay() -> None:
    overlay = FakeOverlay()
    controller = OverlayController(overlay)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD))
    assert overlay.hide_count == 1
