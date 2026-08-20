from __future__ import annotations

import ctypes
import threading
from collections import deque
from collections.abc import Sequence
from ctypes import wintypes
from dataclasses import dataclass

import uiautomation as auto


WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012
WHEEL_DELTA = 120
SPI_GETWHEELSCROLLLINES = 0x0068
WHEEL_PAGESCROLL = 0xFFFFFFFF
PIXELS_PER_SCROLL_LINE = 40.0
DEFAULT_SCROLL_LINES = 3
SCROLLBAR_ZONE_WIDTH = 24
SCROLLBAR_DRAG_SCALE = 40.0

PLAYER_BOTTOM = 761
FALLBACK_CONTENT_TOP = 110
SCROLL_SAMPLE_X = 810
SCROLL_SAMPLE_Y = 900
MAX_ANCESTORS = 15


@dataclass(frozen=True)
class WheelEvent:
    delta: int
    x: int
    y: int


@dataclass(frozen=True)
class ScrollbarDragEvent:
    delta_y: int
    x: int
    y: int


ScrollInputEvent = WheelEvent | ScrollbarDragEvent


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MouseWheelMonitor:
    """Collect global vertical mouse-wheel events on a dedicated Win32 hook thread."""

    def __init__(self) -> None:
        self._events: deque[ScrollInputEvent] = deque()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook: int | None = None
        self._callback = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="mouse-wheel-monitor", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)

    def stop(self) -> None:
        thread = self._thread
        thread_id = self._thread_id
        if thread is None:
            return
        if thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        thread.join(2.0)
        self._thread = None
        self._thread_id = None

    def drain(self) -> list[ScrollInputEvent]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events

    def record(self, event: ScrollInputEvent) -> None:
        """Record an event; separated from the hook callback for deterministic tests."""
        with self._lock:
            self._events.append(event)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        drag_last_y: int | None = None

        def low_level_mouse_proc(code: int, message: int, data_pointer: int) -> int:
            nonlocal drag_last_y
            if code >= 0 and message == WM_MOUSEWHEEL:
                data = ctypes.cast(data_pointer, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                delta = ctypes.c_short((int(data.mouseData) >> 16) & 0xFFFF).value
                self.record(WheelEvent(delta, int(data.pt.x), int(data.pt.y)))
            elif code >= 0 and message == WM_LBUTTONDOWN:
                data = ctypes.cast(data_pointer, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                drag_last_y = int(data.pt.y)
            elif code >= 0 and message == WM_MOUSEMOVE and drag_last_y is not None:
                data = ctypes.cast(data_pointer, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                current_y = int(data.pt.y)
                delta_y = current_y - drag_last_y
                if delta_y:
                    self.record(ScrollbarDragEvent(delta_y, int(data.pt.x), current_y))
                    drag_last_y = current_y
            elif code >= 0 and message == WM_LBUTTONUP:
                drag_last_y = None
            return int(user32.CallNextHookEx(self._hook or 0, code, message, data_pointer))

        self._callback = callback_type(low_level_mouse_proc)
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            callback_type,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._hook = int(user32.SetWindowsHookExW(WH_MOUSE_LL, self._callback, None, 0) or 0)
        self._ready.set()
        if not self._hook:
            return

        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            self._callback = None


def configured_scroll_lines() -> int:
    lines = wintypes.UINT()
    success = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETWHEELSCROLLLINES,
        0,
        ctypes.byref(lines),
        0,
    )
    if not success or lines.value in {0, WHEEL_PAGESCROLL}:
        return DEFAULT_SCROLL_LINES
    return int(lines.value)


class WheelScrollAccumulator:
    def __init__(self, scroll_lines: int | None = None) -> None:
        self._scroll_lines = scroll_lines if scroll_lines is not None else configured_scroll_lines()
        self._context: tuple[int, str] | None = None
        self._offset = 0.0
        self._has_input = False

    def reset(self) -> None:
        self._context = None
        self._offset = 0.0
        self._has_input = False

    def update(
        self,
        events: list[ScrollInputEvent],
        *,
        hwnd: int,
        url: str,
        monitor_rect: tuple[int, int, int, int],
        active: bool,
        content_top: int,
    ) -> float | None:
        context = (hwnd, url)
        if context != self._context:
            self._context = context
            self._offset = 0.0
            self._has_input = False

        if not active:
            return self._offset if self._has_input else None

        left, top, right, bottom = monitor_rect
        page_top = top + content_top
        for event in events:
            if not (left <= event.x < right and page_top <= event.y < bottom):
                continue
            if isinstance(event, WheelEvent):
                pixel_delta = (
                    -float(event.delta)
                    / WHEEL_DELTA
                    * self._scroll_lines
                    * PIXELS_PER_SCROLL_LINE
                )
            elif event.x >= right - SCROLLBAR_ZONE_WIDTH:
                pixel_delta = float(event.delta_y) * SCROLLBAR_DRAG_SCALE
            else:
                continue
            self._offset = max(0.0, self._offset + pixel_delta)
            self._has_input = True
        return self._offset if self._has_input else None


@dataclass(frozen=True)
class DocumentScrollState:
    offset: float
    content_top: int


class DocumentScrollReader:
    def __init__(self) -> None:
        self._context: tuple[int, str] | None = None
        self._control: object | None = None

    def reset(self) -> None:
        self._context = None
        self._control = None

    def read(
        self,
        hwnd: int,
        monitor_rect: tuple[int, int, int, int],
        url: str,
    ) -> DocumentScrollState | None:
        context = (hwnd, url)
        if context != self._context:
            self._context = context
            self._control = self._locate(monitor_rect)
        elif self._control is None:
            self._control = self._locate(monitor_rect)

        if self._control is None:
            return None
        try:
            pattern = self._control.GetScrollPattern()  # type: ignore[attr-defined]
            if not pattern or not bool(pattern.VerticallyScrollable):
                return None
            scroll_percent = float(pattern.VerticalScrollPercent)
            view_percent = float(pattern.VerticalViewSize)
            if scroll_percent < 0 or not 0 < view_percent < 100:
                return None

            bounds = self._control.BoundingRectangle  # type: ignore[attr-defined]
            monitor_left, monitor_top, monitor_right, monitor_bottom = monitor_rect
            content_top_screen = min(max(int(bounds.top), monitor_top), monitor_bottom)
            viewport_height = max(1, monitor_bottom - content_top_screen)
            total_height = viewport_height * 100.0 / view_percent
            maximum_scroll = max(0.0, total_height - viewport_height)
            offset = maximum_scroll * scroll_percent / 100.0
            return DocumentScrollState(offset, content_top_screen - monitor_top)
        except Exception:
            self._control = None
            return None

    def _locate(self, monitor_rect: tuple[int, int, int, int]) -> object | None:
        left, top, _right, _bottom = monitor_rect
        control = auto.ControlFromPoint(left + SCROLL_SAMPLE_X, top + SCROLL_SAMPLE_Y)
        for _depth in range(MAX_ANCESTORS):
            if control is None:
                return None
            try:
                pattern = control.GetScrollPattern()
                if pattern and bool(pattern.VerticallyScrollable):
                    return control
                parent = control.GetParentControl()
            except Exception:
                return None
            if parent is None or parent is control:
                return None
            control = parent
        return None


class WatchScrollTracker:
    """Report whether the original main player still intersects the viewport."""

    def __init__(
        self,
        wheel_monitor: MouseWheelMonitor | None = None,
        document_reader: DocumentScrollReader | None = None,
        accumulator: WheelScrollAccumulator | None = None,
    ) -> None:
        self._wheel_monitor = wheel_monitor
        self._document_reader = document_reader or DocumentScrollReader()
        self._accumulator = accumulator or WheelScrollAccumulator()
        self._last_context: tuple[int, str] | None = None
        self._last_visibility: bool | None = None

    def reset(self) -> None:
        self._document_reader.reset()
        self._accumulator.reset()
        self._last_context = None
        self._last_visibility = None
        if self._wheel_monitor is not None:
            self._wheel_monitor.drain()

    def visibility(
        self,
        hwnd: int,
        monitor_rect: tuple[int, int, int, int],
        url: str,
        *,
        active: bool,
        events: Sequence[ScrollInputEvent] | None = None,
    ) -> bool | None:
        context = (hwnd, url)
        if context != self._last_context:
            self._last_context = context
            self._last_visibility = None
        document_state = self._document_reader.read(hwnd, monitor_rect, url) if active else None
        content_top = document_state.content_top if document_state else FALLBACK_CONTENT_TOP
        if events is None:
            events = self._wheel_monitor.drain() if self._wheel_monitor is not None else []
        wheel_offset = self._accumulator.update(
            list(events),
            hwnd=hwnd,
            url=url,
            monitor_rect=monitor_rect,
            active=active,
            content_top=content_top,
        )

        if wheel_offset is not None:
            scroll_offset = wheel_offset
        elif document_state is not None:
            scroll_offset = document_state.offset
        else:
            return self._last_visibility

        threshold = max(1, PLAYER_BOTTOM - content_top)
        self._last_visibility = scroll_offset < threshold
        return self._last_visibility
