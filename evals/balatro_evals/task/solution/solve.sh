#!/bin/bash
# A fixed policy that checks the environment rather than the target: enter every blind, play the first five cards,
# cash out, leave the shop at once, and skip any pack.
set -euo pipefail
python3 - <<'PY'
import json
import subprocess


def call(method, params=None):
    output = subprocess.run(["balatro", method, json.dumps(params or {}), "--json"], capture_output=True, text=True)
    return json.loads(output.stdout) if output.stdout.startswith("{") else {}


state = call("gamestate")
for _ in range(400):
    phase = state.get("state")
    if phase == "GAME_OVER" or state.get("won"):
        break
    if phase == "BLIND_SELECT":
        state = call("select")
    elif phase == "SELECTING_HAND":
        hand = (state.get("hand") or {}).get("cards") or []
        state = call("play", {"cards": list(range(min(5, len(hand))))})
    elif phase == "ROUND_EVAL":
        state = call("cash_out")
    elif phase == "SHOP":
        state = call("next_round")
    elif phase == "SMODS_BOOSTER_OPENED":
        state = call("pack", {"skip": True})
    else:
        state = call("gamestate")
print(f"ended at ante {state.get('ante_num')} in {state.get('state')}")
PY
