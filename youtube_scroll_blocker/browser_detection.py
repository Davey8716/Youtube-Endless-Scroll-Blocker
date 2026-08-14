from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

import uiautomation as auto
import win32api
import win32con
import win32gui
import win32process

from .url_rules import OverlayMode, overlay_mode_for_url


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class DetectionResult:
    mode: OverlayMode = OverlayMode.NONE
    monitor_rect: tuple[int, int, int, int] | None = None
    url: str | None = None

    @property
    def should_show(self) -> bool:
        return self.mode is not OverlayMode.NONE


@dataclass(frozen=True)
class AddressBarState:
    url: str | None = None
    visible: bool = False


def _is_window_maximized(hwnd: int) -> bool:
    return win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED


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


class BraveAddressBarReader:
    """Read Brave's omnibox without changing focus or touching the clipboard."""

    MAX_DEPTH = 8
    MAX_CONTROLS = 500
    CHROME_REGION_HEIGHT = 220

    def inspect(self, hwnd: int) -> AddressBarState:
        root = auto.ControlFromHandle(hwnd)
        window_left, window_top, window_right, _window_bottom = win32gui.GetWindowRect(hwnd)
        minimum_width = min(250, max(1, (window_right - window_left) // 4))

        preferred: list[tuple[int, str, bool]] = []
        fallback: list[tuple[int, str, bool]] = []
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
        _score, value, visible = min(candidates, key=lambda item: (not item[2], item[0]))
        return AddressBarState(value, visible)

    def read(self, hwnd: int) -> str | None:
        return self.inspect(hwnd).url


class BrowserDetector:
    def __init__(self, address_reader: BraveAddressBarReader | None = None) -> None:
        self._address_reader = address_reader or BraveAddressBarReader()

    def detect(self) -> DetectionResult:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or not win32gui.IsWindowVisible(hwnd):
                return DetectionResult()

            _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if _process_executable_name(process_id) != "brave.exe":
                return DetectionResult()
            if not _is_window_maximized(hwnd):
                return DetectionResult()

            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            monitor_rect = tuple(int(value) for value in win32api.GetMonitorInfo(monitor)["Monitor"])
            address_bar = self._address_reader.inspect(hwnd)
            if _is_fullscreen_window(hwnd, monitor_rect, address_bar.visible):
                return DetectionResult(url=address_bar.url)
            if not address_bar.visible or not address_bar.url:
                return DetectionResult(url=address_bar.url)

            mode = overlay_mode_for_url(address_bar.url)
            if mode is OverlayMode.NONE:
                return DetectionResult(url=address_bar.url)
            return DetectionResult(mode, monitor_rect=monitor_rect, url=address_bar.url)
        except Exception:
            return DetectionResult()
