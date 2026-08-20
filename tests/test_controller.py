from youtube_scroll_blocker.browser_detection import DetectionResult
from youtube_scroll_blocker.controller import OverlayController
from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.url_rules import OverlayMode


class FakeOverlay:
    def __init__(self) -> None:
        self.shown_at: list[tuple[Rect, int]] = []
        self.hide_count = 0
        self.close_count = 0

    def show_at(self, rect: Rect, owner_hwnd: int) -> bool:
        self.shown_at.append((rect, owner_hwnd))
        return True

    def hide_overlay(self) -> None:
        self.hide_count += 1

    def close(self) -> None:
        self.close_count += 1


class FakeOverlayFactory:
    def __init__(self) -> None:
        self.created: list[FakeOverlay] = []

    def __call__(self) -> FakeOverlay:
        overlay = FakeOverlay()
        self.created.append(overlay)
        return overlay


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
    assert overlay.shown_at == [(Rect(3280, 170, 536, 858), 102)]
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
    assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 102)]


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
    assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 102)]


def test_portrait_regular_watch_mode_uses_portrait_recommendations_bounds() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)

    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (3840, 0, 4920, 1920),
            browser_hwnd=102,
            player_visible=True,
            theatre_mode=False,
        )
    )

    assert overlay.shown_at == [(Rect(4562, 177, 336, 1694), 102)]
    assert not comments_overlay.shown_at


def test_portrait_theatre_and_unknown_modes_hide_then_regular_mode_restores() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    monitor = (3840, 0, 4920, 1920)

    for theatre_mode in (True, None):
        controller.handle_detection(
            DetectionResult(
                OverlayMode.WATCH,
                monitor,
                browser_hwnd=102,
                player_visible=True,
                theatre_mode=theatre_mode,
            )
        )
    assert not overlay.shown_at

    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            monitor,
            browser_hwnd=102,
            player_visible=True,
            theatre_mode=False,
        )
    )
    assert overlay.shown_at == [(Rect(4562, 177, 336, 1694), 102)]


def test_portrait_feeds_remain_hidden_and_regular_comments_use_portrait_bounds() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    monitor = (3840, 0, 4920, 1920)

    controller.handle_detection(
        DetectionResult(OverlayMode.STANDARD, monitor, browser_hwnd=102)
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            monitor,
            browser_hwnd=102,
            player_visible=False,
            theatre_mode=False,
        )
    )

    assert overlay.shown_at == [(Rect(4562, 177, 336, 1694), 102)]
    assert comments_overlay.shown_at == [(Rect(3846, 177, 717, 1694), 102)]


def test_portrait_comments_hide_for_theatre_and_unknown_then_restore() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    monitor = (3840, 0, 4920, 1920)

    for theatre_mode in (True, None):
        controller.handle_detection(
            DetectionResult(
                OverlayMode.WATCH,
                monitor,
                browser_hwnd=102,
                player_visible=False,
                theatre_mode=theatre_mode,
            )
        )
    assert not comments_overlay.shown_at

    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            monitor,
            browser_hwnd=102,
            player_visible=False,
            theatre_mode=False,
        )
    )
    assert comments_overlay.shown_at == [(Rect(3846, 177, 717, 1694), 102)]


def test_portrait_comments_hide_when_player_is_visible() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    monitor = (3840, 0, 4920, 1920)

    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            monitor,
            browser_hwnd=102,
            player_visible=False,
            theatre_mode=False,
        )
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            monitor,
            browser_hwnd=102,
            player_visible=True,
            theatre_mode=False,
        )
    )

    assert comments_overlay.shown_at == [(Rect(3846, 177, 717, 1694), 102)]
    assert comments_overlay.hide_count == 1


def test_global_master_and_watch_setting_control_portrait_recommendations() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(overlay, comments_overlay)
    result = DetectionResult(
        OverlayMode.WATCH,
        (3840, 0, 4920, 1920),
        browser_hwnd=102,
        player_visible=True,
        theatre_mode=False,
    )

    controller.set_enabled(False)
    controller.handle_detection(result)
    assert not overlay.shown_at

    controller.set_enabled(True)
    controller.handle_detection(result)
    assert overlay.shown_at == [(Rect(4562, 177, 336, 1694), 102)]

    controller.set_watch_recommendations_enabled(False)
    controller.handle_detection(result)
    assert len(overlay.shown_at) == 1


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
    assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 102)]
    assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 102)]

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


def test_disabled_feed_recommendations_allow_standard_pages() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        feed_recommendations_enabled=False,
    )
    controller.handle_detection(
        DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080), browser_hwnd=101)
    )
    assert not overlay.shown_at
    assert overlay.hide_count == 1
    assert comments_overlay.hide_count == 1


def test_disabled_watch_recommendations_do_not_affect_standard_pages() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        feed_recommendations_enabled=True,
        watch_recommendations_enabled=False,
    )
    controller.handle_detection(
        DetectionResult(OverlayMode.STANDARD, (0, 0, 1920, 1080), browser_hwnd=101)
    )
    assert overlay.shown_at == [(Rect(260, 171, 1631, 852), 101)]


def test_disabled_feed_recommendations_do_not_affect_watch_pages() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        feed_recommendations_enabled=False,
        watch_recommendations_enabled=True,
    )
    controller.handle_detection(
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=101,
            player_visible=True,
        )
    )
    assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 101)]


def test_comments_remain_independent_when_watch_recommendations_are_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        watch_recommendations_enabled=False,
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
    assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]


def test_watch_recommendations_remain_independent_when_comments_are_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        watch_recommendations_enabled=True,
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
    assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 101)]
    assert not comments_overlay.shown_at


def test_all_individual_blockers_can_be_disabled() -> None:
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    controller = OverlayController(
        overlay,
        comments_overlay,
        feed_recommendations_enabled=False,
        watch_recommendations_enabled=False,
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
        feed_recommendations_enabled=False,
        watch_recommendations_enabled=False,
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

    assert controller.feed_recommendations_enabled is False
    assert controller.watch_recommendations_enabled is False
    assert controller.comments_enabled is True
    assert not overlay.shown_at
    assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]


def test_multiple_windows_receive_independent_overlay_pairs() -> None:
    factory = FakeOverlayFactory()
    controller = OverlayController(factory)
    standard = DetectionResult(
        OverlayMode.STANDARD,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
    )
    watch = DetectionResult(
        OverlayMode.WATCH,
        (1920, 0, 3840, 1080),
        browser_hwnd=102,
        player_visible=False,
    )

    controller.handle_detections((standard, watch))

    standard_overlay, standard_comments, watch_overlay, watch_comments = factory.created
    assert standard_overlay.shown_at == [(Rect(260, 171, 1631, 852), 101)]
    assert not standard_comments.shown_at
    assert watch_overlay.shown_at == [(Rect(3280, 170, 536, 858), 102)]
    assert watch_comments.shown_at == [(Rect(1930, 170, 1360, 910), 102)]

    controller.set_enabled(False)
    assert all(overlay.hide_count for overlay in factory.created)
    controller.set_enabled(True)
    controller.handle_detections((standard, watch))
    assert len(standard_overlay.shown_at) == 2
    assert len(watch_overlay.shown_at) == 2

    controller.close()
    assert all(overlay.close_count == 1 for overlay in factory.created)


def test_removing_one_result_disposes_only_that_windows_overlays() -> None:
    factory = FakeOverlayFactory()
    controller = OverlayController(factory)
    first = DetectionResult(
        OverlayMode.STANDARD,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
    )
    second = DetectionResult(
        OverlayMode.STANDARD,
        (1920, 0, 3840, 1080),
        browser_hwnd=102,
    )
    controller.handle_detections((first, second))
    first_overlay, first_comments, second_overlay, second_comments = factory.created

    controller.handle_detections((second,))

    assert first_overlay.close_count == 1
    assert first_comments.close_count == 1
    assert second_overlay.close_count == 0
    assert second_comments.close_count == 0
    assert len(second_overlay.shown_at) == 2


def test_individual_blocker_preferences_apply_to_every_window() -> None:
    factory = FakeOverlayFactory()
    controller = OverlayController(factory)
    standard = DetectionResult(
        OverlayMode.STANDARD,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
    )
    watch = DetectionResult(
        OverlayMode.WATCH,
        (1920, 0, 3840, 1080),
        browser_hwnd=102,
        player_visible=False,
    )
    controller.handle_detections((standard, watch))
    standard_overlay, _standard_comments, watch_overlay, watch_comments = factory.created

    controller.set_feed_recommendations_enabled(False)
    controller.set_watch_recommendations_enabled(False)
    controller.set_comments_enabled(False)
    controller.handle_detections((standard, watch))

    assert len(standard_overlay.shown_at) == 1
    assert len(watch_overlay.shown_at) == 1
    assert len(watch_comments.shown_at) == 1

    controller.set_feed_recommendations_enabled(True)
    controller.set_watch_recommendations_enabled(True)
    controller.set_comments_enabled(True)
    controller.handle_detections((standard, watch))
    assert len(standard_overlay.shown_at) == 2
    assert len(watch_overlay.shown_at) == 2
    assert len(watch_comments.shown_at) == 2
