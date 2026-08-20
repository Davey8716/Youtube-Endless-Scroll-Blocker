from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "YouTubeEndlessScrollBlocker"


def startup_command(
    *,
    executable: Path | None = None,
    entry_point: Path | None = None,
    frozen: bool | None = None,
) -> str:
    executable_path = executable or Path(sys.executable)
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        arguments = [str(executable_path)]
    else:
        source_entry_point = entry_point or Path(__file__).resolve().parent.parent / "main.py"
        arguments = [str(executable_path), str(source_entry_point)]
    return subprocess.list2cmdline(arguments)


class StartupManager:
    def __init__(self, command: str | None = None) -> None:
        self._command = command or startup_command()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, self._command)
            return

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
