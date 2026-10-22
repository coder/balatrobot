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
class TestLinuxLauncher:
    """Tests for Linux launcher (Linux only)."""

    @pytest.fixture
    def steam_installation(self, tmp_path, monkeypatch):
        """Provide a fake Steam, Balatro, and Proton installation."""
        steam_root = tmp_path / ".local/share/Steam"
        balatro = steam_root / "steamapps/common/Balatro"
        balatro.mkdir(parents=True)
        (balatro / "Balatro.exe").touch()
        proton = steam_root / "steamapps/common/Proton - Experimental/proton"
        proton.parent.mkdir(parents=True)
        proton.touch()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DISPLAY", ":0")
        return balatro

    @pytest.mark.parametrize("dll_name", ["winmm.dll", "version.dll"])
    def test_detects_lovely_dll(self, steam_installation, dll_name):
        """Select an installed Lovely DLL and set its Wine override."""
        lovely = steam_installation / dll_name
        lovely.touch()
        config = Config()
        launcher = LinuxLauncher()

        launcher.validate_paths(config)

        assert config.lovely_path == str(lovely)
        assert launcher.build_env(config)["WINEDLLOVERRIDES"] == (f"{lovely.stem}=n,b")

    def test_prefers_winmm_when_both_lovely_dlls_exist(self, steam_installation):
        """Prefer the newer DLL when both names are present."""
        (steam_installation / "version.dll").touch()
        winmm = steam_installation / "winmm.dll"
        winmm.touch()
        config = Config()
        launcher = LinuxLauncher()

        launcher.validate_paths(config)

        assert config.lovely_path == str(winmm)
        assert launcher.build_env(config)["WINEDLLOVERRIDES"] == "winmm=n,b"

    @pytest.mark.parametrize("dll_name", ["winmm.dll", "version.dll"])
    def test_uses_explicit_lovely_path(self, steam_installation, dll_name):
        """An explicit DLL path takes precedence over auto-detection."""
        (steam_installation / "winmm.dll").touch()
        lovely = steam_installation / dll_name
        lovely.touch()
        config = Config(lovely_path=str(lovely))
        launcher = LinuxLauncher()

        launcher.validate_paths(config)

        assert config.lovely_path == str(lovely)
        assert launcher.build_env(config)["WINEDLLOVERRIDES"] == (f"{lovely.stem}=n,b")

    def test_missing_lovely_dll(self, steam_installation):
        """Report both supported DLL names when auto-detection fails."""
        with pytest.raises(RuntimeError, match="winmm.dll or version.dll not found"):
            LinuxLauncher().validate_paths(Config())

    def test_missing_explicit_lovely_path(self, steam_installation, tmp_path):
        """Reject an explicit DLL path that does not name a file."""
        lovely = tmp_path / "missing" / "winmm.dll"
        config = Config(lovely_path=str(lovely))

        with pytest.raises(RuntimeError, match="Lovely injector DLL not found"):
            LinuxLauncher().validate_paths(config)

    def test_explicit_lovely_path_must_be_file(self, steam_installation, tmp_path):
        """Reject a directory even if its name looks like a DLL."""
        lovely = tmp_path / "winmm.dll"
        lovely.mkdir()

        with pytest.raises(RuntimeError, match="Lovely injector DLL not found"):
            LinuxLauncher().validate_paths(Config(lovely_path=str(lovely)))

    def test_validate_paths_missing_steam_root(self, tmp_path, monkeypatch):
        """Raises RuntimeError when Steam root not found."""
        launcher = LinuxLauncher()
        config = Config()
        # Point HOME to tmp_path so Steam detection fails
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DISPLAY", ":0")
        with pytest.raises(RuntimeError, match="Steam installation not found"):
            launcher.validate_paths(config)

    def test_validate_paths_missing_display(self, tmp_path, monkeypatch):
        """Raises RuntimeError when no display server is available."""
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        launcher = LinuxLauncher()
        config = Config()
        with pytest.raises(RuntimeError, match="No display server found"):
            launcher.validate_paths(config)

    def test_validate_paths_auto_detects_balatro(self, tmp_path, monkeypatch):
        """Auto-detects Balatro game dir under Steam root."""
        # Create fake Steam root with Balatro
        steam_root = tmp_path / ".local/share/Steam"
        balatro = steam_root / "steamapps/common/Balatro"
        balatro.mkdir(parents=True)
        (balatro / "Balatro.exe").touch()
        # Create fake proton
        proton_dir = steam_root / "steamapps/common/Proton - Experimental"
        proton_dir.mkdir(parents=True)
        (proton_dir / "proton").touch()
        # Create fake version.dll
        (balatro / "version.dll").touch()
        # Create fake compat data
        compat = steam_root / "steamapps/compatdata/2379780"
        compat.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DISPLAY", ":0")
        launcher = LinuxLauncher()
        config = Config()
        launcher.validate_paths(config)

        assert config.balatro_path is not None
        assert "Balatro" in config.balatro_path

    def test_validate_paths_missing_balatro_exe(self, tmp_path, monkeypatch):
        """Raises RuntimeError when Balatro.exe is missing."""
        steam_root = tmp_path / ".local/share/Steam"
        balatro = steam_root / "steamapps/common/Balatro"
        balatro.mkdir(parents=True)
        # No Balatro.exe
        proton_dir = steam_root / "steamapps/common/Proton - Experimental"
        proton_dir.mkdir(parents=True)
        (proton_dir / "proton").touch()
        (balatro / "version.dll").touch()

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DISPLAY", ":0")
        launcher = LinuxLauncher()
        config = Config()
        with pytest.raises(RuntimeError, match="Balatro game directory not found"):
            launcher.validate_paths(config)

    def test_build_env_includes_winedlloverrides(self):
        """build_env includes WINEDLLOVERRIDES."""
        launcher = LinuxLauncher()
        config = Config()
        env = launcher.build_env(config)
        assert env["WINEDLLOVERRIDES"] == "version=n,b"

    def test_build_env_includes_steam_compat_vars(self, tmp_path, monkeypatch):
        """build_env includes STEAM_COMPAT_* vars when Steam root detected."""
        steam_root = tmp_path / ".local/share/Steam"
        compat = steam_root / "steamapps/compatdata/2379780"
        compat.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DISPLAY", ":0")

        launcher = LinuxLauncher()
        config = Config()
        env = launcher.build_env(config)

        assert "STEAM_COMPAT_CLIENT_INSTALL_PATH" in env
        assert "Steam" in env["STEAM_COMPAT_CLIENT_INSTALL_PATH"]
        assert "STEAM_COMPAT_DATA_PATH" in env
        assert "compatdata/2379780" in env["STEAM_COMPAT_DATA_PATH"]

    def test_build_cmd(self):
        """build_cmd returns proton run with Balatro.exe."""
        launcher = LinuxLauncher()
        config = Config(
            love_path="/path/to/proton",
            balatro_path="/path/to/Balatro",
        )
        cmd = launcher.build_cmd(config)
        assert cmd == ["/path/to/proton", "run", "/path/to/Balatro/Balatro.exe"]


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
