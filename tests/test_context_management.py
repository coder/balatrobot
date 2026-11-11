"""CPU regressions for resets, exact training prefixes and snapshot fidelity."""

import ast
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


class Tokenizer:
    """Deterministic character tokens; different action IDs test prefix fidelity."""

    eos_token = "<|im_end|>"
    eos_token_id = 0
    unk_token_id = -1

    def __call__(self, text, **kwargs):
        if text == "</think>":
            return {"input_ids": [99000]}
        return {"input_ids": list(text.encode())}

    def apply_chat_template(self, messages, **kwargs):
        result = "".join("<|im_start|>" + m["role"] + "\n" + m["content"] + "<|im_end|>\n" for m in messages)
        suffix = "<|im_start|>assistant\n<think>\n" if kwargs.get("enable_thinking") else "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        return result + (suffix if kwargs.get("add_generation_prompt") else "")


@dataclass
class Action:
    name: str
    arguments: dict


@dataclass
class Sample:
    class Status(Enum):
        COMPLETED = "completed"
        ABORTED = "aborted"

    prompt: str = "TEST-SEED"
    metadata: dict = field(default_factory=dict)
    rollout_id: int | None = None
    index: int = 7
    group_index: int = 1
    status: Any = None


@pytest.fixture
def harness(monkeypatch):
    names = {
        "_compact_state", "_area_items", "_slot_usage", "_purchasable_indices", "_sellable_indices",
        "_consumable_target_bounds", "_consumable_requires_joker", "_consumable_available", "_target_action_help",
        "_action_help", "_turn_prompt", "_chat_prompt", "_feedback_chat_turn", "_action_payload",
        "_state_delta", "_delta_payload", "_selected_blind", "_skip_transition",
        "_environment_feedback", "_balatro_context_limits", "_validate_balatro_trainer",
        "_validate_balatro_loss_config", "_invalid_action_weight",
        "_BalatroContext", "_StateBudgetExceeded", "_SnapshotUnavailable",
        "_segment_reward_events", "generate_balatro_episode", "_progress_value",
        "_transition_reward_parts", "_ante_clear_reward", "_episode_reward_parts",
        "normalize_episode_rewards", "_sample_reward", "_generate_action",
        "_validate_balatro_sampling_params", "_validate_balatro_sampling_config",
        "_validate_balatro_context_config", "_assign_action_advantages", "_finalize_action_credit",
        "generate_balatro_comparison", "_unique_json_keys", "_reject_json_constant",
        "_single_action_object", "_action_object_count", "_action_output_error",
        "_decode_action", "_parse_action", "_action_is_locally_legal",
        "_thinking_budget", "_thinking_action_text", "_balatro_system_prompt", "_sample_action_tokens",
    }
    constants = {
        "BALATRO_SYSTEM_PROMPT", "_DELTA_ANCHORS", "_UNCHANGED", "_ALLOWED_METHODS",
        "ANTE_CHECKPOINT_BONUS", "FINAL_ANTE", "DECISION_CAP_PENALTY",
        "_CONSUMABLE_TARGET_BOUNDS", "_CONSUMABLE_REQUIRES_JOKER",
    }
    tree = ast.parse((ROOT / "batro_modal_rl.py").read_text())
    selected = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in constants:
            selected.append(node)
    ns = dict(Any=Any, json=json, math=math, re=re, time=time, asyncio=asyncio,
              Path=Path, deepcopy=deepcopy, ToolCall=Action)
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), "harness", "exec"), ns)
    for name in ("slime", "slime.utils", "slime.utils.types"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["slime.utils.types"].Sample = Sample
    ns["_log_balatro_event"] = lambda *a, **k: None
    ns["_tokenizer"] = lambda checkpoint: Tokenizer()
    return ns


def game_state(turn=0, *, done=False):
    card = {"id": 19, "key": "S_A", "modifier": {"seal": "GOLD"}, "counters": {"perma_bonus": 30}}
    return {
        "snapshot_version": 1, "state": "GAME_OVER" if done else "SELECTING_HAND",
        "ante_num": 1, "round_num": 1, "money": turn, "won": done,
        "round": {"chips": turn * 10, "hands_left": 4, "discards_left": 3},
        "blinds": {"small": {"type": "SMALL", "status": "CURRENT", "score": 1000}},
        "hand": {"cards": [card]}, "cards": {"count": 1, "cards": [{"key": "C_K"}]},
        "owned_cards": {"cards": [card, {"key": "C_K"}]},
        "jokers": {"cards": [{"id": 70, "key": "j_green_joker", "value": {"effect": "gain Mult"}, "counters": {"mult": turn}}]},
        "used_vouchers": {"v_blank": ""},
        "hands": {"Pair": {"level": 3, "chips": 40, "mult": 4, "played": turn}},
        "tags": [{"key": "tag_double"}], "run_state": {"last_tarot_planet": "c_devil"},
    }


def run_episode(harness, *, decisions=30, target=7000, hard=12288, final_extra="", fail_initial=False, forced_error=False, phases=False, missing_schema=False, responses=None, sampled_tokens=2, thinking_budget=0, generate_override=None):
    seen = []
    env = SimpleNamespace(closed=False, steps=0)
    env._terminal = lambda state: state.get("state") == "GAME_OVER"
    initial = game_state()
    if missing_schema:
        initial.pop("snapshot_version")
    if fail_initial:
        initial["jokers"]["cards"][0]["value"]["effect"] = "X" * hard
    env.start = lambda seed: deepcopy(initial)

    def step(action):
        env.steps += 1
        state = game_state(env.steps, done=env.steps == decisions)
        if phases and env.steps < decisions:
            state["state"] = ["SELECTING_HAND", "SHOP", "SMODS_BOOSTER_OPENED", "BLIND_SELECT"][env.steps % 4]
            if state["state"] == "BLIND_SELECT":
                state["blinds"]["small"]["status"] = "SELECT"
        if env.steps == decisions:
            state["jokers"]["cards"][0]["value"]["effect"] += final_extra
        if forced_error:
            return SimpleNamespace(observation=SimpleNamespace(metadata={"state": state}, is_error=True, text="bad action"))
        return SimpleNamespace(observation=SimpleNamespace(metadata={"state": state}, is_error=False), done=env.steps == decisions)

    env.step = step
    env.close = lambda: setattr(env, "closed", True)
    harness["_get_env_pool"] = lambda: SimpleNamespace(acquire=lambda seed: env)
    harness["_fallback_action"] = lambda state: Action("play", {"cards": [0]})

    async def generate(args, params, ids, phase):
        # IDs intentionally differ from encoding the response text. Training
        # must use the original IDs, not re-tokenize the pretty transcript.
        action_ids = [100000 + len(seen)] * (sampled_tokens - 1) + [99999]
        if thinking_budget:
            action_ids[-3] = 99000
        seen.append((list(ids), action_ids))
        defaults = {
            "SELECTING_HAND": {"method": "play", "params": {"cards": [0]}},
            "SHOP": {"method": "next_round", "params": {}},
            "SMODS_BOOSTER_OPENED": {"method": "pack", "params": {"skip": True}},
            "BLIND_SELECT": {"method": "select", "params": {}},
        }
        if responses:
            text, finish = responses[min(len(seen)-1, len(responses)-1)]
        else:
            text, finish = json.dumps(defaults[phase], separators=(",", ":")), "stop"
        return action_ids, text, finish, [-0.2] * (sampled_tokens - 1) + [-0.3], [1] * sampled_tokens

    harness["_generate_action"] = generate_override or generate
    args = SimpleNamespace(balatro_max_decisions=decisions + 2, balatro_context_len=hard,
                           balatro_segment_tokens=target, balatro_capture_screenshot=False,
                           hf_checkpoint="unused", balatro_thinking_budget=thinking_budget)
    samples = asyncio.run(harness["generate_balatro_episode"](args, Sample(), {}, evaluation=True))
    return samples, seen, env


def test_rebases_keep_game_running_and_train_every_action_with_its_exact_prefix(harness):
    samples, seen, env = run_episode(harness)
    assert env.closed and env.steps == 30
    assert 1 < len(samples) < 30
    assert {s.rollout_id for s in samples} == {samples[0].rollout_id}
    assert {s.reward for s in samples} == {samples[0].reward}
    assert {s.metadata["exit_status"] for s in samples} == {"won"}
    reconstructed = []
    for index, sample in enumerate(samples):
        assert sample.metadata["segment_id"] == index
        assert len(sample.tokens) + 128 <= 12288
        assert len(sample.loss_mask) == sample.response_length == len(sample.rollout_log_probs)
        assert len(sample.metadata["trajectory_messages"]) <= 128
        offset = len(sample.tokens) - sample.response_length
        for token in range(sample.response_length):
            if sample.loss_mask[token] and (token == 0 or not sample.loss_mask[token - 1]):
                reconstructed.append((sample.tokens[:offset + token], sample.tokens[offset + token:offset + token + 2]))
        # Snapshots stand alone and retain changes made before a reset.
        assert '"perma_bonus":30' in sample.prompt and '"seal":"GOLD"' in sample.prompt
        assert '"owned_vouchers"' in sample.prompt and '"last_tarot_planet":"c_devil"' in sample.prompt
    assert reconstructed == seen
    assert sum(sum(s.loss_mask) for s in samples) == 60
    assert sum("balatro/won" in s.metadata for s in samples) == 1
    assert sum("balatro_episode_archive" in s.metadata for s in samples) == 1
    events = [e for s in samples for e in s.metadata["reward_events"]]
    assert len(events) == 1 and events[0]["label"] == "WON"
    assert len(events[0]["segment_spans"]) > 1


def test_oversized_terminal_feedback_does_not_turn_a_win_into_context_cap(harness):
    samples, seen, env = run_episode(harness, decisions=2, final_extra="X" * 20000)
    assert len(seen) == 2 and env.closed
    assert all(s.metadata["exit_status"] == "won" for s in samples)
    assert all(len(s.tokens) < 12288 for s in samples)
    assert "X" * 20000 in samples[0].metadata["balatro_episode_archive"]["response"]


def test_oversized_initial_snapshot_never_calls_model_and_closes_game(harness):
    sample, seen, env = run_episode(harness, fail_initial=True)
    assert not seen and env.closed and env.steps == 0
    assert sample.status == Sample.Status.ABORTED
    assert sample.metadata["exit_status"] == "state_budget_exceeded"


def test_old_assets_are_rejected_before_generating_with_incomplete_snapshots(harness):
    sample, seen, env = run_episode(harness, missing_schema=True)
    assert not seen and env.closed
    assert sample.metadata["exit_status"] == "state_schema_mismatch"


def test_full_length_game_survives_history_larger_than_the_old_context_cap(harness):
    samples, seen, env = run_episode(harness, decisions=250, phases=True)
    assert len(seen) == env.steps == 250 and env.closed
    assert samples[0].metadata["balatro/episode_archive_tokens"] > 49152
    assert samples[0].metadata["balatro/context_tokens"] < 12288
    assert all(s.metadata["exit_status"] == "won" for s in samples)
    assert sum(sum(s.loss_mask) for s in samples) == 500
    assert all(len(prefix) + 224 <= 12288 for prefix, _ in seen)


def test_rpc_recovery_error_is_archived_without_dropping_generated_action(harness):
    samples, seen, env = run_episode(harness, forced_error=True)
    assert len(seen) == 1 and env.closed
    assert samples[0].metadata["exit_status"] == "rpc_error"
    assert sum(samples[0].loss_mask) == 2
    assert "bad action" in samples[0].metadata["balatro_episode_archive"]["response"]


def test_oversized_snapshot_can_exceed_soft_target_but_not_hard_cap(harness):
    context = harness["_BalatroContext"](Tokenizer(), 2048, 512)
    context.begin("X" * 1000, "snapshot", 1)
    assert len(context.input_ids()) == 1000
    context.add_action([1], "a", [-0.1], turn=1, archive_start=0)
    context.add_feedback("f", [2])
    assert context.needs_reset
    with pytest.raises(RuntimeError, match="fresh snapshot"):
        context.input_ids()


@pytest.mark.parametrize("ended", [False, True])
def test_continuations_use_fresh_assistant_framing_without_retokenizing_actions(harness, ended):
    tokenizer = Tokenizer()
    context = harness["_BalatroContext"](tokenizer, 12288, 10000)
    context.begin(harness["_chat_prompt"](tokenizer, "snapshot"), "snapshot", 1)
    action_ids = [123456, tokenizer.eos_token_id] if ended else [123456, 654321]
    context.add_action(action_ids, "sampled action", [-.2, -.1], turn=1, archive_start=0)
    exact_prefix = context.input_ids().copy()
    context.add_feedback("new observation", [99])
    framed = harness["_feedback_chat_turn"](tokenizer, "new observation", assistant_ended=ended)
    suffix = tokenizer(framed)["input_ids"]
    assert context.input_ids() == exact_prefix + suffix
    assert context.current["loss_mask"] == [1, 1] + [0] * len(suffix)
    assert context.current["log_probs"] == [-.2, -.1] + [0.] * len(suffix)
    assert framed.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert framed.startswith(("" if ended else tokenizer.eos_token) + "\n<|im_start|>user\n")
    assert "system" not in framed


def test_budget_counts_output_margin_and_training_padding(harness):
    args = SimpleNamespace(balatro_context_len=49152, balatro_segment_tokens=8192,
                           sglang_context_length=49000, tensor_model_parallel_size=4,
                           context_parallel_size=4, max_tokens_per_gpu=12288)
    with pytest.raises(ValueError, match="permit only 47104"):
        harness["_balatro_context_limits"](args)
    args.sglang_context_length = 49152
    args.max_position_embeddings = 49152
    assert harness["_balatro_context_limits"](args) == (49152, 8192)
    context = harness["_BalatroContext"](Tokenizer(), 512, 512)
    context.begin("a" * (512 - 224), "snapshot", 1)
    with pytest.raises(harness["_StateBudgetExceeded"]):
        context.begin("a" * (512 - 223), "snapshot", 1)


def test_inherited_4k_position_limit_fails_before_game_acquisition(harness):
    args = SimpleNamespace(balatro_context_len=49152, balatro_segment_tokens=8192,
                           sglang_context_length=49152, max_position_embeddings=4096,
                           tensor_model_parallel_size=4, context_parallel_size=4,
                           max_tokens_per_gpu=12288)
    with pytest.raises(ValueError, match="permit only 4096"):
        harness["_balatro_context_limits"](args)


def test_launch_requires_explicit_serving_and_trainer_context(harness):
    recipe = SimpleNamespace(context_parallel_size=4, tensor_model_parallel_size=4,
                             max_tokens_per_gpu=12288, extra_config={})
    with pytest.raises(ValueError, match="explicit max_position_embeddings"):
        harness["_validate_balatro_context_config"](recipe)
    recipe.extra_config = {"max_position_embeddings": 49152, "sglang_context_length": 49152}
    assert harness["_validate_balatro_context_config"](recipe) == (49152, 8192)
    recipe.extra_config["sglang_context_length"] = 4096
    with pytest.raises(ValueError, match="permit only 4096"):
        harness["_validate_balatro_context_config"](recipe)


def test_context_parallel_launch_rejects_unfused_attention(harness):
    recipe = SimpleNamespace(context_parallel_size=4, tensor_model_parallel_size=4,
                             max_tokens_per_gpu=12288, attention_backend="unfused",
                             extra_config={"max_position_embeddings": 49152,
                                           "sglang_context_length": 49152})
    validate = harness["_validate_balatro_context_config"]
    with pytest.raises(ValueError, match="Unfused attention does not support"):
        validate(recipe)
    recipe.attention_backend = "flash"
    assert validate(recipe) == (49152, 8192)
    recipe.extra_config["attention_backend"] = "unfused"
    with pytest.raises(ValueError, match="Unfused attention does not support"):
        validate(recipe)


def test_action_returns_include_terminal_bonus_and_exclude_past_rewards(harness):
    samples, seen, _ = run_episode(harness, decisions=30)
    actions = [a for s in samples for a in s.metadata["action_credit"]]
    assert len(actions) == len(seen) == 30
    assert actions[0]["return_to_go"] == pytest.approx(samples[0].reward)
    # The fixture earns 0.01 progress per move before the terminal win.
    assert actions[1]["return_to_go"] == pytest.approx(samples[0].reward - .01)
    assert actions[-1]["return_to_go"] > 0  # includes terminal/win bonus
    assert all(a["token_end"] - a["token_start"] == 2 for a in actions)


def test_comparison_eval_reports_one_game_but_training_keeps_exact_segments(harness):
    segments, _, _ = run_episode(harness)
    async def generate(*args, **kwargs):
        return deepcopy(segments)
    harness["generate_balatro_episode"] = generate
    args = SimpleNamespace(hf_checkpoint="unused")
    train = asyncio.run(harness["generate_balatro_comparison"](args, Sample(), {}, evaluation=False))
    assert len(train) == len(segments)
    assert train[0].tokens == segments[0].tokens
    evaluated = asyncio.run(harness["generate_balatro_comparison"](args, Sample(), {}, evaluation=True))
    assert not isinstance(evaluated, list)
    assert evaluated.reward == segments[0].reward
    assert evaluated.response == segments[0].metadata["balatro_episode_archive"]["response"]
    assert len(evaluated.loss_mask) == evaluated.response_length
    assert sum(evaluated.loss_mask) == 0


def test_startup_connection_failure_retries_before_any_policy_action(harness, monkeypatch):
    run_episode(harness, decisions=2)  # install the normal game/tokenizer fixtures
    healthy = harness["_get_env_pool"]().acquire("unused")
    healthy.steps = 0
    healthy.closed = False
    failed = SimpleNamespace(closed=False)
    failed.start = lambda seed: (_ for _ in ()).throw(ConnectionError("Connection refused"))
    failed.close = lambda: setattr(failed, "closed", True)
    acquired = []
    def acquire(seed):
        acquired.append(seed)
        return failed if len(acquired) == 1 else healthy
    harness["_get_env_pool"] = lambda: SimpleNamespace(acquire=acquire)
    async def no_sleep(seconds):
        pass
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    args = SimpleNamespace(hf_checkpoint="unused", balatro_capture_screenshot=False)
    result = asyncio.run(harness["generate_balatro_comparison"](args, Sample(prompt="RETRY-SEED"), {}, evaluation=True))
    assert acquired == ["RETRY-SEED", "RETRY-SEED"]
    assert failed.closed and healthy.closed
    assert healthy.steps == 2
    assert math.isfinite(result.reward)


def test_persistent_startup_failure_reports_seed_and_closes_every_sandbox(harness, monkeypatch):
    environments = []
    def acquire(seed):
        env = SimpleNamespace(closed=False)
        env.start = lambda seed: (_ for _ in ()).throw(ConnectionError("Connection refused"))
        env.close = lambda: setattr(env, "closed", True)
        environments.append(env)
        return env
    harness["_get_env_pool"] = lambda: SimpleNamespace(acquire=acquire)
    async def no_sleep(seconds):
        pass
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    args = SimpleNamespace(hf_checkpoint="unused", balatro_capture_screenshot=False)
    with pytest.raises(RuntimeError, match="RETRY-SEED after 3 attempts: Connection refused"):
        asyncio.run(harness["generate_balatro_comparison"](args, Sample(prompt="RETRY-SEED"), {}, evaluation=True))
    assert len(environments) == 3
    assert all(env.closed for env in environments)


@pytest.mark.parametrize("reward", [None, float("nan"), float("inf")])
def test_eval_rejects_unscored_results_before_trainer_aggregation(harness, reward):
    async def generate(*args, **kwargs):
        return SimpleNamespace(reward=reward, status=Sample.Status.ABORTED)
    harness["generate_balatro_episode"] = generate
    with pytest.raises(RuntimeError, match="incomplete/unscored episode for TEST-SEED"):
        asyncio.run(harness["generate_balatro_comparison"](SimpleNamespace(), Sample(), {}, evaluation=True))


def credit_sample(game, reward, returns, *, turn_start=1):
    return SimpleNamespace(rollout_id=game, reward=reward, train_metadata=None,
                           metadata={"balatro": {"seed_group": "same"}, "policy_episode_reward": reward, "action_credit": [
                               {"turn": turn_start + i, "token_start": 3*i,
                                "token_end": 3*i + 2, "return_to_go": value, "intervention_penalty": 0.0}
                               for i, value in enumerate(returns)
                           ]})


def test_later_bad_decision_does_not_inherit_earlier_success(harness):
    # A earned 9 then lost 1; B earned 0 then 2. Whole-game GRPO prefers A
    # on both moves. Return-to-go prefers B on the second move.
    samples = [credit_sample(1, 8, [8, -1]), credit_sample(2, 2, [2, 2])]
    args = SimpleNamespace(balatro_credit_assignment="reward_to_go")
    raw, episode_adv = harness["normalize_episode_rewards"](args, samples)
    assert raw == [8, 2] and episode_adv[0] > 0
    assert [a["advantage"] for a in samples[0].train_metadata["balatro_action_advantages"]] == [2, -1]
    assert [a["advantage"] for a in samples[1].train_metadata["balatro_action_advantages"]] == [-2, 1]


def test_intervention_progress_is_excluded_but_later_model_rewards_remain(harness):
    # Model earns 10, a repair earns 14 minus its 2-point penalty, then the
    # model earns a 100-point terminal bonus. The task score remains 122.
    actions = [{"reward_before": 0, "invalid_events": 0},
               {"reward_before": 10, "invalid_events": 1},
               {"reward_before": 22, "invalid_events": 0}]
    total = harness["_finalize_action_credit"]([{"actions": actions[:2]}, {"actions": actions[2:]}], 122)
    assert total == 108
    assert [a["policy_return_to_go"] for a in actions] == [108, 98, 100]
    assert [a["intervention_penalty"] for a in actions] == [0, -2, 0]


def test_rejected_actions_never_execute_repairs_or_fallbacks(harness):
    harness["_parse_action"] = lambda text, state: None
    harness["_repair_action"] = lambda *a: pytest.fail("Rejected output must not be repaired")
    samples, seen, env = run_episode(harness, decisions=2)
    assert env.closed and env.steps == 0 and len(seen) == 3
    assert samples[0].reward == -6
    assert samples[0].metadata["balatro"]["terminal_reason"] == "invalid_action_limit"
    actions = [a for s in samples for a in s.metadata["action_credit"]]
    assert [a["return_to_go"] for a in actions] == [-6, -4, -2]
    assert [a["intervention_penalty"] for a in actions] == [-2, -2, -2]
    assert sum(sum(s.loss_mask) for s in samples) == 6


def test_rejected_action_stays_negative_even_when_peer_returns_are_worse(harness):
    samples = [credit_sample(1, 108, [108, 98, 100]),
               credit_sample(2, -100, [-100, -100, -100])]
    samples[0].metadata["action_credit"][1]["intervention_penalty"] = -2
    harness["normalize_episode_rewards"](SimpleNamespace(balatro_credit_assignment="reward_to_go"), samples)
    spans = samples[0].train_metadata["balatro_action_advantages"]
    assert spans[0]["advantage"] > 0 and spans[2]["advantage"] > 0
    assert spans[1]["advantage"] == -5.0


@pytest.mark.parametrize("spread", [0, 1, 100, 1_000_000])
def test_invalid_penalty_does_not_shrink_with_reward_spread(harness, spread):
    samples = [credit_sample(1, spread, [spread]), credit_sample(2, -spread, [-spread])]
    samples[0].metadata["action_credit"][0]["intervention_penalty"] = -2
    raw, _ = harness["normalize_episode_rewards"](SimpleNamespace(balatro_credit_assignment="reward_to_go"), samples)
    assert raw == [spread, -spread]
    assert samples[0].train_metadata["balatro_action_advantages"][0]["advantage"] == -5


def test_invalid_penalty_preserves_larger_negative_future_credit(harness):
    samples = [credit_sample(1, 100, [100, -50]), credit_sample(2, 100, [100, 50])]
    samples[0].metadata["action_credit"][1]["intervention_penalty"] = -2
    harness["normalize_episode_rewards"](SimpleNamespace(balatro_credit_assignment="reward_to_go"), samples)
    assert samples[0].train_metadata["balatro_action_advantages"][1]["advantage"] == -100


def test_invalid_penalty_weight_is_configurable_without_changing_valid_credit(harness):
    samples = [credit_sample(1, 8, [8, -1]), credit_sample(2, 2, [2, 2])]
    samples[0].metadata["action_credit"][1]["intervention_penalty"] = -2
    args = SimpleNamespace(balatro_credit_assignment="reward_to_go", balatro_invalid_action_weight=10)
    harness["normalize_episode_rewards"](args, samples)
    assert [a["advantage"] for a in samples[0].train_metadata["balatro_action_advantages"]] == [2, -10]
    assert [a["advantage"] for a in samples[1].train_metadata["balatro_action_advantages"]] == [-2, 1]


@pytest.mark.parametrize("weight", [0, -1, float("nan"), float("inf"), None, True, "bad"])
def test_invalid_penalty_configuration_fails_closed(harness, weight):
    with pytest.raises(ValueError, match="finite and positive"):
        harness["_invalid_action_weight"](SimpleNamespace(balatro_invalid_action_weight=weight))


def test_advantage_recentering_rejected_before_launch(harness):
    args = SimpleNamespace(calculate_per_token_loss=False, extra_config={
        "balatro_credit_assignment": "reward_to_go",
        "custom_advantage_function_path": "balatro_credit.compute_advantages",
        "normalize_advantages": True,
    })
    with pytest.raises(ValueError, match="normalize_advantages=False"):
        harness["_validate_balatro_loss_config"](args)


@pytest.mark.parametrize("penalty", [1, float("nan"), float("inf")])
def test_intervention_penalties_fail_closed(harness, penalty):
    samples = [credit_sample(1, 8, [8]), credit_sample(2, 2, [2])]
    samples[0].metadata["action_credit"][0]["intervention_penalty"] = penalty
    with pytest.raises(ValueError, match="intervention penalty"):
        harness["normalize_episode_rewards"](SimpleNamespace(balatro_credit_assignment="reward_to_go"), samples)


def test_action_credit_is_invariant_to_segmentation_and_sample_order(harness):
    args = SimpleNamespace(balatro_credit_assignment="reward_to_go")
    whole = [credit_sample(1, 8, [8, 4, -1]), credit_sample(2, 2, [2, 2])]
    split = [credit_sample(2, 2, [2], turn_start=2), credit_sample(1, 8, [4, -1], turn_start=2),
             credit_sample(1, 8, [8]), credit_sample(2, 2, [2])]
    for samples in (whole, split):
        for sample in samples:
            for action in sample.metadata["action_credit"]:
                if sample.rollout_id == 1 and action["turn"] == 3:
                    action["intervention_penalty"] = -2
        harness["normalize_episode_rewards"](args, samples)
    def by_turn(samples):
        return {(s.rollout_id, a["turn"]): v["advantage"] for s in samples
                for a, v in zip(s.metadata["action_credit"], s.train_metadata["balatro_action_advantages"])}
    assert by_turn(split) == by_turn(whole)


@pytest.mark.parametrize("case", ["missing", "duplicate", "gap", "nonfinite", "singleton"])
def test_invalid_action_credit_fails_closed(harness, case):
    samples = [credit_sample(1, 8, [8, -1]), credit_sample(2, 2, [2, 2])]
    if case == "missing":
        samples[0].metadata.pop("action_credit")
    if case == "duplicate":
        samples.append(deepcopy(samples[0]))
    if case == "gap":
        samples[0].metadata["action_credit"][1]["turn"] = 3
    if case == "nonfinite":
        samples[0].metadata["action_credit"][0]["return_to_go"] = math.nan
    if case == "singleton":
        samples = samples[:1]
    with pytest.raises(ValueError):
        harness["normalize_episode_rewards"](SimpleNamespace(balatro_credit_assignment="reward_to_go"), samples)


def test_generation_sends_bounded_ids_and_retains_serving_log_probabilities(harness, monkeypatch):
    http = ModuleType("slime.utils.http_utils")
    requests = []

    async def post(url, payload):
        requests.append(payload)
        return {"text": "action", "meta_info": {
            "finish_reason": {"type": "stop"},
            "output_token_logprobs": [[-0.25, 101, None], [-0.5, 102, None]],
        }}

    http.post = post
    monkeypatch.setitem(sys.modules, "slime.utils.http_utils", http)
    args = SimpleNamespace(balatro_context_len=512, balatro_segment_tokens=512,
                           sglang_router_ip="unused", sglang_router_port=1234)
    output = asyncio.run(harness["_generate_action"](args, {"max_new_tokens": 999}, [1] * 288, "hand"))
    assert output == ([101, 102], "action", "stop", [-0.25, -0.5], [1, 1])
    assert requests[0]["sampling_params"]["max_new_tokens"] == 96
    assert not any(requests[0]["sampling_params"].get(key) is not None
                   for key in ("regex", "json_schema", "ebnf"))
    assert len(requests[0]["input_ids"]) + 96 + 128 == 512
    assert asyncio.run(harness["_generate_action"](args, {}, [1] * 512, "hand"))[1] is None
    assert len(requests) == 1


@pytest.mark.parametrize("constraint", ["regex", "json_schema", "ebnf"])
def test_generation_rejects_constraints_the_trainer_cannot_replay(harness, monkeypatch, constraint):
    http = ModuleType("slime.utils.http_utils")
    async def post(*args, **kwargs):
        pytest.fail("A probability-mismatched rollout must not be submitted")
    http.post = post
    monkeypatch.setitem(sys.modules, "slime.utils.http_utils", http)
    args = SimpleNamespace(balatro_context_len=512, balatro_segment_tokens=512)
    with pytest.raises(ValueError, match="trainer does not replay grammar masks"):
        asyncio.run(harness["_generate_action"](args, {constraint: "constraint"}, [1], "hand"))


def test_trainer_refuses_segment_weighting_that_counts_long_games_more(harness):
    with pytest.raises(ValueError, match="per-game mean"):
        harness["_validate_balatro_trainer"](SimpleNamespace(calculate_per_token_loss=True), Sample)


@pytest.mark.parametrize("params", [
    {"temperature": 0.0}, {"temperature": 0.7}, {"temperature": float("nan")},
    {"top_p": 0.9}, {"top_k": 50}, {"min_p": 0.1},
    {"presence_penalty": 1.0}, {"frequency_penalty": 1.0},
    {"repetition_penalty": 1.1}, {"logit_bias": {"123": 10}},
    {"custom_logit_processor": "processor"}, {"regex": "json-only"},
])
def test_mismatched_training_sampling_rejected_before_game_start(harness, params):
    # Empty args would fail later trainer/context validation; this must reject
    # the distribution mismatch first, before acquiring any environment.
    with pytest.raises(ValueError, match="Balatro training"):
        asyncio.run(harness["generate_balatro_episode"](SimpleNamespace(), Sample(), params))


def test_greedy_evaluation_is_allowed_but_grammar_still_rejected(harness):
    validate = harness["_validate_balatro_sampling_params"]
    validate({"temperature": 0.0, "top_p": 1.0, "top_k": -1}, evaluation=True)
    with pytest.raises(ValueError, match="grammar masks"):
        validate({"temperature": 0.0, "regex": "json-only"}, evaluation=True)


@pytest.mark.parametrize("pairs", [[], [[float("nan"), 101, None]], [[float("inf"), 101, None]]])
def test_missing_or_nonfinite_serving_probabilities_fail(harness, monkeypatch, pairs):
    http = ModuleType("slime.utils.http_utils")
    async def post(*args, **kwargs):
        return {"text": "action", "meta_info": {
            "finish_reason": {"type": "stop"}, "output_token_logprobs": pairs,
        }}
    http.post = post
    monkeypatch.setitem(sys.modules, "slime.utils.http_utils", http)
    args = SimpleNamespace(balatro_context_len=512, balatro_segment_tokens=512,
                           sglang_router_ip="unused", sglang_router_port=1234)
    with pytest.raises(RuntimeError, match="token log probabilities"):
        asyncio.run(harness["_generate_action"](args, {}, [1], "hand"))


def test_checkpoint_crossing_reset_has_one_reward_and_local_token_offsets(harness):
    segments = [
        {"actions": [{"token_start": 0, "token_end": 2, "episode_token_start": 0, "episode_token_end": 2}]},
        {"actions": [{"token_start": 0, "token_end": 3, "episode_token_start": 30, "episode_token_end": 33}]},
    ]
    result = harness["_segment_reward_events"]([{"token_start": 0, "token_end": 40, "reward": 8}], segments)
    assert result[0] == [] and len(result[1]) == 1
    assert result[1][0]["token_start"] == 0 and result[1][0]["token_end"] == 3
    assert result[1][0]["episode_token_end"] == 40
    assert result[1][0]["segment_spans"] == [
        {"segment_id": 0, "token_start": 0, "token_end": 2},
        {"segment_id": 1, "token_start": 0, "token_end": 3},
    ]


def test_snapshot_keeps_inventory_and_zero_counters_in_every_phase(harness):
    state = game_state(0)
    state["state"] = "SHOP"
    state["jokers"]["cards"][0]["state"] = {"debuff": True}
    before = deepcopy(state)
    compact = json.loads(harness["_compact_state"](state, limit=1))
    assert compact["owned_vouchers"] == [{"id": "v_blank", "effect": ""}]
    assert compact["jokers"]["items"][0]["counters"]["mult"] == 0
    assert compact["jokers"]["items"][0]["debuff"] is True
    assert compact["hand_values"]["Pair"] == [3, 40, 4]
    assert "owned_deck" in compact and "deck" in compact and "truncated" not in compact
    assert state == before


def test_hidden_card_cannot_be_identified_by_key_instance_or_effect(harness):
    state = game_state()
    state["hand"]["cards"][0]["state"] = {"hidden": True}
    compact = json.loads(harness["_compact_state"](state))
    assert compact["hand"] == [{"hidden": True}]


def test_hidden_jokers_keep_known_composition_without_slot_mapping(harness):
    state = game_state()
    visible = deepcopy(state["jokers"]["cards"][0])
    state["jokers"]["cards"][0]["state"] = {"hidden": True}
    state["joker_inventory"] = {"cards": [{**visible, "id": 0}]}
    compact = json.loads(harness["_compact_state"](state))
    assert compact["jokers"]["items"] == [{"hidden": True}]
    assert compact["joker_inventory"][0]["id"] == "j_green_joker"
    assert "instance" not in compact["joker_inventory"][0]


def test_delta_never_silently_keeps_stale_shop_fields(harness):
    previous = {"phase": "shop", "shop": [{"id": "j_joker"}], "packs": [1], "reroll_cost": 5, "money": 4}
    current = {"phase": "BLIND_SELECT", "money": 4}
    delta = harness["_delta_payload"](previous, current)
    assert delta["shop"] is None and delta["packs"] is None and delta["reroll_cost"] is None


def test_segment_count_does_not_change_game_advantage(harness):
    def sample(game, reward):
        return SimpleNamespace(rollout_id=game, reward=reward, metadata={"balatro": {"seed_group": "same"}})
    original = [sample(1, 10), sample(2, 20)]
    split = [sample(1, 10)] * 3 + [sample(2, 20)] * 7
    _, expected = harness["normalize_episode_rewards"](None, original)
    _, actual = harness["normalize_episode_rewards"](None, split)
    assert actual == [expected[0]] * 3 + [expected[1]] * 7


def test_real_lua_snapshot_preserves_public_mechanics_without_mutation():
    lua = shutil.which("luajit")
    if not lua:
        pytest.skip("LuaJIT required")
    script = r'''
local gs = dofile("src/lua/utils/gamestate.lua")
function pseudorandom() error("must not advance RNG") end
local function card(id, key, ability)
  return {sort_id=id, config={card_key=key,card={suit="Spades",value="Ace"}},
    ability=ability, seal="Gold", generate_UIBox_ability_table=function() return {main={}} end}
end
local a=card(10,"S_A",{perma_bonus=30,played_this_ante=true,forced_selection=true,private_seed=999})
local b=card(11,"S_A",{perma_bonus=0})
G={STATE=1,STATES={SELECTING_HAND=1},playing_cards={a,b},
  hand={cards={a},config={card_count=1,card_limit=8}},
  deck={cards={b},config={card_count=1,card_limit=52}},
  GAME={current_round={hands_played=2,discards_used=1},last_tarot_planet="c_devil",
    used_vouchers={v_blank=true},tags={{key="tag_double",ability={orbital_hand="Pair",private_seed=123}}},
    blind={only_hand="Pair",hands={Pair=true,Flush=false}},pseudorandom={seed="SECRET"}}}
local first=gs.get_gamestate()
assert(first.snapshot_version==1)
assert(first.cards.count==1 and first.owned_cards.count==2)
assert(first.hand.cards[1].id==10 and first.hand.cards[1].counters.perma_bonus==30)
assert(first.hand.cards[1].counters.played_this_ante and first.hand.cards[1].counters.forced_selection)
assert(first.hand.cards[1].counters.private_seed==nil)
assert(first.owned_cards.cards[1].id==0 and first.owned_cards.cards[1].state.hidden==nil)
assert(first.run_state.last_tarot_planet=="c_devil" and first.run_state.round.hands_played==2)
assert(first.blind_state.only_hand=="Pair" and first.blind_state.played_hands.Pair)
assert(first.tags[1].key=="tag_double" and first.tags[1].ability.private_seed==nil)
assert(first.used_vouchers.v_blank=="")
a.ability.perma_bonus=60
assert(first.hand.cards[1].counters.perma_bonus==30)
assert(gs.get_gamestate().hand.cards[1].counters.perma_bonus==60)
assert(a.sort_id==10 and a.seal=="Gold")
local joker={sort_id=99,config={center_key="j_green_joker"},ability={set="Joker",mult=7},
  facing="back",generate_UIBox_ability_table=function() return {main={}} end}
G.jokers={cards={joker},config={card_count=1,card_limit=5}}
local hidden=gs.get_gamestate()
assert(hidden.jokers.cards[1].state.hidden)
assert(hidden.joker_inventory.cards[1].id==0 and hidden.joker_inventory.cards[1].key=="j_green_joker")
assert(hidden.joker_inventory.cards[1].state.hidden==nil)
print("ok")
'''
    result = subprocess.run([lua, "-"], input=script, cwd=ROOT, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "ok"


@pytest.mark.parametrize("cp_size", [1, 4])
def test_pinned_trainer_reducer_weights_unequal_segments_across_microbatches(harness, monkeypatch, cp_size):
    """Optional integration with sources read from the actual pinned image."""
    source_dir = os.environ.get("BALATRO_SLIME_SOURCE")
    if not source_dir:
        pytest.skip("Set BALATRO_SLIME_SOURCE to the pinned image's extracted slime source")
    torch = pytest.importorskip("torch")
    path = Path(source_dir) / "backends/megatron_utils/cp_utils.py"
    tree = ast.parse(path.read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"get_sum_of_sample_mean", "get_logits_and_tokens_offset_with_cp"}]
    mpu = SimpleNamespace(get_context_parallel_world_size=lambda: cp_size)
    from collections.abc import Callable
    ns = {"torch": torch, "mpu": mpu, "Callable": Callable}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), ns)
    reduce = ns["get_sum_of_sample_mean"]
    import inspect
    monkeypatch.setattr(inspect, "getfile", lambda cls: str(Path(source_dir) / "utils/types.py"))
    harness["_validate_balatro_trainer"](SimpleNamespace(calculate_per_token_loss=False), Sample)

    def contribution(values, denominator):
        x = torch.tensor(values)
        length = len(values)
        total = length + 4
        result = torch.tensor(0.)
        for rank in range(cp_size):
            mpu.get_context_parallel_rank = lambda: rank
            local = x
            if cp_size > 1:
                *_, offsets = ns["get_logits_and_tokens_offset_with_cp"](total, length)
                local = torch.cat([x[lo - 4:hi - 4] for lo, hi in offsets])
            result = result + reduce([total], [length], [torch.ones(length)], [torch.tensor(float(denominator))], False)(local)
        return result

    # Two games: A losses [1,3,5,7], B losses [10,20]. Split A into
    # unequal segments in different microbatches, keeping its full denominator.
    a_first = contribution([1.], 4)
    a_later = contribution([3., 5., 7.], 4)
    b = contribution([10., 20.], 2)
    assert ((a_first + a_later + b) / 2).item() == pytest.approx((4 + 15) / 2)
