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
    recommendations_enabled: bool = True
    comments_enabled: bool = True


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
        recommendations = payload.get("recommendations_enabled")
        comments = payload.get("comments_enabled")
        return BlockerSettings(
            recommendations_enabled=(
                recommendations
                if isinstance(recommendations, bool)
                else defaults.recommendations_enabled
            ),
            comments_enabled=comments if isinstance(comments, bool) else defaults.comments_enabled,
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
