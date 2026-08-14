import win32con
import win32gui
from PySide6.QtWidgets import QApplication, QWidget

from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.overlay import BlackOverlay


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
