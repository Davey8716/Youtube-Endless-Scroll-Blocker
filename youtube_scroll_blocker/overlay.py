from __future__ import annotations

import win32con
import win32gui
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

from .geometry import Rect


class BlackOverlay(QWidget):
    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
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
        self._native_hwnd = int(self.winId())
        self._apply_native_styles()

    def _apply_native_styles(self) -> None:
        styles = win32gui.GetWindowLong(self._native_hwnd, win32con.GWL_EXSTYLE)
        styles |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        styles &= ~win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(self._native_hwnd, win32con.GWL_EXSTYLE, styles)

    def show_at(self, rect: Rect) -> None:
        if self._last_rect == rect and self.isVisible():
            return
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
            win32con.SWP_NOACTIVATE,
        )
        self.show()
        self._apply_native_styles()
        win32gui.SetWindowPos(
            self._native_hwnd,
            win32con.HWND_TOPMOST,
            rect.left,
            rect.top,
            rect.width,
            rect.height,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )
        self.repaint()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 255))
        painter.end()
        event.accept()

    def hide_overlay(self) -> None:
        if self.isVisible():
            self.hide()
        self._last_rect = None
