# Developing Bots

BalatroBot allows you to create automated players (bots) that can play Balatro by implementing decision-making logic in Python. Your bot communicates with the game through a TCP socket connection, sending actions to perform and receiving back the game state.

## Bot Architecture

A bot is a finite state machine that implements a sequence of actions to play the game. The bot can be in one state at a time and has access to a set of functions that can move the bot to other states.

| **State**        | **Description**                              | **Functions**                            |
| ---------------- | -------------------------------------------- | ---------------------------------------- |
| `MENU`           | The main menu                                | `start_run`                              |
| `BLIND_SELECT`   | Selecting or skipping the blind              | `skip_or_select_blind`                   |
| `SELECTING_HAND` | Selecting cards to play or discard           | `play_hand_or_discard`, `rearrange_hand` |
| `ROUND_EVAL`     | Evaluating the round outcome and cashing out | `cash_out`                               |
| `SHOP`           | Buy items and move to the next round         | `shop`                                   |
| `GAME_OVER`      | Game has ended                               | –                                        |

Developing a bot boils down to providing the action name and its parameters for each state.

### State Diagram

The following diagram illustrates the possible states of the game and how the functions can be used to move the bot between them:

- Start (◉) and End (⦾) states
- States are written in uppercase (e.g., `MENU`, `BLIND_SELECT`, ...)
- Functions are written in lowercase (e.g., `start_run`, `skip_or_select_blind`, ...)
- Function parameters are written in italics (e.g., `action = play_hand`). Not all parameters are reported in the diagram.
- Comments are reported in parentheses (e.g., `(win round)`, `(lose round)`).
- Abstract groups are written with capital letters (e.g., `Run`, `Round`, ...)

```
stateDiagram-v2
  direction TB

  BLIND_SELECT_1:BLIND_SELECT

  [*] --> MENU: go_to_menu
  MENU --> BLIND_SELECT: start_run

  state Run{

    BLIND_SELECT --> skip_or_select_blind

    skip_or_select_blind --> BLIND_SELECT: *action = skip*</br>(small or big blind)
    skip_or_select_blind --> SELECTING_HAND: *action = select*

    state Round {
      SELECTING_HAND --> play_hand_or_discard

      play_hand_or_discard --> SELECTING_HAND: *action = play_hand*
      play_hand_or_discard --> SELECTING_HAND: *action = discard*
      play_hand_or_discard --> ROUND_EVAL: *action = play_hand*<br/>(win round)
      play_hand_or_discard --> GAME_OVER: *action = play_hand*<br/>(lose round)
    }

    state RoundEval {
      ROUND_EVAL --> SHOP: *cash_out*
    }

    state Shop {
      SHOP --> shop
      shop --> BLIND_SELECT_1: *action = next_round*
    }

    state GameOver {
      GAME_OVER --> [*]
    }

  }

  state skip_or_select_blind <<choice>>
  state play_hand_or_discard <<choice>>
  state shop <<choice>>
```

## Development Environment Setup

The BalatroBot project provides a complete development environment with all necessary tools and resources for developing bots.

### Environment Setup

Before developing or running bots, you need to set up the development environment by configuring the `.envrc` file:

```sh
cd %AppData%/Balatro/Mods/balatrobot
copy .envrc.example .envrc
.envrc

```

```sh
cd "/Users/$USER/Library/Application Support/Balatro/Mods/balatrobot"
cp .envrc.example .envrc
source .envrc

```

```sh
cd ~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/balatrobot
cp .envrc.example .envrc
source .envrc

```

Always Source Environment

Remember to source the `.envrc` file every time you start a new terminal session before developing or running bots. The environment variables are essential for proper bot functionality.

Automatic Environment Loading with direnv

For a better development experience, consider using [direnv](https://direnv.net/) to automatically load and unload environment variables when entering and leaving the project directory.

After installing direnv and hooking it into your shell:

```sh
# Allow direnv to load the .envrc file automatically
direnv allow .

```

This eliminates the need to manually source `.envrc` every time you work on the project.

### Bot File Location

When developing new bots, place your files in the `bots/` directory using one of these recommended patterns:

- **Single file bots**: `bots/my_new_bot.py`
- **Complex bots**: `bots/my_new_bot/main.py` (for bots with multiple modules)

## Next Steps

After setting up your development environment:

- Explore the [BalatroBot API](https://coder.github.io/balatrobot/0.7.0/balatrobot-api/index.md) for detailed client and model documentation
- Learn about the underlying [Protocol API](https://coder.github.io/balatrobot/0.7.0/protocol-api/index.md) for TCP communication details
