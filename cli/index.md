# CLI Reference

Command-line interface for the BalatroBot framework.

## Usage

```bash
# Start Balatro server
uvx balatrobot serve [OPTIONS]

# Call API on running server
uvx balatrobot api METHOD [PARAMS] [OPTIONS]

```

BalatroBot provides two commands:

- **serve** - Start Balatro with the BalatroBot mod loaded
- **api** - Call API endpoints on a running server

## serve Command

Start Balatro with the BalatroBot mod loaded and API server running.

```bash
uvx balatrobot serve [OPTIONS]

```

### Options

All options can be set via CLI flags or environment variables. CLI flags override environment variables.

| CLI Flag                        | Environment Variable             | Default       | Description                                |
| ------------------------------- | -------------------------------- | ------------- | ------------------------------------------ |
| `--host HOST`                   | `BALATROBOT_HOST`                | `127.0.0.1`   | Server hostname                            |
| `--port PORT`                   | `BALATROBOT_PORT`                | `12346`       | Server port                                |
| `--fast`                        | `BALATROBOT_FAST`                | `0`           | Enable fast mode (10x game speed)          |
| `--headless`                    | `BALATROBOT_HEADLESS`            | `0`           | Enable headless mode (minimal rendering)   |
| `--render-on-api`               | `BALATROBOT_RENDER_ON_API`       | `0`           | Render only on API calls                   |
| `--audio`                       | `BALATROBOT_AUDIO`               | `0`           | Enable audio                               |
| `--debug`                       | `BALATROBOT_DEBUG`               | `0`           | Enable debug mode (requires DebugPlus mod) |
| `--no-shaders`                  | `BALATROBOT_NO_SHADERS`          | `0`           | Disable all shaders                        |
| `--fps-cap FPS_CAP`             | `BALATROBOT_FPS_CAP`             | `60`          | Maximum FPS cap                            |
| `--gamespeed GAMESPEED`         | `BALATROBOT_GAMESPEED`           | `4`           | Game speed multiplier                      |
| `--animation-fps ANIMATION_FPS` | `BALATROBOT_ANIMATION_FPS`       | `10`          | Animation FPS                              |
| `--no-reduced-motion`           | `BALATROBOT_NO_REDUCED_MOTION`   | `0`           | Disable reduced motion                     |
| `--pixel-art-smoothing`         | `BALATROBOT_PIXEL_ART_SMOOTHING` | `0`           | Enable pixel art smoothing                 |
| `--balatro-path BALATRO_PATH`   | `BALATROBOT_BALATRO_PATH`        | auto-detected | Path to Balatro game directory             |
| `--lovely-path LOVELY_PATH`     | `BALATROBOT_LOVELY_PATH`         | auto-detected | Path to lovely library (dll/so/dylib)      |
| `--love-path LOVE_PATH`         | `BALATROBOT_LOVE_PATH`           | auto-detected | Path to game launcher executable           |
| `--platform PLATFORM`           | `BALATROBOT_PLATFORM`            | auto-detected | Platform: darwin, linux, windows, native   |
| `--logs-path LOGS_PATH`         | `BALATROBOT_LOGS_PATH`           | `logs`        | Directory for log files                    |
| `-h, --help`                    | -                                | -             | Show help message and exit                 |

Mutually Exclusive Flags

`--headless` and `--render-on-api` are mutually exclusive.

**Note:** Boolean flags (`--fast`, `--headless`, etc.) use `1` for enabled and `0` for disabled when set via environment variables.

## api Command

Call an API endpoint on a running BalatroBot server. Returns JSON response to stdout.

```bash
uvx balatrobot api METHOD [PARAMS] [OPTIONS]

```

### Arguments

| Argument | Required | Description                                        |
| -------- | -------- | -------------------------------------------------- |
| `METHOD` | Yes      | API method to call (see available methods below)   |
| `PARAMS` | No       | JSON object with method parameters (default: `{}`) |

### Options

| CLI Flag      | Default     | Description     |
| ------------- | ----------- | --------------- |
| `--host HOST` | `127.0.0.1` | Server hostname |
| `--port PORT` | `12346`     | Server port     |

### Available Methods

`add`, `buy`, `cash_out`, `discard`, `gamestate`, `health`, `load`, `menu`, `next_round`, `pack`, `play`, `rearrange`, `reroll`, `save`, `screenshot`, `select`, `sell`, `set`, `skip`, `start`, `use`

For detailed method documentation including parameters and schemas, see the [OpenRPC specification](https://coder.github.io/balatrobot/src/lua/utils/openrpc.json).

### api Examples

```bash
# Health check
uvx balatrobot api health

# Get current game state
uvx balatrobot api gamestate

# Start a new game with Red Deck
uvx balatrobot api start '{"deck": "RED", "stake": "WHITE"}'

# Play cards at indices 0 and 2
uvx balatrobot api play '{"cards": [0, 2]}'

# Connect to server on different port
uvx balatrobot api health --port 8080

```

### Error Handling

On success, prints JSON result to stdout (exit code 0). On error, prints `Error: NAME - message` to stderr (exit code 1).

## Examples

### Basic Usage

```bash
# Start with default settings
uvx balatrobot serve

# Start with fast mode for development
uvx balatrobot serve --fast

# Start with debug mode (requires DebugPlus mod)
uvx balatrobot serve --fast --debug

# Start headless for automated testing
uvx balatrobot serve --headless --fast

```

### Custom Configuration

```bash
# Use a different port
uvx balatrobot serve --port 8080

# Custom Balatro installation
uvx balatrobot serve --balatro-path /path/to/Balatro.exe

```

## Examples with Environment Variables

**Bash:**

```bash
# Configure via environment variables
export BALATROBOT_PORT=8080
export BALATROBOT_FAST=1

# Launch with defaults from env vars
uvx balatrobot serve

# CLI flags override env vars
uvx balatrobot serve --port 9000  # Uses port 9000, not 8080

```

**Windows PowerShell:**

```powershell
$env:BALATROBOT_PORT = "8080"
$env:BALATROBOT_FAST = "1"
uvx balatrobot serve

```

## Process Management

The CLI automatically:

- Logs output to `logs/{timestamp}/{port}.log`
- Sets up the correct environment variables
- Gracefully shuts down on Ctrl+C

## Platform-Specific Details

### Windows Platform

The `windows` platform launches Balatro via Steam on Windows. The CLI auto-detects the Steam installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_LOVE_PATH`: `C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe`
- `BALATROBOT_LOVELY_PATH`: `C:\Program Files (x86)\Steam\steamapps\common\Balatro\version.dll`

**Requirements:**

- Balatro installed via Steam
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `version.dll` placed in the Balatro game directory
- Mods directory: `%AppData%\Balatro\Mods`

**Launch:**

```powershell
# Auto-detects paths
uvx balatrobot serve --fast

# Or specify custom paths
uvx balatrobot serve --love-path "C:\Custom\Path\Balatro.exe" --lovely-path "C:\Custom\Path\version.dll"

```

### macOS Platform

The `darwin` platform launches Balatro via Steam on macOS. The CLI auto-detects the Steam installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_LOVE_PATH`: `~/Library/Application Support/Steam/steamapps/common/Balatro/Balatro.app/Contents/MacOS/love`
- `BALATROBOT_LOVELY_PATH`: `~/Library/Application Support/Steam/steamapps/common/Balatro/liblovely.dylib`

**Requirements:**

- Balatro installed via Steam
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `liblovely.dylib` in the Balatro game directory
- Mods directory: `~/Library/Application Support/Balatro/Mods`

**Note:** You cannot run the game through Steam on macOS due to a Steam client bug. The CLI handles this by directly executing the LOVE runtime with proper environment variables.

**Launch:**

```bash
# Auto-detects paths
uvx balatrobot serve --fast

# Or specify custom paths
uvx balatrobot serve --love-path "/path/to/love" --lovely-path "/path/to/liblovely.dylib"

```

### Linux (Proton) Platform

The `linux` platform launches Balatro via Steam Proton. The CLI auto-detects Steam and Proton installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_BALATRO_PATH`: `~/.local/share/Steam/steamapps/common/Balatro`
- `BALATROBOT_LOVE_PATH`: Best available Proton executable (scans `steamapps/common/`)
- `BALATROBOT_LOVELY_PATH`: `~/.local/share/Steam/steamapps/common/Balatro/version.dll`

**Requirements:**

- Balatro installed via Steam with Proton
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `version.dll` (Windows version) placed in the Balatro game directory
- A display server (`DISPLAY` or `WAYLAND_DISPLAY` must be set)
- Mods directory: `~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods`

**Launch:**

```bash
# Auto-detects paths
uvx balatrobot serve --fast

# Or specify custom paths
uvx balatrobot serve --love-path /path/to/proton --balatro-path /path/to/Balatro

```

Steam Installation

Only the official Steam package from Valve is tested. Flatpak and Snap installations of Steam use different data paths and are not currently supported.

### Native Platform (Linux Only)

The `native` platform runs Balatro from source code using the LÖVE framework installed via package manager. This requires specific directory structure:

**Required Paths:**

- `BALATROBOT_BALATRO_PATH`: Directory containing Balatro source code with `main.lua`
- `BALATROBOT_LOVE_PATH`: Path to LÖVE executable (find with `which love`), e.g., `/usr/bin/love`
- `BALATROBOT_LOVELY_PATH`: Must be `/usr/local/lib/liblovely.so`
- Mods directory: `~/.config/love/Mods` (auto-discovered, used by lovely)
- Settings directory: `~/.local/share/love/balatro` (must contain game settings)

**Setup:**

```bash
# Copy game settings to the expected location
mkdir -p ~/.local/share/love/balatro
cp -r /path/to/balatro/settings/* ~/.local/share/love/balatro/

# Launch with native platform
uvx balatrobot serve --platform native --balatro-path /path/to/balatro/source

```

Hyprland Configuration

If you are using Hyprland, you can configure the window manager with the following rules to spawn the Balatro window in an organized way:

```ini
#################################################################################
# Balatro window rules
################################################################################

# Open on Workspace 9 SILENTLY
windowrulev2 = workspace 9 silent, class:^(love)$, title:^(Balatro)$

# Float the window
windowrulev2 = float, class:^(love)$, title:^(Balatro)$

# Center it
windowrulev2 = center, class:^(love)$, title:^(Balatro)$

# Block focus stealing
windowrulev2 = noinitialfocus, class:^(love)$, title:^(Balatro)$
windowrulev2 = suppressevent activate, class:^(love)$, title:^(Balatro)$

```

## Troubleshooting

**Connection refused**: Ensure Balatro is running and the mod loaded successfully. Check logs in `logs/{timestamp}/{port}.log` for errors.

**Mod not loading**: Verify that Lovely Injector and Steamodded are installed correctly.

**Port in use**: Change the port with `--port` or set `BALATROBOT_PORT` to a different value.

**Game crashes**: Try disabling shaders with `--no-shaders` or running in headless mode with `--headless`.
