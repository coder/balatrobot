---
name: balatrobot
description: Launch Balatro with the BalatroBot mod and interact via the CLI. Use when you need to manually test, reproduce issues, or inspect game state through the JSON-RPC API.
---

# BalatroBot CLI

Three commands: `serve`, `api`, `list`. Explore any with `--help`.

## `serve` — start Balatro

```bash
balatrobot serve --help
```

Typical invocation:

```bash
balatrobot serve --headless --fast --debug
```

Key flags: `--headless`, `--fast` (10× speed), `--debug` (DebugPlus logging), `-n`/`--num-instances` (pool).

All flags have `BALATROBOT_*` env var equivalents (e.g. `BALATROBOT_FAST=1`). See `src/balatrobot/config.py` for the full mapping.

`serve` auto-allocates ports, prints instance URLs and the session logs directory, then blocks until Ctrl+C. It writes a state file so other commands can discover the running instances.

## `list` — show running instances

```bash
balatrobot list            # human-readable
balatrobot list --json     # machine-readable (pipe to jq)
```

Shows instances from the current session's state file, including per-instance log paths. Use `--json` and pipe to `jq` to extract specific fields.

## `api` — call endpoints

```bash
balatrobot api <method> [JSON_PARAMS]
balatrobot api <method> --help
```

Auto-discovers the running instance from the state file — no `--host`/`--port` needed for single-instance sessions. For multi-instance pools, use `-i`/`--index` (0-based, default 0).

Params are a JSON string (default `{}`). Examples:

```bash
balatrobot api health
balatrobot api gamestate
balatrobot api start '{"deck":"RED","stake":"WHITE"}'
balatrobot api select
balatrobot api play '{"cards":[0,1,2,3,4]}'
balatrobot api discard '{"cards":[0,1]}'
...
```

Output is pretty-printed JSON. Pipe to `jq` for filtering:

```bash
balatrobot api gamestate | jq '.state'
balatrobot api gamestate | jq '{state, money, hand: .hand.count}'
```

API errors surface as `<NAME> - <message>` on stderr (e.g. `INVALID_STATE`, `BAD_REQUEST`).
Full API reference (methods, errors, states): `docs/api.md`.

## Logs

Each instance has a log file (Balatro/Love2D output, Lovely traces, Lua errors, HTTP server logs). Find log paths via `balatrobot list` or `balatrobot list --json | jq '.instances[].log_path'`.

Logs are stored under `logs/<timestamp>/<port>.log` (configurable via `--logs-path`). When `serve` fails or endpoints behave unexpectedly, check the log file.
