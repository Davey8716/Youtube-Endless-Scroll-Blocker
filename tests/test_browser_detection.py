from youtube_scroll_blocker import browser_detection
from youtube_scroll_blocker.browser_detection import BrowserDetector


class StubAddressReader:
    def __init__(self, url: str | None) -> None:
        self.url = url

    def read(self, _hwnd: int) -> str | None:
        return self.url


def configure_active_brave(monkeypatch, *, maximized: bool = True) -> None:
    monkeypatch.setattr(browser_detection.win32gui, "GetForegroundWindow", lambda: 101)
    monkeypatch.setattr(browser_detection.win32gui, "IsWindowVisible", lambda _hwnd: True)
    monkeypatch.setattr(browser_detection, "_is_window_maximized", lambda _hwnd: maximized)
    monkeypatch.setattr(browser_detection.win32process, "GetWindowThreadProcessId", lambda _hwnd: (1, 202))
    monkeypatch.setattr(browser_detection, "_process_executable_name", lambda _pid: "brave.exe")
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
    assert result.monitor_rect == (0, 0, 1920, 1080)


def test_video_page_is_not_eligible(monkeypatch) -> None:
    configure_active_brave(monkeypatch)
    result = BrowserDetector(StubAddressReader("https://www.youtube.com/watch?v=test")).detect()
    assert not result.should_show
    assert result.url == "https://www.youtube.com/watch?v=test"


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
