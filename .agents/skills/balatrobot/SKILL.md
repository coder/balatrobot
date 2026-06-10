---
name: balatrobot
description: Launch Balatro with the BalatroBot mod and interact via the CLI. Use when you need to manually test, reproduce issues, or inspect game state through the JSON-RPC API.
---

# BalatroBot CLI

Four commands: `serve`, `api`, `list`, `stop`. Explore any with `--help`.

## `serve` — start Balatro

```bash
balatrobot serve --help
```

Typical invocation:

```bash
balatrobot serve --render headless --settings ~/balatrosettings/profiles/fast --debug
```

Key flags:
- `--render [headfull|headless|ondemand]` — rendering mode (default: headfull)
- `--settings PATH` — path to balatrosettings profile directory
- `--debug` — enable debug endpoints
- `--num` — number of instances
- `--path-*` — path overrides (`--path-balatro`, `--path-lovely`, `--path-love`, `--path-logs`)

All flags have `BALATROBOT_*` env var equivalents (e.g. `BALATROBOT_RENDER=headless`). See `src/balatrobot/config.py` for the full mapping.

**Requirement:** The mod only activates when the selected Balatro in-game profile is named exactly `BalatroBot`. Create this profile in Balatro's profile selector and select it before launching via `serve`.

`serve` auto-allocates ports, prints instance URLs and the session logs directory, then blocks until Ctrl+C. It writes a state file so other commands can discover the running instances.

## `stop` — stop a running server

```bash
balatrobot stop
```

Reads the session state file, sends SIGTERM to the server PID, then polls up to 5 s for it to exit. Cleans up the state file on success. Safe to call when nothing is running (prints "No running instances.").

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

Each session directory (`logs/<timestamp>/`) contains per-instance files: `<port>.log` (Balatro/Love2D output, traces, errors), `<port>.req.jsonl` (JSON-RPC requests), `<port>.res.jsonl` (JSON-RPC responses). JSONL traces are written automatically by the Lua server. Find paths via `balatrobot list` or `balatrobot list --json | jq '.instances[].log_path'`.

## `api --requests` — replay & verify

```bash
balatrobot api --requests logs/<ts>/<port>.req.jsonl
balatrobot api --requests logs/<ts>/<port>.req.jsonl --responses logs/<ts>/<port>.res.jsonl
```

Replays a JSONL request trace against a running instance. `--responses` compares each live response against the recorded one (exits on first divergence). Mutually exclusive with positional `METHOD`.
