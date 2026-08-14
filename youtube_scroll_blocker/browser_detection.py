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

from .url_rules import should_show_overlay


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class DetectionResult:
    should_show: bool
    monitor_rect: tuple[int, int, int, int] | None = None
    url: str | None = None


def _is_window_maximized(hwnd: int) -> bool:
    return win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED


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

    def read(self, hwnd: int) -> str | None:
        root = auto.ControlFromHandle(hwnd)
        window_left, window_top, window_right, _window_bottom = win32gui.GetWindowRect(hwnd)
        minimum_width = min(250, max(1, (window_right - window_left) // 4))

        preferred: list[tuple[int, str]] = []
        fallback: list[tuple[int, str]] = []
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
            except Exception:
                continue

            if control_type == "editcontrol" and bounds:
                top = int(bounds.top)
                width = int(bounds.width())
                in_chrome = window_top <= top <= window_top + self.CHROME_REGION_HEIGHT
                if in_chrome and width >= minimum_width:
                    value = _control_value(control)
                    if value:
                        score = top
                        is_address_bar = (
                            "address and search bar" in automation_id
                            or "address and search bar" in name
                            or "omnibox" in automation_id
                        )
                        (preferred if is_address_bar else fallback).append((score, value))

            if depth < self.MAX_DEPTH:
                try:
                    queue.extend((child, depth + 1) for child in control.GetChildren())
                except Exception:
                    continue

        candidates = preferred or fallback
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]


class BrowserDetector:
    def __init__(self, address_reader: BraveAddressBarReader | None = None) -> None:
        self._address_reader = address_reader or BraveAddressBarReader()

    def detect(self) -> DetectionResult:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or not win32gui.IsWindowVisible(hwnd):
                return DetectionResult(False)

            _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if _process_executable_name(process_id) != "brave.exe":
                return DetectionResult(False)
            if not _is_window_maximized(hwnd):
                return DetectionResult(False)

            url = self._address_reader.read(hwnd)
            if not should_show_overlay(url):
                return DetectionResult(False, url=url)

            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            monitor_rect = tuple(int(value) for value in win32api.GetMonitorInfo(monitor)["Monitor"])
            return DetectionResult(True, monitor_rect=monitor_rect, url=url)
        except Exception:
            return DetectionResult(False)
