"""Tests for balatrobot.platforms module."""

import platform as platform_module

import pytest

from balatrobot.config import Config
from balatrobot.platforms import VALID_PLATFORMS, get_launcher
from balatrobot.platforms.linux import LinuxLauncher
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

    def test_linux_returns_linux_launcher(self):
        """'linux' returns LinuxLauncher."""
        launcher = get_launcher("linux")
        assert isinstance(launcher, LinuxLauncher)

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


@pytest.mark.skipif(not IS_LINUX, reason="Linux only")
class TestLinuxLauncher:
    """Tests for LinuxLauncher (Linux only)."""

    def test_validate_paths_missing_steam(self, tmp_path):
        """Raises RuntimeError when Steam installation not found."""
        launcher = LinuxLauncher()
        config = Config(steam_path=str(tmp_path / "nonexistent"))

        with pytest.raises(RuntimeError, match="Steam directory not found"):
            launcher.validate_paths(config)

    def test_validate_paths_invalid_steam(self, tmp_path):
        """Raises RuntimeError when Steam directory has no steamapps."""
        # Create a fake Steam directory without steamapps
        steam_path = tmp_path / "Steam"
        steam_path.mkdir()

        launcher = LinuxLauncher()
        config = Config(steam_path=str(steam_path))

        with pytest.raises(RuntimeError, match="Invalid Steam directory"):
            launcher.validate_paths(config)

    def test_build_env_includes_proton_vars(self, tmp_path):
        """build_env includes Proton compatibility environment variables."""
        launcher = LinuxLauncher()
        config = Config(steam_path="/path/to/Steam")

        env = launcher.build_env(config)

        assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == "/path/to/Steam"
        assert "compatdata/2379780" in env["STEAM_COMPAT_DATA_PATH"]
        assert env["WINEDLLOVERRIDES"] == "version=n,b"

    def test_build_cmd(self, tmp_path):
        """build_cmd returns proton run command."""
        launcher = LinuxLauncher()
        config = Config(
            balatro_path="/path/to/proton",
            love_path="/path/to/Balatro.exe",
        )

        cmd = launcher.build_cmd(config)

        assert cmd == ["/path/to/proton", "run", "/path/to/Balatro.exe"]

    def test_validate_paths_missing_proton_prefix(self, tmp_path):
        """Raises RuntimeError when Proton prefix (compatdata) not found."""
        # Create valid Steam structure but without compatdata
        steam_path = tmp_path / "Steam"
        steamapps = steam_path / "steamapps"
        steamapps.mkdir(parents=True)

        # Create Balatro and Proton directories
        balatro_dir = steamapps / "common/Balatro"
        balatro_dir.mkdir(parents=True)
        (balatro_dir / "Balatro.exe").touch()
        (balatro_dir / "version.dll").touch()

        proton_dir = steamapps / "common/Proton - Experimental"
        proton_dir.mkdir(parents=True)
        (proton_dir / "proton").touch()

        # No compatdata/2379780 directory

        launcher = LinuxLauncher()
        config = Config(steam_path=str(steam_path))

        with pytest.raises(RuntimeError, match="Proton prefix not found"):
            launcher.validate_paths(config)
