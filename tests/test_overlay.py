import win32con
import win32gui
from PySide6.QtWidgets import QApplication, QWidget

from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.overlay import BlackOverlay


class StubPoint:
    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y


class StubWheelEvent:
    def __init__(self, delta: int, x: int, y: int) -> None:
        self._delta = StubPoint(0, delta)
        self._position = StubPoint(x, y)
        self.accepted = False

    def angleDelta(self) -> StubPoint:
        return self._delta

    def globalPosition(self) -> StubPoint:
        return self._position

    def accept(self) -> None:
        self.accepted = True


def test_overlay_is_visible_positioned_black_and_click_blocking() -> None:
    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    owner.show()
    overlay = BlackOverlay()
    requested = Rect(20, 20, 80, 60)

    try:
        app.processEvents()
        owner_hwnd = int(owner.winId())
        assert overlay.show_at(requested, owner_hwnd)
        app.processEvents()

        hwnd = int(overlay.winId())
        assert overlay.isVisible()
        assert win32gui.IsWindowVisible(hwnd)
        assert win32gui.GetWindowRect(hwnd) == (20, 20, 100, 80)
        assert win32gui.GetWindow(hwnd, win32con.GW_OWNER) == owner_hwnd

        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        assert styles & win32con.WS_EX_NOACTIVATE
        assert styles & win32con.WS_EX_TOOLWINDOW
        assert not styles & win32con.WS_EX_TRANSPARENT
        assert not styles & win32con.WS_EX_TOPMOST

        image = overlay.grab().toImage()
        center = image.pixelColor(image.width() // 2, image.height() // 2)
        assert center.red() == 0
        assert center.green() == 0
        assert center.blue() == 0
        assert center.alpha() == 255

        overlay.hide_overlay()
        app.processEvents()
        assert not overlay.isVisible()
        assert not win32gui.IsWindowVisible(hwnd)
        assert not win32gui.GetWindow(hwnd, win32con.GW_OWNER)
    finally:
        overlay.close()
        owner.close()
        app.processEvents()


def test_overlay_forwards_wheel_input_to_owner(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    overlay = BlackOverlay()
    event = StubWheelEvent(-120, 800, 500)
    messages: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(
        win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: messages.append((hwnd, message, wparam, lparam)),
    )

    try:
        overlay._owner_hwnd = 101
        overlay.wheelEvent(event)  # type: ignore[arg-type]
        assert messages == [
            (
                101,
                win32con.WM_MOUSEWHEEL,
                0xFF880000,
                800 | (500 << 16),
            )
        ]
        assert event.accepted
    finally:
        overlay._owner_hwnd = None
        overlay.close()
        app.processEvents()
