# CLI Reference

Command-line interface for launching Balatro with the BalatroBot mod.

## Usage

```bash
balatrobot [OPTIONS]
```

Start Balatro with the BalatroBot mod loaded and API server running.

## Options

All options can be set via CLI flags or environment variables. CLI flags override environment variables.

| CLI Flag                      | Environment Variable       | Default       | Description                                |
| ----------------------------- | -------------------------- | ------------- | ------------------------------------------ |
| `--host HOST`                 | `BALATROBOT_HOST`          | `127.0.0.1`   | Server hostname                            |
| `--port PORT`                 | `BALATROBOT_PORT`          | `12346`       | Server port                                |
| `--fast`                      | `BALATROBOT_FAST`          | `0`           | Enable fast mode (10x game speed)          |
| `--headless`                  | `BALATROBOT_HEADLESS`      | `0`           | Enable headless mode (minimal rendering)   |
| `--render-on-api`             | `BALATROBOT_RENDER_ON_API` | `0`           | Render only on API calls                   |
| `--audio`                     | `BALATROBOT_AUDIO`         | `0`           | Enable audio                               |
| `--debug`                     | `BALATROBOT_DEBUG`         | `0`           | Enable debug mode (requires DebugPlus mod) |
| `--no-shaders`                | `BALATROBOT_NO_SHADERS`    | `0`           | Disable all shaders                        |
| `--balatro-path BALATRO_PATH` | `BALATROBOT_BALATRO_PATH`  | auto-detected | Path to Balatro game directory             |
| `--lovely-path LOVELY_PATH`   | `BALATROBOT_LOVELY_PATH`   | auto-detected | Path to lovely library (dll/so/dylib)      |
| `--love-path LOVE_PATH`       | `BALATROBOT_LOVE_PATH`     | auto-detected | Path to LOVE executable (native only)      |
| `--platform PLATFORM`         | `BALATROBOT_PLATFORM`      | auto-detected | Platform: darwin, linux, windows, native   |
| `--logs-path LOGS_PATH`       | `BALATROBOT_LOGS_PATH`     | `logs`        | Directory for log files                    |
| `-h, --help`                  | -                          | -             | Show help message and exit                 |

**Note:** Boolean flags (`--fast`, `--headless`, etc.) use `1` for enabled and `0` for disabled when set via environment variables.

## Examples

### Basic Usage

```bash
# Start with default settings
balatrobot

# Start with fast mode for development
balatrobot --fast

# Start with debug mode (requires DebugPlus mod)
balatrobot --fast --debug

# Start headless for automated testing
balatrobot --headless --fast
```

### Custom Configuration

```bash
# Use a different port
balatrobot --port 8080

# Custom Balatro installation
balatrobot --balatro-path /path/to/Balatro.exe
```

## Examples with Environment Variables

**Bash:**

```bash
# Configure via environment variables
export BALATROBOT_PORT=8080
export BALATROBOT_FAST=1

# Launch with defaults from env vars
balatrobot

# CLI flags override env vars
balatrobot --port 9000  # Uses port 9000, not 8080
```

**Windows PowerShell:**

```powershell
$env:BALATROBOT_PORT = "8080"
$env:BALATROBOT_FAST = "1"
balatrobot
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
balatrobot --fast

# Or specify custom paths
balatrobot --love-path "C:\Custom\Path\Balatro.exe" --lovely-path "C:\Custom\Path\version.dll"
```

### macOS Platform

The `darwin` platform launches Balatro via Steam on macOS. The CLI auto-detects the Steam installation paths:

**Auto-Detected Paths:**

- `BALATROBOT_LOVE_PATH`: `~/Library/Application Support/Steam/steamapps/common/Balatro/Balatro.app/Contents/MacOS/love`
- `BALATROBOT_LOVELY_PATH`: `~/Library/Application Support/Steam/steamapps/common/Balatro/liblovely.dylib`

**Requirements:**

- Balatro installed via Steam
- [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) `liblovely.dylib` and `run_lovely_macos.sh` in the Balatro game directory
- Mods directory: `~/Library/Application Support/Balatro/Mods`

**Note:** You cannot run the game through Steam on macOS due to a Steam client bug. The CLI handles this by directly executing the LOVE runtime with proper environment variables.

**Launch:**

```bash
# Auto-detects paths
balatrobot --fast

# Or specify custom paths
balatrobot --love-path "/path/to/love" --lovely-path "/path/to/liblovely.dylib"
```

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
balatrobot --platform native --balatro-path /path/to/balatro/source
```

??? tip "Hyprland Configuration"

    If you are using Hyprland, you can configure the window manager with the following rules to spawn the Balatro window in an organized way:

    ```ini
    #################################################################################
    # Balatro window rules
    ################################################################################

    # 1. Open on Workspace 9 SILENTLY
    windowrulev2 = workspace 9 silent, class:^(love)$, title:^(Balatro)$

    # 2. Float the window
    windowrulev2 = float, class:^(love)$, title:^(Balatro)$

    # 3. Set size to 640x360 (Tiny)
    windowrulev2 = size 640 360, class:^(love)$, title:^(Balatro)$

    # 4. Center it
    windowrulev2 = center, class:^(love)$, title:^(Balatro)$

    # 5. BLOCK FOCUS STEALING (Crucial for "Silent" to work)
    windowrulev2 = noinitialfocus, class:^(love)$, title:^(Balatro)$
    windowrulev2 = suppressevent activate, class:^(love)$, title:^(Balatro)$
    ```

## Troubleshooting

**Connection refused**: Ensure Balatro is running and the mod loaded successfully. Check logs in `logs/{timestamp}/{port}.log` for errors.

**Mod not loading**: Verify that Lovely Injector and Steamodded are installed correctly.

**Port in use**: Change the port with `--port` or set `BALATROBOT_PORT` to a different value.

**Game crashes**: Try disabling shaders with `--no-shaders` or running in headless mode with `--headless`.
