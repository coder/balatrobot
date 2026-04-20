"""Steam Proton launcher for Linux.

Supports three Steam installation types with automatic detection:

- native: Steam installed via the package manager / Valve installer.
  Launches by invoking the Proton ``run`` command directly.
- snap: Steam installed from the Snap Store (runs in a sandbox).
- flatpak: Steam installed via Flathub (runs in a sandbox).

For sandboxed Steam installs (snap, flatpak) invoking ``proton`` from the host
does not work because the Steam Linux Runtime container lives inside the
sandbox. Instead, BALATROBOT_* settings are written into the Wine prefix's
``user.reg`` ``[Environment]`` section and the game is launched through the
Steam client itself via the ``steam://rungameid/<app_id>`` URL handler.
"""

import os
import re
import time
from pathlib import Path
from shutil import which

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

BALATRO_APP_ID = "2379780"


def _detect_steam_root() -> Path | None:
    """Detect the Steam installation directory."""
    candidates = [
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
        Path("/usr/local/share/Steam"),
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        Path.home() / "snap/steam/common/.local/share/Steam",
        Path.home() / "snap/steam/common/.steam/steam",
    ]
    for p in candidates:
        if (p / "steamapps").is_dir():
            return p
    return None


def _detect_steam_package(steam_root: Path) -> str:
    """Return 'snap', 'flatpak', or 'native' based on the Steam root path."""
    s = str(steam_root.resolve() if steam_root.exists() else steam_root)
    home = str(Path.home())
    if s.startswith(f"{home}/snap/steam") or "/snap/steam/" in s:
        return "snap"
    if "com.valvesoftware.Steam" in s:
        return "flatpak"
    return "native"


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


def _write_wine_environment(compat_data: Path, env_vars: dict[str, str]) -> None:
    """Write BALATROBOT_* env vars into the Wine prefix's ``user.reg`` registry.

    Wine reads ``HKEY_CURRENT_USER\\Environment`` at process launch and exposes
    the entries as environment variables to all processes spawned inside the
    prefix. This allows Python to propagate configuration to Balatro even when
    the game is launched by a sandboxed Steam client we cannot invoke directly.

    Existing non-BALATROBOT_ entries are preserved.
    """
    user_reg = compat_data / "pfx" / "user.reg"
    if not user_reg.is_file():
        raise RuntimeError(
            f"Wine prefix registry not found at {user_reg}. "
            "Launch Balatro through Steam once to initialise the prefix."
        )

    content = user_reg.read_text(encoding="utf-8")

    section_re = re.compile(
        r"(\[Environment\][^\n]*\n)(.*?)(?=\n\[|\Z)", re.DOTALL
    )
    match = section_re.search(content)

    preserved: list[str] = []
    header: str
    if match:
        header = match.group(1).rstrip("\n")
        for line in match.group(2).splitlines():
            stripped = line.strip()
            if stripped.startswith('"BALATROBOT_'):
                continue
            preserved.append(line)
    else:
        header = f"[Environment] {int(time.time())}"

    new_entries = [f'"{k}"="{v}"' for k, v in env_vars.items()]

    body = "\n".join([*preserved, *new_entries]).rstrip("\n") + "\n"
    section = f"{header}\n{body}"

    if match:
        content = content[: match.start()] + section + content[match.end() :]
    else:
        content = content.rstrip() + "\n\n" + section

    user_reg.write_text(content, encoding="utf-8")


class ProtonLauncher(BaseLauncher):
    """Steam Proton launcher for Balatro on Linux.

    Selects the launch strategy based on the Steam package type:
    - native: invokes ``proton run`` directly
    - snap:   delegates to ``snap run steam steam://rungameid/<id>``
    - flatpak: delegates to ``flatpak run com.valvesoftware.Steam steam://rungameid/<id>``
    """

    def validate_paths(self, config: Config) -> None:
        """Validate paths, auto-detect Steam/Proton/Balatro paths where needed."""
        errors: list[str] = []
        steam_root = _detect_steam_root()

        if not steam_root:
            errors.append(
                "Steam installation not found.\n"
                "  Searched: ~/.local/share/Steam, ~/.steam/steam, /usr/local/share/Steam,\n"
                "            ~/.var/app/com.valvesoftware.Steam/... (Flatpak),\n"
                "            ~/snap/steam/common/... (Snap)"
            )
            raise RuntimeError("Path validation failed:\n\n" + "\n\n".join(errors))

        package = _detect_steam_package(steam_root)
        config._steam_package = package  # type: ignore[attr-defined]
        config._steam_root = str(steam_root)  # type: ignore[attr-defined]

        # Balatro game dir (needed for lovely-injector validation)
        if config.balatro_path is None:
            detected = _detect_balatro_path(steam_root)
            if detected:
                config.balatro_path = str(detected)

        if config.balatro_path is None:
            errors.append(
                "Balatro game directory is required.\n"
                "  Set via: --balatro-path or BALATROBOT_BALATRO_PATH"
            )
        else:
            balatro = Path(config.balatro_path)
            if not balatro.is_dir():
                errors.append(f"Balatro game directory not found: {balatro}")
            elif not (balatro / "Balatro.exe").is_file():
                errors.append(f"Balatro.exe not found in: {balatro}")

        # lovely-injector version.dll
        if config.lovely_path is None and config.balatro_path:
            detected = _detect_lovely_path(Path(config.balatro_path))
            if detected:
                config.lovely_path = str(detected)

        if config.lovely_path is None:
            errors.append(
                "lovely-injector version.dll is required.\n"
                "  Set via: --lovely-path or BALATROBOT_LOVELY_PATH\n"
                "  Place version.dll in the Balatro game directory."
            )
        else:
            lovely = Path(config.lovely_path)
            if not lovely.is_file():
                errors.append(f"version.dll not found: {lovely}")

        # Proton is only required for the native launch strategy
        if package == "native":
            if config.love_path is None:
                detected = _detect_proton_path(steam_root)
                if detected:
                    config.love_path = str(detected)

            if config.love_path is None:
                errors.append(
                    "Proton executable is required for native Steam.\n"
                    "  Set via: --love-path or BALATROBOT_LOVE_PATH"
                )
            else:
                proton = Path(config.love_path)
                if not proton.is_file():
                    errors.append(f"Proton executable not found: {proton}")
        else:
            # Sandboxed Steam: verify the CLI tool is available on the host
            tool = "snap" if package == "snap" else "flatpak"
            if which(tool) is None:
                errors.append(
                    f"{tool!r} executable not found on PATH but Steam is installed as a {package}.\n"
                    f"  Install {tool} or run balatrobot outside the snap sandbox."
                )

            compat_data = _detect_compat_data_path(steam_root)
            if compat_data is None:
                errors.append(
                    "Balatro Wine prefix not found. Launch Balatro through Steam at "
                    "least once to create the prefix."
                )

        if errors:
            raise RuntimeError("Path validation failed:\n\n" + "\n\n".join(errors))

        print(f"Detected Steam package: {package}")

    def build_env(self, config: Config) -> dict[str, str]:
        """Build the subprocess environment.

        For native Steam, sets the Proton-required STEAM_COMPAT_* variables and
        appends BALATROBOT_* variables. For sandboxed Steam, BALATROBOT_*
        variables are instead written to the Wine prefix registry so they reach
        the game process launched by the sandboxed Steam client.
        """
        assert config.balatro_path is not None

        env = os.environ.copy()
        package: str = getattr(config, "_steam_package", "native")
        steam_root = Path(getattr(config, "_steam_root", _detect_steam_root() or ""))

        if package == "native":
            env["WINEDLLOVERRIDES"] = "version=n,b"
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_root)
            compat_data = _detect_compat_data_path(steam_root)
            if compat_data:
                env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)
            env.update(config.to_env())
            return env

        # Sandboxed Steam: write BALATROBOT_* to the Wine prefix registry.
        compat_data = _detect_compat_data_path(steam_root)
        assert compat_data is not None  # validated in validate_paths
        _write_wine_environment(compat_data, config.to_env())
        return env

    def build_cmd(self, config: Config) -> list[str]:
        """Build the launch command appropriate for the detected Steam package."""
        package: str = getattr(config, "_steam_package", "native")

        if package == "native":
            assert config.love_path is not None
            assert config.balatro_path is not None
            balatro_exe = str(Path(config.balatro_path) / "Balatro.exe")
            return [config.love_path, "run", balatro_exe]

        steam_url = f"steam://rungameid/{BALATRO_APP_ID}"
        if package == "snap":
            return ["snap", "run", "steam", steam_url]
        if package == "flatpak":
            return ["flatpak", "run", "com.valvesoftware.Steam", steam_url]

        raise RuntimeError(f"Unknown Steam package type: {package}")


