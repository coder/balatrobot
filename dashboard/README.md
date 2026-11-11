# Balatro dashboard component

`TrajectoryViewer.svelte` is the Balatro-specific trajectory viewer shipped
with this repository. `batro_modal_rl.py` resolves it relative to its own
file and attaches it to each launched run through Training Gym's
`training-gym-dashboard-overlay` volume.

Training Gym also ships a framework-default viewer at
`training-gym/dashboards/frontend/src/components/TrajectoryViewer.svelte`.
That file is the fallback used by the dashboard when no Balatro component is
attached (and can be replaced globally with `training-gym setup`).

The Balatro viewer follows the same Svelte props contract as the default:
`sample`, `samples`, `trajectory`, `rewardEvents`, `rollout`, and `run`.

The board shows chips scored, the current blind's target, and chips still
needed. Targets are per blind, not per ante; selection starts at zero and
shop/pack screens never reuse the previous blind's score. The initial
selection is available as the `S` frame. Blind selection lists each target,
skip tag, and its recorded effect; skip outcomes distinguish the tag taken
from the next blind's offer. Missing recorded effects are explicitly marked.

Run compiler and rendered-output regression tests with
`node --test dashboard/TrajectoryViewer.test.mjs`. This uses Svelte installed
in `../training-gym/dashboards/frontend`; set `TRAINING_GYM_FRONTEND` to
override that location.

## Card rendering

Playing cards and all 150 standard jokers use the sprite atlases and layering
approach from EFHIII's Balatro Calculator, pinned to commit
`55322d59197ba08c16874a54b59ac0d443c8ab32`. Enhancement backgrounds, rank/suit
art, legendary-joker overlays, edition textures, seals and debuff crosses are
composed separately. Polychrome uses the calculator's color blend; Negative
uses an inverted-art treatment. Unknown/modded cards retain a text fallback.
Modifier badges remain visible, including stickers and remaining perishable
rounds. Hover is optional, not required to identify a modifier.

The four PNG atlases are embedded once as CSS variables in the single-file
component, so viewing a trajectory makes no external image requests. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and license.
## UI-only calculator and joker information

The viewer now embeds the pinned upstream `balatro-sim.js` scoring logic,
wrapped to isolate mutable hand-value tables between calculations. The only
change inside the upstream implementation is a Svelte performance-warning
annotation; no scoring rules are rewritten. Its result is an **estimate**,
not an engine RPC or a claim of full Balatro accuracy.

Click 1–5 cards in play order, then **Calculate**. The compact HUD displays
hand type, Chips × Mult, and the upstream worst/best range for random effects.
Recorded play frames calculate automatically. Their actual `play_commit.score`
is shown separately and remains visible even when calculator inputs are missing.
Discard frames highlight the removed pre-action cards in red, independently
of calculator selection. The discard-pile button opens its card inventory.
Historical plays use pre-action cards, jokers, and hand values. Joker order
stays as recorded; this UI does not optimize, commit a play, call a model,
or change harness rewards. Calculations never mutate trajectory state.

Counters not present in the compact trace must be entered explicitly in the
same units as the upstream calculator (for example Hologram's *Cards Added*,
not its Mult). Known money/discard counters are populated from the trace.
Unsupported cards/jokers block calculation; missing persistent card bonuses
and unmodeled boss/deck effects remain limitations. Flint, Eye, Plasma Deck,
and Observatory settings are available for inspection/editing. Missing hand
levels/history default to level 1 / zero, as in the upstream calculator.

The Lua gamestate RPC exports `card.scoring_state.target` for The Idol,
Ancient Joker, Mail-In Rebate and Castle, plus Castle's current chip tally.
The compact harness preserves this in each joker's snapshot and sparse deltas.
These are already-selected, player-visible targets—not RNG seeds or future
draws. The calculator converts rank/suit to its internal Card/Suit ID, so no
manual ID is needed. For older traces, exact English target descriptions can
be recovered from recorded effect text. Unknown targets remain unknown;
current live targets are never substituted into historical frames.
Structured capture requires newly built sandboxes; existing running training
workers are not hot-patched by a dashboard upload.

Joker sprites have hover/focus/tap tooltips with the recorded effect, edition
bonuses, stickers, and sell value. Escape dismisses a focused tooltip.

## Compact game layout

The layout follows Balatro's game board: score/status HUD on the left, jokers
and consumables across the top, phase-specific content in the center, hand
and deck inspection below. It uses the embedded m6x11plus pixel font,
blue/red Chips × Mult blocks, chunky controls, and a muted felt table.
Container queries adapt to the dashboard panel's width, not just the window.

The replay navigation stays expanded above the board, with ante/round/phase
tabs and individual turn buttons for the selected group. Previous/next buttons
can cross group boundaries. There is no continuous frame scrubber.
**Run info**, **Calculator**, and **Trace & rewards** open an inspector below
the board. Deck/discard contents, vouchers, joker counters, hand levels,
calculator settings, raw pre/post-action states and reward events remain
available without keeping every panel expanded. Rewards are explicitly
episode-wide rather than falsely aligned to the selected frame.

Run Info sections start collapsed, including the empty owned-voucher message.
Expanding inventory sections shows card racks with modifiers and click-to-open
details; raw fields remain under **Recorded data**. Poker hand levels and
history use a compact table, with missing values shown as dashes. The board's
deck/discard buttons still expand the corresponding section directly.

Shop cards, prices, vouchers, booster offers and reroll cost are visible in
shop frames; pack frames show their choices. Item details retain all recorded
fields. Non-playing, non-joker cards currently use labeled symbolic tiles.
The top inventory and HUD always show the resulting state; historical play
inputs below are explicitly labeled pre-action. Discards left is distinct
from the discard pile size. Unknown counters display a dash, not a guessed
value. No training settings, harness behavior or rewards change with this UI.
