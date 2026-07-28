# Example Bot

A minimal Python bot that plays Balatro using the BalatroBot API.

## The Bot

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
# ]
# ///

import requests

# BalatroBot API endpoint
URL = "http://127.0.0.1:12346"


def rpc(method: str, params: dict = {}) -> dict:
    """Send a JSON-RPC 2.0 request to the BalatroBot API."""
    response = requests.post(
        URL,
        json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        },
    )
    data = response.json()
    # Raise if error, otherwise return result (contains game state)
    if "error" in data:
        raise Exception(data["error"]["message"])
    return data["result"]


def play_game():
    """Play a complete game of Balatro."""
    # Return to menu and start a new game
    rpc("menu")
    state = rpc("start", {"deck": "b_red", "stake": "WHITE"})
    print(f"Started game with seed: {state['seed']}")

    # Main game loop
    while state["state"] != "GAME_OVER":
        match state["state"]:
            case "BLIND_SELECT":
                # Always select the current blind
                state = rpc("select")

            case "SELECTING_HAND":
                # Play the first 5 cards (simple strategy)
                num_cards = min(5, len(state["hand"]["cards"]))
                cards = list(range(num_cards))
                state = rpc("play", {"cards": cards})

            case "ROUND_EVAL":
                # Collect rewards and go to shop
                state = rpc("cash_out")

            case "SHOP":
                # Skip the shop and proceed to next round
                state = rpc("next_round")

            case _:
                # Handle any transitional states
                state = rpc("gamestate")

    # Game ended
    if state["won"]:
        print(f"Victory! Final ante: {state['ante_num']}")
    else:
        print(f"Game over at ante {state['ante_num']}, round {state['round_num']}")

    return state["won"]


if __name__ == "__main__":
    play_game()
```

## Running the Bot

1. Start Balatro with the mod:

    ```bash
    uvx balatrobot serve
    ```

2. In another terminal, run the bot:

    ```bash
    uv run bot.py
    ```

The bot will automatically start a new game and play until it wins or loses.

## Community Bots

Looking for more advanced examples? Check out these bots created by the community:

- [polina4096/Ballad](https://github.com/polina4096/Ballad): LLMs play balatro through Anthropic-compatible APIs

!!! tip "Share Your Bot"

    Built a bot with BalatroBot? We'd love to feature it here! Share your repository with the community:

    - Tag `@S1M0N38` on the [BalatroBot Discord server](https://discord.gg/TPn6FYgGPv)
    - [Open an issue](https://github.com/coder/balatrobot/issues/new) on GitHub
    - [Submit a pull request](https://github.com/coder/balatrobot/pulls) to add your bot to this list

    Whether it's a simple strategy or a sophisticated AI, sharing your work helps others learn and grow the BalatroBot ecosystem!
