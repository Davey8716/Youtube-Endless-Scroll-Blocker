from __future__ import annotations

from youtube_scroll_blocker import browser_detection
from youtube_scroll_blocker.browser_detection import AddressBarState, BrowserDetector
from youtube_scroll_blocker.url_rules import OverlayMode


class StubAddressReader:
    def __init__(
        self,
        url: str | None,
        visible: bool = True,
        theatre_mode: bool | None = None,
    ) -> None:
        self.url = url
        self.visible = visible
        self.theatre_mode = theatre_mode

    def inspect(self, _hwnd: int) -> AddressBarState:
        return AddressBarState(self.url, self.visible, self.theatre_mode)


class StubPlayerTracker:
    def __init__(self, visible: bool | None = None) -> None:
        self.visible = visible
        self.calls: list[tuple[int, tuple[int, int, int, int], str, bool]] = []
        self.reset_count = 0

    def visibility(
        self,
        hwnd: int,
        monitor_rect: tuple[int, int, int, int],
        url: str,
        *,
        active: bool,
    ) -> bool | None:
        self.calls.append((hwnd, monitor_rect, url, active))
        return self.visible

    def reset(self) -> None:
        self.reset_count += 1


class MappingAddressReader:
    def __init__(self, addresses: dict[int, AddressBarState]) -> None:
        self.addresses = addresses

    def inspect(self, hwnd: int) -> AddressBarState:
        return self.addresses[hwnd]


class StubPattern:
    def __init__(self, value: str) -> None:
        self.Value = value


class StubBounds:
    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def width(self) -> int:
        return self.right - self.left


class StubControl:
    def __init__(
        self,
        *,
        children: list["StubControl"] | None = None,
        value: str | None = None,
        offscreen: bool = False,
        name: str | None = None,
        automation_id: str | None = None,
        bounds: StubBounds | None = None,
        parent: "StubControl" | None = None,
        control_type: str | None = None,
    ) -> None:
        self.ControlTypeName = control_type or ("EditControl" if value is not None else "WindowControl")
        self.AutomationId = automation_id if automation_id is not None else (
            "address and search bar" if value is not None else ""
        )
        self.Name = name if name is not None else (
            "Address and search bar" if value is not None else ""
        )
        self.BoundingRectangle = bounds or StubBounds(200, 50, 1200, 90)
        self.IsOffscreen = offscreen
        self._children = children or []
        self._value = value
        self._parent = parent

    def GetChildren(self) -> list["StubControl"]:
        return self._children

    def GetValuePattern(self) -> StubPattern | None:
        return StubPattern(self._value) if self._value is not None else None

    def GetParentControl(self) -> "StubControl" | None:
        return self._parent


def configure_active_brave(monkeypatch, *, maximized: bool = True, fullscreen: bool = False) -> dict:
    environment = {
        "foreground": 101,
        "brave_hwnds": {101},
        "valid_hwnds": {101, 999},
        "visible_hwnds": {101, 999},
        "iconic_hwnds": set(),
        "maximized_hwnds": {101} if maximized else set(),
    }
    monkeypatch.setattr(browser_detection.win32gui, "GetForegroundWindow", lambda: environment["foreground"])
    monkeypatch.setattr(browser_detection.win32gui, "IsWindow", lambda hwnd: hwnd in environment["valid_hwnds"])
    monkeypatch.setattr(
        browser_detection.win32gui,
        "IsWindowVisible",
        lambda hwnd: hwnd in environment["visible_hwnds"],
    )
    monkeypatch.setattr(browser_detection.win32gui, "IsIconic", lambda hwnd: hwnd in environment["iconic_hwnds"])
    monkeypatch.setattr(
        browser_detection,
        "_is_window_maximized",
        lambda hwnd: hwnd in environment["maximized_hwnds"],
    )
    monkeypatch.setattr(
        browser_detection.win32process,
        "GetWindowThreadProcessId",
        lambda hwnd: (1, hwnd + 1000),
    )
    monkeypatch.setattr(
        browser_detection,
        "_process_executable_name",
        lambda pid: "brave.exe" if pid - 1000 in environment["brave_hwnds"] else "notepad.exe",
    )
    monkeypatch.setattr(
        browser_detection,
        "_is_fullscreen_window",
        lambda _hwnd, _monitor_rect, _chrome_visible: fullscreen,
    )
    monkeypatch.setattr(browser_detection.win32api, "MonitorFromWindow", lambda _hwnd, _flag: 303)
    monkeypatch.setattr(
        browser_detection.win32api,
        "GetMonitorInfo",
        lambda _monitor: {"Monitor": (0, 0, 1920, 1080)},
    )
    return environment


def test_active_maximized_brave_non_video_page_is_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/results")).detect()
    assert result.should_show
    assert result.mode is OverlayMode.STANDARD
    assert result.monitor_rect == (0, 0, 1920, 1080)
    assert result.browser_hwnd == 101


def test_non_fullscreen_watch_page_uses_watch_overlay(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    player_tracker = StubPlayerTracker(True)
    result = BrowserDetector(
        StubAddressReader("https://www.youtube.com/watch?v=test-id"),
        player_tracker,
    ).detect()
    assert result.mode is OverlayMode.WATCH
    assert result.monitor_rect == (0, 0, 1920, 1080)
    assert result.player_visible is True
    assert player_tracker.calls == [
        (101, (0, 0, 1920, 1080), "https://www.youtube.com/watch?v=test-id", True)
    ]


def test_watch_page_propagates_theatre_mode(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(
        StubAddressReader(
            "https://www.youtube.com/watch?v=test-id",
            theatre_mode=True,
        ),
        StubPlayerTracker(True),
    ).detect()
    assert result.mode is OverlayMode.WATCH
    assert result.theatre_mode is True


def test_search_results_are_visible_then_clicked_video_uses_watch_overlay(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    address_reader = StubAddressReader("https://www.youtube.com/results?search_query=lol")
    detector = BrowserDetector(address_reader, StubPlayerTracker())

    search_result = detector.detect()
    assert search_result.mode is OverlayMode.NONE

    address_reader.url = "https://www.youtube.com/watch?v=test-id"
    watch_result = detector.detect()
    assert watch_result.mode is OverlayMode.WATCH
    assert watch_result.monitor_rect == (0, 0, 1920, 1080)


def test_fullscreen_watch_page_is_not_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch, fullscreen=True)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/watch?v=test-id", visible=False)).detect()
    assert result.mode is OverlayMode.NONE
    assert result.url == "https://www.youtube.com/watch?v=test-id"


def test_hidden_browser_chrome_fails_closed(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/watch?v=test-id", visible=False)).detect()
    assert result.mode is OverlayMode.NONE


def test_watch_page_without_video_id_is_not_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/watch?feature=test")).detect()
    assert not result.should_show
    assert result.url == "https://www.youtube.com/watch?feature=test"


def test_shorts_page_is_not_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/shorts/test-id")).detect()
    assert result.mode is OverlayMode.NONE


def test_restored_brave_window_is_not_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch, maximized=False)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/")).detect()
    assert not result.should_show


def test_non_brave_foreground_window_is_not_eligible(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    environment["foreground"] = 999
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/")).detect()
    assert not result.should_show


def test_tracked_overlay_persists_when_another_application_gets_focus(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(StubAddressReader("https://www.youtube.com/results"))

    assert detector.detect().browser_hwnd == 101
    environment["foreground"] = 999

    result = detector.detect()
    assert result.mode is OverlayMode.STANDARD
    assert result.browser_hwnd == 101


def test_tracked_watch_overlay_persists_when_another_application_gets_focus(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(
        StubAddressReader("https://www.youtube.com/watch?v=test-id"),
        StubPlayerTracker(),
    )

    assert detector.detect().mode is OverlayMode.WATCH
    environment["foreground"] = 999

    result = detector.detect()
    assert result.mode is OverlayMode.WATCH
    assert result.browser_hwnd == 101


def test_newly_focused_brave_window_replaces_tracked_window(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    environment["brave_hwnds"].add(102)
    environment["valid_hwnds"].add(102)
    environment["visible_hwnds"].add(102)
    environment["maximized_hwnds"].add(102)
    reader = MappingAddressReader(
        {
            101: AddressBarState("https://www.youtube.com/results", True),
            102: AddressBarState("https://www.youtube.com/@MandyCaneLane", True),
        }
    )
    detector = BrowserDetector(reader)

    assert detector.detect().browser_hwnd == 101
    environment["foreground"] = 102

    result = detector.detect()
    assert result.mode is OverlayMode.NONE
    assert result.browser_hwnd == 102

    environment["foreground"] = 999
    assert detector.detect().browser_hwnd == 102


def test_exempt_navigation_is_detected_while_brave_is_unfocused(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    reader = StubAddressReader("https://www.youtube.com/results")
    detector = BrowserDetector(reader)

    assert detector.detect().should_show
    environment["foreground"] = 999
    reader.url = "https://www.youtube.com/feed/history"

    result = detector.detect()
    assert result.mode is OverlayMode.NONE
    assert result.browser_hwnd == 101


def test_invalid_tracked_window_is_cleared(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(StubAddressReader("https://www.youtube.com/results"))

    assert detector.detect().should_show
    environment["foreground"] = 999
    environment["valid_hwnds"].remove(101)

    result = detector.detect()
    assert result.mode is OverlayMode.NONE
    assert result.browser_hwnd is None


def test_hidden_tracked_window_is_cleared(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(StubAddressReader("https://www.youtube.com/results"))

    assert detector.detect().should_show
    environment["foreground"] = 999
    environment["visible_hwnds"].remove(101)

    assert detector.detect().browser_hwnd is None


def test_minimized_tracked_window_is_cleared(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(StubAddressReader("https://www.youtube.com/results"))

    assert detector.detect().should_show
    environment["foreground"] = 999
    environment["iconic_hwnds"].add(101)

    assert detector.detect().browser_hwnd is None


def test_restored_tracked_window_is_cleared(monkeypatch) -> None:
    environment = configure_active_brave(monkeypatch)
    detector = BrowserDetector(StubAddressReader("https://www.youtube.com/results"))

    assert detector.detect().should_show
    environment["foreground"] = 999
    environment["maximized_hwnds"].remove(101)

    assert detector.detect().browser_hwnd is None


def test_detection_failure_hides_overlay(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection.win32gui, "GetForegroundWindow", lambda: (_ for _ in ()).throw(OSError()))
    assert not BrowserDetector(StubAddressReader(None)).detect().should_show


def test_address_bar_inspection_reports_visible_chrome(monkeypatch) -> None:
    address_bar = StubControl(value="https://www.youtube.com/watch?v=test-id")
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: StubControl(children=[address_bar]))
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))
    assert browser_detection.BraveAddressBarReader().inspect(101) == AddressBarState(
        "https://www.youtube.com/watch?v=test-id",
        True,
    )


def test_address_bar_inspection_reports_offscreen_chrome(monkeypatch) -> None:
    address_bar = StubControl(value="https://www.youtube.com/watch?v=test-id", offscreen=True)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: StubControl(children=[address_bar]))
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))
    assert browser_detection.BraveAddressBarReader().inspect(101) == AddressBarState(
        "https://www.youtube.com/watch?v=test-id",
        False,
    )


def watch_page_controls(
    player: StubControl | None,
) -> StubControl:
    address_bar = StubControl(value="https://www.youtube.com/watch?v=test-id")
    children = [player] if player is not None else []
    for _depth in range(10):
        children = [StubControl(children=children)]
    document = StubControl(
        children=children,
        control_type="DocumentControl",
        bounds=StubBounds(4, 114, 1916, 1028),
    )
    empty_document = StubControl(
        control_type="DocumentControl",
        bounds=StubBounds(4, 114, 1916, 1028),
    )
    content_pane = StubControl(
        children=[document],
        name="Chrome Legacy Window",
        control_type="PaneControl",
        bounds=StubBounds(4, 114, 1916, 1028),
    )
    return StubControl(children=[address_bar, empty_document, content_pane])


def test_address_bar_inspection_detects_default_view_from_player_width(monkeypatch) -> None:
    player = StubControl(
        name="YouTube Video Player",
        control_type="GroupControl",
        bounds=StubBounds(20, 182, 1352, 931),
    )
    root = watch_page_controls(player)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: root)
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))

    assert browser_detection.BraveAddressBarReader().inspect(101) == AddressBarState(
        "https://www.youtube.com/watch?v=test-id",
        True,
        False,
    )


def test_address_bar_inspection_detects_theatre_mode_from_player_width(monkeypatch) -> None:
    player = StubControl(
        name="YouTube Video Player",
        control_type="GroupControl",
        bounds=StubBounds(4, 170, 1901, 915),
    )
    root = watch_page_controls(player)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: root)
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))

    assert browser_detection.BraveAddressBarReader().inspect(101) == AddressBarState(
        "https://www.youtube.com/watch?v=test-id",
        True,
        True,
    )


def test_theatre_mode_tracks_recreated_player_on_same_url(monkeypatch) -> None:
    roots = [
        watch_page_controls(
            StubControl(
                name="YouTube Video Player",
                control_type="GroupControl",
                bounds=bounds,
            )
        )
        for bounds in (
            StubBounds(4, 170, 1901, 915),
            StubBounds(20, 182, 1352, 931),
            StubBounds(4, 170, 1901, 915),
        )
    ]
    current = {"root": roots[0]}
    monkeypatch.setattr(
        browser_detection.auto,
        "ControlFromHandle",
        lambda _hwnd: current["root"],
    )
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))
    reader = browser_detection.BraveAddressBarReader()

    assert reader.inspect(101).theatre_mode is True
    current["root"] = roots[1]
    assert reader.inspect(101).theatre_mode is False
    current["root"] = roots[2]
    assert reader.inspect(101).theatre_mode is True


def test_theatre_detection_does_not_require_visible_player_buttons(monkeypatch) -> None:
    player = StubControl(
        name="YouTube Video Player",
        control_type="GroupControl",
        bounds=StubBounds(4, 170, 1901, 915),
    )
    root = watch_page_controls(player)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: root)
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))

    assert browser_detection.BraveAddressBarReader().inspect(101).theatre_mode is True


def test_missing_player_control_returns_unknown(monkeypatch) -> None:
    root = watch_page_controls(None)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: root)
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))

    assert browser_detection.BraveAddressBarReader().inspect(101).theatre_mode is None


def test_invalid_player_bounds_return_unknown(monkeypatch) -> None:
    player = StubControl(
        name="YouTube Video Player",
        control_type="GroupControl",
    )
    player.BoundingRectangle = None
    root = watch_page_controls(player)
    monkeypatch.setattr(browser_detection.auto, "ControlFromHandle", lambda _hwnd: root)
    monkeypatch.setattr(browser_detection.win32gui, "GetWindowRect", lambda _hwnd: (0, 0, 1920, 1080))

    assert browser_detection.BraveAddressBarReader().inspect(101).theatre_mode is None


def test_full_monitor_window_with_hidden_chrome_is_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1080))
    assert browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=False)


def test_full_monitor_window_with_visible_chrome_is_not_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1080))
    assert not browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=True)


def test_maximized_work_area_window_is_not_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1040))
    assert not browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=False)
