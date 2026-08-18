from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32con
import win32gui
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QWheelEvent
from PySide6.QtWidgets import QWidget

from .geometry import Rect


class BlackOverlay(QWidget):
    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.setPalette(palette)
        self._last_rect: Rect | None = None
        self._owner_hwnd: int | None = None
        self._native_hwnd = int(self.winId())
        self._apply_native_styles()

    def _apply_native_styles(self) -> None:
        styles = win32gui.GetWindowLong(self._native_hwnd, win32con.GWL_EXSTYLE)
        styles |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        styles &= ~(win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST)
        win32gui.SetWindowLong(self._native_hwnd, win32con.GWL_EXSTYLE, styles)

    def _set_native_owner(self, owner_hwnd: int | None) -> bool:
        owner = int(owner_hwnd or 0)
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            set_window_long_ptr = user32.SetWindowLongPtrW
            set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            set_window_long_ptr.restype = ctypes.c_ssize_t
            ctypes.set_last_error(0)
            set_window_long_ptr(self._native_hwnd, win32con.GWL_HWNDPARENT, owner)
            error = ctypes.get_last_error()
            actual_owner = win32gui.GetWindow(self._native_hwnd, win32con.GW_OWNER)
            if error or int(actual_owner or 0) != owner:
                return False
        except (AttributeError, OSError, win32gui.error):
            return False
        self._owner_hwnd = owner_hwnd
        return True

    def show_at(self, rect: Rect, owner_hwnd: int) -> bool:
        if self._last_rect == rect and self._owner_hwnd == owner_hwnd and self.isVisible():
            return True
        if not self._set_native_owner(owner_hwnd):
            self.hide_overlay()
            return False
        self._last_rect = rect

        # Position the native window before Qt shows it to avoid a flash at the
        # toolkit's default geometry. Qt must still perform the actual show so
        # its backing store is created and paint events are delivered.
        win32gui.SetWindowPos(
            self._native_hwnd,
            win32con.HWND_TOPMOST,
            rect.left,
            rect.top,
            rect.width,
            rect.height,
            win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
        )
        self.show()
        if not self._set_native_owner(owner_hwnd):
            self.hide_overlay()
            return False
        self._apply_native_styles()
        win32gui.SetWindowPos(
            self._native_hwnd,
            win32con.HWND_TOP,
            rect.left,
            rect.top,
            rect.width,
            rect.height,
            win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW,
        )
        self.repaint()
        return True

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 255))
        painter.end()
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Forward wheel input to Brave while the overlay continues blocking clicks."""
        if self._owner_hwnd is not None:
            delta = int(event.angleDelta().y())
            position = event.globalPosition()
            x = int(position.x())
            y = int(position.y())
            wheel_parameter = (delta & 0xFFFF) << 16
            screen_position = (x & 0xFFFF) | ((y & 0xFFFF) << 16)
            try:
                win32gui.PostMessage(
                    self._owner_hwnd,
                    win32con.WM_MOUSEWHEEL,
                    wheel_parameter,
                    screen_position,
                )
            except win32gui.error:
                pass
        event.accept()

    def hide_overlay(self) -> None:
        if self.isVisible():
            self.hide()
        if self._owner_hwnd is not None:
            self._set_native_owner(None)
        self._last_rect = None
