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
from .settings import BlockerSettings, SettingsStore
from .startup import StartupManager


APP_NAME = "YouTube Endless Scroll Blocker"
POLL_INTERVAL_SECONDS = 0.25
PAUSE_DURATIONS_MINUTES = (5, 15, 30,60,120)
TRAY_MENU_STYLESHEET = """
QMenu {
    background-color: #0b1f3a;
    color: #f4f7fb;
    border: 1px solid #294867;
    padding: 6px;
}
QMenu::item {
    padding: 7px 28px 7px 26px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #1d4f7a;
}
QMenu::item:checked {
    background-color: #163f66;
}
QMenu::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #8aa4bf;
    border-radius: 2px;
}
QMenu::indicator:checked {
    background-color: #38bdf8;
    border-color: #bae6fd;
}
QMenu::separator {
    height: 1px;
    background-color: #294867;
    margin: 5px 8px;
}
"""


def _pause_duration_label(minutes: int) -> str:
    if minutes >= 60:
        hours = minutes / 60
        unit = "hour" if hours == 1 else "hours"
        return f"{hours:g} {unit}"
    return f"{minutes} minutes"


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
    def __init__(
        self,
        app: QApplication,
        settings_store: SettingsStore | None = None,
        startup_manager: StartupManager | None = None,
    ) -> None:
        self._app = app
        self._shutting_down = False
        self._settings_store = settings_store or SettingsStore()
        self._startup_manager = startup_manager or StartupManager()
        settings = self._settings_store.load()
        self._start_with_windows_enabled = settings.start_with_windows_enabled
        self._overlay = BlackOverlay()
        self._comments_overlay = BlackOverlay()
        self._controller = OverlayController(
            self._overlay,
            self._comments_overlay,
            feed_recommendations_enabled=settings.feed_recommendations_enabled,
            watch_recommendations_enabled=settings.watch_recommendations_enabled,
            comments_enabled=settings.comments_enabled,
        )
        self._latest_result = DetectionResult()

        icon = QIcon(str(resource_path("assets/app.ico")))
        self._tray = QSystemTrayIcon(icon, app)
        self._tray.setToolTip(APP_NAME)
        self._menu = QMenu()
        self._build_menu()
        self._tray.setContextMenu(self._menu)

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
        self._synchronize_startup_registration()

    def _build_menu(self) -> None:
        self._menu.setStyleSheet(TRAY_MENU_STYLESHEET)
        self._pause_active = False
        self._pause_minutes: int | None = None
        self._pause_timer = QTimer(self._menu)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._finish_pause)
        self._start_with_windows_action = QAction("Start with Windows", self._menu)
        self._start_with_windows_action.setCheckable(True)
        self._start_with_windows_action.setChecked(self._start_with_windows_enabled)
        self._toggle_action = QAction("Turn Off", self._menu)
        self._pause_menu = QMenu("Pause", self._menu)
        self._pause_actions: dict[int, QAction] = {}
        for minutes in PAUSE_DURATIONS_MINUTES:
            action = QAction(_pause_duration_label(minutes), self._pause_menu)
            action.triggered.connect(
                lambda checked=False, duration=minutes: self._start_pause(duration)
            )
            self._pause_menu.addAction(action)
            self._pause_actions[minutes] = action
        self._feed_recommendations_action = QAction("Block home and discovery feeds", self._menu)
        self._feed_recommendations_action.setCheckable(True)
        self._feed_recommendations_action.setChecked(
            self._controller.feed_recommendations_enabled
        )
        self._watch_recommendations_action = QAction("Block watch-page suggestions", self._menu)
        self._watch_recommendations_action.setCheckable(True)
        self._watch_recommendations_action.setChecked(
            self._controller.watch_recommendations_enabled
        )
        self._comments_action = QAction("Block comments section", self._menu)
        self._comments_action.setCheckable(True)
        self._comments_action.setChecked(self._controller.comments_enabled)
        self._exit_action = QAction("Close App", self._menu)
        self._menu.addAction(self._start_with_windows_action)
        self._menu.addSeparator()
        self._menu.addAction(self._toggle_action)
        self._pause_menu_action = self._menu.addMenu(self._pause_menu)
        self._menu.addSeparator()
        self._menu.addAction(self._feed_recommendations_action)
        self._menu.addAction(self._watch_recommendations_action)
        self._menu.addAction(self._comments_action)
        self._menu.addSeparator()
        self._menu.addAction(self._exit_action)

        self._start_with_windows_action.toggled.connect(self._toggle_start_with_windows)
        self._toggle_action.triggered.connect(self._toggle)
        self._feed_recommendations_action.toggled.connect(self._toggle_feed_recommendations)
        self._watch_recommendations_action.toggled.connect(self._toggle_watch_recommendations)
        self._comments_action.toggled.connect(self._toggle_comments)
        self._exit_action.triggered.connect(self.shutdown)

    def _toggle(self) -> None:
        if self._controller.enabled:
            self._cancel_pause()
            self._controller.set_enabled(False)
        else:
            self._cancel_pause()
            self._controller.set_enabled(True)
            self._controller.handle_detection(self._latest_result)
        self._sync_master_controls()

    def _start_pause(self, minutes: int) -> None:
        if not self._controller.enabled and not self._pause_active:
            return
        self._pause_active = True
        self._pause_minutes = minutes
        self._controller.set_enabled(False)
        self._pause_timer.start(minutes * 60 * 1000)
        self._sync_master_controls()

    def _cancel_pause(self) -> None:
        self._pause_timer.stop()
        self._pause_active = False
        self._pause_minutes = None

    def _finish_pause(self) -> None:
        if not self._pause_active:
            return
        self._pause_timer.stop()
        self._pause_active = False
        self._pause_minutes = None
        self._controller.set_enabled(True)
        self._sync_master_controls()
        self._controller.handle_detection(self._latest_result)

    def _sync_master_controls(self) -> None:
        self._toggle_action.setText("Turn Off" if self._controller.enabled else "Turn On")
        if self._pause_active and self._pause_minutes is not None:
            duration = _pause_duration_label(self._pause_minutes)
            self._pause_menu.setTitle(f"Paused for {duration}")
        else:
            self._pause_menu.setTitle("Pause")
        self._pause_menu_action.setEnabled(self._controller.enabled or self._pause_active)

    def _toggle_start_with_windows(self, enabled: bool) -> None:
        previous = self._start_with_windows_enabled
        try:
            self._startup_manager.set_enabled(enabled)
        except OSError:
            self._set_startup_action_checked(previous)
            self._show_startup_error()
            return

        self._start_with_windows_enabled = enabled
        if self._save_blocker_settings():
            return

        try:
            self._startup_manager.set_enabled(previous)
        except OSError:
            pass
        self._start_with_windows_enabled = previous
        self._set_startup_action_checked(previous)
        self._show_startup_error("The preference could not be saved.")

    def _set_startup_action_checked(self, checked: bool) -> None:
        self._start_with_windows_action.blockSignals(True)
        self._start_with_windows_action.setChecked(checked)
        self._start_with_windows_action.blockSignals(False)

    def _synchronize_startup_registration(self) -> None:
        try:
            self._startup_manager.set_enabled(self._start_with_windows_enabled)
        except OSError:
            self._show_startup_error()

    def _show_startup_error(self, detail: str = "Windows startup could not be updated.") -> None:
        self._tray.showMessage(
            APP_NAME,
            detail,
            QSystemTrayIcon.MessageIcon.Warning,
        )

    def _toggle_feed_recommendations(self, enabled: bool) -> None:
        self._controller.set_feed_recommendations_enabled(enabled)
        self._save_blocker_settings()
        self._controller.handle_detection(self._latest_result)

    def _toggle_watch_recommendations(self, enabled: bool) -> None:
        self._controller.set_watch_recommendations_enabled(enabled)
        self._save_blocker_settings()
        self._controller.handle_detection(self._latest_result)

    def _toggle_comments(self, enabled: bool) -> None:
        self._controller.set_comments_enabled(enabled)
        self._save_blocker_settings()
        self._controller.handle_detection(self._latest_result)

    def _save_blocker_settings(self) -> bool:
        return self._settings_store.save(
            BlockerSettings(
                start_with_windows_enabled=self._start_with_windows_enabled,
                feed_recommendations_enabled=self._controller.feed_recommendations_enabled,
                watch_recommendations_enabled=self._controller.watch_recommendations_enabled,
                comments_enabled=self._controller.comments_enabled,
            )
        )

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
        self._pause_timer.stop()
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
