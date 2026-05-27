---
name: balatrobot
description: Launch Balatro with the BalatroBot mod and interact via the CLI. Use when you need to manually test, reproduce issues, or inspect game state through the JSON-RPC API.
---

# BalatroBot CLI runbook

Run commands from the repo root. Use `balatrobot ...` only (no `curl`, no `uvx`).
Help is available with `balatrobot --help`.

## Start a session

Pick a random port in 20000–30000 to avoid conflicts:

```bash
PORT="$((20000 + RANDOM % 10001))"
balatrobot serve --port "$PORT" --headless --fast --debug
```

Help is available with `balatrobot serve --help`.
Use `--render-on-api` instead of `--headless` when you need screenshots.

## Call the API (in a second terminal)

```bash
balatrobot api health --port "$PORT"
balatrobot api gamestate --port "$PORT"
balatrobot api start '{"deck":"RED","stake":"WHITE"}' --port "$PORT"
balatrobot api select --port "$PORT"
balatrobot api play '{"cards":[0,1,2,3,4]}' --port "$PORT"
balatrobot api menu --port "$PORT"
```

Help is available with `balatrobot serve --help`.
Pipe to `jq` to filter responses. Example: `balatrobot api gamestate --port "$PORT" | jq '.state'`.

Full API reference: `docs/api.md`.
