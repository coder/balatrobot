"""Configuration dataclass for BalatroBot launcher."""

import os
from dataclasses import dataclass
from typing import Any, Self

ENV_MAP: dict[str, str] = {
    "host": "BALATROBOT_HOST",
    "render": "BALATROBOT_RENDER",
    "debug": "BALATROBOT_DEBUG",
    "screenshots": "BALATROBOT_SCREENSHOTS",
    "settings": "BALATROBOT_SETTINGS",
    "path_balatro": "BALATROBOT_PATH_BALATRO",
    "path_lovely": "BALATROBOT_PATH_LOVELY",
    "path_love": "BALATROBOT_PATH_LOVE",
    "platform": "BALATROBOT_PLATFORM",
    "path_logs": "BALATROBOT_PATH_LOGS",
}

RENDER_CHOICES = frozenset({"headfull", "headless", "ondemand"})


def _parse_env_value(field: str, value: str) -> str | bool:
    """Coerce env var string to the right Python type."""
    if field in ("debug", "screenshots"):
        return value in ("1", "true")
    return value


@dataclass
class Config:
    """Configuration for BalatroBot launcher."""

    # HTTP
    host: str = "127.0.0.1"
    port: int = 12346

    # Settings profile name (bare name, e.g. "fast", "turbo", "light")
    settings: str | None = None

    # Render mode
    render: str = "headfull"

    # Debug
    debug: bool = False

    # Screenshot logging
    screenshots: bool = False

    # Launcher
    path_balatro: str | None = None
    path_lovely: str | None = None
    path_love: str | None = None
    platform: str | None = None
    path_logs: str | None = None

    def __post_init__(self) -> None:
        if self.render not in RENDER_CHOICES:
            raise ValueError(
                f"Invalid render mode '{self.render}'. "
                f"Choose from: {', '.join(sorted(RENDER_CHOICES))}"
            )

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
            if field in ("debug", "screenshots"):
                if value:
                    env[env_var] = "1"
            else:
                env[env_var] = str(value)
        env["BALATROBOT_PORT"] = str(self.port)
        return env
