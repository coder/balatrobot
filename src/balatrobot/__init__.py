"""BalatroBot - API for developing Balatro bots."""

from balatrobot.cli.client import APIError, BalatroClient
from balatrobot.config import Config
from balatrobot.instance import BalatroInstance
from balatrobot.pool import BalatroPool, InstanceInfo
from balatrobot.state import StateFile

__version__ = "1.5.2"
__all__ = [
    "APIError",
    "BalatroClient",
    "BalatroInstance",
    "BalatroPool",
    "Config",
    "InstanceInfo",
    "StateFile",
    "__version__",
]
