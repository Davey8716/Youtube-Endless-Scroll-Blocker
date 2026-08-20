from PySide6.QtWidgets import QApplication, QMenu

from youtube_scroll_blocker.app import TrayRuntime
from youtube_scroll_blocker.browser_detection import DetectionResult
from youtube_scroll_blocker.controller import OverlayController
from youtube_scroll_blocker.geometry import Rect
from youtube_scroll_blocker.settings import BlockerSettings
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
    def __init__(self) -> None:
        self.saved: list[BlockerSettings] = []

    def save(self, settings: BlockerSettings) -> bool:
        self.saved.append(settings)
        return True


def test_tray_actions_reflect_and_update_individual_blockers() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = FakeOverlay()
    comments_overlay = FakeOverlay()
    runtime = TrayRuntime.__new__(TrayRuntime)
    runtime._controller = OverlayController(overlay, comments_overlay)
    runtime._settings_store = FakeSettingsStore()
    runtime._latest_result = DetectionResult(
        OverlayMode.WATCH,
        (0, 0, 1920, 1080),
        browser_hwnd=101,
        player_visible=False,
    )
    runtime._menu = QMenu()
    runtime._shutting_down = False

    try:
        runtime._build_menu()
        assert runtime._recommendations_action.isCheckable()
        assert runtime._comments_action.isCheckable()
        assert runtime._recommendations_action.isChecked()
        assert runtime._comments_action.isChecked()

        runtime._recommendations_action.setChecked(False)
        assert runtime._controller.recommendations_enabled is False
        assert comments_overlay.shown_at == [(Rect(10, 170, 1360, 910), 101)]
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            recommendations_enabled=False,
            comments_enabled=True,
        )

        runtime._comments_action.setChecked(False)
        assert runtime._controller.comments_enabled is False
        assert runtime._settings_store.saved[-1] == BlockerSettings(
            recommendations_enabled=False,
            comments_enabled=False,
        )

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is False
        assert runtime._toggle_action.text() == "Turn On"
        assert not runtime._recommendations_action.isChecked()
        assert not runtime._comments_action.isChecked()

        runtime._toggle_action.trigger()
        assert runtime._controller.enabled is True
        assert runtime._toggle_action.text() == "Turn Off"
        assert runtime._controller.recommendations_enabled is False
        assert runtime._controller.comments_enabled is False
    finally:
        runtime._menu.close()
        runtime._menu.deleteLater()
        app.processEvents()
