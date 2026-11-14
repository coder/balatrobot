"""Windows platform launcher."""

import ctypes
import os
import subprocess
import threading
import time
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

# The game opens its window a few seconds into startup and may show it again
# while loading, so headless launches keep hiding it for this long.
HIDE_WATCH_SECONDS = 60.0
_SW_HIDE = 0
_NORMAL_PRIORITY_CLASS = 0x20
_PROCESS_SET_INFORMATION = 0x200


def own_priority_class() -> int:
    """This process's Windows priority class."""
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetPriorityClass.argtypes = [ctypes.c_void_p]
    return kernel32.GetPriorityClass(kernel32.GetCurrentProcess())


def set_priority_class(pid: int, priority: int) -> bool:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(_PROCESS_SET_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.SetPriorityClass(handle, priority))
    finally:
        kernel32.CloseHandle(handle)


def hide_windows(pid: int) -> int:
    """Hide every visible, titled top-level window owned by *pid*. Returns how many."""
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hidden = 0

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        nonlocal hidden
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if (owner.value == pid and user32.IsWindowVisible(hwnd)
                and user32.GetWindowTextLengthW(hwnd) > 0):
            user32.ShowWindow(hwnd, _SW_HIDE)
            hidden += 1
        return True

    user32.EnumWindows(visit, 0)
    return hidden


def _watch_game(process: subprocess.Popen, hide: bool, priority: int | None) -> None:
    """Hide the game's windows through startup and hold it at *priority* until it exits.

    Windows' start-hidden flag doesn't help: the game shows its own window.
    A hidden window still gets WM_CLOSE, so graceful shutdown is unaffected.
    The game resets its own priority class while starting, so it can't
    simply inherit the launcher's.
    """
    deadline = time.monotonic() + HIDE_WATCH_SECONDS
    while process.poll() is None:
        starting = time.monotonic() < deadline
        if starting and hide:
            hide_windows(process.pid)
        if priority is not None:
            set_priority_class(process.pid, priority)
        elif not starting:
            return
        time.sleep(0.25 if starting else 5.0)


class WindowsLauncher(BaseLauncher):
    """Windows-specific Balatro launcher via Steam."""

    def validate_paths(self, config: Config) -> None:
        """Validate paths, apply Windows defaults if None."""
        if config.love_path is None:
            config.love_path = (
                r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe"
            )
        if config.lovely_path is None:
            config.lovely_path = (
                r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\version.dll"
            )

        love = Path(config.love_path)
        lovely = Path(config.lovely_path)

        if not love.exists():
            raise RuntimeError(f"Balatro executable not found: {love}")
        if not lovely.exists():
            raise RuntimeError(f"version.dll not found: {lovely}")

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment."""
        env = os.environ.copy()
        env.update(config.to_env())
        return env

    async def start(self, config: Config, session_dir: Path) -> subprocess.Popen:
        """Start Balatro; hide its window when headless, and run it at this launcher's priority."""
        process = await super().start(config, session_dir)
        priority = own_priority_class()
        priority = None if priority == _NORMAL_PRIORITY_CLASS else priority
        if config.headless or priority is not None:
            threading.Thread(
                target=_watch_game,
                args=(process, config.headless, priority),
                daemon=True,
            ).start()
        return process

    def build_cmd(self, config: Config) -> list[str]:
        """Build Windows launch command.

        --disable-console is Lovely's own flag: it skips the console window
        Lovely opens per game. Lovely still writes its log files.
        """
        assert config.love_path is not None
        return [config.love_path, "--disable-console"]
