# Contributing

Guide for contributing to BalatroBot development.

!!! warning "Help Needed: Linux (Proton) Support"

    We currently lack CLI support for **Linux (Proton)**. Contributions to implement this platform are highly welcome!

    Please refer to the existing implementations for guidance:

    - **macOS:** `src/balatrobot/platforms/macos.py`
    - **Windows:** `src/balatrobot/platforms/windows.py`
    - **Linux (Native):** `src/balatrobot/platforms/native.py`

## Prerequisites

- **Balatro** (v1.0.1+) - Purchase from [Steam](https://store.steampowered.com/app/2379780/Balatro/)
- **Lovely Injector** (v0.8.0+) - Follow the [installation guide](https://github.com/ethangreen-dev/lovely-injector#manual-installation)
- **Steamodded** (v1.0.0-beta-1221a+) - Follow the [installation guide](https://github.com/Steamodded/smods/wiki)
- **Uv** (v0.9.21+) - Follow the [installation guide](https://docs.astral.sh/uv)
- **DebugPlus** (v1.5.1+) (optional) - Follow the [installation guide](https://github.com/WilsontheWolf/DebugPlus) - Required for test endpoints

## Development Environment Setup

### direnv (Recommended)

We use [direnv](https://direnv.net/) to automatically manage environment variables and virtual environment activation. When you `cd` into the project directory, direnv automatically loads settings from `.envrc`.

!!! warning "Contains Secrets"

    The `.envrc` file may contain API keys and tokens. **Never commit this file**.

**Example `.envrc` configuration:**

```bash
# Load the virtual environment
source .venv/bin/activate

# Python-specific variables
export PYTHONUNBUFFERED="1"
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
export PYTHONPATH="${PWD}/tests:${PYTHONPATH}"

# BALATROBOT env vars
export BALATROBOT_FAST=1
export BALATROBOT_DEBUG=1
export BALATROBOT_LOVE_PATH='/path/to/Balatro/love'
export BALATROBOT_LOVELY_PATH='/path/to/liblovely.dylib'
export BALATROBOT_RENDER_ON_API=0
export BALATROBOT_HEADLESS=1
export BALATROBOT_AUDIO=0
```

**Setup:** Install [direnv](https://direnv.net/), then create `.envrc` in the project root with the above configuration, updating paths for your system.

### Lua LSP Configuration

The `.luarc.json` file should be placed at the root of the balatrobot repository. It configures the Lua Language Server for IDE support (autocomplete, diagnostics, type checking).

!!! info "Update Library Paths"

    You **must** update the `workspace.library` paths in `.luarc.json` to match your system:

    - Steamodded LSP definitions: `path/to/Mods/smods/lsp_def`
    - Love2D library: `path/to/love2d/library` (clone locally: [LuaCATS/love2d](https://github.com/LuaCATS/love2d))
    - LuaSocket library: `path/to/luasocket/library` (clone locally: [LuaCATS/luasocket](https://github.com/LuaCATS/luasocket))

**Example `.luarc.json`:**

```json
{
  "$schema": "https://raw.githubusercontent.com/LuaLS/vscode-lua/master/setting/schema.json",
  "workspace": {
    "library": [
      "/path/to/Balatro/Mods/smods/lsp_def",
      "/path/to/love2d/library",
      "/path/to/luasocket/library",
      "src/lua"
    ]
  },
  "diagnostics": {
    "disable": [
      "lowercase-global"
    ],
    "globals": [
      "G",
      "BB_GAMESTATE",
      "BB_ERROR_NAMES",
      "BB_ENDPOINTS"
    ]
  },
  "type": {
    "weakUnionCheck": true
  }
}
```

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

**Linux (Proton):**

```bash
ln -s "$(pwd)" ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/
```

**Linux (native):**

```bash
ln -s "$(pwd)" ~/.config/love/Mods/balatrobot/
```

**Windows (PowerShell as Admin):**

```powershell
New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Balatro\Mods\balatrobot" -Target (Get-Location)
```

### 3. Install Dependencies

```bash
make install
```

### 4. Activate Virtual Environment

Activate the virtual environment to use the `balatrobot` command:

**macOS/Linux:**

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

### 5. Launch Balatro

Start with debug and fast mode for development:

```bash
balatrobot --debug --fast
```

For detailed CLI options, see the [CLI Reference](cli.md).

### 6. Running Tests

Tests use Python + pytest to communicate with the Lua API. You don't need to have balatrobot running—the tests automatically start the required Balatro instances.

!!! info "Separate Lua and CLI test suites"

    The Lua and CLI test suites **must be run separately**. Running them together (e.g., `pytest tests`) is not supported.

```bash
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

## Available Make Commands

The project includes a Makefile with convenient targets for common development tasks. Run `make help` to see all available commands.

```bash
make help      # Show all available commands with descriptions
make install   # Install all dependencies (dev + test groups)
make lint      # Run ruff linter with auto-fix
make format    # Format code (Python, Markdown, Lua)
make typecheck # Run type checker (ty)
make quality   # Run all code quality checks
make fixtures  # Generate test fixtures (starts Balatro)
make test      # Run all tests (CLI + Lua suites)
make all       # Run quality checks + tests
```

!!! note "Test Fixtures"

    The `make fixtures` command is only required if you need to explicitly generate fixtures. When running tests, missing fixtures are automatically generated if required.

## Code Structure

```
src/lua/
├── core/
│   ├── server.lua       # HTTP server
│   ├── dispatcher.lua   # Request routing
│   └── validator.lua    # Schema validation
├── endpoints/           # API endpoints
│   ├── tests/           # Test-only endpoints
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

## Code Quality

Before committing, always run:

```bash
make quality  # Runs lint, typecheck, and format
```

**Test markers:**

- `@pytest.mark.dev`: Run only tests under development with `-m dev`
- `@pytest.mark.integration`: Tests that start Balatro (skip with `-m "not integration"`)

## Pull Request Guidelines

1. **One feature per PR** - Keep changes focused
2. **Add tests** - New endpoints need test coverage
3. **Update docs** - Update api.md and openrpc.json for API changes
4. **Run code quality checks** - Execute `make quality` before committing (see [Code Quality Tools](#code-quality-tools))
5. **Test locally** - Ensure both `pytest -n 6 tests/lua` and `pytest tests/cli` pass
6. **Use Conventional Commits** - Follow [Conventional Commits](https://www.conventionalcommits.org/) for automated changelog generation

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment.

### Workflows

- **code_quality.yml**: Runs linting, type checking, and formatting on every PR (equivalent to `make quality`)
- **deploy_docs.yml**: Deploys documentation to GitHub Pages when a release is published
- **release_please.yml**: Automated version management and changelog generation
- **release_pypi.yml**: Publishes the package to PyPI on release

### For Contributors

You don't need to worry about most CI/CD workflows—just ensure your PR passes the **code quality checks**:

```bash
make quality  # Run this before pushing
```

If CI fails on your PR, check the workflow logs on GitHub for details. Most issues can be fixed by running `make quality` locally.
