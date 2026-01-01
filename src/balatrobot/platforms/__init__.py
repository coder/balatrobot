"""Platform detection and launcher dispatch."""

import platform as platform_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balatrobot.platforms.base import BaseLauncher

VALID_PLATFORMS = frozenset({"darwin", "linux", "windows", "native"})


def get_launcher(platform: str | None = None) -> "BaseLauncher":
    """Get launcher for the specified or detected platform.

    Args:
        platform: Optional platform to use instead of auto-detection.
            Valid values: "darwin", "linux", "windows", "native"

    Returns:
        Launcher instance for the platform

    Raises:
        RuntimeError: If platform is not supported
        ValueError: If platform is invalid
    """
    # Use override if provided, otherwise auto-detect
    if platform:
        if platform not in VALID_PLATFORMS:
            raise ValueError(
                f"Invalid platform '{platform}'. "
                f"Must be one of: {', '.join(sorted(VALID_PLATFORMS))}"
            )
        system = platform
    else:
        system = platform_module.system().lower()

    match system:
        case "darwin":
            from balatrobot.platforms.macos import MacOSLauncher

            return MacOSLauncher()
        case "linux":
            from balatrobot.platforms.linux import LinuxLauncher

            return LinuxLauncher()
        case "windows":
            from balatrobot.platforms.windows import WindowsLauncher

            return WindowsLauncher()
        case "native":
            from balatrobot.platforms.native import NativeLauncher

            return NativeLauncher()
        case _:
            raise RuntimeError(f"Unsupported platform: {system}")
