# Contributing to BalatroBot

Welcome to BalatroBot! We're excited that you're interested in contributing to this Python framework and Lua mod for creating automated bots to play Balatro.

BalatroBot uses a dual-architecture approach with a Python framework that communicates with a Lua mod running inside Balatro via TCP sockets. This allows for real-time bot automation and game state analysis.

## Project Status & Priorities

We track all development work using the [BalatroBot GitHub Project](https://github.com/orgs/coder/projects). This is the best place to see current priorities, ongoing work, and opportunities for contribution.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Balatro**: Version 1.0.1o-FULL
- **SMODS (Steamodded)**: Version 1.0.0-beta-0711a or newer
- **Python**: 3.13+ (managed via uv)
- **uv**: Python package manager ([Installation Guide](https://docs.astral.sh/uv/))
- **OS**: macOS, Linux. Windows is not currently supported
- **[DebugPlus](https://github.com/WilsontheWolf/DebugPlus) (optional)**: useful for Lua API development and debugging

### Development Environment Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/balatrobot.git
   cd balatrobot

   ```

1. **Install Dependencies**

   ```bash
   make install-dev

   ```

1. **Start Balatro with Mods**

   ```bash
   ./balatro.sh -p 12346

   ```

1. **Verify Balatro is Running**

   ```bash
   # Check if Balatro is running
   ./balatro.sh --status

   # Monitor startup logs
   tail -n 100 logs/balatro_12346.log

   ```

   Look for these success indicators:

   - "BalatrobotAPI initialized"
   - "BalatroBot loaded - version X.X.X"
   - "TCP socket created on port 12346"

## How to Contribute

### Types of Contributions Welcome

- **Bug Fixes**: Issues tracked in our GitHub project
- **Feature Development**: New bot strategies, API enhancements
- **Performance Improvements**: Optimization of TCP communication or game interaction
- **Documentation**: Improvements to guides, API documentation, or examples
- **Testing**: Additional test coverage, edge case handling

### Contribution Workflow

1. **Check Issues First** (Highly Encouraged)

   - Browse the [BalatroBot GitHub Project](https://github.com/orgs/coder/projects)
   - Comment on issues you'd like to work on
   - Create new issues for bugs or feature requests

1. **Fork & Branch**

   ```bash
   git checkout -b feature/your-feature-name

   ```

1. **Make Changes**

   - Follow our code style guidelines (see below)
   - Add tests for new functionality
   - Update documentation as needed

1. **Create Pull Request**

   - **Important**: Enable "Allow edits from maintainers" when creating your PR
   - Link to related issues
   - Provide clear description of changes
   - Include tests for new functionality

### Commit Messages

We highly encourage following [Conventional Commits](https://www.conventionalcommits.org/) format:

```text
feat(api): add new game state detection
fix(tcp): resolve connection timeout issues
docs(readme): update setup instructions
test(api): add shop booster validation tests

```

## Development & Testing

### Makefile Commands

BalatroBot includes a comprehensive Makefile that provides a convenient interface for all development tasks. Use `make help` to see all available commands:

```bash
# Show all available commands with descriptions
make help

```

#### Installation & Setup

```bash
make install        # Install package dependencies
make install-dev    # Install with development dependencies

```

#### Code Quality & Formatting

```bash
make lint           # Run ruff linter (check only)
make lint-fix       # Run ruff linter with auto-fixes
make format         # Run ruff formatter and stylua
make format-md      # Run markdown formatter
make typecheck      # Run type checker
make quality        # Run all code quality checks
make dev            # Quick development check (format + lint + typecheck, no tests)

```

### Testing Requirements

#### Testing with Makefile

```bash
make test           # Run tests with single instance (auto-starts if needed)
make test-parallel  # Run tests on 4 instances (auto-starts if needed)
make test-teardown  # Kill all Balatro instances

# Complete workflow including tests
make all            # Run format + lint + typecheck + test

```

The testing system automatically handles Balatro instance management:

- **`make test`**: Runs tests with a single instance, auto-starting if needed
- **`make test-parallel`**: Runs tests on 4 instances for ~4x speedup, auto-starting if needed
- **`make test-teardown`**: Cleans up all instances when done

Both test commands keep instances running after completion for faster subsequent runs.

#### Using Checkpoints for Test Setup

The checkpointing system allows you to save and load specific game states, significantly speeding up test setup:

**Creating Test Checkpoints:**

```bash
# Create a checkpoint at a specific game state
python scripts/create_test_checkpoint.py shop tests/lua/endpoints/checkpoints/shop_state.jkr
python scripts/create_test_checkpoint.py blind_select tests/lua/endpoints/checkpoints/blind_select.jkr
python scripts/create_test_checkpoint.py in_game tests/lua/endpoints/checkpoints/in_game.jkr

```

**Using Checkpoints in Tests:**

```python
# In conftest.py or test files
from ..conftest import prepare_checkpoint

def setup_and_teardown(tcp_client):
    # Load a checkpoint directly (no restart needed!)
    checkpoint_path = Path(__file__).parent / "checkpoints" / "shop_state.jkr"
    game_state = prepare_checkpoint(tcp_client, checkpoint_path)
    assert game_state["state"] == State.SHOP.value

```

**Benefits of Checkpoints:**

- **Faster Tests**: Skip manual game setup steps (particularly helpful for edge cases)
- **Consistency**: Always start from exact same state
- **Reusability**: Share checkpoints across multiple tests
- **No Restarts**: Uses `load_save` API to load directly from any game state

**Python Client Methods:**

```python
from balatrobot import BalatroClient

with BalatroClient() as client:
    # Save current game state as checkpoint
    client.save_checkpoint("tests/fixtures/my_state.jkr")

    # Load a checkpoint for testing
    save_path = client.prepare_save("tests/fixtures/my_state.jkr")
    game_state = client.load_save(save_path)

```

**Manual Setup for Advanced Testing:**

```bash
# Check/manage Balatro instances
./balatro.sh --status                   # Show running instances
./balatro.sh --kill                     # Kill all instances

# Start instances manually
./balatro.sh -p 12346 -p 12347          # Two instances
./balatro.sh --headless --fast -p 12346 -p 12347 -p 12348 -p 12349  # Full setup
./balatro.sh --audio -p 12346                                    # With audio enabled

# Manual parallel testing
pytest -n 4 --port 12346 --port 12347 --port 12348 --port 12349 tests/lua/

```

**Performance Modes:**

- **`--headless`**: No graphics, ideal for servers
- **`--fast`**: 10x speed, disabled effects, optimal for testing
- **`--audio`**: Enable audio (disabled by default for performance)

### Documentation

```bash
make docs-serve     # Serve documentation locally
make docs-build     # Build documentation
make docs-clean     # Clean built documentation

```

### Build & Maintenance

```bash
make build          # Build package for distribution
make clean          # Clean build artifacts and caches

```

## Technical Guidelines

### Python Development

- **Style**: Follow modern Python 3.13+ patterns
- **Type Hints**: Use pipe operator for unions (`str | int | None`)
- **Type Aliases**: Use `type` statement
- **Docstrings**: Google-style without type information (types in annotations)
- **Generics**: Modern syntax (`class Container[T]:`)

### Lua Development

- **Focus Area**: Primary development is on `src/lua/api.lua`
- **Communication**: TCP protocol on port 12346
- **Debugging**: Use DebugPlus mod for enhanced debugging capabilities

### Environment Variables

Configure BalatroBot behavior with these environment variables:

- **`BALATROBOT_HEADLESS=1`**: Disable graphics for server environments
- **`BALATROBOT_FAST=1`**: Enable 10x speed with disabled effects for testing
- **`BALATROBOT_AUDIO=1`**: Enable audio (disabled by default for performance)
- **`BALATROBOT_PORT`**: TCP communication port (default: "12346")

## Communication & Community

### Preferred Channels

- **GitHub Issues**: Primary communication for bugs, features, and project coordination
- **Discord**: Join us at the [Balatro Discord](https://discord.com/channels/1116389027176787968/1391371948629426316) for real-time discussions

Happy contributing!
