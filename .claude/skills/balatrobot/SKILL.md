---
name: balatrobot
description: Run and debug BalatroBot locally. Use when you need to start Balatro with the BalatroBot Lua mod, manually test or reproduce issues via the JSON-RPC HTTP API, inspect the newest session logs under logs/, and capture screenshots into logs/<session>/artifacts/ using only the balatrobot CLI (no curl, no uvx).
disable-model-invocation: true
---

# BalatroBot debug/runbook

## Ground rules

- Run commands from the repo root.
- Use `balatrobot ...` only (no `uvx`, no `curl`).
- Run `balatrobot api ...` requests sequentially (avoid concurrent calls).
- Prefer minimal, targeted changes while debugging; avoid large refactors.

## Start BalatroBot

### Choose a port (recommended)

Pick a random port in the range `20000-30000` to avoid the port staying busy for ~20-30s after restarting:

```bash
PORT="$((20000 + RANDOM % 10001))"
echo "Using PORT=$PORT"
```

Pick a new random `PORT` every time you restart `balatrobot serve` (crash/restart/kill/start).

### Default profile (most cases)

Use headless mode unless explicitly asked to take screenshots:

```bash
balatrobot serve --port "$PORT" --headless --fast --debug
```

### Screenshot profile (only when explicitly asked)

Use render-on-API mode for deterministic screenshots:

```bash
balatrobot serve --port "$PORT" --render-on-api --fast --debug
```

## Call the API (no curl)

Run API calls in a second terminal while `balatrobot serve ...` is running.

Reminder: wrap JSON params in single quotes so you don't need to escape JSON double quotes.

```bash
# Health check
balatrobot api health --port "$PORT"

# Get full game state
balatrobot api gamestate --port "$PORT"

# Return to menu
balatrobot api menu --port "$PORT"

# Start a new run
balatrobot api start '{"deck":"RED","stake":"WHITE"}' --port "$PORT"

# Select blind
balatrobot api select --port "$PORT"

# Play cards (0-based indices)
balatrobot api play '{"cards":[0,1,2,3,4]}' --port "$PORT"
```

Always pass the same `--port` to both `serve` and `api`.

## Logs and sessions

### Session layout

Each `balatrobot serve ...` run creates:

- `logs/<session>/<port>.log` (game + mod stdout/stderr)

`<session>` is a timestamp folder like `2025-12-29T19-18-18` (lexicographically sortable).

### Find the current session

Pick the newest session directory (works because of the timestamp format):

```bash
SESSION="$(ls -1 logs | sort | tail -n 1)"
```

Use it to open/tail the log:

```bash
tail -f "logs/$SESSION/$PORT.log"
```

The log filename matches the port: `logs/<session>/<port>.log`.

## Screenshots (write to logs/<session>/artifacts/)

Only do this when explicitly asked for a screenshot.

1) Start the server with the screenshot profile:

```bash
balatrobot serve --port "$PORT" --render-on-api --fast --debug
```

2) Create the artifacts directory under the newest session:

```bash
SESSION="$(ls -1 logs | sort | tail -n 1)"
mkdir -p "logs/$SESSION/artifacts"
```

3) Call the screenshot endpoint with a path inside that folder:

```bash
balatrobot api screenshot "{\"path\":\"logs/$SESSION/artifacts/screenshot.png\"}" --port "$PORT"
```

## Debug workflow (tight loop)

1) Reproduce with the smallest possible sequence of `balatrobot api ...` calls.
2) Capture:
   - the exact `balatrobot serve ...` command,
   - host/port,
   - the session folder name,
   - relevant excerpts from `logs/<session>/<port>.log`,
   - the JSON outputs/errors from `balatrobot api ...`.
3) Read the most relevant code before changing anything.
4) If needed, add minimal logging close to the suspected behavior, then re-run.

## Where to look in the repo

- CLI entry points: `src/balatrobot/cli/serve.py`, `src/balatrobot/cli/api.py`
- Game process + log session creation: `src/balatrobot/manager.py`
- Lua HTTP server + dispatcher: `src/lua/core/server.lua`, `src/lua/core/dispatcher.lua`
- API reference/spec: `docs/api.md`, `src/lua/utils/openrpc.json`
- Endpoint implementations: `src/lua/endpoints/*.lua`
