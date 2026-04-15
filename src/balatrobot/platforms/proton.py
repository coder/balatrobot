"""Steam Proton launcher for Linux."""

import os
import re
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

BALATRO_APP_ID = "2379780"


def _detect_steam_root() -> Path | None:
    """Detect the Steam installation directory."""
    candidates = [
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
        Path("/usr/local/share/Steam"),
    ]
    for p in candidates:
        if (p / "steamapps").is_dir():
            return p
    return None


def _proton_sort_key(p: Path) -> tuple:
    """Sort key that prefers GE-Proton > official Proton > Experimental."""
    name = p.parent.name
    m = re.match(r"GE-Proton(\d+)-(\d+)", name)
    if m:
        return (0, -int(m.group(1)), -int(m.group(2)))
    m = re.match(r"Proton (\d+)\.(\d+)", name)
    if m:
        return (1, -int(m.group(1)), -int(m.group(2)))
    if "Experimental" in name:
        return (2, 0, 0)
    return (3, 0, 0)


def _detect_proton_path(steam_root: Path) -> Path | None:
    """Find the best available Proton executable."""
    candidates: list[Path] = []

    # Community Proton builds (GE-Proton, etc.)
    compat_dirs = [
        steam_root / "compatibilitytools.d",
        Path.home() / ".steam/root/compatibilitytools.d",
    ]
    for compat_dir in compat_dirs:
        if compat_dir.is_dir():
            for d in compat_dir.iterdir():
                proton = d / "proton"
                if proton.is_file():
                    candidates.append(proton)

    # Official Proton builds in steamapps/common
    steamapps_common = steam_root / "steamapps/common"
    if steamapps_common.is_dir():
        for d in steamapps_common.iterdir():
            proton = d / "proton"
            if proton.is_file() and "proton" in d.name.lower():
                candidates.append(proton)

    if not candidates:
        return None
    return sorted(candidates, key=_proton_sort_key)[0]


def _detect_balatro_path(steam_root: Path) -> Path | None:
    """Detect the Balatro game directory."""
    p = steam_root / "steamapps/common/Balatro"
    return p if p.is_dir() else None


def _detect_lovely_path(balatro_path: Path) -> Path | None:
    """Detect the lovely-injector version.dll inside the Balatro directory."""
    p = balatro_path / "version.dll"
    return p if p.is_file() else None


def _detect_compat_data_path(steam_root: Path) -> Path | None:
    """Detect the Steam compatibility data directory for Balatro."""
    p = steam_root / f"steamapps/compatdata/{BALATRO_APP_ID}"
    return p if p.is_dir() else None


class ProtonLauncher(BaseLauncher):
    """Steam Proton launcher for Balatro on Linux."""

    def validate_paths(self, config: Config) -> None:
        """Validate paths, auto-detect Steam/Proton/Balatro paths if not set."""
        errors: list[str] = []
        steam_root = _detect_steam_root()

        # --- Balatro path ---
        if config.balatro_path is None and steam_root:
            detected = _detect_balatro_path(steam_root)
            if detected:
                config.balatro_path = str(detected)

        if config.balatro_path is None:
            errors.append(
                "Balatro game directory is required.\n"
                "  Set via: --balatro-path or BALATROBOT_BALATRO_PATH\n"
                "  Expected: ~/.local/share/Steam/steamapps/common/Balatro"
            )
        else:
            balatro = Path(config.balatro_path)
            if not balatro.is_dir():
                errors.append(f"Balatro game directory not found: {balatro}")
            elif not (balatro / "Balatro.exe").is_file():
                errors.append(f"Balatro.exe not found in: {balatro}")

        # --- Proton path (stored in love_path) ---
        if config.love_path is None and steam_root:
            detected = _detect_proton_path(steam_root)
            if detected:
                config.love_path = str(detected)

        if config.love_path is None:
            errors.append(
                "Proton executable is required.\n"
                "  Set via: --love-path or BALATROBOT_LOVE_PATH\n"
                "  Expected: path to a 'proton' script inside your Proton installation"
            )
        else:
            proton = Path(config.love_path)
            if not proton.is_file():
                errors.append(f"Proton executable not found: {proton}")

        # --- lovely-injector (version.dll) ---
        if config.lovely_path is None and config.balatro_path:
            detected = _detect_lovely_path(Path(config.balatro_path))
            if detected:
                config.lovely_path = str(detected)

        if config.lovely_path is None:
            errors.append(
                "lovely-injector version.dll is required.\n"
                "  Set via: --lovely-path or BALATROBOT_LOVELY_PATH\n"
                "  Expected: ~/.local/share/Steam/steamapps/common/Balatro/version.dll"
            )
        else:
            lovely = Path(config.lovely_path)
            if not lovely.is_file():
                errors.append(f"version.dll not found: {lovely}")

        if errors:
            raise RuntimeError("Path validation failed:\n\n" + "\n\n".join(errors))

    def build_env(self, config: Config) -> dict[str, str]:
        """Build environment for Proton, including Wine DLL override for lovely-injector."""
        assert config.love_path is not None
        assert config.balatro_path is not None

        env = os.environ.copy()

        # lovely-injector uses a version.dll DLL hijack — tell Wine to load it
        env["WINEDLLOVERRIDES"] = "version=n,b"

        steam_root = _detect_steam_root()
        if steam_root:
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_root)
            compat_data = _detect_compat_data_path(steam_root)
            if compat_data:
                env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)

        env.update(config.to_env())
        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build Proton launch command: proton run Balatro.exe."""
        assert config.love_path is not None
        assert config.balatro_path is not None

        balatro_exe = str(Path(config.balatro_path) / "Balatro.exe")
        return [config.love_path, "run", balatro_exe]
