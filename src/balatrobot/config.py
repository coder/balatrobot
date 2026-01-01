"""Configuration dataclass for BalatroBot launcher."""

import os
from dataclasses import dataclass
from typing import Any, Self

# Mapping: config field -> env var
ENV_MAP: dict[str, str] = {
    "host": "BALATROBOT_HOST",
    "port": "BALATROBOT_PORT",
    "fast": "BALATROBOT_FAST",
    "headless": "BALATROBOT_HEADLESS",
    "render_on_api": "BALATROBOT_RENDER_ON_API",
    "audio": "BALATROBOT_AUDIO",
    "debug": "BALATROBOT_DEBUG",
    "no_shaders": "BALATROBOT_NO_SHADERS",
    "balatro_path": "BALATROBOT_BALATRO_PATH",
    "lovely_path": "BALATROBOT_LOVELY_PATH",
    "love_path": "BALATROBOT_LOVE_PATH",
    "steam_path": "BALATROBOT_STEAM_PATH",
    "platform": "BALATROBOT_PLATFORM",
    "logs_path": "BALATROBOT_LOGS_PATH",
}

BOOL_FIELDS = frozenset(
    {"fast", "headless", "render_on_api", "audio", "debug", "no_shaders"}
)
INT_FIELDS = frozenset({"port"})


def _parse_env_value(field: str, value: str) -> str | int | bool:
    """Convert env var string to proper type. Raises ValueError on invalid int."""
    if field in BOOL_FIELDS:
        return value in ("1", "true")
    if field in INT_FIELDS:
        return int(value)  # Raises ValueError if invalid
    return value


@dataclass
class Config:
    """Configuration for BalatroBot launcher."""

    # HTTP
    host: str = "127.0.0.1"
    port: int = 12346

    # Balatro
    fast: bool = False
    headless: bool = False
    render_on_api: bool = False
    audio: bool = False
    debug: bool = False
    no_shaders: bool = False

    # Launcher
    balatro_path: str | None = None
    lovely_path: str | None = None
    love_path: str | None = None
    steam_path: str | None = None

    # Instance
    platform: str | None = None
    logs_path: str = "logs"

    @classmethod
    def from_args(cls, args) -> Self:
        """Create Config from CLI args with env var fallback."""
        kwargs: dict[str, Any] = {}

        for field, env_var in ENV_MAP.items():
            cli_val = getattr(args, field, None)
            if cli_val is not None:
                kwargs[field] = cli_val
            elif (env_val := os.environ.get(env_var)) is not None:
                kwargs[field] = _parse_env_value(field, env_val)

        return cls(**kwargs)

    @classmethod
    def from_env(cls) -> Self:
        """Create Config from environment variables only."""
        kwargs: dict[str, Any] = {}

        for field, env_var in ENV_MAP.items():
            if (env_val := os.environ.get(env_var)) is not None:
                kwargs[field] = _parse_env_value(field, env_val)

        return cls(**kwargs)

    def to_env(self) -> dict[str, str]:
        """Convert config to environment variables dict."""
        env: dict[str, str] = {}
        for field, env_var in ENV_MAP.items():
            value = getattr(self, field)
            if value is None:
                continue
            if field in BOOL_FIELDS:
                if value:
                    env[env_var] = "1"
            else:
                env[env_var] = str(value)
        return env
