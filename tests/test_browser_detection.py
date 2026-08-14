from youtube_scroll_blocker import browser_detection
from youtube_scroll_blocker.browser_detection import AddressBarState, BrowserDetector
from youtube_scroll_blocker.url_rules import OverlayMode


class StubAddressReader:
    def __init__(self, url: str | None, visible: bool = True) -> None:
        self.url = url
        self.visible = visible

    def inspect(self, _hwnd: int) -> AddressBarState:
        return AddressBarState(self.url, self.visible)


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
    ) -> None:
        self.ControlTypeName = "EditControl" if value is not None else "WindowControl"
        self.AutomationId = "address and search bar" if value is not None else ""
        self.Name = "Address and search bar" if value is not None else ""
        self.BoundingRectangle = StubBounds(200, 50, 1200, 90)
        self.IsOffscreen = offscreen
        self._children = children or []
        self._value = value

    def GetChildren(self) -> list["StubControl"]:
        return self._children

    def GetValuePattern(self) -> StubPattern | None:
        return StubPattern(self._value) if self._value is not None else None


def configure_active_brave(monkeypatch, *, maximized: bool = True, fullscreen: bool = False) -> None:
    monkeypatch.setattr(browser_detection.win32gui, "GetForegroundWindow", lambda: 101)
    monkeypatch.setattr(browser_detection.win32gui, "IsWindowVisible", lambda _hwnd: True)
    monkeypatch.setattr(browser_detection, "_is_window_maximized", lambda _hwnd: maximized)
    monkeypatch.setattr(browser_detection.win32process, "GetWindowThreadProcessId", lambda _hwnd: (1, 202))
    monkeypatch.setattr(browser_detection, "_process_executable_name", lambda _pid: "brave.exe")
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


def test_active_maximized_brave_non_video_page_is_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/results")).detect()
    assert result.should_show
    assert result.mode is OverlayMode.STANDARD
    assert result.monitor_rect == (0, 0, 1920, 1080)


def test_non_fullscreen_watch_page_uses_watch_overlay(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/watch?v=test-id")).detect()
    assert result.mode is OverlayMode.WATCH
    assert result.monitor_rect == (0, 0, 1920, 1080)


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
    configure_active_brave(monkeypatch)
    monkeypatch.setattr(browser_detection, "_process_executable_name", lambda _pid: "notepad.exe")
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/")).detect()
    assert not result.should_show


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


def test_full_monitor_window_with_hidden_chrome_is_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1080))
    assert browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=False)


def test_full_monitor_window_with_visible_chrome_is_not_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1080))
    assert not browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=True)


def test_maximized_work_area_window_is_not_fullscreen(monkeypatch) -> None:
    monkeypatch.setattr(browser_detection, "_extended_frame_bounds", lambda _hwnd: (0, 0, 1920, 1040))
    assert not browser_detection._is_fullscreen_window(101, (0, 0, 1920, 1080), chrome_visible=False)
