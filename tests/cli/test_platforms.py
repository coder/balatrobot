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
        """build_cmd returns Balatro.exe path."""
        launcher = WindowsLauncher()
        config = Config(love_path=r"C:\path\to\Balatro.exe")

        cmd = launcher.build_cmd(config)

        assert cmd == [r"C:\path\to\Balatro.exe"]
