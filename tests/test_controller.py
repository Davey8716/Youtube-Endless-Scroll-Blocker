from youtube_scroll_blocker.browser_detection import DetectionResult
from youtube_scroll_blocker.controller import OverlayController
from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.url_rules import OverlayMode


class FakeOverlay:
    def __init__(self) -> None:
        self.shown_at: list[tuple[Rect, int]] = []
        self.hide_count = 0

    def show_at(self, rect: Rect, owner_hwnd: int) -> bool:
        self.shown_at.append((rect, owner_hwnd))
        return True

    def hide_overlay(self) -> None:
        self.hide_count += 1


def test_eligible_detection_shows_at_monitor_relative_bounds() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(OverlayMode.STANDARD, (1920, 0, 3840, 1080), browser_hwnd=101)
    )
    assert overlay.shown_at == [(Rect(2180, 171, 1631, 852), 101)]
    assert comments_overlay.hide_count == 1


def test_watch_detection_uses_watch_bounds() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (1920, 0, 3840, 1080),
            browser_hwnd=102,
            player_visible=True,
        )
    )
    assert overlay.shown_at == [(Rect(3280, 170, 536, 860), 102)]
    assert not comments_overlay.shown_at
    assert comments_overlay.hide_count == 1


def test_theatre_mode_hides_recommendations_but_keeps_comments_independent() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=102,
            player_visible=False,
            theatre_mode=True,
        )
    )
    assert not overlay.shown_at
    assert overlay.hide_count == 1
    assert comments_overlay.shown_at == [(Rect(0, 170, 1360, 910), 102)]


def test_leaving_theatre_mode_restores_recommendations() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=102,
            player_visible=True,
            theatre_mode=True,
        )
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=102,
            player_visible=True,
            theatre_mode=False,
        )
    )
    assert overlay.shown_at == [(Rect(1360, 170, 536, 860), 102)]


def test_watch_comments_show_when_player_is_no_longer_visible() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=102,
            player_visible=False,
        )
    )
    assert overlay.shown_at == [(Rect(1360, 170, 536, 860), 102)]
    assert comments_overlay.shown_at == [(Rect(0, 170, 1360, 910), 102)]

    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=102,
            player_visible=True,
        )
    )
    assert comments_overlay.hide_count == 1


def test_unknown_player_visibility_keeps_comments_hidden() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(
        DetectionResult(OverlayMode.WATCH, (0, 0, 1920, 1080), browser_hwnd=102)
    )
    assert not comments_overlay.shown_at
    assert comments_overlay.hide_count == 1


def test_ineligible_detection_hides_overlay() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(DetectionResult())
    assert overlay.hide_count == 1
    assert comments_overlay.hide_count == 1


def test_disabled_controller_ignores_eligible_detection() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.set_enabled(False)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080), browser_hwnd=101))
    assert not overlay.shown_at
    assert overlay.hide_count == 2
    assert comments_overlay.hide_count == 2


def test_open_menu_hides_and_suppresses_overlay() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.set_menu_open(True)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080), browser_hwnd=101))
    assert not overlay.shown_at
    assert overlay.hide_count == 2
    assert comments_overlay.hide_count == 2


def test_detection_without_monitor_bounds_hides_overlay() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, browser_hwnd=101))
    assert overlay.hide_count == 1


def test_detection_without_owner_hides_overlay() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    controller.handle_detection(DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080)))
    assert overlay.hide_count == 1


def test_disabled_recommendations_allow_standard_pages() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        recommendations_enabled=False,
    )
    controller.handle_detection(
        DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080), browser_hwnd=101)
    )
    assert not overlay.shown_at
    assert overlay.hide_count == 1
    assert comments_overlay.hide_count == 1


def test_comments_remain_independent_when_recommendations_are_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        recommendations_enabled=False,
        comments_enabled=True,
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=101,
            player_visible=False,
        )
    )
    assert not overlay.shown_at
    assert comments_overlay.shown_at == [(Rect(0, 170, 1360, 910), 101)]


def test_recommendations_remain_independent_when_comments_are_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        recommendations_enabled=True,
        comments_enabled=False,
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=101,
            player_visible=False,
        )
    )
    assert overlay.shown_at == [(Rect(1360, 170, 536, 860), 101)]
    assert not comments_overlay.shown_at


def test_both_individual_blockers_can_be_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        recommendations_enabled=False,
        comments_enabled=False,
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=101,
            player_visible=False,
        )
    )
    assert not overlay.shown_at
    assert not comments_overlay.shown_at


def test_master_toggle_preserves_individual_preferences() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        recommendations_enabled=False,
        comments_enabled=True,
    )
    result = DetectionResult(
        OverlayMode.WATCH,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
        player_visible=False,
    )

    controller.set_enabled(False)
    controller.handle_detection(result)
    controller.set_enabled(True)
    controller.handle_detection(result)

    assert controller.recommendations_enabled is False
    assert controller.comments_enabled is True
    assert not overlay.shown_at
    assert comments_overlay.shown_at == [(Rect(0, 170, 1360, 910), 101)]
