"""Configuration dataclass for BalatroBot launcher."""

import os
from dataclasses import dataclass
from typing import Any, Self

ENV_MAP: dict[str, str] = {
    "host": "BALATROBOT_HOST",
    "port": "BALATROBOT_PORT",
    "render": "BALATROBOT_RENDER",
    "debug": "BALATROBOT_DEBUG",
    "settings": "BALATROBOT_SETTINGS",
    "path_balatro": "BALATROBOT_PATH_BALATRO",
    "path_lovely": "BALATROBOT_PATH_LOVELY",
    "path_love": "BALATROBOT_PATH_LOVE",
    "platform": "BALATROBOT_PLATFORM",
    "path_logs": "BALATROBOT_PATH_LOGS",
}

BOOL_FIELDS = frozenset({"debug"})

INT_FIELDS = frozenset({"port"})

RENDER_CHOICES = frozenset({"headfull", "headless", "ondemand"})


def _parse_env_value(field: str, value: str) -> str | int | bool:
    """Convert env var string to proper type. Raises ValueError on invalid int."""
    if field in BOOL_FIELDS:
        return value in ("1", "true")
    if field in INT_FIELDS:
        return int(value)
    return value


@dataclass
class Config:
    """Configuration for BalatroBot launcher."""

    # HTTP
    host: str = "127.0.0.1"
    port: int = 12346

    # Settings profile
    settings: str | None = None

    # Render mode
    render: str = "headfull"

    # Debug
    debug: bool = False

    # Launcher
    path_balatro: str | None = None
    path_lovely: str | None = None
    path_love: str | None = None
    platform: str | None = None
    path_logs: str = "logs"

    def __post_init__(self) -> None:
        if self.render not in RENDER_CHOICES:
            raise ValueError(
                f"Invalid render mode '{self.render}'. "
                f"Choose from: {', '.join(sorted(RENDER_CHOICES))}"
            )

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

    @classmethod
    def from_kwargs(cls, **kw: Any) -> Self:
        """Create Config from keyword arguments with env var fallback."""
        kwargs: dict[str, Any] = {}

        for field, env_var in ENV_MAP.items():
            if kw.get(field) is not None:
                kwargs[field] = kw[field]
            elif (env_val := os.environ.get(env_var)) is not None:
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
