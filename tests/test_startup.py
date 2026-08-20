from pathlib import Path

import pytest

from youtube_scroll_blocker import startup


class FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback) -> None:
        return None


def test_frozen_startup_command_quotes_executable_path() -> None:
    assert startup.startup_command(
        executable=Path(r"C:\Program Files\Scroll Blocker\Blocker.exe"),
        frozen=True,
    ) == r'"C:\Program Files\Scroll Blocker\Blocker.exe"'


def test_source_startup_command_quotes_interpreter_and_entry_point() -> None:
    assert startup.startup_command(
        executable=Path(r"C:\Program Files\Python 3.10\python.exe"),
        entry_point=Path(r"C:\My Projects\Scroll Blocker\main.py"),
        frozen=False,
    ) == (
        r'"C:\Program Files\Python 3.10\python.exe" '
        r'"C:\My Projects\Scroll Blocker\main.py"'
    )


def test_enabling_writes_owned_current_user_run_value(monkeypatch) -> None:
    key = FakeKey()
    created: list[tuple] = []
    written: list[tuple] = []
    monkeypatch.setattr(
        startup.winreg,
        "CreateKeyEx",
        lambda *args: created.append(args) or key,
    )
    monkeypatch.setattr(
        startup.winreg,
        "SetValueEx",
        lambda *args: written.append(args),
    )

    startup.StartupManager("expected command").set_enabled(True)

    assert created == [
        (
            startup.winreg.HKEY_CURRENT_USER,
            startup.RUN_KEY_PATH,
            0,
            startup.winreg.KEY_SET_VALUE,
        )
    ]
    assert written == [
        (key, startup.RUN_VALUE_NAME, 0, startup.winreg.REG_SZ, "expected command")
    ]


def test_disabling_removes_only_owned_run_value(monkeypatch) -> None:
    key = FakeKey()
    opened: list[tuple] = []
    deleted: list[tuple] = []
    monkeypatch.setattr(
        startup.winreg,
        "OpenKey",
        lambda *args: opened.append(args) or key,
    )
    monkeypatch.setattr(
        startup.winreg,
        "DeleteValue",
        lambda *args: deleted.append(args),
    )

    startup.StartupManager("expected command").set_enabled(False)

    assert opened == [
        (
            startup.winreg.HKEY_CURRENT_USER,
            startup.RUN_KEY_PATH,
            0,
            startup.winreg.KEY_SET_VALUE,
        )
    ]
    assert deleted == [(key, startup.RUN_VALUE_NAME)]


def test_disabling_tolerates_missing_run_key(monkeypatch) -> None:
    def missing_key(*_args):
        raise FileNotFoundError

    monkeypatch.setattr(startup.winreg, "OpenKey", missing_key)
    startup.StartupManager("expected command").set_enabled(False)


def test_registry_errors_propagate_to_the_ui_layer(monkeypatch) -> None:
    def denied(*_args):
        raise PermissionError("denied")

    monkeypatch.setattr(startup.winreg, "CreateKeyEx", denied)
    with pytest.raises(PermissionError):
        startup.StartupManager("expected command").set_enabled(True)
