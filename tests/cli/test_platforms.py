"""Tests for balatrobot.platforms module."""

import platform as platform_module

import pytest

from balatrobot.config import Config
from balatrobot.platforms import VALID_PLATFORMS, get_launcher
from balatrobot.platforms.macos import MacOSLauncher
from balatrobot.platforms.native import NativeLauncher
from balatrobot.platforms.windows import WindowsLauncher

IS_MACOS = platform_module.system() == "Darwin"
IS_LINUX = platform_module.system() == "Linux"
IS_WINDOWS = platform_module.system() == "Windows"


class TestGetLauncher:
    """Tests for get_launcher() factory function."""

    def test_invalid_platform_raises(self):
        """Invalid platform string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid platform"):
            get_launcher("invalid")

    def test_darwin_returns_macos_launcher(self):
        """'darwin' returns MacOSLauncher."""
        launcher = get_launcher("darwin")
        assert isinstance(launcher, MacOSLauncher)

    def test_native_returns_native_launcher(self):
        """'native' returns NativeLauncher."""
        launcher = get_launcher("native")
        assert isinstance(launcher, NativeLauncher)

    def test_windows_returns_windows_launcher(self):
        """'windows' returns WindowsLauncher."""
        launcher = get_launcher("windows")
        assert isinstance(launcher, WindowsLauncher)

    def test_linux_not_implemented(self):
        """'linux' raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            get_launcher("linux")

    def test_valid_platforms_constant(self):
        """VALID_PLATFORMS contains expected values."""
        assert "darwin" in VALID_PLATFORMS
        assert "linux" in VALID_PLATFORMS
        assert "windows" in VALID_PLATFORMS
        assert "native" in VALID_PLATFORMS


@pytest.mark.skipif(not IS_MACOS, reason="macOS only")
class TestMacOSLauncher:
    """Tests for MacOSLauncher (macOS only)."""

    def test_validate_paths_missing_love(self, tmp_path):
        """Raises RuntimeError when love executable missing."""
        launcher = MacOSLauncher()
        config = Config(love_path=str(tmp_path / "nonexistent"))

        with pytest.raises(RuntimeError, match="LOVE executable not found"):
            launcher.validate_paths(config)

    def test_validate_paths_missing_lovely(self, tmp_path):
        """Raises RuntimeError when liblovely.dylib missing."""
        # Create a fake love executable
        love_path = tmp_path / "love"
        love_path.touch()

        launcher = MacOSLauncher()
        config = Config(
            love_path=str(love_path),
            lovely_path=str(tmp_path / "nonexistent.dylib"),
        )

        with pytest.raises(RuntimeError, match="liblovely.dylib not found"):
            launcher.validate_paths(config)

    def test_build_env_includes_dyld(self, tmp_path):
        """build_env includes DYLD_INSERT_LIBRARIES."""
        launcher = MacOSLauncher()
        config = Config(lovely_path="/path/to/liblovely.dylib")

        env = launcher.build_env(config)

        assert env["DYLD_INSERT_LIBRARIES"] == "/path/to/liblovely.dylib"

    def test_build_cmd(self, tmp_path):
        """build_cmd returns love executable path."""
        launcher = MacOSLauncher()
        config = Config(love_path="/path/to/love")

        cmd = launcher.build_cmd(config)

        assert cmd == ["/path/to/love"]


@pytest.mark.skipif(not IS_LINUX, reason="Linux only")
class TestNativeLauncher:
    """Tests for NativeLauncher (Linux only)."""

    def test_validate_paths_missing_love(self, tmp_path):
        """Raises RuntimeError when love executable missing."""
        launcher = NativeLauncher()
        config = Config(
            love_path=str(tmp_path / "nonexistent"),
            balatro_path=str(tmp_path),
        )

        with pytest.raises(RuntimeError, match="LOVE executable not found"):
            launcher.validate_paths(config)

    def test_build_env_includes_ld_preload(self, tmp_path):
        """build_env includes LD_PRELOAD."""
        launcher = NativeLauncher()
        config = Config(lovely_path="/path/to/liblovely.so")

        env = launcher.build_env(config)

        assert env["LD_PRELOAD"] == "/path/to/liblovely.so"

    def test_build_cmd(self, tmp_path):
        """build_cmd returns love and balatro path."""
        launcher = NativeLauncher()
        config = Config(love_path="/usr/bin/love", balatro_path="/path/to/balatro")

        cmd = launcher.build_cmd(config)

        assert cmd == ["/usr/bin/love", "/path/to/balatro"]


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows only")
class TestWindowsLauncher:
    """Tests for WindowsLauncher (Windows only)."""

    def test_validate_paths_missing_balatro_exe(self, tmp_path):
        """Raises RuntimeError when Balatro.exe missing."""
        launcher = WindowsLauncher()
        config = Config(love_path=str(tmp_path / "nonexistent.exe"))

        with pytest.raises(RuntimeError, match="Balatro executable not found"):
            launcher.validate_paths(config)

    def test_validate_paths_missing_version_dll(self, tmp_path):
        """Raises RuntimeError when version.dll missing."""
        # Create a fake Balatro.exe
        exe_path = tmp_path / "Balatro.exe"
        exe_path.touch()

        launcher = WindowsLauncher()
        config = Config(
            love_path=str(exe_path),
            lovely_path=str(tmp_path / "nonexistent.dll"),
        )

        with pytest.raises(RuntimeError, match="version.dll not found"):
            launcher.validate_paths(config)

    def test_build_env_no_dll_injection_var(self, tmp_path):
        """build_env does not include DLL injection environment variable."""
        launcher = WindowsLauncher()
        config = Config(lovely_path=r"C:\path\to\version.dll")

        env = launcher.build_env(config)

        assert "DYLD_INSERT_LIBRARIES" not in env
        assert "LD_PRELOAD" not in env

    def test_build_cmd(self, tmp_path):
        """build_cmd returns Balatro.exe path with Lovely's console turned off."""
        launcher = WindowsLauncher()
        config = Config(love_path=r"C:\path\to\Balatro.exe")

        cmd = launcher.build_cmd(config)

        assert cmd == [r"C:\path\to\Balatro.exe", "--disable-console"]


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows only")
class TestWindowsHiding:
    """Headless launches keep the game window hidden."""

    @pytest.mark.parametrize("headless", [True, False])
    def test_watcher_runs_only_when_headless(self, monkeypatch, tmp_path, headless):
        import asyncio

        from balatrobot.platforms import base, windows

        fake = object()

        async def fake_start(self, config, session_dir):
            return fake

        started = []
        monkeypatch.setattr(base.BaseLauncher, "start", fake_start)
        monkeypatch.setattr(
            windows.threading, "Thread",
            lambda target, args, daemon: type("T", (), {"start": lambda s: started.append(args)})(),
        )
        process = asyncio.run(WindowsLauncher().start(Config(headless=headless), tmp_path))
        assert process is fake
        assert bool(started) is headless

    def test_hide_windows_hides_a_visible_window(self):
        import ctypes
        import os
        import tkinter as tk

        from balatrobot.platforms.windows import hide_windows

        root = tk.Tk()
        root.title("hide me")
        root.update()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        try:
            assert ctypes.windll.user32.IsWindowVisible(hwnd)
            assert hide_windows(os.getpid()) >= 1
            assert not ctypes.windll.user32.IsWindowVisible(hwnd)
        finally:
            root.destroy()

    def test_watcher_runs_for_a_below_normal_launcher(self, monkeypatch, tmp_path):
        import asyncio

        from balatrobot.platforms import base, windows

        async def fake_start(self, config, session_dir):
            return object()

        started = []
        monkeypatch.setattr(base.BaseLauncher, "start", fake_start)
        monkeypatch.setattr(windows, "own_priority_class", lambda: 0x4000)  # BELOW_NORMAL
        monkeypatch.setattr(
            windows.threading, "Thread",
            lambda target, args, daemon: type("T", (), {"start": lambda s: started.append(args)})(),
        )
        asyncio.run(WindowsLauncher().start(Config(headless=False), tmp_path))
        assert started and started[0][1:] == (False, 0x4000)

    def test_set_priority_class_changes_a_running_process(self):
        import ctypes
        import subprocess
        import sys

        from balatrobot.platforms.windows import set_priority_class

        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        try:
            assert set_priority_class(child.pid, 0x4000)
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.GetPriorityClass.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel32.OpenProcess(0x1000, False, child.pid)  # QUERY_LIMITED_INFORMATION
            assert kernel32.GetPriorityClass(handle) == 0x4000
            kernel32.CloseHandle(handle)
        finally:
            child.kill()
