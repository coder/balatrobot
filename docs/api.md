# BalatroBot API Reference

JSON-RPC 2.0 API for controlling Balatro programmatically.

## Overview

- **Protocol**: JSON-RPC 2.0 over HTTP/1.1
- **Endpoint**: `http://127.0.0.1:12346` (default)
- **Content-Type**: `application/json`

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": { ... },
  "id": 1
}
```

### Response Format

**Success:**

```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": 1
}
```

**Error:**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Error description",
    "data": { "name": "BAD_REQUEST" }
  },
  "id": 1
}
```

## Quickstart

#### 1. Health Check

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "health", "id": 1}'
```

#### 2. Get Game State

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "gamestate", "id": 1}'
```

#### 3. Start a New Run

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "start", "params": {"deck": "RED", "stake": "WHITE"}, "id": 1}'
```

#### 4. Select Blind and Play Cards

```bash
# Select the blind
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "select", "id": 1}'

# Play cards at indices 0, 1, 2
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "play", "params": {"cards": [0, 1, 2]}, "id": 1}'
```

## Game States

The game progresses through these states:

```
MENU ──► BLIND_SELECT ──► SELECTING_HAND ──► ROUND_EVAL ──► SHOP ─┐
                ▲                │                                │
                │                ▼                                │
                │            GAME_OVER                            │
                │                                                 │
                └─────────────────────────────────────────────────┘
```

| State                  | Description                                     |
| ---------------------- | ----------------------------------------------- |
| `MENU`                 | Main menu                                       |
| `BLIND_SELECT`         | Choosing which blind to play or skip            |
| `SELECTING_HAND`       | Selecting cards to play or discard              |
| `ROUND_EVAL`           | Round complete, ready to cash out               |
| `SHOP`                 | Shopping phase                                  |
| `SMODS_BOOSTER_OPENED` | Booster pack opened, selecting or skipping pack |
| `GAME_OVER`            | Game ended                                      |

---

## Methods

- [`health`](#health) - Health check endpoint
- [`gamestate`](#gamestate) - Get the complete current game state
- [`rpc.discover`](#rpcdiscover) - Returns the OpenRPC specification
- [`start`](#start) - Start a new game run
- [`menu`](#menu) - Return to the main menu
- [`save`](#save) - Save the current run to a file
- [`load`](#load) - Load a saved run from a file
- [`select`](#select) - Select the current blind to begin the round
- [`skip`](#skip) - Skip the current blind (Small or Big only)
- [`buy`](#buy) - Buy a card, voucher, or pack from the shop
- [`pack`](#pack) - Select a card or skip a pack from an opened booster pack, requires to you select targets for Tarot/Spectral consumables when applicable
- [`sell`](#sell) - Sell a joker or consumable
- [`reroll`](#reroll) - Reroll the shop items
- [`cash_out`](#cash_out) - Cash out round rewards and transition to shop
- [`next_round`](#next_round) - Leave the shop and advance to blind selection
- [`play`](#play) - Play cards from hand
- [`discard`](#discard) - Discard cards from hand
- [`rearrange`](#rearrange) - Rearrange cards in hand, jokers, or consumables
- [`use`](#use) - Use a consumable card
- [`add`](#add) - Add a card to the game (debug/testing)
- [`screenshot`](#screenshot) - Take a screenshot of the game
- [`set`](#set) - Set in-game values (debug/testing)

---

### `health`

Health check endpoint.

**Returns:** `{ "status": "ok" }`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "health", "id": 1}'
```

---

### `gamestate`

Get the complete current game state.

**Returns:** [GameState](#gamestate-schema) object

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "gamestate", "id": 1}'
```

---

### `rpc.discover`

Returns the OpenRPC specification for this API.

**Returns:** OpenRPC schema document

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "rpc.discover", "id": 1}'
```

---

### `start`

Start a new game run.

**Parameters:**

| Name    | Type   | Required | Description           |
| ------- | ------ | -------- | --------------------- |
| `deck`  | string | Yes      | [Deck](#deck) to use  |
| `stake` | string | Yes      | [Stake](#stake) level |
| `seed`  | string | No       | Seed for the run      |

**Returns:** [GameState](#gamestate-schema) (state will be `BLIND_SELECT`)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `INTERNAL_ERROR`

**Required State:** `MENU`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "start", "params": {"deck": "BLUE", "stake": "WHITE", "seed": "TEST123"}, "id": 1}'
```

---

### `menu`

Return to the main menu from any state.

**Returns:** [GameState](#gamestate-schema) (state will be `MENU`)

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "menu", "id": 1}'
```

---

### `save`

Save the current run to a file.

**Parameters:**

| Name   | Type   | Required | Description            |
| ------ | ------ | -------- | ---------------------- |
| `path` | string | Yes      | File path for the save |

**Returns:** `{ "success": true, "path": "..." }`

**Errors:** `INVALID_STATE`, `INTERNAL_ERROR`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "save", "params": {"path": "/tmp/save.jkr"}, "id": 1}'
```

---

### `load`

Load a saved run from a file.

**Parameters:**

| Name   | Type   | Required | Description           |
| ------ | ------ | -------- | --------------------- |
| `path` | string | Yes      | Path to the save file |

**Returns:** `{ "success": true, "path": "..." }`

**Errors:** `INTERNAL_ERROR`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "load", "params": {"path": "/tmp/save.jkr"}, "id": 1}'
```

---

### `select`

Select the current blind to begin the round.

**Returns:** [GameState](#gamestate-schema) (state will be `SELECTING_HAND`)

**Errors:** `INVALID_STATE`

**Required State:** `BLIND_SELECT`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "select", "id": 1}'
```

---

### `skip`

Skip the current blind (Small or Big only).

**Returns:** [GameState](#gamestate-schema)

**Errors:** `INVALID_STATE`, `NOT_ALLOWED`

**Required State:** `BLIND_SELECT`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "skip", "id": 1}'
```

---

### `buy`

Buy a card, voucher, or pack from the shop.

**Parameters:** (exactly one required)

| Name      | Type    | Required | Description                     |
| --------- | ------- | -------- | ------------------------------- |
| `card`    | integer | No       | 0-based index of card to buy    |
| `voucher` | integer | No       | 0-based index of voucher to buy |
| `pack`    | integer | No       | 0-based index of pack to buy    |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `NOT_ALLOWED`

**Required State:** `SHOP`

**Example:**

```bash
# Buy first card in shop
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "buy", "params": {"card": 0}, "id": 1}'
```

---

### `pack`

Select a card or skip a pack from an opened booster pack.

After buying a pack with [`buy`](#buy), this method allows you to select a card from the pack or skip the selection. Different pack types behave differently:

- **Buffoon packs**: Selected jokers are added to your joker slots
- **Standard packs**: Selected playing cards are added to your deck
- **Arcana/Celestial/Spectral packs**: Selected consumables are **used immediately**

Some Tarot and Spectral cards require you to select target cards from your hand (e.g., The Magician enhances 1-2 cards to Lucky).

**Parameters:** (exactly one required)

| Name      | Type      | Required | Description                                                              |
| --------- | --------- | -------- | ------------------------------------------------------------------------ |
| `card`    | integer   | No       | 0-based index of card to select from pack                                |
| `targets` | integer[] | No       | 0-based indices of hand cards to target (for consumables that need them) |
| `skip`    | boolean   | No       | Skip pack selection without choosing a card                              |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`

**Required State:** `SMODS_BOOSTER_OPENED`

**Examples:**

```bash
# Select first card from a Buffoon pack (adds joker to slots)
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "pack", "params": {"card": 0}, "id": 1}'

# Select a Tarot card requiring targets (e.g., The Magician on 2 hand cards)
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "pack", "params": {"card": 0, "targets": [0, 1]}, "id": 1}'

# Skip pack selection
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "pack", "params": {"skip": true}, "id": 1}'
```

---

### `sell`

Sell a joker or consumable.

**Parameters:** (exactly one required)

| Name         | Type    | Required | Description                         |
| ------------ | ------- | -------- | ----------------------------------- |
| `joker`      | integer | No       | 0-based index of joker to sell      |
| `consumable` | integer | No       | 0-based index of consumable to sell |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `NOT_ALLOWED`

**Example:**

```bash
# Sell first joker
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "sell", "params": {"joker": 0}, "id": 1}'
```

---

### `reroll`

Reroll the shop items (costs money).

**Returns:** [GameState](#gamestate-schema)

**Errors:** `INVALID_STATE`, `NOT_ALLOWED`

**Required State:** `SHOP`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "reroll", "id": 1}'
```

---

### `cash_out`

Cash out round rewards and transition to shop.

**Returns:** [GameState](#gamestate-schema) (state will be `SHOP`)

**Errors:** `INVALID_STATE`

**Required State:** `ROUND_EVAL`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "cash_out", "id": 1}'
```

---

### `next_round`

Leave the shop and advance to blind selection.

**Returns:** [GameState](#gamestate-schema) (state will be `BLIND_SELECT`)

**Errors:** `INVALID_STATE`

**Required State:** `SHOP`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "next_round", "id": 1}'
```

---

### `play`

Play cards from hand.

**Parameters:**

| Name    | Type      | Required | Description                                  |
| ------- | --------- | -------- | -------------------------------------------- |
| `cards` | integer[] | Yes      | 0-based indices of cards to play (1-5 cards) |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`

**Required State:** `SELECTING_HAND`

**Example:**

```bash
# Play cards at positions 0, 2, 4
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "play", "params": {"cards": [0, 2, 4]}, "id": 1}'
```

---

### `discard`

Discard cards from hand.

**Parameters:**

| Name    | Type      | Required | Description                         |
| ------- | --------- | -------- | ----------------------------------- |
| `cards` | integer[] | Yes      | 0-based indices of cards to discard |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`

**Required State:** `SELECTING_HAND`

**Example:**

```bash
# Discard cards at positions 0 and 1
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "discard", "params": {"cards": [0, 1]}, "id": 1}'
```

---

### `rearrange`

Rearrange cards in hand, jokers, or consumables.

**Parameters:** (exactly one required)

| Name          | Type      | Required | Description                                              |
| ------------- | --------- | -------- | -------------------------------------------------------- |
| `hand`        | integer[] | No       | New order of hand cards (permutation of current indices) |
| `jokers`      | integer[] | No       | New order of jokers                                      |
| `consumables` | integer[] | No       | New order of consumables                                 |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`

**Required State:** Hand cards can be rearranged in `SELECTING_HAND` or `SMODS_BOOSTER_OPENED`. Jokers and consumables can be rearranged in `SHOP`, `SELECTING_HAND`, or `SMODS_BOOSTER_OPENED`.

**Example:**

```bash
# Reverse a 5-card hand
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "rearrange", "params": {"hand": [4, 3, 2, 1, 0]}, "id": 1}'
```

---

### `use`

Use a consumable card.

**Parameters:**

| Name         | Type      | Required | Description                                                              |
| ------------ | --------- | -------- | ------------------------------------------------------------------------ |
| `consumable` | integer   | Yes      | 0-based index of consumable to use                                       |
| `cards`      | integer[] | No       | 0-based indices of target cards (for consumables that require selection) |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`

**Example:**

```bash
# Use The Magician on cards 0 and 1
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "use", "params": {"consumable": 0, "cards": [0, 1]}, "id": 1}'
```

---

### `add`

Add a card to the game (debug/testing). Supports jokers, consumables, vouchers, packs, and playing cards.

**Parameters:**

| Name          | Type    | Required | Description                                                                    |
| ------------- | ------- | -------- | ------------------------------------------------------------------------------ |
| `key`         | string  | Yes      | [Card key](#card-keys) (e.g., `j_joker`, `c_fool`, `p_arcana_normal_1`, `H_A`) |
| `seal`        | string  | No       | [Seal](#card-modifier-seal) type (playing cards only)                          |
| `edition`     | string  | No       | [Edition](#card-modifier-edition) type (not vouchers or packs)                 |
| `enhancement` | string  | No       | [Enhancement](#card-modifier-enhancement) type (playing cards only)            |
| `eternal`     | boolean | No       | Cannot be sold/destroyed (jokers only)                                         |
| `perishable`  | integer | No       | Rounds until perish (jokers only)                                              |
| `rental`      | boolean | No       | Costs $1/round (jokers only)                                                   |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`

**Required State:** Vouchers and packs require `SHOP` state. Packs also require available booster slots.

**Examples:**

```bash
# Add a Polychrome Joker
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "add", "params": {"key": "j_joker", "edition": "POLYCHROME"}, "id": 1}'

# Add an Arcana Pack to the shop (requires SHOP state)
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "add", "params": {"key": "p_arcana_normal_1"}, "id": 1}'
```

---

### `screenshot`

Take a screenshot of the game.

**Parameters:**

| Name   | Type   | Required | Description                  |
| ------ | ------ | -------- | ---------------------------- |
| `path` | string | Yes      | File path for PNG screenshot |

**Returns:** `{ "success": true, "path": "..." }`

**Errors:** `INTERNAL_ERROR`

**Example:**

```bash
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "screenshot", "params": {"path": "/tmp/screenshot.png"}, "id": 1}'
```

---

### `set`

Set in-game values (debug/testing).

**Parameters:** (at least one required)

| Name       | Type    | Required | Description                     |
| ---------- | ------- | -------- | ------------------------------- |
| `money`    | integer | No       | Set money amount                |
| `chips`    | integer | No       | Set chips scored                |
| `ante`     | integer | No       | Set ante number                 |
| `round`    | integer | No       | Set round number                |
| `hands`    | integer | No       | Set hands remaining             |
| `discards` | integer | No       | Set discards remaining          |
| `shop`     | boolean | No       | Re-stock shop (SHOP state only) |

**Returns:** [GameState](#gamestate-schema)

**Errors:** `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`

**Example:**

```bash
# Set money to 100 and hands to 5
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "set", "params": {"money": 100, "hands": 5}, "id": 1}'
```

---

## Schemas

### GameState Schema

The complete game state returned by most methods.

```json
{
  "state": "SELECTING_HAND",
  "round_num": 1,
  "ante_num": 1,
  "money": 4,
  "deck": "RED",
  "stake": "WHITE",
  "seed": "ABC123",
  "won": false,
  "used_vouchers": {},
  "hands": { ... },
  "round": { ... },
  "blinds": { ... },
  "jokers": { ... },
  "consumables": { ... },
  "cards": { ... },
  "hand": { ... },
  "shop": { ... },
  "vouchers": { ... },
  "packs": { ... },
  "pack": { ... }
}
```

### Area

Represents a card area (hand, jokers, consumables, shop, etc.).

```json
{
  "count": 8,
  "limit": 8,
  "highlighted_limit": 5,
  "cards": [ ... ]
}
```

### Card

```json
{
  "id": 1,
  "key": "H_A",
  "set": "DEFAULT",
  "label": "Ace of Hearts",
  "value": {
    "suit": "H",
    "rank": "A",
    "effect": "..."
  },
  "modifier": {
    "seal": null,
    "edition": null,
    "enhancement": null,
    "eternal": false,
    "perishable": null,
    "rental": false
  },
  "state": {
    "debuff": false,
    "hidden": false,
    "highlight": false
  },
  "cost": {
    "sell": 1,
    "buy": 0
  }
}
```

### Round

```json
{
  "hands_left": 4,
  "hands_played": 0,
  "discards_left": 3,
  "discards_used": 0,
  "reroll_cost": 5,
  "chips": 0
}
```

### Blind

```json
{
  "type": "SMALL",
  "status": "SELECT",
  "name": "Small Blind",
  "effect": "No special effect",
  "score": 300,
  "tag_name": "Uncommon Tag",
  "tag_effect": "Shop has a free Uncommon Joker"
}
```

### Hand (Poker Hand Info)

```json
{
  "order": 1,
  "level": 1,
  "chips": 10,
  "mult": 1,
  "played": 0,
  "played_this_round": 0,
  "example": [["H_A", true], ["H_K", true]]
}
```

---

## Enums

### Deck

| Value       | Description                                                   |
| ----------- | ------------------------------------------------------------- |
| `RED`       | +1 discard every round                                        |
| `BLUE`      | +1 hand every round                                           |
| `YELLOW`    | Start with extra $10                                          |
| `GREEN`     | $2 per remaining Hand, $1 per remaining Discard (no interest) |
| `BLACK`     | +1 Joker slot, -1 hand every round                            |
| `MAGIC`     | Start with Crystal Ball voucher and 2 copies of The Fool      |
| `NEBULA`    | Start with Telescope voucher, -1 consumable slot              |
| `GHOST`     | Spectral cards may appear in shop, start with Hex card        |
| `ABANDONED` | Start with no Face Cards                                      |
| `CHECKERED` | Start with 26 Spades and 26 Hearts                            |
| `ZODIAC`    | Start with Tarot Merchant, Planet Merchant, and Overstock     |
| `PAINTED`   | +2 hand size, -1 Joker slot                                   |
| `ANAGLYPH`  | Gain Double Tag after each Boss Blind                         |
| `PLASMA`    | Balanced Chips/Mult, 2X base Blind size                       |
| `ERRATIC`   | Randomized Ranks and Suits                                    |

### Stake

| Value    | Description                     |
| -------- | ------------------------------- |
| `WHITE`  | Base difficulty                 |
| `RED`    | Small Blind gives no reward     |
| `GREEN`  | Required score scales faster    |
| `BLACK`  | Shop can have Eternal Jokers    |
| `BLUE`   | -1 Discard                      |
| `PURPLE` | Required score scales faster    |
| `ORANGE` | Shop can have Perishable Jokers |
| `GOLD`   | Shop can have Rental Jokers     |

### Card Value Suit

| Value | Description |
| ----- | ----------- |
| `H`   | Hearts      |
| `D`   | Diamonds    |
| `C`   | Clubs       |
| `S`   | Spades      |

### Card Value Rank

| Value | Description |
| ----- | ----------- |
| `2`   | Two         |
| `3`   | Three       |
| `4`   | Four        |
| `5`   | Five        |
| `6`   | Six         |
| `7`   | Seven       |
| `8`   | Eight       |
| `9`   | Nine        |
| `T`   | Ten         |
| `J`   | Jack        |
| `Q`   | Queen       |
| `K`   | King        |
| `A`   | Ace         |

### Card Set

| Value      | Description                   |
| ---------- | ----------------------------- |
| `DEFAULT`  | Playing card                  |
| `ENHANCED` | Playing card with enhancement |
| `JOKER`    | Joker card                    |
| `TAROT`    | Tarot consumable              |
| `PLANET`   | Planet consumable             |
| `SPECTRAL` | Spectral consumable           |
| `VOUCHER`  | Voucher                       |
| `BOOSTER`  | Booster pack                  |

### Card Modifier Seal

| Value    | Description                                |
| -------- | ------------------------------------------ |
| `RED`    | Retrigger card 1 time                      |
| `BLUE`   | Creates Planet card for final hand if held |
| `GOLD`   | Earn $3 when scored                        |
| `PURPLE` | Creates Tarot when discarded               |

### Card Modifier Edition

| Value        | Description                       |
| ------------ | --------------------------------- |
| `FOIL`       | +50 Chips                         |
| `HOLO`       | +10 Mult                          |
| `POLYCHROME` | X1.5 Mult                         |
| `NEGATIVE`   | +1 slot (jokers/consumables only) |

### Card Modifier Enhancement

| Value   | Description                          |
| ------- | ------------------------------------ |
| `BONUS` | +30 Chips when scored                |
| `MULT`  | +4 Mult when scored                  |
| `WILD`  | Counts as every suit                 |
| `GLASS` | X2 Mult when scored                  |
| `STEEL` | X1.5 Mult while held                 |
| `STONE` | +50 Chips (no rank/suit)             |
| `GOLD`  | $3 if held at end of round           |
| `LUCKY` | 1/5 chance +20 Mult, 1/15 chance $20 |

### Blind Type

| Value   | Description                           |
| ------- | ------------------------------------- |
| `SMALL` | Can be skipped for a Tag              |
| `BIG`   | Can be skipped for a Tag              |
| `BOSS`  | Cannot be skipped, has special effect |

### Blind Status

| Value      | Description        |
| ---------- | ------------------ |
| `SELECT`   | Can be selected    |
| `CURRENT`  | Currently active   |
| `UPCOMING` | Future blind       |
| `DEFEATED` | Previously beaten  |
| `SKIPPED`  | Previously skipped |

### Card Keys

Card keys are used with the `add` method and appear in the `key` field of Card objects.

#### Tarot Cards

Consumables that enhance playing cards, change suits, generate other cards, or provide money. Keys use prefix `c_` followed by the card name (e.g., `c_fool`, `c_magician`). 22 cards total.

| Key                  | Effect                                                                          |
| -------------------- | ------------------------------------------------------------------------------- |
| `c_fool`             | Creates the last Tarot or Planet card used during this run (The Fool excluded)  |
| `c_magician`         | Enhances 2 selected cards to Lucky Cards                                        |
| `c_high_priestess`   | Creates up to 2 random Planet cards (Must have room)                            |
| `c_empress`          | Enhances 2 selected cards to Mult Cards                                         |
| `c_emperor`          | Creates up to 2 random Tarot cards (Must have room)                             |
| `c_heirophant`       | Enhances 2 selected cards to Bonus Cards                                        |
| `c_lovers`           | Enhances 1 selected card into a Wild Card                                       |
| `c_chariot`          | Enhances 1 selected card into a Steel Card                                      |
| `c_justice`          | Enhances 1 selected card into a Glass Card                                      |
| `c_hermit`           | Doubles money (Max of $20)                                                      |
| `c_wheel_of_fortune` | 1 in 4 chance to add Foil, Holographic, or Polychrome edition to a random Joker |
| `c_strength`         | Increases rank of up to 2 selected cards by 1                                   |
| `c_hanged_man`       | Destroys up to 2 selected cards                                                 |
| `c_death`            | Select 2 cards, convert the left card into the right card                       |
| `c_temperance`       | Gives the total sell value of all current Jokers (Max of $50)                   |
| `c_devil`            | Enhances 1 selected card into a Gold Card                                       |
| `c_tower`            | Enhances 1 selected card into a Stone Card                                      |
| `c_star`             | Converts up to 3 selected cards to Diamonds                                     |
| `c_moon`             | Converts up to 3 selected cards to Clubs                                        |
| `c_sun`              | Converts up to 3 selected cards to Hearts                                       |
| `c_judgement`        | Creates a random Joker card (Must have room)                                    |
| `c_world`            | Converts up to 3 selected cards to Spades                                       |

#### Planet Cards

Consumables that upgrade poker hand levels, increasing their base Chips and Mult. Keys use prefix `c_` followed by planet names (e.g., `c_mercury`, `c_pluto`). 12 cards total.

| Key          | Effect                                                        |
| ------------ | ------------------------------------------------------------- |
| `c_mercury`  | Increases Pair hand value by +1 Mult and +15 Chips            |
| `c_venus`    | Increases Three of a Kind hand value by +2 Mult and +20 Chips |
| `c_earth`    | Increases Full House hand value by +2 Mult and +25 Chips      |
| `c_mars`     | Increases Four of a Kind hand value by +3 Mult and +30 Chips  |
| `c_jupiter`  | Increases Flush hand value by +2 Mult and +15 Chips           |
| `c_saturn`   | Increases Straight hand value by +3 Mult and +30 Chips        |
| `c_uranus`   | Increases Two Pair hand value by +1 Mult and +20 Chips        |
| `c_neptune`  | Increases Straight Flush hand value by +4 Mult and +40 Chips  |
| `c_pluto`    | Increases High Card hand value by +1 Mult and +10 Chips       |
| `c_planet_x` | Increases Five of a Kind hand value by +3 Mult and +35 Chips  |
| `c_ceres`    | Increases Flush House hand value by +4 Mult and +40 Chips     |
| `c_eris`     | Increases Flush Five hand value by +3 Mult and +50 Chips      |

#### Spectral Cards

Rare consumables with powerful effects that often come with drawbacks. Can add seals, editions, copy cards, or destroy cards. Keys use prefix `c_` (e.g., `c_familiar`, `c_hex`). 18 cards total.

| Key             | Effect                                                              |
| --------------- | ------------------------------------------------------------------- |
| `c_familiar`    | Destroy 1 random card in hand, add 3 random Enhanced face cards     |
| `c_grim`        | Destroy 1 random card in hand, add 2 random Enhanced Aces           |
| `c_incantation` | Destroy 1 random card in hand, add 4 random Enhanced numbered cards |
| `c_talisman`    | Add a Gold Seal to 1 selected card                                  |
| `c_aura`        | Add Foil, Holographic, or Polychrome effect to 1 selected card      |
| `c_wraith`      | Creates a random Rare Joker, sets money to $0                       |
| `c_sigil`       | Converts all cards in hand to a single random suit                  |
| `c_ouija`       | Converts all cards in hand to a single random rank (-1 hand size)   |
| `c_ectoplasm`   | Add Negative to a random Joker, -1 hand size                        |
| `c_immolate`    | Destroys 5 random cards in hand, gain $20                           |
| `c_ankh`        | Create a copy of a random Joker, destroy all other Jokers           |
| `c_deja_vu`     | Add a Red Seal to 1 selected card                                   |
| `c_hex`         | Add Polychrome to a random Joker, destroy all other Jokers          |
| `c_trance`      | Add a Blue Seal to 1 selected card                                  |
| `c_medium`      | Add a Purple Seal to 1 selected card                                |
| `c_cryptid`     | Create 2 copies of 1 selected card                                  |
| `c_soul`        | Creates a Legendary Joker (Must have room)                          |
| `c_black_hole`  | Upgrade every poker hand by 1 level                                 |

#### Joker Cards

Persistent cards that provide scoring bonuses, triggered abilities, or passive effects throughout a run. Keys use prefix `j_` followed by the joker name (e.g., `j_joker`, `j_blueprint`). 150 cards total.

| Key                  | Effect                                                                                   |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `j_joker`            | +4 Mult                                                                                  |
| `j_greedy_joker`     | Played Diamond cards give +3 Mult when scored                                            |
| `j_lusty_joker`      | Played Heart cards give +3 Mult when scored                                              |
| `j_wrathful_joker`   | Played Spade cards give +3 Mult when scored                                              |
| `j_gluttenous_joker` | Played Club cards give +3 Mult when scored                                               |
| `j_jolly`            | +8 Mult if played hand contains a Pair                                                   |
| `j_zany`             | +12 Mult if played hand contains a Three of a Kind                                       |
| `j_mad`              | +10 Mult if played hand contains a Two Pair                                              |
| `j_crazy`            | +12 Mult if played hand contains a Straight                                              |
| `j_droll`            | +10 Mult if played hand contains a Flush                                                 |
| `j_sly`              | +50 Chips if played hand contains a Pair                                                 |
| `j_wily`             | +100 Chips if played hand contains a Three of a Kind                                     |
| `j_clever`           | +80 Chips if played hand contains a Two Pair                                             |
| `j_devious`          | +100 Chips if played hand contains a Straight                                            |
| `j_crafty`           | +80 Chips if played hand contains a Flush                                                |
| `j_half`             | +20 Mult if played hand contains 3 or fewer cards                                        |
| `j_stencil`          | X1 Mult for each empty Joker slot                                                        |
| `j_four_fingers`     | All Flushes and Straights can be made with 4 cards                                       |
| `j_mime`             | Retrigger all cards held in hand abilities                                               |
| `j_credit_card`      | Go up to -$20 in debt                                                                    |
| `j_ceremonial`       | When Blind is selected, destroy Joker to the right and add double its sell value to Mult |
| `j_banner`           | +30 Chips for each remaining discard                                                     |
| `j_mystic_summit`    | +15 Mult when 0 discards remaining                                                       |
| `j_marble`           | Adds one Stone card to the deck when Blind is selected                                   |
| `j_loyalty_card`     | X4 Mult every 6 hands played                                                             |
| `j_8_ball`           | 1 in 4 chance for each played 8 to create a Tarot card when scored                       |
| `j_misprint`         | +0-23 Mult                                                                               |
| `j_dusk`             | Retrigger all played cards in final hand of the round                                    |
| `j_raised_fist`      | Adds double the rank of lowest ranked card held in hand to Mult                          |
| `j_chaos`            | 1 free Reroll per shop                                                                   |
| `j_fibonacci`        | Each played Ace, 2, 3, 5, or 8 gives +8 Mult when scored                                 |
| `j_steel_joker`      | Gives X0.2 Mult for each Steel Card in your full deck                                    |
| `j_scary_face`       | Played face cards give +30 Chips when scored                                             |
| `j_abstract`         | +3 Mult for each Joker card                                                              |
| `j_delayed_grat`     | Earn $2 per discard if no discards are used by end of the round                          |
| `j_hack`             | Retrigger each played 2, 3, 4, or 5                                                      |
| `j_pareidolia`       | All cards are considered face cards                                                      |
| `j_gros_michel`      | +15 Mult, 1 in 6 chance this is destroyed at end of round                                |
| `j_even_steven`      | Played cards with even rank give +4 Mult when scored                                     |
| `j_odd_todd`         | Played cards with odd rank give +31 Chips when scored                                    |
| `j_scholar`          | Played Aces give +20 Chips and +4 Mult when scored                                       |
| `j_business`         | Played face cards have a 1 in 2 chance to give $2 when scored                            |
| `j_supernova`        | Adds the number of times poker hand has been played this run to Mult                     |
| `j_ride_the_bus`     | Gains +1 Mult per consecutive hand played without a scoring face card                    |
| `j_space`            | 1 in 4 chance to upgrade level of played poker hand                                      |
| `j_egg`              | Gains $3 of sell value at end of round                                                   |
| `j_burglar`          | When Blind is selected, gain +3 Hands and lose all discards                              |
| `j_blackboard`       | X3 Mult if all cards held in hand are Spades or Clubs                                    |
| `j_runner`           | Gains +15 Chips if played hand contains a Straight                                       |
| `j_ice_cream`        | +100 Chips, -5 Chips for every hand played                                               |
| `j_dna`              | If first hand of round has only 1 card, add a permanent copy to deck                     |
| `j_splash`           | Every played card counts in scoring                                                      |
| `j_blue_joker`       | +2 Chips for each remaining card in deck                                                 |
| `j_sixth_sense`      | If first hand of round is a single 6, destroy it and create a Spectral card              |
| `j_constellation`    | Gains X0.1 Mult every time a Planet card is used                                         |
| `j_hiker`            | Every played card permanently gains +5 Chips when scored                                 |
| `j_faceless`         | Earn $5 if 3 or more face cards are discarded at the same time                           |
| `j_green_joker`      | +1 Mult per hand played, -1 Mult per discard                                             |
| `j_superposition`    | Create a Tarot card if poker hand contains an Ace and a Straight                         |
| `j_todo_list`        | Earn $4 if poker hand is a specific hand, changes at end of round                        |
| `j_cavendish`        | X3 Mult, 1 in 1000 chance this card is destroyed at end of round                         |
| `j_card_sharp`       | X3 Mult if played poker hand has already been played this round                          |
| `j_red_card`         | Gains +3 Mult when any Booster Pack is skipped                                           |
| `j_madness`          | When Small/Big Blind is selected, gain X0.5 Mult and destroy a random Joker              |
| `j_square`           | Gains +4 Chips if played hand has exactly 4 cards                                        |
| `j_seance`           | If poker hand is a Straight Flush, create a random Spectral card                         |
| `j_riff_raff`        | When Blind is selected, create 2 Common Jokers                                           |
| `j_vampire`          | Gains X0.1 Mult per scoring Enhanced card played, removes Enhancement                    |
| `j_shortcut`         | Allows Straights to be made with gaps of 1 rank                                          |
| `j_hologram`         | Gains X0.25 Mult every time a playing card is added to your deck                         |
| `j_vagabond`         | Create a Tarot card if hand is played with $4 or less                                    |
| `j_baron`            | Each King held in hand gives X1.5 Mult                                                   |
| `j_cloud_9`          | Earn $1 for each 9 in your full deck at end of round                                     |
| `j_rocket`           | Earn $1 at end of round, payout increases by $2 when Boss Blind is defeated              |
| `j_obelisk`          | Gains X0.2 Mult per consecutive hand without playing most played hand                    |
| `j_midas_mask`       | All played face cards become Gold cards when scored                                      |
| `j_luchador`         | Sell this card to disable the current Boss Blind                                         |
| `j_photograph`       | First played face card gives X2 Mult when scored                                         |
| `j_gift`             | Add $1 of sell value to every Joker and Consumable at end of round                       |
| `j_turtle_bean`      | +5 hand size, reduces by 1 each round                                                    |
| `j_erosion`          | +4 Mult for each card below deck's starting size                                         |
| `j_reserved_parking` | Each face card held in hand has a 1 in 2 chance to give $1                               |
| `j_mail`             | Earn $5 for each discarded card of a specific rank, changes every round                  |
| `j_to_the_moon`      | Earn an extra $1 of interest for every $5 at end of round                                |
| `j_hallucination`    | 1 in 2 chance to create a Tarot card when any Booster Pack is opened                     |
| `j_fortune_teller`   | +1 Mult per Tarot card used this run                                                     |
| `j_juggler`          | +1 hand size                                                                             |
| `j_drunkard`         | +1 discard each round                                                                    |
| `j_stone`            | Gives +25 Chips for each Stone Card in your full deck                                    |
| `j_golden`           | Earn $4 at end of round                                                                  |
| `j_lucky_cat`        | Gains X0.25 Mult every time a Lucky card successfully triggers                           |
| `j_baseball`         | Uncommon Jokers each give X1.5 Mult                                                      |
| `j_bull`             | +2 Chips for each $1 you have                                                            |
| `j_diet_cola`        | Sell this card to create a free Double Tag                                               |
| `j_trading`          | If first discard of round has only 1 card, destroy it and earn $3                        |
| `j_flash`            | Gains +2 Mult per reroll in the shop                                                     |
| `j_popcorn`          | +20 Mult, -4 Mult per round played                                                       |
| `j_trousers`         | Gains +2 Mult if played hand contains a Two Pair                                         |
| `j_ancient`          | Each played card with specific suit gives X1.5 Mult, suit changes at end of round        |
| `j_ramen`            | X2 Mult, loses X0.01 Mult per card discarded                                             |
| `j_walkie_talkie`    | Each played 10 or 4 gives +10 Chips and +4 Mult when scored                              |
| `j_selzer`           | Retrigger all cards played for the next 10 hands                                         |
| `j_castle`           | Gains +3 Chips per discarded card of specific suit, changes every round                  |
| `j_smiley`           | Played face cards give +5 Mult when scored                                               |
| `j_campfire`         | Gains X0.25 Mult for each card sold, resets when Boss Blind is defeated                  |
| `j_ticket`           | Played Gold cards earn $4 when scored                                                    |
| `j_mr_bones`         | Prevents Death if chips scored are at least 25% of required, self destructs              |
| `j_acrobat`          | X3 Mult on final hand of round                                                           |
| `j_sock_and_buskin`  | Retrigger all played face cards                                                          |
| `j_swashbuckler`     | Adds the sell value of all other owned Jokers to Mult                                    |
| `j_troubadour`       | +2 hand size, -1 hand each round                                                         |
| `j_certificate`      | When round begins, add a random playing card with a random seal to hand                  |
| `j_smeared`          | Hearts/Diamonds count as same suit, Spades/Clubs count as same suit                      |
| `j_throwback`        | X0.25 Mult for each Blind skipped this run                                               |
| `j_hanging_chad`     | Retrigger first played card used in scoring 2 additional times                           |
| `j_rough_gem`        | Played Diamond cards earn $1 when scored                                                 |
| `j_bloodstone`       | 1 in 2 chance for played Heart cards to give X1.5 Mult when scored                       |
| `j_arrowhead`        | Played Spade cards give +50 Chips when scored                                            |
| `j_onyx_agate`       | Played Club cards give +7 Mult when scored                                               |
| `j_glass`            | Gains X0.75 Mult for every Glass Card that is destroyed                                  |
| `j_ring_master`      | Joker, Tarot, Planet, and Spectral cards may appear multiple times                       |
| `j_flower_pot`       | X3 Mult if poker hand contains a Diamond, Club, Heart, and Spade card                    |
| `j_blueprint`        | Copies ability of Joker to the right                                                     |
| `j_wee`              | Gains +8 Chips when each played 2 is scored                                              |
| `j_merry_andy`       | +3 discards each round, -1 hand size                                                     |
| `j_oops`             | Doubles all listed probabilities                                                         |
| `j_idol`             | Each played card of specific rank and suit gives X2 Mult, changes every round            |
| `j_seeing_double`    | X2 Mult if played hand has a scoring Club and a card of any other suit                   |
| `j_matador`          | Earn $8 if played hand triggers the Boss Blind ability                                   |
| `j_hit_the_road`     | Gains X0.5 Mult for every Jack discarded this round                                      |
| `j_duo`              | X2 Mult if played hand contains a Pair                                                   |
| `j_trio`             | X3 Mult if played hand contains a Three of a Kind                                        |
| `j_family`           | X4 Mult if played hand contains a Four of a Kind                                         |
| `j_order`            | X3 Mult if played hand contains a Straight                                               |
| `j_tribe`            | X2 Mult if played hand contains a Flush                                                  |
| `j_stuntman`         | +250 Chips, -2 hand size                                                                 |
| `j_invisible`        | After 2 rounds, sell this card to Duplicate a random Joker                               |
| `j_brainstorm`       | Copies the ability of leftmost Joker                                                     |
| `j_satellite`        | Earn $1 at end of round per unique Planet card used this run                             |
| `j_shoot_the_moon`   | Each Queen held in hand gives +13 Mult                                                   |
| `j_drivers_license`  | X3 Mult if you have at least 16 Enhanced cards in your full deck                         |
| `j_cartomancer`      | Create a Tarot card when Blind is selected                                               |
| `j_astronomer`       | All Planet cards and Celestial Packs in the shop are free                                |
| `j_burnt`            | Upgrade the level of the first discarded poker hand each round                           |
| `j_bootstraps`       | +2 Mult for every $5 you have                                                            |
| `j_caino`            | Gains X1 Mult when a face card is destroyed                                              |
| `j_triboulet`        | Played Kings and Queens each give X2 Mult when scored                                    |
| `j_yorick`           | Gains X1 Mult every 23 cards discarded                                                   |
| `j_chicot`           | Disables effect of every Boss Blind                                                      |
| `j_perkeo`           | Creates a Negative copy of 1 random consumable at the end of the shop                    |

#### Voucher Cards

Permanent upgrades purchased from the shop that provide lasting benefits like extra slots, discounts, or improved odds. Keys use prefix `v_` followed by the voucher name (e.g., `v_grabber`, `v_antimatter`). 32 cards total.

| Key                 | Effect                                                                         |
| ------------------- | ------------------------------------------------------------------------------ |
| `v_overstock_norm`  | +1 card slot available in shop (to 3 slots)                                    |
| `v_clearance_sale`  | All cards and packs in shop are 25% off                                        |
| `v_hone`            | Foil, Holographic, and Polychrome cards appear 2X more often                   |
| `v_reroll_surplus`  | Rerolls cost $2 less                                                           |
| `v_crystal_ball`    | +1 consumable slot                                                             |
| `v_telescope`       | Celestial Packs always contain the Planet card for your most played poker hand |
| `v_grabber`         | Permanently gain +1 hand per round                                             |
| `v_wasteful`        | Permanently gain +1 discard each round                                         |
| `v_tarot_merchant`  | Tarot cards appear 2X more frequently in the shop                              |
| `v_planet_merchant` | Planet cards appear 2X more frequently in the shop                             |
| `v_seed_money`      | Raise the cap on interest earned in each round to $10                          |
| `v_blank`           | Does nothing?                                                                  |
| `v_magic_trick`     | Playing cards can be purchased from the shop                                   |
| `v_hieroglyph`      | -1 Ante, -1 hand each round                                                    |
| `v_directors_cut`   | Reroll Boss Blind 1 time per Ante, $10 per roll                                |
| `v_paint_brush`     | +1 hand size                                                                   |
| `v_overstock_plus`  | +1 card slot available in shop (to 4 slots)                                    |
| `v_liquidation`     | All cards and packs in shop are 50% off                                        |
| `v_glow_up`         | Foil, Holographic, and Polychrome cards appear 4X more often                   |
| `v_reroll_glut`     | Rerolls cost an additional $2 less                                             |
| `v_omen_globe`      | Spectral cards may appear in any of the Arcana Packs                           |
| `v_observatory`     | Planet cards in consumable area give X1.5 Mult for their poker hand            |
| `v_nacho_tong`      | Permanently gain an additional +1 hand per round                               |
| `v_recyclomancy`    | Permanently gain an additional +1 discard each round                           |
| `v_tarot_tycoon`    | Tarot cards appear 4X more frequently in the shop                              |
| `v_planet_tycoon`   | Planet cards appear 4X more frequently in the shop                             |
| `v_money_tree`      | Raise the cap on interest earned in each round to $20                          |
| `v_antimatter`      | +1 Joker slot                                                                  |
| `v_illusion`        | Playing cards in shop may have an Enhancement, Edition, and/or a Seal          |
| `v_petroglyph`      | -1 Ante again, -1 discard each round                                           |
| `v_retcon`          | Reroll Boss Blind unlimited times, $10 per roll                                |
| `v_palette`         | +1 hand size again                                                             |

#### Pack Cards

Booster packs that can be purchased in the shop. When opened, you select cards to add to your collection. Keys use prefix `p_` followed by pack type, size, and variant number. 32 packs total.

| Key                    | Effect                                                                        |
| ---------------------- | ----------------------------------------------------------------------------- |
| `p_arcana_normal_1`    | Arcana Pack: Choose 1 of 3 Tarot Cards to be used immediately                 |
| `p_arcana_normal_2`    | Arcana Pack: Choose 1 of 3 Tarot Cards to be used immediately                 |
| `p_arcana_normal_3`    | Arcana Pack: Choose 1 of 3 Tarot Cards to be used immediately                 |
| `p_arcana_normal_4`    | Arcana Pack: Choose 1 of 3 Tarot Cards to be used immediately                 |
| `p_arcana_jumbo_1`     | Jumbo Arcana Pack: Choose 1 of 5 Tarot Cards to be used immediately           |
| `p_arcana_jumbo_2`     | Jumbo Arcana Pack: Choose 1 of 5 Tarot Cards to be used immediately           |
| `p_arcana_mega_1`      | Mega Arcana Pack: Choose up to 2 of 5 Tarot Cards to be used immediately      |
| `p_arcana_mega_2`      | Mega Arcana Pack: Choose up to 2 of 5 Tarot Cards to be used immediately      |
| `p_celestial_normal_1` | Celestial Pack: Choose 1 of 3 Planet Cards to be used immediately             |
| `p_celestial_normal_2` | Celestial Pack: Choose 1 of 3 Planet Cards to be used immediately             |
| `p_celestial_normal_3` | Celestial Pack: Choose 1 of 3 Planet Cards to be used immediately             |
| `p_celestial_normal_4` | Celestial Pack: Choose 1 of 3 Planet Cards to be used immediately             |
| `p_celestial_jumbo_1`  | Jumbo Celestial Pack: Choose 1 of 5 Planet Cards to be used immediately       |
| `p_celestial_jumbo_2`  | Jumbo Celestial Pack: Choose 1 of 5 Planet Cards to be used immediately       |
| `p_celestial_mega_1`   | Mega Celestial Pack: Choose up to 2 of 5 Planet Cards to be used immediately  |
| `p_celestial_mega_2`   | Mega Celestial Pack: Choose up to 2 of 5 Planet Cards to be used immediately  |
| `p_spectral_normal_1`  | Spectral Pack: Choose 1 of 2 Spectral Cards to be used immediately            |
| `p_spectral_normal_2`  | Spectral Pack: Choose 1 of 2 Spectral Cards to be used immediately            |
| `p_spectral_jumbo_1`   | Jumbo Spectral Pack: Choose 1 of 4 Spectral Cards to be used immediately      |
| `p_spectral_mega_1`    | Mega Spectral Pack: Choose up to 2 of 4 Spectral Cards to be used immediately |
| `p_standard_normal_1`  | Standard Pack: Choose 1 of 3 Playing Cards to add to your Deck                |
| `p_standard_normal_2`  | Standard Pack: Choose 1 of 3 Playing Cards to add to your Deck                |
| `p_standard_normal_3`  | Standard Pack: Choose 1 of 3 Playing Cards to add to your Deck                |
| `p_standard_normal_4`  | Standard Pack: Choose 1 of 3 Playing Cards to add to your Deck                |
| `p_standard_jumbo_1`   | Jumbo Standard Pack: Choose 1 of 5 Playing Cards to add to your Deck          |
| `p_standard_jumbo_2`   | Jumbo Standard Pack: Choose 1 of 5 Playing Cards to add to your Deck          |
| `p_standard_mega_1`    | Mega Standard Pack: Choose up to 2 of 5 Playing Cards to add to your Deck     |
| `p_standard_mega_2`    | Mega Standard Pack: Choose up to 2 of 5 Playing Cards to add to your Deck     |
| `p_buffoon_normal_1`   | Buffoon Pack: Choose 1 of 2 Joker Cards                                       |
| `p_buffoon_normal_2`   | Buffoon Pack: Choose 1 of 2 Joker Cards                                       |
| `p_buffoon_jumbo_1`    | Jumbo Buffoon Pack: Choose 1 of 4 Joker Cards                                 |
| `p_buffoon_mega_1`     | Mega Buffoon Pack: Choose up to 2 of 4 Joker Cards                            |

#### Playing Cards

Playing cards use the format `{Suit}_{Rank}` where:

- **Suit**: `H` (Hearts), `D` (Diamonds), `C` (Clubs), `S` (Spades)
- **Rank**: `2`-`9`, `T` (Ten), `J` (Jack), `Q` (Queen), `K` (King), `A` (Ace)

Examples: `H_A` (Ace of Hearts), `S_K` (King of Spades), `D_T` (Ten of Diamonds), `C_7` (Seven of Clubs)

---

## Error Codes

| Code   | Name             | Description                              |
| ------ | ---------------- | ---------------------------------------- |
| -32000 | `INTERNAL_ERROR` | Server-side failure                      |
| -32001 | `BAD_REQUEST`    | Invalid parameters or protocol error     |
| -32002 | `INVALID_STATE`  | Action not allowed in current game state |
| -32003 | `NOT_ALLOWED`    | Game rules prevent this action           |

---

## OpenRPC Specification

For machine-readable API documentation, use the `rpc.discover` method to retrieve the full OpenRPC specification.
