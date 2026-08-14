from __future__ import annotations

import win32api
import win32event
import winerror


DEFAULT_MUTEX_NAME = r"Local\YouTubeEndlessScrollBlocker.6D16753E-168B-45D6-84BC-54F3DDA8FD3F"


class SingleInstanceMutex:
    def __init__(self, name: str = DEFAULT_MUTEX_NAME) -> None:
        self._handle = win32event.CreateMutex(None, True, name)
        self.acquired = win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
        if not self.acquired:
            win32api.CloseHandle(self._handle)
            self._handle = None

    def close(self) -> None:
        if self._handle is None:
            return
        if self.acquired:
            win32event.ReleaseMutex(self._handle)
        win32api.CloseHandle(self._handle)
        self._handle = None
        self.acquired = False

    def __enter__(self) -> "SingleInstanceMutex":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
