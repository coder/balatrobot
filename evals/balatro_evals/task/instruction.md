# Balatro

A run of Balatro (Red Deck, White Stake, a fixed seed) is ready in this
container, and you play it from the terminal with the `balatro` command. Your
score is the number of blinds you defeat, out of the 24 in a winning run (8
antes, each a Small, Big, and Boss blind); winning the run scores all 24. The
run ends when you fail a blind, and it cannot be restarted, so make each hand
count. Play until the state is `GAME_OVER` or the run is won.

## Commands

Every command prints the state of the game afterwards: the phase, ante, money,
the blinds and their targets, your hand, jokers, consumables, and what the shop
or an opened pack offers. Indices are 0-based positions in the printed lists,
and cards move after every play, discard, and draw, so read the state before
each action. Add `--json` to any command for the raw game state.

- `balatro gamestate` prints the state.
- `balatro select` enters the blind on offer; `balatro skip` skips a Small or
  Big blind for the tag shown. Both at `BLIND_SELECT`.
- `balatro play '{"cards":[0,1,2]}'` plays up to 5 cards from your hand;
  `balatro discard '{"cards":[3,4]}'` discards up to 5. Both at
  `SELECTING_HAND`.
- `balatro cash_out` collects the round's money at `ROUND_EVAL` and enters the
  shop.
- `balatro buy '{"card":0}'`, `balatro buy '{"voucher":0}'`, and
  `balatro buy '{"pack":0}'` buy from the shop; `balatro reroll` rerolls it;
  `balatro next_round` leaves it. All at `SHOP`.
- `balatro pack '{"card":0}'` takes a card from an opened pack, with
  `"targets":[...]` for a Tarot or Spectral card that needs cards from your
  hand; `balatro pack '{"skip":true}'` skips it. At `SMODS_BOOSTER_OPENED`.
- `balatro sell '{"joker":0}'` and `balatro sell '{"consumable":0}'` sell;
  `balatro use '{"consumable":0}'`, with `"cards":[...]` where the card needs
  targets, uses a consumable. At `SELECTING_HAND` or `SHOP`.

A rejected action prints why and leaves the game unchanged. The game's debug
methods (`add`, `set`, `save`, `load`, `start`, `menu`) are disabled.

## Scoring a hand

A played hand scores roughly (base chips + the chips of its scoring cards +
bonuses) × (base mult + bonuses); jokers, card enhancements, debuffs, and boss
blind effects change it. At level 1, the bases are High Card 5×1, Pair 10×2, Two
Pair 20×2, Three of a Kind 30×3, Straight 30×4, Flush 35×4, Full House 40×4,
Four of a Kind 60×7, and Straight Flush 100×8; the printed `hands` line has the
current values. Number cards score their rank in chips, face cards 10, and
Aces 11. Choose hands that clear the blind's target, not only the highest rank,
and consider discarding to improve your hand while discards remain.
