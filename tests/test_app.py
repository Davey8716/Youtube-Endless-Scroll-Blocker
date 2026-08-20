from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMenu

from youtube_scroll_blocker.app import (
    PAUSE_DURATIONS_MINUTES,
    TrayRuntime,
    _pause_duration_label,
)
from youtube_scroll_blocker.browser_detection import DetectionResult
from youtube_scroll_blocker.controller import OverlayController
from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.settings import BlockerSettings
from youtube_scroll_blocker.styles import TRAY_MENU_STYLESHEET
from youtube_scroll_blocker.url_rules import OverlayMode


class FakeOverlay:
    def __init__(self) -> None:
        self.shown_at: list[tuple[Rect, int]] = []
        self.hide_count = 0

    def show_at(self, rect: Rect, owner_hwnd: int) -> bool:
        self.shown_at.append((rect, owner_hwnd))
        return True

    def hide_overlay(self) -> None:
        self.hide_count += 1


class FakeSettingsStore:
    def __init__(self, succeeds: bool = True) -> None:
        self.saved: list[BlockerSettings] = []
        self.succeeds = succeeds

    def save(self, settings: BlockerSettings) -> bool:
        self.saved.append(settings)
        return self.succeeds


class FakeStartupManager:
    def __init__(self) -> None:
        self.calls: list[bool] = []
        self.error: OSError | None = None

    def set_enabled(self, enabled: bool) -> None:
        self.calls.append(enabled)
        if self.error is not None:
            raise self.error


class FakeTray:
    def __init__(self) -> None:
        self.messages: list[tuple] = []

    def showMessage(self, *args) -> None:
        self.messages.append(args)


def test_tray_actions_reflect_and_update_individual_blockers() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(overlay, comments_overlay)
    runtime._settings_store = FakeSettingsStore()
    runtime._startup_manager = FakeStartupManager()
    runtime._start_with_windows_enabled = False
    runtime._latest_results = (DetectionResult(
        OverlayMode.WATCH,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
        player_visible=False,
    ),)
    runtime._menu = QMenu()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        assert runtime._menu.actions()[0] is runtime._start_with_windows_action
        assert runtime._start_with_windows_action.text() == "Start with Windows"
        assert runtime._start_with_windows_action.isCheckable()
        assert not runtime._start_with_windows_action.isChecked()
        assert runtime._menu.styleSheet() == TRAY_MENU_STYLESHEET
        assert "QMenu::item:disabled" in runtime._menu.styleSheet()
        assert runtime._pause_menu.title() == "Pause"
        assert tuple(runtime._pause_actions) == PAUSE_DURATIONS_MINUTES
        assert [action.text() for action in runtime._pause_menu.actions()] == [
            _pause_duration_label(minutes) for minutes in PAUSE_DURATIONS_MINUTES
        ]
        assert runtime._feed_recommendations_action.isCheckable()
        assert runtime._watch_recommendations_action.isCheckable()
        assert runtime._comments_action.isCheckable()
        assert runtime._feed_recommendations_action.isChecked()
        assert runtime._watch_recommendations_action.isChecked()
        assert runtime._comments_action.isChecked()
        assert runtime._feed_recommendations_action.text() == "Block home and discovery feeds"
        assert runtime._watch_recommendations_action.text() == "Block watch-page suggestions"

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is False
        assert runtime._feed_recommendations_action.isChecked()
        assert runtime._watch_recommendations_action.isChecked()
        assert runtime._comments_action.isChecked()
        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is True
        overlay.shown_at.clear()
        comments_overlay.shown_at.clear()

        runtime._feed_recommendations_action.setChecked(False)
        assert runtime._controller.feed_recommendations_enabled is False
        assert runtime._controller.watch_recommendations_enabled is True
        assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            feed_recommendations_enabled=False,
            watch_recommendations_enabled=True,
            comments_enabled=True,
        )

        runtime._watch_recommendations_action.setChecked(False)
        assert runtime._controller.watch_recommendations_enabled is False
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            feed_recommendations_enabled=False,
            watch_recommendations_enabled=False,
            comments_enabled=True,
        )

        runtime._comments_action.setChecked(False)
        assert runtime._controller.comments_enabled is False
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            feed_recommendations_enabled=False,
            watch_recommendations_enabled=False,
            comments_enabled=False,
        )

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is False
        assert runtime._toggle_action.text() == "Turn On"
        assert not runtime._pause_menu_action.isEnabled()
        assert not runtime._feed_recommendations_action.isChecked()
        assert not runtime._watch_recommendations_action.isChecked()
        assert not runtime._comments_action.isChecked()

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is True
        assert runtime._toggle_action.text() == "Turn Off"
        assert runtime._controller.feed_recommendations_enabled is False
        assert runtime._controller.watch_recommendations_enabled is False
        assert runtime._controller.comments_enabled is False
    finally:
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()


def test_pause_actions_disable_temporarily_and_resume_without_saving() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(overlay, comments_overlay)
    runtime._settings_store = FakeSettingsStore()
    runtime._startup_manager = FakeStartupManager()
    runtime._start_with_windows_enabled = False
    runtime._latest_results = (DetectionResult(
        OverlayMode.WATCH,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
        player_visible=False,
    ),)
    runtime._menu = QMenu()
    runtime._shutting_down = False

    try:
        runtime._build_menu()

        for minutes in PAUSE_DURATIONS_MINUTES:
            runtime._pause_actions[minutes].trigger()
            assert runtime._pause_active
            assert not runtime._controller.enabled
            assert runtime._toggle_action.text() == "Turn On"
            expected_duration = _pause_duration_label(minutes)
            assert runtime._pause_menu.title() == f"Paused for {expected_duration}"
            assert runtime._pause_menu_action.text() == f"Paused for {expected_duration}"
            assert runtime._pause_menu_action.isEnabled()
            assert runtime._pause_timer.isActive()
            assert runtime._pause_timer.interval() == minutes * 60 * 1000

        assert overlay.hide_count == len(PAUSE_DURATIONS_MINUTES)
        assert comments_overlay.hide_count == len(PAUSE_DURATIONS_MINUTES)
        assert runtime._settings_store.saved == []

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled
        assert not runtime._pause_active
        assert not runtime._pause_timer.isActive()
        assert runtime._toggle_action.text() == "Turn Off"
        assert runtime._pause_menu.title() == "Pause"
        assert runtime._pause_menu_action.text() == "Pause"
        assert runtime._pause_menu_action.isEnabled()
        assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 101)]
        assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]

        runtime._toggle_action.trigger()
        assert not runtime._controller.enabled
        assert not runtime._pause_active
        assert not runtime._pause_menu_action.isEnabled()
        assert runtime._pause_menu_action.text() == "Pause"
        runtime._start_pause(30)
        assert not runtime._pause_active
        assert not runtime._pause_timer.isActive()

        runtime._toggle_action.trigger()
        overlay.shown_at.clear()
        comments_overlay.shown_at.clear()
        runtime._pause_actions[5].trigger()
        runtime._finish_pause()
        assert runtime._controller.enabled
        assert not runtime._pause_active
        assert not runtime._pause_timer.isActive()
        assert runtime._toggle_action.text() == "Turn Off"
        assert runtime._pause_menu_action.text() == "Pause"
        assert overlay.shown_at == [(Rect(1360, 170, 536, 858), 101)]
        assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]
        assert runtime._settings_store.saved == []
    finally:
        runtime._pause_timer.stop()
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()


def test_opening_and_hovering_tray_menus_keeps_overlays_visible() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(overlay, comments_overlay)
    runtime._settings_store = FakeSettingsStore()
    runtime._startup_manager = FakeStartupManager()
    runtime._start_with_windows_enabled = False
    runtime._latest_results = (
        DetectionResult(
            OverlayMode.WATCH,
            (0, 0, 1920, 1080),
            browser_hwnd=101,
            player_visible=False,
        ),
    )
    runtime._menu = QMenu()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        runtime._handle_detection(runtime._latest_results)
        assert overlay.hide_count == 0
        assert comments_overlay.hide_count == 0

        runtime._menu.popup(QPoint(10, 10))
        app.processEvents()
        runtime._menu.setActiveAction(runtime._pause_menu_action)
        runtime._pause_menu.popup(QPoint(20, 20))
        app.processEvents()

        assert overlay.hide_count == 0
        assert comments_overlay.hide_count == 0

        runtime._handle_detection(runtime._latest_results)
        assert len(overlay.shown_at) == 2
        assert len(comments_overlay.shown_at) == 2
        assert overlay.hide_count == 0
        assert comments_overlay.hide_count == 0
    finally:
        runtime._pause_timer.stop()
        runtime._pause_menu.close()
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()


def test_startup_action_updates_registry_and_preserves_preference_in_settings() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(FakeOverlay(), FakeOverlay())
    runtime._settings_store = FakeSettingsStore()
    runtime._startup_manager = FakeStartupManager()
    runtime._start_with_windows_enabled = False
    runtime._latest_results = ()
    runtime._menu = QMenu()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        runtime._start_with_windows_action.setChecked(True)

        assert runtime._startup_manager.calls == [True]
        assert runtime._settings_store.saved[-1].start_with_windows_enabled is True

        runtime._feed_recommendations_action.setChecked(False)
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            start_with_windows_enabled=True,
            feed_recommendations_enabled=False,
            watch_recommendations_enabled=True,
            comments_enabled=True,
        )
    finally:
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()


def test_startup_registry_failure_reverts_checkbox_and_does_not_save() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(FakeOverlay(), FakeOverlay())
    runtime._settings_store = FakeSettingsStore()
    runtime._startup_manager = FakeStartupManager()
    runtime._startup_manager.error = PermissionError("denied")
    runtime._start_with_windows_enabled = False
    runtime._latest_results = ()
    runtime._menu = QMenu()
    runtime._tray = FakeTray()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        runtime._start_with_windows_action.setChecked(True)

        assert not runtime._start_with_windows_action.isChecked()
        assert runtime._start_with_windows_enabled is False
        assert runtime._settings_store.saved == []
        assert runtime._tray.messages
    finally:
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()


def test_startup_setting_save_failure_rolls_back_registry_and_checkbox() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(FakeOverlay(), FakeOverlay())
    runtime._settings_store = FakeSettingsStore(succeeds=False)
    runtime._startup_manager = FakeStartupManager()
    runtime._start_with_windows_enabled = False
    runtime._latest_results = ()
    runtime._menu = QMenu()
    runtime._tray = FakeTray()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        runtime._start_with_windows_action.setChecked(True)

        assert runtime._startup_manager.calls == [True, False]
        assert not runtime._start_with_windows_action.isChecked()
        assert runtime._start_with_windows_enabled is False
        assert runtime._tray.messages
    finally:
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()
