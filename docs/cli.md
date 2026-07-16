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

### Profile Activation

The BalatroBot mod only activates when the selected Balatro in-game profile is named exactly `"BalatroBot"` (case-sensitive). If no such profile exists, the HTTP server does not start and no settings overrides are applied. The game boots normally.

### Options

All options can be set via CLI flags or environment variables. CLI flags override environment variables.

| CLI Flag              | Environment Variable      | Default       | Description                                        |
| --------------------- | ------------------------- | ------------- | -------------------------------------------------- |
| `--settings NAME`     | `BALATROBOT_SETTINGS`     | `default`     | Settings profile name                              |
| `--render MODE`       | `BALATROBOT_RENDER`       | `headfull`    | Render mode: `headfull`, `headless`, or `ondemand` |
| `--debug`             | `BALATROBOT_DEBUG`        | `0`           | Enable debug mode (requires DebugPlus mod)         |
| `--screenshots`       | `BALATROBOT_SCREENSHOTS`  | `0`           | Save a PNG after each successful API response      |
| `--host HOST`         | `BALATROBOT_HOST`         | `127.0.0.1`   | Server hostname                                    |
| `--num N`             | -                         | `1`           | Number of instances to start (CLI only)            |
| `--path-balatro PATH` | `BALATROBOT_PATH_BALATRO` | auto-detected | Path to Balatro game directory                     |
| `--path-lovely PATH`  | `BALATROBOT_PATH_LOVELY`  | auto-detected | Path to lovely library (dll/so/dylib)              |
| `--path-love PATH`    | `BALATROBOT_PATH_LOVE`    | auto-detected | Path to game launcher executable                   |
| `--platform PLATFORM` | `BALATROBOT_PLATFORM`     | auto-detected | Platform: `darwin`, `linux`, `windows`, `native`   |
| `--logs PATH`         | `BALATROBOT_LOGS`         | `logs`        | Log directory (parent of timestamped sessions)     |
| `-h, --help`          | -                         | -             | Show help message and exit                         |

### Render Modes

| Mode       | Behavior                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------- |
| `headfull` | Normal rendering. Game window visible and fully interactive.                                  |
| `headless` | All rendering disabled. Window hidden at 1×1 pixels. Use for CI/automated environments.       |
| `ondemand` | Frames rendered only when explicitly requested via the API. Use with the screenshot endpoint. |

### Settings Profiles

BalatroBot bundles settings profiles that configure Balatro's game settings (speed, graphics, audio, window, etc.). Use `--settings` with a bare profile name:

```bash
# Use the "fast" profile (max speed, no audio, minimal graphics)
uvx balatrobot serve --settings fast

# Default profile is applied when --settings is omitted
uvx balatrobot serve
```

Available profiles: `default`, `fast`, `turbo`, `light`.

The profile contains `settings.lua` (merged into `G.SETTINGS`) and optionally `profile.lua` (merged into `G.PROFILES`). Profiles live in `src/lua/profiles/<name>/`. Custom profiles can be added by creating a new directory with a `settings.lua` file.

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

For detailed method documentation including parameters and schemas, see the [OpenRPC specification](../src/lua/utils/openrpc.json).

### api Examples

```bash
# Health check
uvx balatrobot api health

# Get current game state
uvx balatrobot api gamestate

# Start a new game with Red Deck
uvx balatrobot api start '{"deck": "b_red", "stake": "WHITE"}'

# Play cards at indices 0 and 2
uvx balatrobot api play '{"cards": [0, 2]}'

# Connect to server on different port
uvx balatrobot api health --port 8080
```

### Error Handling

On success, prints JSON result to stdout (exit code 0).
On error, prints `Error: NAME - message` to stderr (exit code 1).

## Examples

### Basic Usage

```bash
# Start with default settings profile (headfull)
uvx balatrobot serve

# Start headless with the fast profile
uvx balatrobot serve --settings fast --render headless

# Start with debug mode (requires DebugPlus mod)
uvx balatrobot serve --settings fast --debug
```

### Custom Configuration

```bash
# Custom Balatro installation
uvx balatrobot serve --path-balatro /path/to/Balatro

# On-demand rendering for screenshot capture
uvx balatrobot serve --render ondemand
```

## Examples with Environment Variables

**Bash:**

```bash
# Configure via environment variables
export BALATROBOT_RENDER=headless
export BALATROBOT_SETTINGS=fast

# Launch with defaults from env vars
uvx balatrobot serve
```

**Windows PowerShell:**

```powershell
$env:BALATROBOT_RENDER = "headless"
uvx balatrobot serve
```

## Process Management

The CLI automatically:

- Logs output to `logs/{timestamp}/{port}/balatro.log`
- Sets up the correct environment variables
- Gracefully shuts down on Ctrl+C

## Platform-Specific Details

### Windows Platform

The `windows` platform launches Balatro via Steam on Windows. The CLI auto-detects the Steam installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_PATH_LOVE`: `C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe`
- `BALATROBOT_PATH_LOVELY`: `C:\Program Files (x86)\Steam\steamapps\common\Balatro\version.dll`

**Requirements:**

- Balatro installed via Steam
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `version.dll` placed in the Balatro game directory
- Mods directory: `%AppData%\Balatro\Mods`

**Launch:**

```powershell
# Auto-detects paths
uvx balatrobot serve --render headless

# Or specify custom paths
uvx balatrobot serve --path-love "C:\Custom\Path\Balatro.exe" --path-lovely "C:\Custom\Path\version.dll"
```

### macOS Platform

The `darwin` platform launches Balatro via Steam on macOS. The CLI auto-detects the Steam installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_PATH_LOVE`: `~/Library/Application Support/Steam/steamapps/common/Balatro/Balatro.app/Contents/MacOS/love`
- `BALATROBOT_PATH_LOVELY`: `~/Library/Application Support/Steam/steamapps/common/Balatro/liblovely.dylib`

**Requirements:**

- Balatro installed via Steam
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `liblovely.dylib` in the Balatro game directory
- Mods directory: `~/Library/Application Support/Balatro/Mods`

**Note:** You cannot run the game through Steam on macOS due to a Steam client bug. The CLI handles this by directly executing the LOVE runtime with proper environment variables.

**Launch:**

```bash
# Auto-detects paths
uvx balatrobot serve --render headless

# Or specify custom paths
uvx balatrobot serve --path-love "/path/to/love" --path-lovely "/path/to/liblovely.dylib"
```

### Linux (Proton) Platform

The `linux` platform launches Balatro via Steam Proton. The CLI auto-detects Steam and Proton installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_PATH_BALATRO`: `~/.local/share/Steam/steamapps/common/Balatro`
- `BALATROBOT_PATH_LOVE`: Best available Proton executable (scans `steamapps/common/`)
- `BALATROBOT_PATH_LOVELY`: `~/.local/share/Steam/steamapps/common/Balatro/version.dll`

**Requirements:**

- Balatro installed via Steam with Proton
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `version.dll` (Windows version) placed in the Balatro game directory
- A display server (`DISPLAY` or `WAYLAND_DISPLAY` must be set)
- Mods directory: `~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods`

**Launch:**

```bash
# Auto-detects paths
uvx balatrobot serve --render headless

# Or specify custom paths
uvx balatrobot serve --path-love /path/to/proton --path-balatro /path/to/Balatro
```

!!! warning "Steam Installation"

    Only the official Steam package from Valve is tested. Flatpak and Snap installations of Steam use different data paths and are not currently supported.

### Native Platform (Linux Only)

The `native` platform runs Balatro from source code using the LÖVE framework installed via package manager. This requires specific directory structure:

**Required Paths:**

- `BALATROBOT_PATH_BALATRO`: Directory containing Balatro source code with `main.lua`
- `BALATROBOT_PATH_LOVE`: Path to LÖVE executable (find with `which love`), e.g., `/usr/bin/love`
- `BALATROBOT_PATH_LOVELY`: Must be `/usr/local/lib/liblovely.so`
- Mods directory: `~/.config/love/Mods` (auto-discovered, used by lovely)
- Settings directory: `~/.local/share/love/balatro` (must contain game settings)

**Setup:**

```bash
# Copy game settings to the expected location
mkdir -p ~/.local/share/love/balatro
cp -r /path/to/balatro/settings/* ~/.local/share/love/balatro/

# Launch with native platform
uvx balatrobot serve --platform native --path-balatro /path/to/balatro/source
```

??? tip "Hyprland Configuration"

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

### Docker Platform

The `docker` platform runs the [`balatrobox`](https://github.com/coder/balatrobox) reference image — a container with LOVE + Lovely + Steamodded + the balatrobot mod pre-baked. One container = one Balatro process. balatrobot never touches game files on the host; it only drives the container through the same JSON-RPC API.

**Requirements:**

- Docker installed and the daemon running
- The image built once from the balatrobox repo: `docker build -t balatrobox .`

**Launch:**

```bash
# Spin up 2 containers and drive them through the usual pool/list/stop commands
uvx balatrobot serve --platform docker --num 2
uvx balatrobot list
uvx balatrobot api health --index 1
```

**Streaming (HLS):** Set `BALATROBOX_STREAM=1` on the host. The pool allocates one stream port per instance (mapped to the container's internal `:8080`) and `balatrobot list` prints each `stream` URL:

```bash
export BALATROBOX_STREAM=1
uvx balatrobot serve --platform docker --num 2
uvx balatrobot list   # rpc urls + stream urls
mpv <stream_url>      # e.g. http://127.0.0.1:<stream_port>/index.m3u8
```

**Mounting local checkouts (optional):** The docker platform reads these host env vars and translates them into read-only bind mounts — handy for developing balatrobot, the game source, or the DebugPlus mod without rebuilding the image:

| Env var                 | Mounts to                               |
| ----------------------- | --------------------------------------- |
| `BALATROSRC_LOCAL_REPO` | `/app/balatro:ro` (game source)         |
| `BALATROBOT_LOCAL_REPO` | `/mods/balatrobot:ro` (this mod)        |
| `DEBUGPLUS_LOCAL_REPO`  | `/mods/DebugPlus:ro` (debug dependency) |

All other `BALATROBOX_*` and `BALATROSRC_GITHUB_*` / `BALATROBOT_GITHUB_*` vars are forwarded into the container verbatim when set (see the balatrobox README). `BALATROBOX_PLATFORM` is a build/run-arch concern and is ignored.

**Mounting extra host paths (optional):** `BALATROBOT_DOCKER_MOUNT` is a colon-separated list of host paths bind-mounted **read-write at their identical path** inside the container. Because the `load`/`save` endpoints open the exact path string they receive, these are identity mounts (same path inside and out). The test suite sets this automatically when `BALATROBOT_PLATFORM=docker` to expose `tests/fixtures/` and a temp dir to the container.

## Troubleshooting

**Connection refused**: Ensure Balatro is running and the mod loaded successfully. Check logs in `logs/{timestamp}/{port}/balatro.log` for errors. Verify the in-game profile is named exactly `"BalatroBot"`.

**Mod not loading**: Verify that Lovely Injector and Steamodded are installed correctly. Ensure you have a Balatro profile named `"BalatroBot"` and it is selected.

**Port in use**: Ports are allocated ephemerally. If you need a specific port, adjust your firewall rules to allow the ephemeral range.

**Game crashes**: Try running in headless mode with `--render headless` and the `fast` profile (`--settings fast`).
