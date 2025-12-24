# Contributing

Guide for contributing to BalatroBot development.

!!! warning "Help Needed: Linux (Proton) Support"

    We currently lack CLI support for **Linux (Proton)**. Contributions to implement this platform are highly welcome!

    Please refer to the existing implementations for guidance:

    - **macOS:** `src/balatrobot/platforms/macos.py`
    - **Windows:** `src/balatrobot/platforms/windows.py`
    - **Linux (Native):** `src/balatrobot/platforms/native.py`

## Prerequisites

- **Balatro** (v1.0.1+)
- **Lovely Injector** (v0.8.0+) - [Installation](https://github.com/ethangreen-dev/lovely-injector)
- **Steamodded** (v1.0.0-beta-1221a+) - [Installation](https://github.com/Steamopollys/Steamodded)
- **DebugPlus** (v1.5.1+) (optional) - Required for test endpoints

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/balatrobot.git
cd balatrobot
```

### 2. Symlink to Mods Folder

Instead of copying files, create a symlink for easier development:

**macOS:**

```bash
ln -s "$(pwd)" ~/Library/Application\ Support/Balatro/Mods/balatrobot
```

**Linux:**

```bash
ln -s "$(pwd)" ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/
```

**Windows (PowerShell as Admin):**

```powershell
New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Balatro\Mods\balatrobot" -Target (Get-Location)
```

### 3. Activate Virtual Environment

Activate the virtual environment to use the `balatrobot` command:

**macOS/Linux:**

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Launch Balatro

Start with debug and fast mode for development:

```bash
balatrobot --debug --fast
```

For detailed CLI options, see the [CLI Reference](cli.md).

### 5. Running Tests

Tests use Python + pytest to communicate with the Lua API.

!!! info "Separate Lua and CLI test suites"

    The Lua and CLI test suites **must be run separately**. Running them together (e.g., `pytest tests`) is not supported.

```bash
# Install all dependencies
make install

# Run all tests (runs CLI and Lua suites separately)
make test

# Run Lua tests (parallel execution recommended)
# Use -n 6 (or lower if your system is resource constrained)
pytest -n 6 tests/lua

# Run CLI tests (must be run separately)
pytest tests/cli

# Run specific test file
pytest tests/lua/endpoints/test_health.py -v

# Run tests with dev marker only
pytest -n 6 tests/lua -m dev

# Run only integration tests (starts Balatro)
pytest tests/lua -m integration

# Run tests that do not require Balatro instance
pytest tests/lua -m "not integration"
```

## Code Structure

```
src/lua/
├── core/
│   ├── server.lua       # HTTP server
│   ├── dispatcher.lua   # Request routing
│   └── validator.lua    # Schema validation
├── endpoints/           # API endpoints
│   ├── health.lua
│   ├── gamestate.lua
│   ├── play.lua
│   └── ...
└── utils/
    ├── types.lua        # Type definitions
    ├── enums.lua        # Enum values
    ├── errors.lua       # Error codes
    ├── gamestate.lua    # State extraction
    └── openrpc.json     # API spec
```

## Adding a New Endpoint

- Create `src/lua/endpoints/your_endpoint.lua`:

```lua
return {
  name = "your_endpoint",
  description = "Brief description",
  schema = {
    param_name = {
      type = "string",
      required = true,
      description = "Parameter description",
    },
  },
  requires_state = { G.STATES.SHOP },  -- Optional
  execute = function(args, send_response)
    -- Implementation
    send_response(BB_GAMESTATE.get_gamestate())
  end,
}
```

- Add tests in `tests/lua/endpoints/test_your_endpoint.py`

> When writing tests for new endpoints, you can use the `@pytest.mark.dev` decorator to only run the tests you are developing with `pytest -n 6 tests/lua -m dev`.

- Update `src/lua/utils/openrpc.json` with the new method

- Update `docs/api.md` with the new method

## Pull Request Guidelines

1. **One feature per PR** - Keep changes focused
2. **Add tests** - New endpoints need test coverage
3. **Update docs** - Update api.md and openrpc.json for API changes
4. **Follow conventions** - Match existing code style
5. **Test locally** - Ensure both `pytest -n 6 tests/lua` and `pytest tests/cli` pass
