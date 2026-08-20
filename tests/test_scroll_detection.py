from __future__ import annotations

from youtube_scroll_blocker import scroll_detection
from youtube_scroll_blocker.scroll_detection import (
    DocumentScrollReader,
    DocumentScrollState,
    MouseWheelMonitor,
    ScrollbarDragEvent,
    WatchScrollTracker,
    WheelEvent,
    WheelScrollAccumulator,
)


MONITOR = (0, 0, 1920, 1080)
PORTRAIT_MONITOR = (0, 0, 1080, 1920)
WATCH_URL = "https://www.youtube.com/watch?v=test-id"


class FakeMonitor:
    def __init__(self) -> None:
        self.events: list[WheelEvent | ScrollbarDragEvent] = []

    def drain(self) -> list[WheelEvent | ScrollbarDragEvent]:
        events = list(self.events)
        self.events.clear()
        return events


class FakeDocumentReader:
    def __init__(self, state: DocumentScrollState | None = None) -> None:
        self.state = state
        self.reset_count = 0

    def read(
        self,
        _hwnd: int,
        _monitor_rect: tuple[int, int, int, int],
        _url: str,
    ) -> DocumentScrollState | None:
        return self.state

    def reset(self) -> None:
        self.reset_count += 1


class StubBounds:
    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom


class StubScrollPattern:
    def __init__(
        self,
        *,
        scrollable: bool = True,
        scroll_percent: float = 0.0,
        view_percent: float = 10.0,
    ) -> None:
        self.VerticallyScrollable = scrollable
        self.VerticalScrollPercent = scroll_percent
        self.VerticalViewSize = view_percent


class StubControl:
    def __init__(
        self,
        pattern: StubScrollPattern | None,
        bounds: StubBounds,
        parent: "StubControl" | None = None,
    ) -> None:
        self._pattern = pattern
        self.BoundingRectangle = bounds
        self._parent = parent

    def GetScrollPattern(self) -> StubScrollPattern | None:
        return self._pattern

    def GetParentControl(self) -> "StubControl" | None:
        return self._parent


def make_tracker(
    monitor: FakeMonitor,
    document_reader: FakeDocumentReader | None = None,
) -> WatchScrollTracker:
    return WatchScrollTracker(
        monitor,  # type: ignore[arg-type]
        document_reader or FakeDocumentReader(),  # type: ignore[arg-type]
        WheelScrollAccumulator(scroll_lines=3),
    )


def test_mouse_wheel_monitor_records_and_drains_events() -> None:
    monitor = MouseWheelMonitor()
    event = WheelEvent(-120, 800, 500)
    monitor.record(event)
    assert monitor.drain() == [event]
    assert monitor.drain() == []


def test_one_wheel_event_does_not_hide_player() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.append(WheelEvent(-120, 800, 500))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is True


def test_accumulated_wheel_events_hide_player_then_upward_scroll_restores_it() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.extend(WheelEvent(-120, 800, 500) for _ in range(6))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False

    monitor.events.extend(WheelEvent(120, 800, 500) for _ in range(6))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is True


def test_portrait_wheel_events_hide_player_after_four_notches_and_restore_it() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)

    monitor.events.extend(WheelEvent(-120, 800, 500) for _ in range(3))
    assert tracker.visibility(101, PORTRAIT_MONITOR, WATCH_URL, active=True) is True

    monitor.events.append(WheelEvent(-120, 800, 500))
    assert tracker.visibility(101, PORTRAIT_MONITOR, WATCH_URL, active=True) is False

    monitor.events.extend(WheelEvent(120, 800, 500) for _ in range(4))
    assert tracker.visibility(101, PORTRAIT_MONITOR, WATCH_URL, active=True) is True


def test_high_resolution_wheel_deltas_accumulate() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.extend(WheelEvent(-30, 800, 500) for _ in range(24))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False


def test_irrelevant_wheel_events_are_ignored() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.extend(
        [
            WheelEvent(-1200, 800, 50),
            WheelEvent(-1200, 2000, 500),
        ]
    )
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is None

    monitor.events.append(WheelEvent(-1200, 800, 500))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=False) is None


def test_wheel_events_over_right_side_and_scrollbar_are_counted() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.extend(WheelEvent(-120, 1905, 500) for _ in range(6))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False


def test_scrollbar_drag_down_hides_player_and_drag_up_restores_it() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.append(ScrollbarDragEvent(20, 1905, 300))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False

    monitor.events.append(ScrollbarDragEvent(-20, 1905, 280))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is True


def test_small_scrollbar_drag_does_not_cross_threshold() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.append(ScrollbarDragEvent(5, 1905, 300))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is True


def test_drag_outside_scrollbar_zone_is_ignored() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.append(ScrollbarDragEvent(100, 1800, 500))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is None


def test_watch_context_change_resets_wheel_offset() -> None:
    monitor = FakeMonitor()
    tracker = make_tracker(monitor)
    monitor.events.extend(WheelEvent(-120, 800, 500) for _ in range(6))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False
    assert tracker.visibility(101, MONITOR, WATCH_URL + "-new", active=True) is None


def test_wheel_estimate_takes_precedence_over_stale_document_scroll_state() -> None:
    monitor = FakeMonitor()
    document_reader = FakeDocumentReader(DocumentScrollState(100.0, 110))
    tracker = make_tracker(monitor, document_reader)
    monitor.events.extend(WheelEvent(-120, 800, 500) for _ in range(10))
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False


def test_document_scroll_state_is_used_before_wheel_input_exists() -> None:
    monitor = FakeMonitor()
    document_reader = FakeDocumentReader(DocumentScrollState(700.0, 110))
    tracker = make_tracker(monitor, document_reader)

    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False


def test_landscape_document_scroll_state_keeps_existing_player_bottom_boundary() -> None:
    monitor = FakeMonitor()
    document_reader = FakeDocumentReader(DocumentScrollState(650.0, 110))
    tracker = make_tracker(monitor, document_reader)

    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is True

    document_reader.state = DocumentScrollState(651.0, 110)
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False


def test_portrait_document_scroll_state_changes_at_player_bottom_boundary() -> None:
    monitor = FakeMonitor()
    document_reader = FakeDocumentReader(DocumentScrollState(469.0, 110))
    tracker = make_tracker(monitor, document_reader)

    assert tracker.visibility(101, PORTRAIT_MONITOR, WATCH_URL, active=True) is True

    document_reader.state = DocumentScrollState(470.0, 110)
    assert tracker.visibility(101, PORTRAIT_MONITOR, WATCH_URL, active=True) is False


def test_background_window_retains_its_last_known_player_visibility() -> None:
    monitor = FakeMonitor()
    document_reader = FakeDocumentReader(DocumentScrollState(700.0, 110))
    tracker = make_tracker(monitor, document_reader)

    assert tracker.visibility(101, MONITOR, WATCH_URL, active=True) is False
    document_reader.state = None
    assert tracker.visibility(101, MONITOR, WATCH_URL, active=False) is False
    assert tracker.visibility(101, MONITOR, WATCH_URL + "-new", active=False) is None


def test_document_scroll_reader_converts_percent_to_pixel_offset(monkeypatch) -> None:
    pattern = StubScrollPattern(scroll_percent=10.0, view_percent=10.0)
    control = StubControl(pattern, StubBounds(0, 110, 1920, 1080))
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        scroll_detection.auto,
        "ControlFromPoint",
        lambda x, y: calls.append((x, y)) or control,
    )
    reader = DocumentScrollReader()

    state = reader.read(101, MONITOR, WATCH_URL)
    assert state == DocumentScrollState(873.0, 110)
    assert reader.read(101, MONITOR, WATCH_URL) == state
    assert calls == [(810, 900)]


def test_document_scroll_reader_relocates_for_new_window(monkeypatch) -> None:
    pattern = StubScrollPattern(scroll_percent=0.0, view_percent=10.0)
    control = StubControl(pattern, StubBounds(0, 110, 1920, 1080))
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        scroll_detection.auto,
        "ControlFromPoint",
        lambda x, y: calls.append((x, y)) or control,
    )
    reader = DocumentScrollReader()

    assert reader.read(101, MONITOR, WATCH_URL) is not None
    control.BoundingRectangle = StubBounds(1920, 110, 3840, 1080)
    assert reader.read(102, (1920, 0, 3840, 1080), WATCH_URL) is not None
    assert calls == [(810, 900), (2730, 900)]
