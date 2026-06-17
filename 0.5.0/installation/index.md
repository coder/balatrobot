# Installation Guide

This guide will walk you through installing and setting up BalatroBot.

## Prerequisites

Before installing BalatroBot, ensure you have:

- **[balatro](https://store.steampowered.com/app/2379780/Balatro/)**: Steam version (>= 1.0.1)
- **[git](https://git-scm.com/downloads)**: for cloning the repository
- **[uv](https://docs.astral.sh/uv/)**: for managing Python installations, environments and dependencies
- **[lovely](https://github.com/ethangreen-dev/lovely-injector)**: for injecting Lua code into Balatro (>= 0.8.0)
- **[steamodded](https://github.com/Steamodded/smods)**: for loading and injecting mods (>=1.0.0)

## Step 1: Install BalatroBot

BalatroBot is installed like any other Steamodded mod.

WindowsMacOSLinux

```sh
cd %AppData%/Balatro
mkdir -p Mods
cd Mods
git clone https://github.com/S1M0N38/balatrobot.git

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro"
mkdir -p Mods
cd Mods
git clone https://github.com/S1M0N38/balatrobot.git

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro
mkdir -p Mods
cd Mods
git clone https://github.com/S1M0N38/balatrobot.git

```

Tip

You can also clone the repository somewhere else and then provide a symlink to the `balatrobot` directory in the `Mods` directory.

WindowsMacOSLinux

```sh
# Clone repository to a custom location
cd C:\your\custom\path
git clone https://github.com/S1M0N38/balatrobot.git

# Create symlink in Mods directory
cd %AppData%/Balatro/Mods
mklink /D balatrobot C:\your\custom\path\balatrobot

```

```sh
# Clone repository to a custom location
cd /your/custom/path
git clone https://github.com/S1M0N38/balatrobot.git

# Create symlink in Mods directory
cd "/Users/$USER/Library/Application Support/Balatro/Mods"
ln -s /your/custom/path/balatrobot balatrobot

```

```sh
# Clone repository to a custom location
cd /your/custom/path
git clone https://github.com/S1M0N38/balatrobot.git

# Create symlink in Mods directory
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods
ln -s /your/custom/path/balatrobot balatrobot

```

Update BalatroBot

Updating BalatroBot is as simple as pulling the latest changes from the repository.

WindowsMacOSLinux

```sh
cd %AppData%/Balatro/Mods/balatrobot
git pull

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods/balatrobot"
git pull

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/balatrobot
git pull

```

Uninstall BalatroBot

Simply delete the balatrobot mod directory.

WindowsMacOSLinux

```sh
cd %AppData%/Balatro/Mods
rmdir /S /Q balatrobot

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods"
rm -rf balatrobot

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods
rm -rf balatrobot

```

## Step 2: Setup Python Environment

Uv takes care of managing Python installations, virtual environments creation and dependencies installation. To setup the Python environment for running BalatroBot bots simply run:

WindowsMacOSLinux

```sh
cd %AppData%/Balatro/Mods/balatrobot
uv sync

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods/balatrobot"
uv sync

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/balatrobot
uv sync

```

The same command can be used to update the Python environment and dependencies in the future.

Remove Python Environment

To uninstall the Python environment and dependencies, simply remove the `.venv` directory.

WindowsMacOSLinux

```sh
cd %AppData%/Balatro/Mods/balatrobot
rmdir /S /Q .venv

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods/balatrobot"
rm -rf .venv

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/balatrobot
rm -rf .venv

```

## Step 3: Test Installation

### Launch Balatro with Mods

1. Start Balatro through Steam
1. In the main menu, click "Mods"
1. Verify "BalatroBot" appears in the mod list
1. Enable the mod if it's not already enabled and restart the game

macOS Steam Client Issue

On macOS, you cannot start Balatro through the Steam App due to a bug in the Steam client. Instead, you must use the `run_lovely_macos.sh` script.

MacOS

```sh
cd "/Users/$USER/Library/Application Support/Steam/steamapps/common/Balatro"
./run_lovely_macos.sh

```

**First-time setup:** If this is your first time running the script, macOS Security & Privacy settings will prevent it from executing. Open **System Preferences** → **Security & Privacy** and click "Allow" when prompted, then run the script again.

### Quick Test with Example Bot

With Balatro running and the mod enabled, you can quickly test if everything is set up correctly using the provided example bot.

WindowsMacOSLinux

```sh
cd %AppData%/Balatro/Mods/balatrobot
uv run bots/example.py

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods/balatrobot"
uv run bots/example.py

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/balatrobot
uv run bots/example.py

```

Tip

You can also navigate to the `balatrobot` directory, activate the Python environment and run the bot with `python bots/example.py` if you prefer. However, remember to always activate the virtual environment first.

The bot is working correctly if:

1. Game starts automatically
1. Cards are played/discarded automatically
1. Win the first round
1. Game progresses through rounds

## Troubleshooting

If you encounter issues during installation or testing:

- **Discord Support**: Join our community at <https://discord.gg/xzBAj4JFVC> for real-time help
- **GitHub Issues**: Report bugs or request features by [opening an issue](https://github.com/S1M0N38/balatrobot/issues) on GitHub

______________________________________________________________________

*Once installation is complete, proceed to the [Developing Bots](https://s1m0n38.github.io/balatrobot/0.5.0/developing-bots/index.md) to create your first bot!*
