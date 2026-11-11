"""Score the run: the blinds it defeated, of the 24 in a winning run, from the live game or the last state the
`balatro` command saw if the game is gone."""

import json
import subprocess
import sys
from pathlib import Path

BLINDS = 24
LAST_STATE = Path("/var/lib/balatro/last_state.json")


def defeated_blinds(state: dict) -> int:
    """Blinds the run defeated: a won run's 24, else three per ante passed and those beaten in the current one."""
    if state.get("won"):
        return BLINDS
    ante = max(1, int(state.get("ante_num") or 1))
    blinds = state.get("blinds") or {}
    current = sum(
        1
        for name in ("small", "big", "boss")
        if isinstance(blinds.get(name), dict)
        and blinds[name].get("status") == "DEFEATED"
    )
    return min(BLINDS, (ante - 1) * 3 + current)


def final_state() -> dict:
    try:
        output = subprocess.run(
            ["balatro", "gamestate", "--json"],
            capture_output=True,
            check=False,
            text=True,
            timeout=300,
        )
        state = json.loads(output.stdout) if output.returncode == 0 else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        state = {}
    if state.get("state") != "MENU" and "ante_num" in state:
        return state
    return json.loads(LAST_STATE.read_text()) if LAST_STATE.exists() else {}


if __name__ == "__main__":
    state = final_state()
    defeated = defeated_blinds(state)
    print(
        f"ante {state.get('ante_num')}, {state.get('state')}, {defeated} of {BLINDS} blinds defeated",
        file=sys.stderr,
    )
    print(json.dumps({"reward": defeated / BLINDS, "blinds": defeated}))
