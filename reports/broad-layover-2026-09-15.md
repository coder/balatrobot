# Broad-layover trace audit — 2026-09-15

Run: `broad-layover-3a0ce678e7da`, resumed from
`perfect-adhesive-da14ace5a831`, 8 colocated nodes, 16 seed groups × 4 samples
(64 episodes/update). No training settings or rewards were changed for this audit.

## Status and learning trend

At the final status check the job was running, reporting weight sync at
416/600, with rollout 415 reward 46.47. The numbering resumes at 400; this
does not mean this continuation has already performed 416 new updates.

For the first 14 completed batches (400–413):

| Window | Episodes | Mean reward | Mean final ante |
|---|---:|---:|---:|
| 400–406 | 448 | 51.70 | 3.27 |
| 407–413 | 448 | 50.52 | 3.18 |
| Parent run 390–399 | 320 | 51.32 | 3.30 |

The continuation is approximately flat, not demonstrating a clear increase
in depth. Across 400–413 there were no wins in 896 episodes; the highest
recorded final ante was 7. These are training batches with different seeds,
not a controlled fixed-seed evaluation. A single low batch is not sufficient
evidence of parameter/entropy collapse.

## What happened in the traces

I reconstructed sparse states (including nested fallback/error results),
read prompts and model responses, and audited all 192 episodes in batches
400, 412 and 413. The dashboard CLI rejected its stored authentication;
the reads used the authenticated Training Gym SDK and persisted rollout data.

| Rollout | Mean reward | Game over | Context cap | Ended at ante 1 |
|---|---:|---:|---:|---:|
| 400 | 52.23 | 55 | 9 | 12 |
| 412 | 55.67 | 59 | 5 | 11 |
| 413 | 36.45 | 63 | 1 | 29 |

The latest audited dip is primarily more early game overs, not more context
cutoffs or terminal RPC errors. No audited episode hit the 250-decision cap.
This does not prove every game over is free of harness influence.

### 1. Narrow hand selection and missed joker synergies

Of 3,914 executed plays, 2,799 (71.5%) were Pair or Two Pair. Only four were
Straights and two were Flushes. The model made no `sell` or blind `skip`
actions across these batches, and rerolled a shop only three times.
This describes a narrow strategy, not a proof that each such action was bad.

There were 131 plays of Pair/High Card while a raw five-rank straight existed
in hand, across 91 episodes. This is an opportunity flag, not an exact-regret
metric: debuffs, enhancements and joker synergies can favor a lower hand type.

One unambiguous example is rollout 413, sample index 0, action 16:

- Ante 1 Big Blind; 256/450 chips, one hand and one discard remaining.
- Hand indices: `0 H_A, 1 D_K, 2 S_Q, 3 H_J, 4 D_J, 5 H_T, 6 S_8, 7 C_2`.
- Jokers: Superposition and Devious Joker (+100 Chips for a Straight).
- Played `[4,3,5,6,2]`: a Pair, 60 chips; lost at 316/450.
- `[0,1,2,3,5]` is A-K-Q-J-10. From the recorded, unmodified inputs,
  `(30 + 51 + 100) × 4 = 724` chips, comfortably enough to clear.
  This arithmetic is not a new game-engine replay, but there is no random
  scoring modifier in the recorded state. Superposition also benefits from
  this exact straight. Sample 2 repeats essentially the same mistake.

In sample 3, action 24, A-K-Q-J-10 was again available; the policy instead
played Q-J-10-9-5 as High Card, scoring 15 and losing to The Hook.
The relevant card/joker information was present in the model's context.

### 2. The context budget cuts off deeper attempts

15/192 episodes (7.8%) hit the 49,152-token context limit, typically after
102–135 decisions, well before the 250-decision limit. Examples include
rollout 400 sample 7 ending alive in the ante-6 shop and rollout 412 sample
38 ending at ante 5 with 17,242/22,000 chips and a hand remaining.

These traces do not establish that the capped games would have won, but
the model is denied the opportunity to continue. Raising only the decision
budget cannot fix this. Context caps retain earned progress and receive no
cap penalty in the current reward implementation; decision caps get -10.

### 3. Confirmed pack legality gap: Judgement at full joker capacity

Rollout 413, sample 39:

- Action 61: skipped a Buffoon pack while at 5/5 jokers.
- Action 62: bought an Arcana pack containing The Moon, Judgement and Wheel
  of Fortune.
- Action 63: `pack {card:1}` used Judgement at 5/5.
- The next raw state contains **six actual joker entries**, slots `6/5`,
  adding ordinary Bloodstone with no Negative edition. This is not just a
  dashboard counting artifact.

The pack endpoint checks capacity for a directly selected Joker, but invokes
`G.FUNCS.use_card` for Tarot/Spectral selections without the
`can_use_consumeable()` check used by the normal `use` endpoint. The compact
pack legal-action filter also lacks a Judgement-at-capacity exclusion.
This permits a game-rule violation and should be corrected separately.
No pack behavior was changed during this diagnosis.

### 4. Repeated ante checkpoint bonuses after ante-lowering vouchers

Rollout 400, sample 8 went 1→2→3, bought a voucher at action 48 that changed
ante 3→2, then cleared 2→3 again and later 3→4. It therefore recorded four
ante checkpoint bonuses despite finishing at ante 4.

The ante regression itself is legitimate voucher behavior. The reward
function awards +8 on every positive ante delta and does not distinguish
first attainment from re-clearing an already reached ante. This explains
some reward/final-ante disagreement and creates an objective loophole if the
goal is uniquely advancing toward ante 8. It is separate from UI labeling.
No reward changes were made.

### 5. Missing machine-readable joker targets

Rollout 412 already records Idol targets in effect text, e.g. “3 of Hearts”
and “10 of Diamonds.” The prior calculator adapter did not read them.
The viewer now parses exact recorded targets for historical traces; future
RPC snapshots include structured visible round targets for The Idol, Ancient
Joker, Mail-In Rebate and Castle. It does not save/expose private RNG state,
roll RNG during observation, or substitute today's target into older frames.

The traces also contain unresolved boss-description placeholders such as
`#1# in #2# cards get drawn face down`; structured numerical effect data would
avoid that information loss. This was noted, not repaired in this patch.

## Interpretation and next steps

The evidence supports a mixture of a narrow, sometimes plainly incorrect
policy; context-limited long episodes; and remaining legality/reward gaps.
It does not support explaining everything as flaky execution or diagnosing
an optimizer collapse from the reward dip alone.

The next experiments should first close the Judgement pack legality gap,
decide whether ante bonuses mean first attainment or repeated clears, and
address history growth. Then compare fixed seeds and hand-level decisions.
Larger batches alone do not teach the missing scoring/synergy reasoning.

## Changes completed for the accompanying UI requests

- Restored expanded ante/round/phase navigation and per-group turn buttons.
- Restored discarded-card highlighting and a direct discard-pile inspector.
- Automatically calculate recorded play frames; show actual recorded chips
  separately from estimates, including when estimate inputs are missing.
- Recover saved Idol targets and add structured target capture for newly
  built sandboxes. Existing training workers were not hot-patched.
- 38 viewer tests and 18 CPU serializer/launcher tests passed; the dashboard
  bundle compiled. Browser visual verification was unavailable.
