"""Linux Proton platform launcher for Balatro via Steam."""

import os
import platform
import re
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

# Balatro Steam App ID
BALATRO_APP_ID = "2379780"

# Known Steam installation paths (in priority order)
STEAM_PATH_CANDIDATES = [
    Path.home() / ".local/share/Steam",
    Path.home() / ".steam/steam",
    Path.home() / "snap/steam/common/.local/share/Steam",
    Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
]


def _detect_steam_path() -> Path | None:
    """Detect Steam installation from known locations."""
    for candidate in STEAM_PATH_CANDIDATES:
        if candidate.is_dir() and (candidate / "steamapps").is_dir():
            return candidate
    return None


def _detect_proton_path(steam_path: Path) -> Path | None:
    """Detect Proton runtime in Steam installation.

    Prefers Proton - Experimental, then falls back to latest versioned Proton.
    """
    common = steam_path / "steamapps/common"
    if not common.is_dir():
        return None

    # Prefer Proton - Experimental
    experimental = common / "Proton - Experimental" / "proton"
    if experimental.is_file():
        return experimental

    # Find versioned Proton installations (e.g., "Proton 9.0", "Proton 8.0.5")
    proton_dirs: list[tuple[tuple[int, ...], Path]] = []
    for entry in common.iterdir():
        if entry.is_dir() and entry.name.startswith("Proton "):
            match = re.match(r"Proton (\d+(?:\.\d+)*)", entry.name)
            if match:
                # Parse version as tuple for correct semantic version comparison
                # e.g., "8.10" -> (8, 10) which correctly compares > (8, 9)
                version = tuple(int(part) for part in match.group(1).split("."))
                proton_exec = entry / "proton"
                if proton_exec.is_file():
                    proton_dirs.append((version, proton_exec))

    if proton_dirs:
        # Sort by version descending, return the latest
        proton_dirs.sort(key=lambda x: x[0], reverse=True)
        return proton_dirs[0][1]

    return None


class LinuxLauncher(BaseLauncher):
    """Linux launcher for Balatro via Steam/Proton.

    This launcher is designed for:
    - Linux desktop with Steam and Proton installed
    - Running Windows version of Balatro through Proton

    Requirements:
    - Linux operating system
    - Steam installed with Proton runtime
    - Balatro installed via Steam
    - Lovely injector (version.dll) in Balatro directory
    """

    def validate_paths(self, config: Config) -> None:
        """Validate and auto-detect paths for Linux Proton launcher."""
        if platform.system().lower() != "linux":
            raise RuntimeError("Linux Proton launcher is only supported on Linux")

        errors: list[str] = []

        # Steam path (auto-detect or use config)
        steam_path: Path | None = None
        if config.steam_path:
            steam_path = Path(config.steam_path)
            if not steam_path.is_dir():
                errors.append(f"Steam directory not found: {steam_path}")
            elif not (steam_path / "steamapps").is_dir():
                errors.append(f"Invalid Steam directory (no steamapps): {steam_path}")
        else:
            steam_path = _detect_steam_path()
            if steam_path:
                config.steam_path = str(steam_path)
            else:
                errors.append(
                    "Steam installation not found.\n"
                    "  Set via: --steam-path or BALATROBOT_STEAM_PATH\n"
                    "  Tried: " + ", ".join(str(p) for p in STEAM_PATH_CANDIDATES)
                )

        if not steam_path or not steam_path.is_dir():
            raise RuntimeError("Path validation failed:\n\n" + "\n\n".join(errors))

        # Balatro executable (love_path stores the exe path for consistency)
        if config.love_path is None:
            balatro_exe = steam_path / "steamapps/common/Balatro/Balatro.exe"
            if balatro_exe.is_file():
                config.love_path = str(balatro_exe)
            else:
                errors.append(
                    "Balatro.exe not found.\n"
                    f"  Expected: {balatro_exe}\n"
                    "  Make sure Balatro is installed via Steam."
                )
        else:
            if not Path(config.love_path).is_file():
                errors.append(f"Balatro executable not found: {config.love_path}")

        # Lovely injector (version.dll)
        if config.lovely_path is None:
            version_dll = steam_path / "steamapps/common/Balatro/version.dll"
            if version_dll.is_file():
                config.lovely_path = str(version_dll)
            else:
                errors.append(
                    "Lovely injector (version.dll) not found.\n"
                    f"  Expected: {version_dll}\n"
                    "  Install lovely-injector for Windows into the Balatro directory."
                )
        else:
            if not Path(config.lovely_path).is_file():
                errors.append(f"Lovely injector not found: {config.lovely_path}")

        # Proton runtime (balatro_path stores proton path for this launcher)
        if config.balatro_path is None:
            proton_path = _detect_proton_path(steam_path)
            if proton_path:
                config.balatro_path = str(proton_path)
            else:
                errors.append(
                    "Proton runtime not found.\n"
                    "  Install 'Proton - Experimental' or a versioned Proton via Steam.\n"
                    "  Or set via: --balatro-path or BALATROBOT_BALATRO_PATH"
                )
        else:
            if not Path(config.balatro_path).is_file():
                errors.append(f"Proton executable not found: {config.balatro_path}")

        # Proton prefix must exist (created by first game launch)
        compat_data = steam_path / f"steamapps/compatdata/{BALATRO_APP_ID}"
        if not compat_data.is_dir():
            errors.append(
                f"Proton prefix not found: {compat_data}\n"
                "  Run Balatro at least once through Steam to create the prefix."
            )

        if errors:
            raise RuntimeError("Path validation failed:\n\n" + "\n\n".join(errors))

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment with Proton compatibility variables."""
        assert config.steam_path is not None
        steam_path = Path(config.steam_path)

        env = os.environ.copy()

        # Proton environment variables
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_path)
        env["STEAM_COMPAT_DATA_PATH"] = str(
            steam_path / f"steamapps/compatdata/{BALATRO_APP_ID}"
        )

        # Force native version.dll loading for lovely injection
        env["WINEDLLOVERRIDES"] = "version=n,b"

        # Add config environment variables
        env.update(config.to_env())

        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build Proton launch command."""
        assert config.balatro_path is not None  # Proton path
        assert config.love_path is not None  # Balatro.exe path

        return [config.balatro_path, "run", config.love_path]
