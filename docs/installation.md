# Installation

This guide covers installing the BalatroBot mod for Balatro.

## Prerequisites

- **Balatro** (v1.0.1+) - Purchase from [Steam](https://store.steampowered.com/app/2379780/Balatro/)
- **Lovely Injector** (v0.8.0+) - Follow the [installation guide](https://github.com/ethangreen-dev/lovely-injector#manual-installation)
- **Steamodded** (v1.0.0-beta-1221a+) - Follow the [installation guide](https://github.com/Steamodded/smods/wiki)
- **Uv** (v0.9.21+) - Follow the [installation guide](https://docs.astral.sh/uv)

## Mod Installation

### 1. Download BalatroBot

Download the latest release from the [releases page](https://github.com/coder/balatrobot/releases) or clone the repository.

### 2. Copy to Mods Folder

Copy the following files/folders to your Balatro Mods directory:

```
Mods/
├── smods/                # Mods loader
├── DebugPlus/            # required just for debugging
└── balatrobot/           # BalatroBot directory
    ├── balatrobot.json   # BalatroBot manifest
    ├── balatrobot.lua    # BalatroBot entry point
    └── src/lua           # API source code
```

**Mods directory location:**

| Platform             | Path                                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------------------- |
| Windows              | `%AppData%/Balatro/Mods/balatrobot/`                                                                          |
| macOS                | `~/Library/Application Support/Balatro/Mods/balatrobot/`                                                      |
| Linux (Steam/Proton) | `~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/` |
| Linux (Native)       | `~/.config/love/Mods/balatrobot/`                                                                             |

> Steam/Proton launcher not supported yet. Track progress in [#128](https://github.com/coder/balatrobot/issues/128)

### 3. Launch Balatro

Start Balatro with the BalatroBot CLI:

```bash
uvx balatrobot serve
```

For detailed CLI options and usage, see the [CLI Reference](cli.md).

### 4. Verify Installation

Start Balatro, then test the connection:

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "health", "id": 1}'
```

Expected response:

```json
{"jsonrpc":"2.0","result":{"status":"ok"},"id":1}
```

## Troubleshooting

- **Connection refused**: Ensure Balatro is running and the mod loaded successfully
- **Mod not loading**: Check that Lovely and Steamodded are installed correctly
- **Port in use**: Use `uvx balatrobot serve --port PORT` to specify a different port

For more troubleshooting help, see the [CLI Reference](cli.md).
