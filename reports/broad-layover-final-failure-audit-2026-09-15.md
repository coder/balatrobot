# Broad-layover: final failure and learning audit

Run: [broad-layover-3a0ce678e7da](https://modal-labs-joy-dev--training-gym-dashboard-fastapi-app.modal.run/training/broad-layover-3a0ce678e7da?tab=summary). Checked September 15, 2026.

## Conclusion

Two problems occurred independently:

1. **The first attempt crashed in NCCL during checkpoint saving. Three automatic retries then loaded the same incomplete checkpoint and failed before another training update.**
2. **The policy already performed poorly and regressed before that crash.** It increasingly played weak combinations, left usable discards, and missed straightforward winning hands. The training setup supplies whole-game relative reward, offering weak guidance about which individual decisions were wrong.

The crash is established by logs and checkpoint contents. The mechanism behind poor learning is an evidence-based diagnosis, not a controlled causal experiment.

## Evidence inspected

- Persisted run configuration, status, attempt history, and all 50 rollout summaries (400–449; 3,200 games).
- Full prompts and responses from batches 400, 413, 425, 440, and 449: 320 episodes, with sparse state reconstruction and 6,056 executed plays.
- Modal logs covering optimizer steps 425–449 and all four failure endings.
- Committed checkpoint directory and `.metadata` references. Metadata was inspected with `pickletools`, without executing the pickle.
- Local checkpoint validation and reward code, including the earlier committed harness for comparison. The currently edited harness has changes that this historical run did not use.

The dashboard and normal CLI returned authentication errors. Reads used the authenticated Training Gym SDK and Modal CLI. No training configuration, code, running jobs, or remote data was changed.

## 1. Why it failed four times

All times below are EDT on September 15.

| Attempt | Failure time | Evidence |
|---|---|---|
| 1 | 03:54 | Native segfault in `ras/peers.cc:549`, `rasMsgHandlePeersUpdate`, inside the NCCL RAS thread. Ray reports `ActorDiedError` while waiting for `actor_model.save_model(449)`. |
| 2 | 04:06 | Auto-resumes checkpoint 449; loading fails with missing `__32_1.distcp` through `__35_1.distcp`. |
| 3 | 04:17 | Same checkpoint; missing shards including `__44_1.distcp`, `__48_1.distcp`, `__52_1.distcp`, plus invalid-argument reads. |
| 4 | 04:28 | Same load failure. Persisted final error names `__44_1.distcp`. |

Step 449's optimizer update completed at 03:51:41. Saving began at 03:51:52, and Megatron printed “successfully saved” at 03:52:45. The outer save operation had not returned when actors segfaulted. That message therefore did not establish a durable, reloadable checkpoint.

The committed checkpoint now has **112 of 128 referenced `.distcp` files**. Every `__40_1.distcp` through `__55_1.distcp` is missing. Different missing files in the earlier retry logs indicate that its visible contents changed; they do not change the finding that the checkpoint was incomplete. We did not validate byte ranges in the remaining files, so there may also be truncated shards.

### Why the retries did not recover

`is_complete_torch_dist_checkpoint()` in Training Gym's `common/torch_dist_checkpoint.py` only checks for `.metadata`, `common.pt`, and **any** `.distcp` file. I passed the actual directory listing into that function: it returned `True` despite the 16 missing referenced files. The launcher uses this check when selecting a resume checkpoint.

Thus automatic recovery accepted an invalid checkpoint and repeated the same deterministic failure three times. The exact underlying NCCL defect and the precise timing of failed volume persistence are not established by these logs. The native stack identifies the first crash; there is no need to infer an OOM from Ray's generic list of possible causes.

## 2. Learning did not improve before the crash

This continuation resumed from parent `perfect-adhesive-da14ace5a831` at 400. It completed **50 new updates**, not 450. Retries added none.

| Batches | Games | Mean reward | Mean final ante | Wins |
|---|---:|---:|---:|---:|
| 400–409 | 640 | 51.89 | 3.26 | 0 |
| 410–419 | 640 | 48.31 | 3.11 | 0 |
| 420–429 | 640 | 49.42 | 3.17 | 0 |
| 430–439 | 640 | 50.62 | 3.18 | 0 |
| 440–449 | 640 | 39.13 | 2.67 | 0 |

Last-window reward was **24.6% below** the first window. These are changing training seeds, not a fixed-seed evaluation, so the table alone cannot measure causal checkpoint regression. The decision errors below directly establish poor play.

## 3. What the model actually did

| Batch | Pair / Two Pair share | Discards per play | Game overs with discards left | Context cutoffs |
|---|---:|---:|---:|---:|
| 400 | 66.1% | 0.92 | 21 / 55 | 9 / 64 |
| 413 | 72.4% | 0.60 | 42 / 63 | 1 / 64 |
| 425 | 75.0% | 0.57 | 47 / 64 | 0 / 64 |
| 440 | 80.2% | 0.29 | 58 / 64 | 0 / 64 |
| 449 | 79.2% | 0.41 | 53 / 62 | 2 / 64 |

These counts are behavior indicators: a Pair can be optimal with suitable jokers, and an unused discard does not by itself prove a recoverable loss.

### Directly avoidable losses

**Batch 440, sample position 4 (sample_index 15364), action 7:** Ante 1 Small Blind, 212/300 chips, one hand and two discards left, no jokers. The hand was:

`0 H_A, 1 H_K, 2 C_K, 3 D_K, 4 C_J, 5 S_9, 6 S_3, 7 H_2`.

The model played `[4,3,2,6,5]`: only two Kings, scoring 60 and losing at 272/300. Playing `[1,2,3]` gives Three of a Kind, `(30 + 30) × 3 = 180`, and clears the blind. The state included both the cards and current scoring bases. No boss was active in this Small Blind.

**Batch 449, sample position 7 (sample_index 15943), action 8:** Ante 1 Small Blind, 235/300 chips, one hand and one discard left, no jokers. The hand contained two Eights and two Threes. The model played `[6,7,5,4,3]`, a Pair of Threes worth 32, and lost. Selecting both pairs `[2,3,6,7]` scores `(20 + 8 + 8 + 3 + 3) × 2 = 84`, enough to clear.

These alternatives are deterministic arithmetic from recorded unmodified state, not new engine replays.

### Evidence of reliance on familiar index patterns

The selected set `{3,4,5,6,7}` rose from 94/1,314 plays (7.2%) in batch 400 to 341/1,308 (26.1%) in batch 449. The losing action in the second example uses exactly that set despite omitting the other Eight. This is consistent with learned positional templates that fail to condition sufficiently on actual cards; frequency alone does not prove the internal mechanism.

Across all five sampled batches, the policy never sold a joker or skipped a blind and rerolled only four times. This limits adaptation of its early purchases. The 6,056 plays included just 13 Straights and two Flushes. There were 273 Pair/High Card plays with a raw straight available; these are opportunity flags, not 273 proven mistakes.

## 4. Why this training setup plausibly reinforces the problem

**Whole-game credit assignment is weak.** The persisted recipe uses GRPO, four games per seed, and `normalize_episode_rewards`. The matching local reward implementation normalizes final game scores within a seed group and produces one relative advantage per game. The checkpoint reward events shown in the dashboard do not by themselves supply hand-level advantages. A relatively better losing game can reinforce poor plays embedded in that game. Better joker luck and many intervening actions obscure which card choice deserved credit.

**Useful strategic exploration is narrow.** Four samples per seed yielded distinct transcripts, and 77/80 sampled seed groups had nonzero reward variance. Therefore this is not a blanket zero-reward-variance failure. But many trajectories differ in card-index permutations while repeating the same limited approach. Batch size 64 does not ensure the groups contain examples of the missing strategies.

**The model must select actions without written reasoning.** The run used `enable_thinking=false`, a 96-token generation limit per action, and instructions to return only JSON. It receives scoring rules, but has no demonstrated hand-scoring decision step. This is a plausible constraint on learning the missing combinations, not proof that enabling reasoning would solve it.

**Context limits censor some deeper games.** The run used a single growing conversation capped at 49,152 tokens. Twelve of the 320 sampled games reached that cap. However, batch 440's entire sample ended in game over with zero context caps, so truncation cannot explain the late reward dip. The newer segmented-context code in the workspace was not used by this run.

**There is no evidence here of gradients stopping or exploding.** Steps 425–449 log finite gradient norms of 1.13–2.12 and learning rate `1e-6`. The logged entropy metric rises between the ends of that window, so a simple entropy-collapse claim is unsupported. Zero PPO KL and clip fraction in these logs do not, by themselves, establish that weights were unchanged.

The earlier audit also identified repeated ante bonuses after ante-lowering vouchers and a Judgement pack-capacity gap. Those can distort reward or legality, but do not explain the direct hand-selection failures or the four infrastructure failures.

## Recommended order of follow-up

1. **Fix checkpoint durability and resume validation:** verify every metadata-referenced shard and its required byte range, finish commits from every node, then publish a completion marker. Reject incomplete checkpoints and fall back to a verified earlier checkpoint. More retries cannot repair missing files.
2. **Investigate the native NCCL RAS crash** with the recorded native stack and exact deployed library version. The first failure happened during distributed save, not game rollout.
3. **Measure card-selection competence on fixed states**, including the two guaranteed-clear examples above. Compare available checkpoints on the same seeds, scoring win rate, ante, avoidable losses, discard use, and joker replacement.
4. **Test one learning intervention at a time:** verified scoring demonstrations or a short hand-selection curriculum are justified by these traces. Separately test action-level credit assignment. Preserve the actual win metric and validate the intended objective before changing rewards.
5. **Use bounded context and close known harness gaps** before another long continuation. Verify save/reload as part of a short proof run.

No fix or relaunch was performed during this diagnosis. Structured evidence is in [broad-layover-final-evidence-2026-09-15.json](broad-layover-final-evidence-2026-09-15.json).
