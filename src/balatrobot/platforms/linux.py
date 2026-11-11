"""Linux platform launcher (Steam/Proton)."""

import os
import subprocess
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

BALATRO_APP_ID = "2379780"


def _detect_steam_root() -> Path | None:
    """Detect the Steam installation directory."""
    home = Path.home()
    candidates = [
        home / ".local/share/Steam",
        home / ".steam/steam",
    ]
    for p in candidates:
        if (p / "steamapps").is_dir():
            return p
    return None


def _detect_proton_path(steam_root: Path) -> Path | None:
    """Find the first available Proton executable."""
    common = steam_root / "steamapps/common"
    if not common.is_dir():
        return None
    for d in sorted(common.iterdir()):
        proton = d / "proton"
        if proton.is_file() and "proton" in d.name.lower():
            return proton
    return None


def _detect_compat_data_path(steam_root: Path) -> Path | None:
    """Detect the Steam compatibility data directory for Balatro."""
    p = steam_root / f"steamapps/compatdata/{BALATRO_APP_ID}"
    return p if p.is_dir() else None


class LinuxLauncher(BaseLauncher):
    """Linux-specific Balatro launcher via Steam/Proton."""

    def validate_paths(self, config: Config) -> None:
        """Validate paths, auto-detect Steam/Proton/Balatro paths."""
        # Proton needs a display server to render the game window
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "No display server found. "
                "Set DISPLAY or WAYLAND_DISPLAY in your environment."
            )

        steam_root = _detect_steam_root()
        if not steam_root:
            raise RuntimeError(
                "Steam installation not found. "
                "Searched: ~/.local/share/Steam, ~/.steam/steam"
            )

        # Balatro game directory
        if config.path_balatro is None:
            candidate = steam_root / "steamapps/common/Balatro"
            if candidate.is_dir():
                config.path_balatro = str(candidate)

        if config.path_balatro is None:
            raise RuntimeError(
                "Balatro game directory not found under Steam root. "
                "Set --path-balatro or BALATROBOT_PATH_BALATRO."
            )

        balatro = Path(config.path_balatro)
        if not balatro.is_dir() or not (balatro / "Balatro.exe").is_file():
            raise RuntimeError(f"Balatro game directory not found: {balatro}")

        # Lovely (version.dll)
        if config.path_lovely is None:
            candidate = balatro / "version.dll"
            if candidate.is_file():
                config.path_lovely = str(candidate)

        if config.path_lovely is None:
            raise RuntimeError(
                "lovely-injector version.dll not found. "
                "Set --path-lovely or BALATROBOT_PATH_LOVELY."
            )

        # Proton executable
        if config.path_love is None:
            detected = _detect_proton_path(steam_root)
            if detected:
                config.path_love = str(detected)

        if config.path_love is None:
            raise RuntimeError(
                "Proton executable not found. Set --path-love or BALATROBOT_PATH_LOVE."
            )

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment with Proton-required variables."""
        env = os.environ.copy()
        env["WINEDLLOVERRIDES"] = "version=n,b"

        # Don't override user-set env vars (e.g. custom Wine prefix, Proton version)
        steam_root = _detect_steam_root()
        if steam_root and "STEAM_COMPAT_CLIENT_INSTALL_PATH" not in env:
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_root)
        if "STEAM_COMPAT_DATA_PATH" not in env:
            compat_data = _detect_compat_data_path(steam_root) if steam_root else None
            if compat_data:
                env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)

        env.update(config.to_env())
        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build Linux launch command via Proton."""
        assert config.path_love is not None
        assert config.path_balatro is not None
        balatro_exe = str(Path(config.path_balatro) / "Balatro.exe")
        return [config.path_love, "run", balatro_exe]

    def cleanup(self, config: Config) -> None:
        """Shut down the Wine prefix via wineserver -k.

        Proton/Wine double-forks its children away from the original
        process group, so process.terminate() alone leaves orphans.
        wineserver -k cleanly terminates all Wine processes and
        closes display connections so the compositor removes windows.
        """
        if config.path_love is None:
            return

        # wineserver lives next to the proton script
        proton_dir = Path(config.path_love).parent
        wineserver = proton_dir / "files" / "bin" / "wineserver"
        if not wineserver.is_file():
            return

        # WINEPREFIX is inside the Steam compat data directory
        steam_root = _detect_steam_root()
        if not steam_root:
            return
        compat_data = _detect_compat_data_path(steam_root)
        if not compat_data:
            return
        wineprefix = compat_data / "pfx"
        if not wineprefix.is_dir():
            return

        subprocess.run(
            [str(wineserver), "-k"],
            env={"WINEPREFIX": str(wineprefix)},
            capture_output=True,
            timeout=10,
            check=False,
        )
