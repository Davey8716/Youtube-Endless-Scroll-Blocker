from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import uiautomation as auto
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .browser_detection import BrowserDetector, DetectionResult
from .controller import OverlayController
from .mutex import SingleInstanceMutex
from .overlay import BlackOverlay
from .scroll_detection import MouseWheelMonitor, WatchScrollTracker


APP_NAME = "YouTube Endless Scroll Blocker"
POLL_INTERVAL_SECONDS = 0.25


def resource_path(relative_path: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / relative_path


class DetectionThread(QThread):
    result_ready = Signal(object)

    def __init__(self, detector: BrowserDetector, interval: float = POLL_INTERVAL_SECONDS) -> None:
        super().__init__()
        self._detector = detector
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        with auto.UIAutomationInitializerInThread():
            while not self._stop_event.is_set():
                self.result_ready.emit(self._detector.detect())
                self._stop_event.wait(self._interval)

    def stop(self) -> None:
        self._stop_event.set()


class TrayRuntime:
    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._shutting_down = False
        self._overlay = BlackOverlay()
        self._comments_overlay = BlackOverlay()
        self._controller = OverlayController(self._overlay, self._comments_overlay)
        self._latest_result = DetectionResult()

        icon = QIcon(str(resource_path("assets/app.ico")))
        self._tray = QSystemTrayIcon(icon, app)
        self._tray.setToolTip(APP_NAME)
        self._menu = QMenu()
        self._toggle_action = QAction("Turn Off", self._menu)
        self._exit_action = QAction("Exit", self._menu)
        self._menu.addAction(self._toggle_action)
        self._menu.addSeparator()
        self._menu.addAction(self._exit_action)
        self._tray.setContextMenu(self._menu)

        self._toggle_action.triggered.connect(self._toggle)
        self._exit_action.triggered.connect(self.shutdown)
        self._menu.aboutToShow.connect(self._menu_opened)
        self._menu.aboutToHide.connect(self._menu_closed)

        self._wheel_monitor = MouseWheelMonitor()
        self._wheel_monitor.start()
        self._detector_thread = DetectionThread(
            BrowserDetector(player_tracker=WatchScrollTracker(self._wheel_monitor))
        )
        self._detector_thread.result_ready.connect(self._handle_detection)
        self._detector_thread.start()
        self._tray.show()

    def _toggle(self) -> None:
        self._controller.set_enabled(not self._controller.enabled)
        self._toggle_action.setText("Turn Off" if self._controller.enabled else "Turn On")
        if self._controller.enabled:
            self._controller.handle_detection(self._latest_result)

    def _menu_opened(self) -> None:
        self._controller.set_menu_open(True)

    def _menu_closed(self) -> None:
        QTimer.singleShot(100, self._restore_after_menu)

    def _restore_after_menu(self) -> None:
        if self._shutting_down:
            return
        self._controller.set_menu_open(False)
        self._controller.handle_detection(self._latest_result)

    def _handle_detection(self, result: DetectionResult) -> None:
        self._latest_result = result
        self._controller.handle_detection(result)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._controller.hide()
        self._tray.hide()
        self._detector_thread.stop()
        self._detector_thread.wait(3000)
        self._wheel_monitor.stop()
        self._comments_overlay.close()
        self._overlay.close()
        self._app.quit()


def main() -> int:
    if os.name != "nt":
        print(f"{APP_NAME} only supports Windows.", file=sys.stderr)
        return 1

    with SingleInstanceMutex() as mutex:
        if not mutex.acquired:
            return 0

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setQuitOnLastWindowClosed(False)
        runtime = TrayRuntime(app)
        app.aboutToQuit.connect(runtime.shutdown)
        return app.exec()
