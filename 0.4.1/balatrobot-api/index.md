# BalatroBot API

This page provides comprehensive API documentation for the BalatroBot Python framework. The API enables you to build automated bots that interact with the Balatro card game through a structured TCP communication protocol.

The API is organized into several key components: the `BalatroClient` for managing game connections and sending commands, enums that define game states and actions, exception classes for robust error handling, and data models that structure requests and responses between your bot and the game.

## Client

#### `balatrobot.client.BalatroClient`

Client for communicating with the BalatroBot game API.

##### `cash_out()`

Cash out from the current round to enter the shop.

Returns:

| Type        | Description                  |
| ----------- | ---------------------------- |
| `GameState` | Game state after cashing out |

##### `connect()`

Connect to the BalatroBot game API.

##### `disconnect()`

Disconnect from the BalatroBot game API.

##### `get_game_state()`

Get the current game state.

Returns:

| Type        | Description        |
| ----------- | ------------------ |
| `GameState` | Current game state |

##### `go_to_menu()`

Navigate to the main menu.

Returns:

| Type        | Description                 |
| ----------- | --------------------------- |
| `GameState` | Game state after navigation |

##### `play_hand_or_discard(action, cards)`

Play selected cards or discard them.

Parameters:

| Name     | Type                              | Description                      | Default    |
| -------- | --------------------------------- | -------------------------------- | ---------- |
| `action` | `Literal['play_hand', 'discard']` | Either "play_hand" or "discard"  | *required* |
| `cards`  | `list[int]`                       | List of card indices (0-indexed) | *required* |

Returns:

| Type        | Description                 |
| ----------- | --------------------------- |
| `GameState` | Game state after the action |

##### `shop(action)`

Perform a shop action.

Parameters:

| Name     | Type                    | Description                                          | Default    |
| -------- | ----------------------- | ---------------------------------------------------- | ---------- |
| `action` | `Literal['next_round']` | Shop action to perform (currently only "next_round") | *required* |

Returns:

| Type        | Description                 |
| ----------- | --------------------------- |
| `GameState` | Game state after the action |

##### `skip_or_select_blind(action)`

Skip or select the current blind.

Parameters:

| Name     | Type                        | Description               | Default    |
| -------- | --------------------------- | ------------------------- | ---------- |
| `action` | `Literal['skip', 'select']` | Either "skip" or "select" | *required* |

Returns:

| Type        | Description                 |
| ----------- | --------------------------- |
| `GameState` | Game state after the action |

##### `start_run(deck, stake=1, seed=None, challenge=None)`

Start a new game run.

Parameters:

| Name        | Type  | Description             | Default                   |
| ----------- | ----- | ----------------------- | ------------------------- |
| `deck`      | `str` | Name of the deck to use | *required*                |
| `stake`     | `int` | Stake level (1-8)       | `1`                       |
| `seed`      | \`str | None\`                  | Optional seed for the run |
| `challenge` | \`str | None\`                  | Optional challenge name   |

Returns:

| Type        | Description                       |
| ----------- | --------------------------------- |
| `GameState` | Game state after starting the run |

options: heading_level: 3

______________________________________________________________________

## Enums

#### `balatrobot.enums.State`

Game state values representing different phases of gameplay in Balatro, from menu navigation to active card play and shop interactions.

options: heading_level: 3

#### `balatrobot.enums.Actions`

Bot action values corresponding to user interactions available in different game states, from card play to shop purchases and inventory management.

options: heading_level: 3

#### `balatrobot.enums.Decks`

Starting deck types in Balatro, each providing unique starting conditions, card modifications, or special abilities that affect gameplay throughout the run.

options: heading_level: 3

#### `balatrobot.enums.Stakes`

Difficulty stake levels in Balatro that increase game difficulty through various modifiers and restrictions, with higher stakes providing greater challenges and rewards.

options: heading_level: 3

#### `balatrobot.enums.ErrorCode`

Standardized error codes used in BalatroBot API that match those defined in src/lua/api.lua for consistent error handling across the entire system.

options: heading_level: 3

______________________________________________________________________

## Exceptions

### Connection and Socket Errors

#### `balatrobot.exceptions.SocketCreateFailedError`

Socket creation failed (E006).

#### `balatrobot.exceptions.SocketBindFailedError`

Socket bind failed (E007).

#### `balatrobot.exceptions.ConnectionFailedError`

Connection failed (E008).

### Game State and Logic Errors

#### `balatrobot.exceptions.InvalidGameStateError`

Invalid game state for requested action (E009).

#### `balatrobot.exceptions.InvalidActionError`

Invalid action for current context (E016).

#### `balatrobot.exceptions.DeckNotFoundError`

Deck not found (E013).

#### `balatrobot.exceptions.InvalidCardIndexError`

Invalid card index (E014).

#### `balatrobot.exceptions.NoDiscardsLeftError`

No discards remaining (E015).

### API and Parameter Errors

#### `balatrobot.exceptions.InvalidJSONError`

Invalid JSON in request (E001).

#### `balatrobot.exceptions.MissingNameError`

Message missing required 'name' field (E002).

#### `balatrobot.exceptions.MissingArgumentsError`

Message missing required 'arguments' field (E003).

#### `balatrobot.exceptions.UnknownFunctionError`

Unknown function name (E004).

#### `balatrobot.exceptions.InvalidArgumentsError`

Invalid arguments provided (E005).

#### `balatrobot.exceptions.InvalidParameterError`

Invalid or missing required parameter (E010).

#### `balatrobot.exceptions.ParameterOutOfRangeError`

Parameter value out of valid range (E011).

#### `balatrobot.exceptions.MissingGameObjectError`

Required game object missing (E012).

______________________________________________________________________

## Models

### Request Models

#### `balatrobot.models.StartRunRequest`

Request model for starting a new run.

#### `balatrobot.models.BlindActionRequest`

Request model for skip or select blind actions.

#### `balatrobot.models.HandActionRequest`

Request model for playing hand or discarding cards.

#### `balatrobot.models.ShopActionRequest`

Request model for shop actions.

### Game State Models

#### `balatrobot.models.Card`

Model for a playing card.

#### `balatrobot.models.Game`

Model for game information.

#### `balatrobot.models.GameState`

Model for the complete game state.

##### `state_enum` `property`

Get the state as an enum value.

### Communication Models

#### `balatrobot.models.ErrorResponse`

Model for API error responses.

#### `balatrobot.models.APIRequest`

Model for API requests sent to the game.

#### `balatrobot.models.APIResponse`

Model for API responses from the game.

## Usage Examples

For practical implementation examples:

- Follow the [Developing Bots](https://s1m0n38.github.io/balatrobot/0.4.1/developing-bots/index.md) guide for complete bot setup
- Understand the underlying [Protocol API](https://s1m0n38.github.io/balatrobot/0.4.1/protocol-api/index.md) for advanced usage
- Reference the [Installation](https://s1m0n38.github.io/balatrobot/0.4.1/installation/index.md) guide for environment setup
