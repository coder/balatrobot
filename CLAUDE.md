# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**GitHub Repository**: [`coder/balatrobot`](https://github.com/coder/balatrobot)

## Overview

BalatroBot is a framework for Balatro bot development. It consists of two main parts:

1. **Python Package** (`src/balatrobot/`): A CLI and library to manage the Balatro game process, inject the mod, and handle communication.
2. **Lua API** (`src/lua/`): The mod code running inside Balatro (Love2D) that exposes a HTTP JSON-RPC 2.0 API.

### Testing

Integration tests (`tests/lua`) automatically start and stop Balatro instances on random ports.

```bash
# Run all tests (CLI and Lua suites)
make test

# Run Lua integration tests in parallel
pytest -n 6 tests/lua

# Run CLI tests
pytest tests/cli

# Run specific tests
pytest tests/lua/endpoints/test_health.py -v
pytest tests/lua/endpoints/test_health.py::TestHealthEndpoint::test_health_from_MENU -v

# Run only integration tests
pytest tests/cli -m integration

# Run non-integration tests (no Balatro instance required)
pytest tests/cli -m "not integration"

# Manual launch for dev/debugging
balatrobot --fast --debug
```

### Make Commands

Available make targets:

| Target           | Description                                             |
| ---------------- | ------------------------------------------------------- |
| `make help`      | Show all available targets                              |
| `make lint`      | Run ruff linter (check only)                            |
| `make format`    | Run ruff and mdformat formatters                        |
| `make typecheck` | Run type checker (Python and Lua)                       |
| `make quality`   | Run all code quality checks (lint + typecheck + format) |
| `make test`      | Run all tests                                           |
| `make all`       | Run all quality checks and tests                        |
| `make fixtures`  | Generate test fixtures                                  |
| `make install`   | Install dependencies                                    |

**Important rules:**

1. **Only run make commands when explicitly asked.** Do not proactively run `make test`, `make quality`, etc.
2. **Never run bare linting/formatting/typechecking tools.** Always use make targets instead:
    - Use `make lint` instead of `ruff check`
    - Use `make format` instead of `ruff format`
    - Use `make typecheck` instead of `ty check`
    - Use `make quality` for all checks combined

## Architecture

### 1. Python Layer (`src/balatrobot/`)

Controls the game lifecycle and provides the CLI.

- **CLI** (`cli.py`): Entry point (`balatrobot`). Handles arguments like `--fast`, `--debug`, `--headless`.
- **Manager** (`manager.py`): `BalatroInstance` context manager. Starts the game process, handles logging, and waits for the API to be healthy.
- **Config** (`config.py`): Configuration management using `dataclasses` and environment variables.
- **Platform Abstraction** (`platforms/`): Cross-platform game launcher system with platform-specific implementations for macOS, Windows, and native Love2D.

### 2. Lua Layer (`src/lua/`)

Runs inside the game engine and exposes an API.

- **HTTP Server** (`src/lua/core/server.lua`)

    - Single-client HTTP/1.1 server on port 12346 (default)
    - **Protocol**: JSON-RPC 2.0 over HTTP POST to `/`
    - **Request**: `{"jsonrpc": "2.0", "method": "endpoint", "params": {...}, "id": 1}`
    - **Response**: `{"jsonrpc": "2.0", "result": {...}, "id": 1}`
    - Max body size: 64KB

- **Dispatcher** (`src/lua/core/dispatcher.lua`)

    - Routes requests based on the `method` field.
    - Validates:
        1. Protocol (JSON-RPC 2.0, valid ID)
        2. Schema (via `validator.lua`)
        3. Game State (`requires_state`)
        4. Endpoint execution

- **Endpoints** (`src/lua/endpoints/*.lua`)

    - Stateless modules defining `schema` and `execute` functions.
    - 0-based indexing in API vs 1-based in Lua.
    - OpenRPC Specification (`src/lua/utils/openrpc.json`): Machine-readable API documentation describing all endpoints.

    **Core Endpoints:**

    - `add.lua`: Add a new card (joker, consumable, voucher, playing card, or booster pack).
    - `buy.lua`: Buy a card or booster pack from the shop.
    - `cash_out.lua`: Cash out and collect round rewards.
    - `discard.lua`: Discard cards from the hand.
    - `gamestate.lua`: Get current game state.
    - `health.lua`: Health check endpoint for connection testing.
    - `load.lua`: Load a saved run state from a file.
    - `menu.lua`: Return to the main menu from any game state.
    - `next_round.lua`: Leave the shop and advance to blind selection.
    - `pack.lua`: Select or skip a card from an opened booster pack.
    - `play.lua`: Play a card from the hand.
    - `rearrange.lua`: Rearrange cards in hand, jokers, or consumables.
    - `reroll.lua`: Reroll to update the cards in the shop area.
    - `save.lua`: Save the current run state to a file.
    - `screenshot.lua`: Take a screenshot of the current game state.
    - `select.lua`: Select the current blind.
    - `sell.lua`: Sell a joker or consumable from player inventory.
    - `set.lua`: Set a in-game value (money, chips, ante, etc.).
    - `skip.lua`: Skip the current blind (Small or Big only).
    - `start.lua`: Start a new game run with specified deck and stake.
    - `use.lua`: Use a consumable card with optional target cards.

    **Test Endpoints (`src/lua/endpoints/tests/*.lua`):**

    - `echo.lua`: Test endpoint for dispatcher testing.
    - `endpoint.lua`: Test endpoint with schema for dispatcher testing.
    - `error.lua`: Test endpoint that throws runtime errors.
    - `state.lua`: Test endpoint that requires specific game states.
    - `validation.lua`: Comprehensive validation test endpoint.

## Key Files

- **Python**:
    - `src/balatrobot/cli.py`: Main entry point.
    - `src/balatrobot/manager.py`: Game process logic.
- **Lua**:
    - `balatrobot.lua`: Mod entry point.
    - `src/lua/core/server.lua`: HTTP/TCP handling.
    - `src/lua/endpoints/`: All API commands.
- **Configuration**:
    - `pyproject.toml`: Python dependencies and tools config.
    - `balatrobot.json` / `balatrobot.lua`: SMODS mod metadata.

### Error Handling

Error codes are mapped to JSON-RPC standard and custom ranges:

- `INTERNAL_ERROR` (-32000): Runtime errors
- `BAD_REQUEST` (-32001): Invalid schema or parameters
- `INVALID_STATE` (-32002): Action not allowed in current game state
- `NOT_ALLOWED` (-32003): Action prevented by game rules

Error responses follow JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Human readable error",
    "data": { "name": "BAD_REQUEST" }
  },
  "id": 1
}
```
