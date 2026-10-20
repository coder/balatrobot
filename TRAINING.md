# Training experiments

## Named sandbox image

Game sandboxes use `modal.Image.from_name("balatrobot")` in the selected Modal
environment. Publish the runtime once, and republish when its build recipe changes:

```sh
./training/dojo.sh python batro_modal_rl.py --publish-image
./training/dojo.sh python batro_modal_rl.py --smoke-env
```

The build recipe stays in `batro_modal_rl.py`; no separate image file is needed.
Episode startup resolves `balatrobot:latest` without rebuilding the runtime.
Private game assets still come from the `balatro-rl-assets` volume.
Already deployed training code keeps its previous image-loading behavior; new
training deployments use the named image.

## Define experiments in Python

[`experiments.py`](experiments.py) is the experiment catalog. Each definition
builds a Dojo `TrainConfig` directly in code. Add variants with
`dataclasses.replace(BASE, ...)`; JSON configuration files are unnecessary.

```sh
# List experiments, then preview locally (no remote calls or files written).
./training/dojo.sh python experiments.py
./training/dojo.sh python experiments.py thinking_8k_200

# Validate datasets and exact checkpoint without allocating GPUs.
./training/dojo.sh python experiments.py thinking_8k_200 --validate

# Submit and register cloud monitoring. Reusing a trial prevents duplicates.
./training/dojo.sh python experiments.py thinking_8k_200 --trial baseline --launch
```

The catalog includes `proof` (1 update), `smoke` (10), `reward_to_go_200`, and
`thinking_8k_200` (200 updates with 8,192 thinking tokens). All start from
`perfect-adhesive-da14ace5a831/iter_0000399` with a fresh optimizer. These names
describe configurations, not evidence that training will succeed.

Python callers can use the same definitions:

```python
from experiments import EXPERIMENTS, launch

config = EXPERIMENTS["thinking_8k_200"].build()  # actual Dojo TrainConfig
run = launch("thinking_8k_200", trial="baseline")
```

Dojo stores the resolved training configuration with the run. The local launcher
automatically writes only a submission receipt under
`reports/experiments/<experiment>/<trial>/receipt.json`. This records the run ID
and blocks accidental resubmission, including after an interrupted launch.
Never delete a receipt to retry an uncertain submission; inspect the remote run
first. Choose a new trial name for an intentional new experiment.

The old `.launch-config-examples/` exports were removed. Historical launch
receipts are retained under `reports/legacy-launches/` for diagnosis; generated
evidence and receipts are not experiment inputs. `balatro_compare.py` remains
available as a lower-level builder/CLI and no longer writes `.config.json` files.

## Modal Dojo (October 19)

Replacement run: `overcast-groove-11909ffa4c8f`, 200 updates from
`perfect-adhesive-da14ace5a831/iter_0000399`, fresh optimizer, 8K thinking.
The former `naive-rotation-0d3fe4fb61a0` app was stopped and its zero remaining
containers verified before submission. The Dojo dashboard is
`https://modal-labs-joy-dev--dojo-dashboard-fastapi-app.modal.run`.
Launch receipt and migration evidence are in
`reports/launch-dojo-200step-20261019.json` and `reports/dojo-migration-20261019.json`.

The active launch and monitoring code now uses `modal_dojo`; the Training Gym
checkout is no longer a dependency. Bootstrap the isolated Python 3.12 project:

```sh
uv run --no-project --python 3.12 training/setup_dojo.py
uv sync --project training --group test
```

For an existing Dojo source checkout, pass `--source ../modal-dojo` to the
bootstrap command. It clones pinned revision `0bd6789d1be43c1eb10928d3d69be55de2d2533e`
into `training/.dojo` and applies `training/dojo-checkpoint-recovery.patch`.
The patch preserves strict shard validation, committed-save verification,
temporary Gloo-group cleanup, and correct optimizer/RNG restoration on retry.
It also supports a project-local configuration file and preserves the dashboard's
Modal environment. It does not edit the source checkout or global Dojo settings.

Use `training/dojo.sh` for all training commands. It selects the pinned package,
Python 3.12, profile `modal-labs`, environment `joy-dev`, and private configuration
`training/.dojo-config.toml`. Explicit environment overrides take precedence.
The Balatro model, rewards, thinking handoff, topology, and checkpoint-volume
name remain unchanged. The new dashboard uses `modal-dojo-metadata`; historical
Training Gym records stay in their original volume.

```sh
# Validate configuration, dataset rows, and exact checkpoint 399 without GPUs.
./training/dojo.sh python experiments.py thinking_8k_200 --validate

# Submit once; wait for the receipt to say "submitted".
./training/dojo.sh python experiments.py thinking_8k_200 --trial baseline --launch

# Deploy the watchdog when its code changes (launch registers runs automatically).
./training/dojo.sh modal deploy training/cloud_watchdog.py

./training/dojo.sh modal-dojo run get RUN_ID --verbose
./training/dojo.sh python training/monitor_run.py RUN_ID --learning
```

The Dojo watchdog uses its own `balatro-dojo-watchdog` app/registry and metadata
volume, so it cannot confuse an old Training Gym run with a Dojo run. Dashboard
CLI reads still require the dashboard's existing authentication; failed reads
are not evidence of a training failure.

Migration checks: 237 local harness tests, 35 checkpoint/recovery tests, 3 real
Dojo API checks, 42 viewer tests, and 75 pinned-trainer CPU tests passed. Native
CPU validation also reproduced the old process-group cleanup error and passed
three corrected saves on each of two ranks. These are compatibility checks,
not evidence of improved learning.

## Thinking-budget handoff (October 12)

At the 8,192-token thinking limit, the harness now inserts `</think>` and
continues generation with a separate 96-token final-answer allowance. The
inserted token remains in the exact inference/training context, with zero
loss mask and no action advantage. Naturally sampled closing tokens retain
normal training credit. Reaching the thinking budget alone is no longer an
invalid action; malformed or length-limited final answers still receive the
existing penalties and execute no game action.

Context reservations include up to 8,289 physical response tokens: 8,192
sampled thinking tokens, one optional control token, and 96 sampled answer
tokens. Sampled-token percentiles exclude the inserted control token.
`thinking_forced_close_count/fraction` track handoffs, and episode metrics
separate `balatro/control_tokens` from feedback tokens.

Validation and limitations: `reports/thinking-handoff-fix-20261012.md`.
No replacement training run was launched for this fix.

## Thinking relaunch (October 5)

`warped-median-9f188a4959eb` uses the same 200-update, 8,192-token thinking
recipe from `perfect-adhesive-da14ace5a831/iter_0000399` with a fresh optimizer.
Thinking runs now checkpoint every five updates and allow ten bounded whole-job
recoveries. The previous thinking run hit the 24-hour Modal invocation limit;
recovery still loads this run's latest complete checkpoint and keeps the same
200-update target.

The parent run's metadata was unavailable while checkpoint 399 remained intact.
The comparison launcher can now locate its deterministic checkpoint volume and
validate the exact iteration directly; missing or invalid weights still fail
preflight. Checkpoint 399's shard manifest matched its predecessor.

The dashboard endpoint was unavailable. It was redeployed with its Modal
environment preserved, and an authenticated empty metric request returned HTTP
200 before submission. The cloud watchdog was redeployed as well. Launch
checks: 74 passed, one native-image-only skip. Evidence and source hashes:
`reports/thinking-8k-provenance-20261005.json`.

## Optional 8K thinking (October 1)

`balatro_compare.py --thinking-budget 8192` enables the model's thinking chat
template for initial snapshots and every feedback turn. Each decision has up
to 8,192 sampled thinking tokens, including a naturally sampled closing `</think>` token, then
up to 96 tokens for the final JSON action. The serving request pauses at the
sampled closing token and resumes with those exact IDs in its prefix. As of
October 12, exhausting the thinking budget without closing the block inserts
a masked control token and continues to the final answer (see above).

Both reasoning and final-answer tokens retain their sampled log probabilities
and action advantage. Strict single-action validation applies to the final
answer only. Context reservations include up to 8,289 physical response tokens;
thinking runs use a 16,384-token segment target within the same 49,152-token
hard context limit. Initial checkpoint, optimizer reset, reward, topology,
held-out seeds, and 200-update horizon remain the comparison recipe's defaults.

Diagnostics report total sampled `action_tokens_*`, plus separate
`thinking_tokens_*` and `final_answer_tokens_*` percentiles and
`thinking_budget_hit_fraction`. Watchdog length-limit and malformed-output
checks still apply to invalid responses. Long reasoning alone is not treated as
repeated-action output.

## Single-action output contract (September 30)

The harness now validates the entire generated response: exactly one JSON
object with `method` and `params`, followed by natural termination. Whitespace
and one terminal Qwen end token are allowed. Extra objects, prose, duplicate
keys, malformed parameters, and output-limit finishes reject the response.
Custom stop strings/tokens and `ignore_eos` are rejected at preflight so they
cannot hide trailing output. Generation remains unconstrained by a grammar.

A rejected response executes no game action. It receives a -2 task-reward
penalty and corrective feedback against the unchanged game state. Three
consecutive rejections end the episode; every sampled attempt counts toward
the 250-decision cap. Original sampled token IDs and log probabilities remain
in training, including all rejected output. The existing invalid-action
advantage ceiling of -5 applies to its entire token span, even if a later retry
wins the game.

Episode metadata records exact token lengths for every sampled action.
Diagnostics deduplicate context segments and report `action_tokens_mean`,
`action_tokens_p50/p90/p95/p99`, and format-invalid, multiple-object,
length-limit, and normal-stop counts/fractions under `rollout/` and
`eval/{dataset}/`. These evaluation metrics do not depend on the training loss
mask. Historical episodes without the metadata do not get fabricated zeros.

The deployed watchdog stops immediately when at least half of a batch's
responses violate format, contain multiple objects, or hit the output limit.
It also stops after three consecutive batches with multiple-object rates at
least 5%, length-limit rates at least 25%, or format-invalid rates at least 10%.
Each qualifying batch must contain at least 32 actions. These checks operate
independently of reward and do not require a completed baseline evaluation.

Validation: 260 local tests passed (8 dependency-related skips), and 54 tests
passed in the pinned Slime image on CPU. Replay rejected all 3,883 responses
from collapsed rollout 179 of `crispy-refresh-69af089563f9`, even assuming a
normal finish. That run remains stopped. No replacement run or GPU validation
has been launched for this change; these checks establish contract behavior,
not improved learning. Evidence:
`reports/single-action-contract-fix-20260930.md`.

## Ten-update smoke completed (September 23)

`inventive-groove-c49694376007` completed all ten updates from
`perfect-adhesive-da14ace5a831/iter_0000399`, saved a complete
`iter_0000009`, and finished final evaluation on its first attempt. The recipe
requested 64 H100s with TP4/PP2/CP4; the inspected head node received eight
H200s. Model, sampling correction, reward, context, and parallelism match the
one-update proof. No production code changed for this test.

On the same 32 greedy held-out seeds, mean reward improved **67.6030 →
88.4506 (+30.8%)**, mean ante **3.1875 → 3.65625**, and invalid actions
**54/2,460 → 27/2,869 turns**. Reward increased on 22 seeds, decreased on
eight, and was unchanged on two. Both evaluations had **0/32 wins** and a
best ante of six. The ten training updates kept trainer/rollout probability
disagreement between **0.00281 and 0.00444**, with gradient norms between
**1.37 and 1.95**. Audits cover every generated action in all ten batches;
none showed the previous one-card collapse.

The 250-decision cap truncated two viable training games in batch six
(zero-based): one at ante seven and one at ante eight, each with only one
invalid action. Neither counts as a win. This is a demonstrated evaluation
limitation to address before interpreting the win rate or promoting a longer
run. Ten stable updates do not establish stability over 200 updates; the
historical collapse occurred later.

The run took about two hours including startup, checkpointing, and evaluation.
Its Modal app is stopped, with zero active GPU containers verified.
Evidence: `reports/unconstrained-smoke-20260923.json`, per-batch trace audits,
384 episode summaries, optimizer metrics, and checkpoint validation.

## Original 27B trainer restored (September 22)

The JEV experiment has been removed. `batro_modal_rl.py` and
`balatro_compare.py` remain the active Qwen3.8-27B training path, using the
existing game reward, checkpoint recovery and trajectory viewer.

The grammar correction below is retained. Launch preflight and episode entry
now reject sampling settings this harness cannot reproduce in training:
grammar constraints, top-p/top-k/min-p truncation, logit bias/processors and
non-default repetition/presence/frequency penalties. Training explicitly uses
temperature 1, top-p 1 and top-k -1; greedy held-out evaluation remains allowed.
Invalid settings fail before checkpoint pinning, receipt creation or GPU
submission. Missing/nonfinite serving log probabilities fail rather than
silently entering a training sample.

The 64-H100 proof `spatial-hot-dog-47bd4700e214` completed one optimizer
update from parent checkpoint 399. Trainer/serving log-probability disagreement
was 0.00433 and gradient norm was 1.951; checkpoint `iter_0000000` passes
distributed shard validation. Its Ray control-plane connection failed after
the save, exhausting all five deduplicated RPC retries before final evaluation.
These results validate one corrected update, not long-term learning stability.

Proof and smoke configs now allow the same two whole-job retries as full runs.
The checkpoint image patch also evaluates restored final weights when the
last checkpoint leaves no optimizer updates to run. Previously that recovery
path could exit without the interrupted final evaluation. Tests cover explicit
evaluation-only runs, final-checkpoint recovery, and normal mid-run recovery.

The interrupted 32-seed final evaluation completed separately as
`knurled-kasseri-e6a606c5b791`, loading proof checkpoint 0 with zero additional
training updates. Its evaluation-only allocation is one node of 8 H100s,
TP4/PP2/CP1 (serving TP2), with the same 49,152-token context and seeds.
The earlier 64-GPU evaluation `covering-backpack-f4fc25b5d62f` was stopped
while queued for capacity. Mean held-out reward was **70.5175 before** and
**70.4757 after** the update. Both evaluations averaged ante 3.1875, reached
ante 6, and had 0/32 wins. This is a correctness proof, not evidence of learning
improvement. All five apps are stopped with no active GPU containers.

Evidence: `reports/unconstrained-gpu-proof-20260922.json`, the training trace
audit, per-game evaluation logs, checkpoint validation, and final app states.
Regression checks: 134 passed, 5 dependency-related skips.

`build_checkpoint_evaluation` keeps a positive scheduler horizon with an empty
training range (`start_rollout_id=num_rollout=1`); Slime's nominal
`num_rollout=0` evaluation mode otherwise trips Megatron's scheduler assertion.
Comparison recipes explicitly package `balatro_compare.py` so imported
recovery launchers can deserialize the held-out dataset on workers.

## Generation/training probability correction (September 21)

`arid-gate-422819ed43e1` was stopped after 60 updates for sustained policy
collapse. Fixed-seed reward rose from 64.61 to 79.46 at update 20, then fell to
60.02, 43.41, 4.50, and -0.18 at updates 30/40/50/60. Every game in the last
eight training batches ended at ante 1. All 124 generated play actions in
batch 59 selected one card. Checkpoints 9 through 59 saved; this was a policy
failure, not a repeat of the checkpoint RPC crash.

The pinned SGLang image applies the regex vocabulary mask before computing
returned log probabilities. The Megatron loss does not replay that mask.
The harness therefore sampled a constrained policy while optimizing an
unconstrained one. Trainer/rollout log-probability disagreement grew from
about 0.003 to 28.43. PPO used recomputed trainer probabilities for its old
policy; its clipping metric stayed zero and did not expose this discrepancy.

Generation now omits the regex and rejects inherited regex/JSON-schema/EBNF
constraints. Prompts, parsing, action validation, repair, and reward penalties
remain in effect. Reintroducing constrained decoding requires matching mask
replay in the trainer, not just changing the old-logprob flag. Local regression
checks pass; the September 22 proof and September 23 smoke results above
provide GPU validation and matched baseline evaluations. The exact contribution of
this bug versus other optimization choices is not yet established by ablation.

Evidence: `reports/arid-gate-collapse-diagnosis-20260921.json`, saved traces,
and the exact pinned implementation in `reports/pinned-probability-source/`.
Do not resume the collapsed checkpoint. Checkpoint 19 is the best saved
held-out result; the original parent 399 is also available for a clean comparison.

## Pipeline communication correction (September 17)

The pinned Slime image drops the `group` argument from all four `P2POp`
constructors in Megatron's `_batched_p2p_ops`. Payload transfers therefore use
the default WORLD group, while shape exchanges use the intended pipeline
subgroup. `nearest-dialogue-25c4f89a4658` timed out in this payload path on
WORLD during its first reference forward pass, before any optimizer update.

`training/patch_pipeline_group.py` restores the subgroup argument, matching
upstream Megatron. Both Balatro credit modes install it at image build; the
patch rejects unfamiliar source and is safe to apply again. It does not
change the topology, checkpoint, context limits, reward, or optimizer settings.

`tests/test_pipeline_group.py` exercises the pinned image's transfer function.
The bounded four-GPU regression in `training/pipeline_group_modal.py` checks
independent pipeline pairs and repeated Slime process-group reloads without
loading a model or playing games. This isolates communication correctness;
it does not measure training progress or establish that every cause of the
original 64-GPU hang has been eliminated.

## Context and action-credit correction (September 16)

The recipe now explicitly sets both `max_position_embeddings` and
`sglang_context_length` to **49,152**, with an **8,192** working-history target.
The previous run inherited `max_position_embeddings=4096`, silently forcing
much more frequent history resets. Local launch validation requires explicit
limits; workers reject a trainer/serving limit below the requested hard budget
before acquiring a game. The 49k hard allowance permits large snapshots;
normal histories still reset around 8k.

Two experiment modes keep the context change separable from credit assignment:

- `--credit-assignment episode` (default): corrected context, existing game-level GRPO.
- `--credit-assignment reward_to_go`: corrected context plus per-action returns.

Reward-to-go records the reward accumulated **before** every generated action.
Each action's remaining return is the final reward minus that prior total,
including terminal bonuses and penalties. A leave-one-game-out baseline uses
the other games on the same seed at the same decision number; ended peers
have zero remaining return. The scale is the standard deviation of complete
game rewards with a floor of one reward unit. This is a variance-reduction
baseline, not a comparison between identical game states or a score oracle.

The new mode does not sum overlapping dashboard checkpoint events. It retains
the current reward components and shared-game loss denominator. Advantages
cover only the original generated action tokens; state-feedback tokens remain
masked out. An earlier success therefore cannot directly reward a later bad
move. Earlier moves still receive credit for future outcomes, so this alone
does not guarantee that a missed flush or a poor purchase gets penalized.

`training/balatro_credit.py` installs the native custom-advantage hook and a
small transport patch for the pinned Slime image: training metadata must survive
data-parallel partitioning and be excluded from numeric metric aggregation.
Unsupported source, missing metadata, token gaps/overlaps and mismatched
context-parallel slices fail explicitly instead of falling back to scalar GRPO.

CPU-only preflight, from the Training Gym Python 3.12 environment:

```sh
uv run python /Users/joyliu/balatrobot/batro_modal_rl.py --num-rollout 1
uv run python /Users/joyliu/balatrobot/batro_modal_rl.py --num-rollout 1 \
  --credit-assignment reward_to_go
```

Neither command launches GPUs. Existing runs keep their deployed code. For a
training experiment, use fresh run IDs and the same initial weights and seeds:
prove one update, then compare roughly ten updates per mode with matched
held-out evaluations. Inspect effective context limits, actual token advantages,
win rate, final ante, and scoring decisions before promoting a longer run.
Preserving an old optimizer is not a requirement for a changed estimator.

CPU integration tests can use Slime sources extracted from the pinned image:

```sh
BALATRO_SLIME_SOURCE=/path/to/extracted/slime uv run --with torch \
  pytest tests/test_action_credit.py tests/test_context_management.py -q
```

Those tests execute the pinned converter, DP transport, native advantage hook,
CP slicing and per-game reducer with one and four context-parallel ranks, using
CPU tensors. They establish signal plumbing and gradient weighting, not model
improvement or a successful distributed GPU update.

## Broad-layover recovery fixes

The local Training Gym checkout now validates every shard and required byte
range referenced by a checkpoint's `.metadata`, both in public checkpoint
listing and automatic Slime recovery. An invalid latest checkpoint triggers
a search for an older valid checkpoint. The launcher pins that exact actor
iteration and keeps reference-model loading independent of it.

Checkpoint saving coordinates volume commits over Gloo. After all node
commits, the coordinator reloads the committed view, validates its shards,
and publishes `training_gym_complete.json`. Legacy checkpoints remain usable
when their metadata and byte ranges validate; the marker alone is never
treated as proof of completeness.

This Balatro recipe sets `NCCL_RAS_ENABLE=0` to avoid the RAS peer-update
subsystem in broad-layover's native crash stack. This is a scoped workaround,
not a claim that the underlying NCCL library defect was repaired. NVIDIA
documents the switch in its [NCCL environment reference](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html#nccl-ras-enable).

`broad-layover` checkpoint 449 has 16 missing shards and another 16 truncated
shards. It cannot be repaired by retrying or by creating a completion marker.
The validator rejects it without modifying its data.

Decision snapshots now include `hand_groups`: visible matching ranks, suit
groups, and example standard straights using current indices. Hidden and
Stone cards do not contribute ranks. These are recognition aids, not score
predictions or action replacements. Joker-specific scoring and hand rules
still matter. Two recorded avoidable losses are permanent fixtures in
`tests/fixtures/broad_layover_decisions.json`.

The new code needs a fresh run/image to take effect. CPU tests and validation
of stored checkpoints do not establish improved model performance or prove
multi-node save/reload. Compare fixed seeds and the recorded decision
fixtures in a short experiment before extending training.

## Bounded game context

The harness now starts a fresh conversation from current game state when the
active conversation would exceed `balatro_segment_tokens` (default **8,192**).
The same game continues. Each conversation is a separate training sample;
all samples share the game's `rollout_id` and final reward. The recipe uses
Slime's per-game loss reduction (`calculate_per_token_loss=False`).

Historical recipes such as perfect-adhesive used per-token weighting (`True`)
and must override it to `False` when paired with this segmented harness.
`_launch_training` validates this requirement before creating a receipt,
pinning a checkpoint, or allocating GPUs. The worker repeats the same check.

`balatro_context_len` remains **49,152**. Actual request limits also account
for serving capacity, training padding and the next action. An essential
snapshot that cannot fit reports `state_budget_exceeded`; it is never silently
truncated. A snapshot larger than the 8k working target can use the available
hard-limit space.

Before the next launch, run `python batro_modal_rl.py --prepare-assets` in the
Training Gym Python 3.12 environment to publish the updated Lua snapshot
fields. Older assets are rejected as `state_schema_mismatch`. The harness
checks trainer support before starting a game. The pinned Training Gym image
was checked on CPU for shared-game loss reduction across unequal segments.

`balatro/context_tokens` now means **peak active conversation size**.
`balatro/episode_archive_tokens` measures accumulated initial-prompt/action/
feedback tokens, excluding repeated reset snapshots; `segment_context_tokens`
measures each training sequence. Game-level metrics are emitted once on the
first segment. Reward events include segment-local token offsets and mappings
for checkpoints spanning several segments.

Each segment has its own snapshot and trajectory messages for dashboard replay.
The first sample also carries `balatro_episode_archive` for full training/debug
serialization. Training Gym's generic dashboard metadata size cap can omit that
large archive; use the individual segments there. Raw training `tokens` and
`response` contain only accepted context; trajectory messages also record the
final state update when it was too large to include in that context.

CPU regression checks:

```sh
uv run pytest tests/test_context_management.py tests/test_training_launch.py \
  tests/test_joker_scoring_state.py tests/test_pack_legality.py -q
```

## Launching and resuming

Run `batro_modal_rl.py` through `./training/dojo.sh python` to use the pinned
Modal Dojo dependencies in **Python 3.12**, matching the remote image. Keep `colocate=True` in the recipe.

Validate a one-rollout checkpoint continuation without allocating GPUs:

```sh
python batro_modal_rl.py --resume-run nullary-bezier-022caf585c3e \
  --resume-iteration 199 --num-rollout 201 --save-interval 1
```

Slime resumes at checkpoint iteration + 1; `--num-rollout` is an exclusive
upper bound, not the number of additional rollouts. From checkpoint 199,
target 200 does no work, 201 performs one rollout, and 400 performs 200.

To submit, add `--launch --launch-record /absolute/path/to/new-launch.json`.
Keep the local command alive until it prints `Modal Dojo run id` and the
receipt says `submitted`, with both a Modal app ID and function-call ID.
After that, Modal Dojo's detached app outlives the local process.

Do not use an auto-restarting supervisor for the submission command. Reuse
the same receipt path if an existing invocation is restarted: its exclusive
creation prevents duplicate submissions. A receipt left at `submitting`
means the outcome is uncertain, not that retrying is safe. Check the launch
log and Modal Dojo run before deliberately choosing a new receipt path.

A dashboard cancellation reason of `stale_pre_active_no_modal_app` means
the run record never acquired a persisted Modal app ID before the stale-run
cleanup timeout. It is not evidence of a GPU initialization failure. Look
at the **local submission log**; remote training may never have been spawned.

CPU-only regression checks:

```sh
uv run pytest tests/test_training_launch.py -q
```

### Checkpoint RPC recovery

For the current Balatro training workflow, the user has authorized launching
replacement runs, continuing to monitor them, diagnosing failures, and trying
repairs (2026-09-21). Keep supervising each run through a terminal result;
reassess held-out performance as well as infrastructure health. A background
log collector alone does not provide agent diagnosis or repair.

The persistent launcher package is `training/.dojo`, created by
`training/setup_dojo.py` with the pinned revision and recovery patch described
above. The source `../modal-dojo` checkout stays untouched. Balatro owns its sandbox lifecycle helpers and pins
the existing H100/TP4/PP2 topology explicitly because current main no longer
provides the branch-only environment helpers or the old model preset defaults.
FlashAttention is pinned explicitly: main's default unfused backend does not
support our CP=4 setup. Local launch validation rejects that incompatible pair.
The patch preserves main's optional `common.pt` support and lazy Modal imports.
It also clears the parent's
fresh-finetune/RNG flags when retrying from the run's own checkpoint, so
optimizer and RNG restoration are not accidentally suppressed. The 200-step
comparison configuration allows two whole-job retries as a fallback; each
retry retains the original 200-step horizon.

The Balatro training image installs `training/patch_checkpoint_rpc.py` and
`training/checkpoint_rpc.py`. Checkpoint saves now retry an unavailable Ray
worker RPC up to five times, with delays of 2, 4, 8, 16, and 30 seconds. The
whole save has a 30-minute deadline.

Each save has one operation ID shared across all workers and retries. A worker
records completion only after its original `save_model` returns, including
checkpoint commit and model offload. If its reply is lost, it acknowledges the
same operation without repeating the save or its distributed collectives. A
request lost before execution can run on retry. Successful peers are not
resubmitted. Workers remain single-threaded with in-place restarts disabled,
so their completion records have the same lifetime as their model state.

This recovery applies to `ActorUnavailableError` at the RPC boundary. Save
exceptions, confirmed worker death, exhausted retries, and deadline expiry
remain failures requiring whole-group recovery. It does not change the
launcher's whole-job retry policy or restart existing runs.

Run the local regression tests:

```sh
uv run --group test pytest tests/test_checkpoint_rpc.py tests/test_pipeline_group.py tests/test_training_launch.py -q
```

The integration check runs two real Ray workers with CPU Gloo collectives in
the pinned Slime image. It injects lost requests/replies at the client boundary,
verifies each save executes once, verifies the next collective still works,
and checks that application errors, worker death, and exhausted retries fail.
Run from the Python 3.12 Modal Dojo checkout used for launches:

```sh
./training/dojo.sh modal run training/checkpoint_rpc_modal.py \
  --out /Users/joyliu/balatrobot/reports/checkpoint-rpc-integration.json
```

### Strong invalid-action penalties

The default `reward_to_go` mode assigns rejected model outputs an advantage
of **−5 or more negative**, applied after game-reward normalization. Large
reward variance and successful harness repairs cannot shrink or reverse that
penalty. More negative task credit is retained. Valid-action credit, displayed
game scores, and the exclusion of positive repair rewards are unchanged.

Both launchers accept `--invalid-action-weight` (default `5`), recorded as
`balatro_invalid_action_weight` in the recipe. This is a magnitude in training
advantage units, not raw game-score points. `normalize_advantages=True` is
rejected at launch and inside the trainer because recentering could weaken or
reverse the penalty. Explicit `--credit-assignment episode` (or comparison
`--mode episode`) selects the legacy control without action-level penalties.

The pinned-trainer CPU integration tests verify token transport, CP=1/4
reduction, and a gradient that lowers rejected-output probability. A replay of
179 recorded invalid decisions changed their median penalty magnitude from
0.058 to 5.0. This verifies the training signal; improved gameplay still needs
a new controlled training test.

## Cloud monitoring (September 25)

`training/cloud_watchdog.py` is deployed as `balatro-training-watchdog` in
`joy-dev`. Its scheduled CPU function runs every two minutes and reads Training
Gym's metadata volume directly, so laptop sleep does not interrupt monitoring.
Only runs explicitly registered in the `balatro-training-watchdog` Modal Dict
are monitored; each registration pins the exact training app ID. Snapshots and
stop decisions are also persisted in `balatro-training-watchdog-evidence`.

Automatic stop rules are tested in `tests/test_watchdog_policy.py`:

- Nonfinite loss, gradient norm, probability-gap metric, or held-out reward.
- Two consecutive held-out evaluations more than 20% below baseline.
- After at least 50 updates, the latest three held-out evaluations are at or
  below baseline.

Read failures never trigger a stop. The watchdog records game-level training
reward, ante, wins, and invalid-action rate without counting context segments
as separate games. It does not change the training recipe or relaunch jobs.
A continue decision is not evidence of learning. Check the Dict's `stop_reason`
when interpreting a terminated run: the training driver's status can report
failure after an intentional watchdog stop. The watchdog does not overwrite
the driver's metadata record.

The active registration and deployment verification for each run are in its
`reports/<run-id>-submission.json` and cloud-watchdog evidence files.
# Action contract and reporting correction (2026-09-28)

The September 25 audit found 51 engine-rejected consumable actions advertised
as legal. `_consumable_available` now shares the joker-capacity gate between
the prompt and Python validator for Judgement, Soul, and Wraith, and retains
Ankh's existing-joker requirement. Recorded failures are regression fixtures;
selling a joker must restore availability. Shop and hand hints also exclude
eternal jokers from sale. The engine remains the final authority on legality.

Context protocol 2 frames continued observations as user turns through the
actual tokenizer chat template, with the same assistant prefix as fresh
snapshots. A truncated assistant answer gets a masked end-of-turn marker.
Generated action IDs/log probabilities are preserved exactly; feedback and
template tokens have zero loss mask. This fixes the format inconsistency;
reduced malformed-output rates still require validation on new trajectories.

`training/balatro_diagnostics.py` reports game-deduplicated reward and ante
percentiles (p10/p25/p50/p75/p90/p95), wins, and invalid-action rates during
training and evaluation. `rollout/raw_reward` is the game mean. The trainer's
old segment average is explicitly named `rollout/segment_weighted_raw_reward`.
Sampling/training gap tail fractions above .01, .05, and .1 supplement the mean.
PPO ratio metrics are named `pre_update_ppo_kl` and `pre_update_pg_clipfrac`:
they do not measure policy movement after the optimizer update.

These changes retain the stronger invalid-action floor, original reward
function, reward-to-go baseline, and exact unmasked sampling distribution.
State-conditioned credit and post-update policy-drift measurement remain
separate experiments rather than unvalidated algorithm changes in this run.
