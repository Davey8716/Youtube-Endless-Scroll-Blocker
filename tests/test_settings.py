import json
import os
from pathlib import Path

from youtube_scroll_blocker.settings import (
    BlockerSettings,
    SettingsStore,
    default_settings_path,
)


def test_first_run_uses_enabled_defaults(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "missing.json").load() == BlockerSettings()


def test_settings_round_trip_uses_atomic_replace(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "app" / "settings.json"
    store = SettingsStore(path)
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def tracked_replace(source: Path, destination: Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", tracked_replace)
    settings = BlockerSettings(recommendations_enabled=False, comments_enabled=True)

    assert store.save(settings)
    assert store.load() == settings
    assert replacements == [(path.with_suffix(".json.tmp"), path)]


def test_partial_settings_use_defaults_for_missing_values(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"recommendations_enabled": False}), encoding="utf-8")
    assert SettingsStore(path).load() == BlockerSettings(
        recommendations_enabled=False,
        comments_enabled=True,
    )


def test_malformed_or_wrongly_typed_settings_use_defaults(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    assert SettingsStore(malformed).load() == BlockerSettings()

    wrong_types = tmp_path / "wrong-types.json"
    wrong_types.write_text(
        json.dumps({"recommendations_enabled": "no", "comments_enabled": 0}),
        encoding="utf-8",
    )
    assert SettingsStore(wrong_types).load() == BlockerSettings()


def test_default_path_uses_local_app_data() -> None:
    assert default_settings_path(
        {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}
    ) == Path(r"C:\Users\test\AppData\Local") / "YouTube Endless Scroll Blocker" / "settings.json"


def test_default_path_falls_back_to_per_user_app_data_when_environment_is_missing(
    tmp_path: Path,
) -> None:
    assert default_settings_path({}, home=tmp_path) == (
        tmp_path / "AppData" / "Local" / "YouTube Endless Scroll Blocker" / "settings.json"
    )


def test_save_failure_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    monkeypatch.setattr(os, "replace", lambda _source, _destination: (_ for _ in ()).throw(OSError()))
    assert not store.save(BlockerSettings())
