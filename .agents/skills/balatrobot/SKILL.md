---
name: balatrobot
description: Launch Balatro with the BalatroBot mod and interact via the CLI. Use when you need to manually test, reproduce issues, or inspect game state through the JSON-RPC API.
---

# BalatroBot CLI

Four commands: `serve`, `api`, `list`, `stop`. Explore any with `--help`.

## Workflow

```bash
# Start server in background (ports are ephemeral, auto-allocated)
nohup balatrobot serve --render headless --settings turbo --debug > /tmp/bb.log 2>&1 &
sleep 5
balatrobot api health           # auto-discovers port via state file — no --host/--port

# Call endpoints or replay a trace
balatrobot api gamestate
balatrobot api --requests path/to/trace.req.jsonl      # --requests also auto-discovers

balatrobot stop                                     # always use stop, never kill/pkill
```

## `serve`

```bash
balatrobot serve --render headless --settings turbo --debug
```

Key flags: `--render [headfull|headless|ondemand]` (default headfull), `--settings` (default "default"), `--debug`, `--num`. Blocks until Ctrl+C — background it with `&`/`nohup` before running other commands.

## `api`

```bash
balatrobot api <method> [JSON_PARAMS]       # params default {}
balatrobot api --requests PATH              # replay JSONL trace
balatrobot api --requests PATH --responses PATH  # verify against recorded
```

Reads the running instance from the state file — **never pass `--host`/`--port` manually** (ports are ephemeral). For multi-instance, use `-i`/`--index`.

```bash
balatrobot api health
balatrobot api start '{"deck":"RED","stake":"WHITE"}'
balatrobot api play '{"cards":[0,1,2,3,4]}'
balatrobot api buy '{"pack": 0}'
balatrobot api gamestate | jq '.state'
```

See `docs/api.md` for methods, params, and state machine.

## `list`

```bash
balatrobot list                                     # human-readable
balatrobot list --json | jq '.instances[0].port'    # extract port/log_path
```

## `stop`

```bash
balatrobot stop              # SIGTERM + 5s poll, cleans state file
```

## Logs

Session directory `logs/<timestamp>/` contains `<port>.log`, `<port>.req.jsonl`, `<port>.res.jsonl`. Find paths via `balatrobot list --json`.
