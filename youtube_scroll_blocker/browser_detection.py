from __future__ import annotations

import ctypes
import os
from collections.abc import Callable, Sequence
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

import uiautomation as auto
import win32api
import win32con
import win32gui
import win32process

from .scroll_detection import MouseWheelMonitor, ScrollInputEvent, WatchScrollTracker
from .url_rules import OverlayMode, overlay_mode_for_url


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class DetectionResult:
    mode: OverlayMode = OverlayMode.NONE
    monitor_rect: tuple[int, int, int, int] | None = None
    url: str | None = None
    browser_hwnd: int | None = None
    player_visible: bool | None = None
    theatre_mode: bool | None = None

    @property
    def should_show(self) -> bool:
        return self.mode is not OverlayMode.NONE


@dataclass(frozen=True)
class AddressBarState:
    url: str | None = None
    visible: bool = False
    theatre_mode: bool | None = None


class PlayerVisibilityTracker(Protocol):
    def visibility(
        self,
        hwnd: int,
        monitor_rect: tuple[int, int, int, int],
        url: str,
        *,
        active: bool,
        events: Sequence[ScrollInputEvent] | None = None,
    ) -> bool | None: ...

    def reset(self) -> None: ...


def _is_window_maximized(hwnd: int) -> bool:
    return win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED


def _is_brave_window(hwnd: int) -> bool:
    if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
        return False
    _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
    return _process_executable_name(process_id) == "brave.exe"


def _brave_windows() -> tuple[int, ...]:
    hwnds: list[int] = []

    def collect(hwnd: int, _extra: object) -> bool:
        try:
            if _is_brave_window(hwnd):
                hwnds.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(collect, None)
    return tuple(hwnds)


def _extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int]:
    bounds = wintypes.RECT()
    try:
        get_window_attribute = ctypes.windll.dwmapi.DwmGetWindowAttribute
        get_window_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
        get_window_attribute.restype = wintypes.LONG
        result = get_window_attribute(
            hwnd,
            9,  # DWMWA_EXTENDED_FRAME_BOUNDS
            ctypes.byref(bounds),
            ctypes.sizeof(bounds),
        )
        if result == 0:
            return bounds.left, bounds.top, bounds.right, bounds.bottom
    except (AttributeError, OSError):
        pass
    return tuple(int(value) for value in win32gui.GetWindowRect(hwnd))


def _is_fullscreen_window(
    hwnd: int,
    monitor_rect: tuple[int, int, int, int],
    chrome_visible: bool,
    tolerance: int = 2,
) -> bool:
    if chrome_visible:
        return False
    window_rect = _extended_frame_bounds(hwnd)
    return all(abs(window_value - monitor_value) <= tolerance for window_value, monitor_value in zip(window_rect, monitor_rect))


def _process_executable_name(process_id: int) -> str | None:
    handle = None
    try:
        handle = win32api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        query_name = ctypes.windll.kernel32.QueryFullProcessImageNameW
        query_name.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        query_name.restype = wintypes.BOOL
        if not query_name(int(handle), 0, buffer, ctypes.byref(size)):
            return None
        return os.path.basename(buffer.value).lower()
    except (OSError, TypeError, win32api.error):
        return None
    finally:
        if handle is not None:
            win32api.CloseHandle(handle)


def _control_value(control: object) -> str | None:
    try:
        pattern = control.GetValuePattern()  # type: ignore[attr-defined]
        value = pattern.Value if pattern is not None else None
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalized_control_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _theatre_mode_from_player(
    control: object,
    document_left: int,
    document_right: int,
) -> bool | None:
    try:
        name = _normalized_control_name(str(control.Name or ""))  # type: ignore[attr-defined]
        if name != "youtube video player":
            return None

        bounds = control.BoundingRectangle  # type: ignore[attr-defined]
        player_width = int(bounds.right) - int(bounds.left)
    except Exception:
        return None

    document_width = document_right - document_left
    if document_width <= 0 or player_width <= 0:
        return None
    return player_width / document_width >= 0.85


class BraveAddressBarReader:
    """Read Brave's omnibox without changing focus or touching the clipboard."""

    MAX_DEPTH = 8
    MAX_CONTROLS = 500
    CHROME_REGION_HEIGHT = 220
    PLAYER_MAX_DEPTH = 24
    PLAYER_MAX_CONTROLS = 500

    def _find_player_control(self, document: object) -> object | None:
        stack: list[tuple[object, int]] = [(document, 0)]
        visited = 0
        while stack and visited < self.PLAYER_MAX_CONTROLS:
            control, depth = stack.pop()
            visited += 1
            try:
                control_type = str(control.ControlTypeName).lower()  # type: ignore[attr-defined]
                name = _normalized_control_name(
                    str(control.Name or "")  # type: ignore[attr-defined]
                )
            except Exception:
                continue

            if control_type == "groupcontrol" and name == "youtube video player":
                return control

            if depth < self.PLAYER_MAX_DEPTH:
                try:
                    children = control.GetChildren()  # type: ignore[attr-defined]
                    stack.extend((child, depth + 1) for child in reversed(children))
                except Exception:
                    continue
        return None

    def _inspect_theatre_mode(
        self,
        document: object | None,
        document_left: int,
        document_right: int,
    ) -> bool | None:
        if document is None:
            return None
        player_control = self._find_player_control(document)
        if player_control is None:
            return None
        return _theatre_mode_from_player(
            player_control,
            document_left,
            document_right,
        )

    def inspect(self, hwnd: int) -> AddressBarState:
        root = auto.ControlFromHandle(hwnd)
        window_left, window_top, window_right, _window_bottom = win32gui.GetWindowRect(hwnd)
        minimum_width = min(250, max(1, (window_right - window_left) // 4))

        preferred: list[tuple[int, str, bool]] = []
        fallback: list[tuple[int, str, bool]] = []
        content_roots: list[tuple[int, int, object, int, int]] = []
        queue: list[tuple[object, int]] = [(root, 0)]
        visited = 0

        while queue and visited < self.MAX_CONTROLS:
            control, depth = queue.pop(0)
            visited += 1
            try:
                control_type = str(control.ControlTypeName).lower()
                automation_id = str(control.AutomationId or "").lower()
                name = str(control.Name or "").lower()
                bounds = control.BoundingRectangle
                visible = not bool(control.IsOffscreen)
            except Exception:
                continue

            is_chromium_content_pane = (
                control_type == "panecontrol" and name == "chrome legacy window"
            )
            if (control_type == "documentcontrol" or is_chromium_content_pane) and visible and bounds:
                document_left = int(bounds.left)
                document_right = int(bounds.right)
                document_width = document_right - document_left
                if document_width > 0:
                    priority = 1 if is_chromium_content_pane else 0
                    content_roots.append(
                        (priority, document_width, control, document_left, document_right)
                    )

            if control_type == "editcontrol" and bounds:
                top = int(bounds.top)
                width = int(bounds.width())
                in_chrome = window_top <= top <= window_top + self.CHROME_REGION_HEIGHT
                value = _control_value(control)
                if value:
                    score = top
                    is_address_bar = (
                        "address and search bar" in automation_id
                        or "address and search bar" in name
                        or "omnibox" in automation_id
                    )
                    if is_address_bar:
                        preferred.append((score, value, visible and in_chrome and width >= minimum_width))
                    elif visible and in_chrome and width >= minimum_width:
                        fallback.append((score, value, True))

            if depth < self.MAX_DEPTH:
                try:
                    queue.extend((child, depth + 1) for child in control.GetChildren())
                except Exception:
                    continue

        candidates = preferred or fallback
        if not candidates:
            return AddressBarState()
        _score, value, address_visible = min(candidates, key=lambda item: (not item[2], item[0]))
        if overlay_mode_for_url(value) is OverlayMode.WATCH:
            if content_roots:
                _priority, _width, document, document_left, document_right = max(
                    content_roots,
                    key=lambda item: (item[0], item[1]),
                )
            else:
                document = None
                document_left = window_left
                document_right = window_right
            theatre_mode = self._inspect_theatre_mode(
                document,
                document_left,
                document_right,
            )
        else:
            theatre_mode = None
        return AddressBarState(value, address_visible, theatre_mode)

    def read(self, hwnd: int) -> str | None:
        return self.inspect(hwnd).url


class BrowserDetector:
    def __init__(
        self,
        address_reader: BraveAddressBarReader | None = None,
        player_tracker: PlayerVisibilityTracker | None = None,
        *,
        player_tracker_factory: Callable[[], PlayerVisibilityTracker] | None = None,
        wheel_monitor: MouseWheelMonitor | None = None,
    ) -> None:
        self._address_reader = address_reader or BraveAddressBarReader()
        self._initial_player_tracker = player_tracker
        self._player_tracker_factory = player_tracker_factory or WatchScrollTracker
        self._player_trackers: dict[int, PlayerVisibilityTracker] = {}
        self._wheel_monitor = wheel_monitor

    def _tracker_for(self, hwnd: int) -> PlayerVisibilityTracker:
        tracker = self._player_trackers.get(hwnd)
        if tracker is not None:
            return tracker
        if self._initial_player_tracker is not None:
            tracker = self._initial_player_tracker
            self._initial_player_tracker = None
        else:
            tracker = self._player_tracker_factory()
        self._player_trackers[hwnd] = tracker
        return tracker

    def _discard_tracker(self, hwnd: int) -> None:
        tracker = self._player_trackers.pop(hwnd, None)
        if tracker is not None:
            tracker.reset()

    def detect_all(self) -> tuple[DetectionResult, ...]:
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
        except Exception:
            foreground_hwnd = 0
        try:
            hwnds = _brave_windows()
        except Exception:
            return ()

        events: Sequence[ScrollInputEvent] = ()
        if self._wheel_monitor is not None:
            events = self._wheel_monitor.drain()

        results: list[DetectionResult] = []
        watch_hwnds: set[int] = set()
        for hwnd in hwnds:
            try:
                if win32gui.IsIconic(hwnd) or not _is_window_maximized(hwnd):
                    self._discard_tracker(hwnd)
                    continue

                monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
                monitor_rect = tuple(
                    int(value) for value in win32api.GetMonitorInfo(monitor)["Monitor"]
                )
                address_bar = self._address_reader.inspect(hwnd)
                if _is_fullscreen_window(hwnd, monitor_rect, address_bar.visible):
                    self._discard_tracker(hwnd)
                    continue
                if not address_bar.visible or not address_bar.url:
                    self._discard_tracker(hwnd)
                    continue

                mode = overlay_mode_for_url(address_bar.url)
                if mode is OverlayMode.NONE:
                    self._discard_tracker(hwnd)
                    continue

                player_visible = None
                if mode is OverlayMode.WATCH:
                    watch_hwnds.add(hwnd)
                    player_visible = self._tracker_for(hwnd).visibility(
                        hwnd,
                        monitor_rect,
                        address_bar.url,
                        active=foreground_hwnd == hwnd,
                        events=events,
                    )
                else:
                    self._discard_tracker(hwnd)
                results.append(
                    DetectionResult(
                        mode,
                        monitor_rect=monitor_rect,
                        url=address_bar.url,
                        browser_hwnd=hwnd,
                        player_visible=player_visible,
                        theatre_mode=address_bar.theatre_mode,
                    )
                )
            except Exception:
                self._discard_tracker(hwnd)

        for hwnd in tuple(self._player_trackers):
            if hwnd not in watch_hwnds:
                self._discard_tracker(hwnd)
        return tuple(results)

    def detect(self) -> DetectionResult:
        results = self.detect_all()
        if not results:
            return DetectionResult()
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
        except Exception:
            foreground_hwnd = 0
        return next(
            (result for result in results if result.browser_hwnd == foreground_hwnd),
            results[0],
        )
