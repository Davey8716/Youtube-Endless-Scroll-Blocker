from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


SETTINGS_DIRECTORY_NAME = "YouTube Endless Scroll Blocker"
SETTINGS_FILE_NAME = "settings.json"


@dataclass(frozen=True)
class BlockerSettings:
    start_with_windows_enabled: bool = False
    feed_recommendations_enabled: bool = True
    watch_recommendations_enabled: bool = True
    comments_enabled: bool = True


def _boolean_setting(
    payload: Mapping[str, object],
    key: str,
    default: bool,
    fallback: bool | None = None,
) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return fallback if fallback is not None else default


def default_settings_path(
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    environment = os.environ if environ is None else environ
    local_app_data = environment.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else (home or Path.home()) / "AppData" / "Local"
    return base / SETTINGS_DIRECTORY_NAME / SETTINGS_FILE_NAME


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()

    def load(self) -> BlockerSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return BlockerSettings()
        if not isinstance(payload, dict):
            return BlockerSettings()

        defaults = BlockerSettings()
        legacy_recommendations = payload.get("recommendations_enabled")
        legacy_value = legacy_recommendations if isinstance(legacy_recommendations, bool) else None
        return BlockerSettings(
            start_with_windows_enabled=_boolean_setting(
                payload,
                "start_with_windows_enabled",
                defaults.start_with_windows_enabled,
            ),
            feed_recommendations_enabled=_boolean_setting(
                payload,
                "feed_recommendations_enabled",
                defaults.feed_recommendations_enabled,
                legacy_value,
            ),
            watch_recommendations_enabled=_boolean_setting(
                payload,
                "watch_recommendations_enabled",
                defaults.watch_recommendations_enabled,
                legacy_value,
            ),
            comments_enabled=_boolean_setting(
                payload,
                "comments_enabled",
                defaults.comments_enabled,
            ),
        )

    def save(self, settings: BlockerSettings) -> bool:
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(asdict(settings), indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self.path)
            return True
        except OSError:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
