# BalatroBot API

This page provides comprehensive API documentation for the BalatroBot Python framework. The API enables you to build automated bots that interact with the Balatro card game through a structured TCP communication protocol.

The API is organized into several key components: the `BalatroClient` for managing game connections and sending commands, enums that define game states and actions, exception classes for robust error handling, and data models that structure requests and responses between your bot and the game.

## Client

### `balatrobot.client.BalatroClient`

Client for communicating with the BalatroBot game API.

Attributes:

| Name          | Type     | Description                 |
| ------------- | -------- | --------------------------- |
| `host`        |          | Host address to connect to  |
| `port`        |          | Port number to connect to   |
| `timeout`     |          | Socket timeout in seconds   |
| `buffer_size` |          | Socket buffer size in bytes |
| `_socket`     | \`socket | None\`                      |

Source code in `src/balatrobot/client.py`

|                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ` 18  19  20  21  22  23  24  25  26  27  28  29  30  31  32  33  34  35  36  37  38  39  40  41  42  43  44  45  46  47  48  49  50  51  52  53  54  55  56  57  58  59  60  61  62  63  64  65  66  67  68  69  70  71  72  73  74  75  76  77  78  79  80  81  82  83  84  85  86  87  88  89  90  91  92  93  94  95  96  97  98  99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146` | \`\`\` class BalatroClient: """Client for communicating with the BalatroBot game API. Attributes: host: Host address to connect to port: Port number to connect to timeout: Socket timeout in seconds buffer_size: Socket buffer size in bytes \_socket: Socket connection to BalatroBot """ host = "127.0.0.1" port = 12346 timeout = 10.0 buffer_size = 65536 def __init__(self): """Initialize BalatroBot client""" self.\_socket: socket.socket |

#### `connect()`

Connect to Balatro TCP server

Raises:

| Type                    | Description                  |
| ----------------------- | ---------------------------- |
| `ConnectionFailedError` | If not connected to the game |

Source code in `src/balatrobot/client.py`

|                                                                                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75` | `def connect(self) -> None:     """Connect to Balatro TCP server      Raises:         ConnectionFailedError: If not connected to the game     """     if self._connected:         return      logger.info(f"Connecting to BalatroBot API at {self.host}:{self.port}")     try:         self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)         self._socket.settimeout(self.timeout)         self._socket.setsockopt(             socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size         )         self._socket.connect((self.host, self.port))         self._connected = True         logger.info(             f"Successfully connected to BalatroBot API at {self.host}:{self.port}"         )     except (socket.error, OSError) as e:         logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")         raise ConnectionFailedError(             f"Failed to connect to {self.host}:{self.port}",             error_code="E008",             context={"host": self.host, "port": self.port, "error": str(e)},         ) from e ` |

#### `disconnect()`

Disconnect from the BalatroBot game API.

Source code in `src/balatrobot/client.py`

|                        |                                                                                                                                                                                                                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `77 78 79 80 81 82 83` | `def disconnect(self) -> None:     """Disconnect from the BalatroBot game API."""     if self._socket:         logger.info(f"Disconnecting from BalatroBot API at {self.host}:{self.port}")         self._socket.close()         self._socket = None     self._connected = False ` |

#### `send_message(name, arguments=None)`

Send JSON message to Balatro and receive response

Parameters:

| Name        | Type   | Description           | Default            |
| ----------- | ------ | --------------------- | ------------------ |
| `name`      | `str`  | Function name to call | *required*         |
| `arguments` | \`dict | None\`                | Function arguments |

Returns:

| Type   | Description                |
| ------ | -------------------------- |
| `dict` | Response from the game API |

Raises:

| Type                    | Description                  |
| ----------------------- | ---------------------------- |
| `ConnectionFailedError` | If not connected to the game |
| `BalatroError`          | If the API returns an error  |

Source code in `src/balatrobot/client.py`

|                                                                                                                                                                                                                                                           |                                                          |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| ` 85  86  87  88  89  90  91  92  93  94  95  96  97  98  99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 144 145 146` | \`\`\` def send_message(self, name: str, arguments: dict |

______________________________________________________________________

## Enums

### `balatrobot.enums.State`

Game state values representing different phases of gameplay in Balatro, from menu navigation to active card play and shop interactions.

Source code in `src/balatrobot/enums.py`

|                                                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ` 4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27` | `@unique class State(Enum):     """Game state values representing different phases of gameplay in Balatro,     from menu navigation to active card play and shop interactions."""      SELECTING_HAND = 1     HAND_PLAYED = 2     DRAW_TO_HAND = 3     GAME_OVER = 4     SHOP = 5     PLAY_TAROT = 6     BLIND_SELECT = 7     ROUND_EVAL = 8     TAROT_PACK = 9     PLANET_PACK = 10     MENU = 11     TUTORIAL = 12     SPLASH = 13     SANDBOX = 14     SPECTRAL_PACK = 15     DEMO_CTA = 16     STANDARD_PACK = 17     BUFFOON_PACK = 18     NEW_ROUND = 19 ` |

### `balatrobot.enums.Actions`

Bot action values corresponding to user interactions available in different game states, from card play to shop purchases and inventory management.

Source code in `src/balatrobot/enums.py`

|                                                                                 |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55` | `@unique class Actions(Enum):     """Bot action values corresponding to user interactions available in     different game states, from card play to shop purchases and inventory     management."""      SELECT_BLIND = 1     SKIP_BLIND = 2     PLAY_HAND = 3     DISCARD_HAND = 4     END_SHOP = 5     REROLL_SHOP = 6     BUY_CARD = 7     BUY_VOUCHER = 8     BUY_BOOSTER = 9     SELECT_BOOSTER_CARD = 10     SKIP_BOOSTER_PACK = 11     SELL_JOKER = 12     USE_CONSUMABLE = 13     SELL_CONSUMABLE = 14     REARRANGE_JOKERS = 15     REARRANGE_CONSUMABLES = 16     REARRANGE_HAND = 17     PASS = 18     START_RUN = 19     SEND_GAMESTATE = 20 ` |

### `balatrobot.enums.Decks`

Starting deck types in Balatro, each providing unique starting conditions, card modifications, or special abilities that affect gameplay throughout the run.

Source code in `src/balatrobot/enums.py`

|                                                                  |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78` | `@unique class Decks(Enum):     """Starting deck types in Balatro, each providing unique starting     conditions, card modifications, or special abilities that affect gameplay     throughout the run."""      RED = "Red Deck"     BLUE = "Blue Deck"     YELLOW = "Yellow Deck"     GREEN = "Green Deck"     BLACK = "Black Deck"     MAGIC = "Magic Deck"     NEBULA = "Nebula Deck"     GHOST = "Ghost Deck"     ABANDONED = "Abandoned Deck"     CHECKERED = "Checkered Deck"     ZODIAC = "Zodiac Deck"     PAINTED = "Painted Deck"     ANAGLYPH = "Anaglyph Deck"     PLASMA = "Plasma Deck"     ERRATIC = "Erratic Deck" ` |

### `balatrobot.enums.Stakes`

Difficulty stake levels in Balatro that increase game difficulty through various modifiers and restrictions, with higher stakes providing greater challenges and rewards.

Source code in `src/balatrobot/enums.py`

|                                             |                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `81 82 83 84 85 86 87 88 89 90 91 92 93 94` | `@unique class Stakes(Enum):     """Difficulty stake levels in Balatro that increase game difficulty through     various modifiers and restrictions, with higher stakes providing greater     challenges and rewards."""      WHITE = 1     RED = 2     GREEN = 3     BLACK = 4     BLUE = 5     PURPLE = 6     ORANGE = 7     GOLD = 8 ` |

### `balatrobot.enums.ErrorCode`

Standardized error codes used in BalatroBot API that match those defined in src/lua/api.lua for consistent error handling across the entire system.

Source code in `src/balatrobot/enums.py`

|                                                                                                               |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ` 97  98  99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123` | `@unique class ErrorCode(Enum):     """Standardized error codes used in BalatroBot API that match those defined in src/lua/api.lua for consistent error handling across the entire system."""      # Protocol errors (E001-E005)     INVALID_JSON = "E001"     MISSING_NAME = "E002"     MISSING_ARGUMENTS = "E003"     UNKNOWN_FUNCTION = "E004"     INVALID_ARGUMENTS = "E005"      # Network errors (E006-E008)     SOCKET_CREATE_FAILED = "E006"     SOCKET_BIND_FAILED = "E007"     CONNECTION_FAILED = "E008"      # Validation errors (E009-E012)     INVALID_GAME_STATE = "E009"     INVALID_PARAMETER = "E010"     PARAMETER_OUT_OF_RANGE = "E011"     MISSING_GAME_OBJECT = "E012"      # Game logic errors (E013-E016)     DECK_NOT_FOUND = "E013"     INVALID_CARD_INDEX = "E014"     NO_DISCARDS_LEFT = "E015"     INVALID_ACTION = "E016" ` |

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

- Follow the [Developing Bots](https://s1m0n38.github.io/balatrobot/0.5.0/developing-bots/index.md) guide for complete bot setup
- Understand the underlying [Protocol API](https://s1m0n38.github.io/balatrobot/0.5.0/protocol-api/index.md) for advanced usage
- Reference the [Installation](https://s1m0n38.github.io/balatrobot/0.5.0/installation/index.md) guide for environment setup
