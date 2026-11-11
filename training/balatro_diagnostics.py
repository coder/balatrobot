"""Game-level reporting and explicitly named probability diagnostics."""

import ast
import math
from pathlib import Path


def game_metrics(samples):
    games = {}
    for sample in samples:
        metadata = sample.get("metadata", {}) if isinstance(sample, dict) else sample.metadata
        game = metadata["balatro"]
        games[game["episode_id"]] = game
    if not games:
        raise ValueError("Cannot report an empty Balatro batch")
    games = list(games.values())
    reward = sorted(float(g["episode_reward"]) for g in games)
    ante = sorted(float(g["final_ante"]) for g in games)
    if not all(math.isfinite(x) for x in reward + ante):
        raise ValueError("Nonfinite Balatro game metric")
    def percentile(values, q):
        position = (len(values)-1) * q / 100
        low, high = math.floor(position), math.ceil(position)
        return values[low] + (values[high]-values[low]) * (position-low)
    turns = sum(g["turns"] for g in games)
    invalid = sum(g["invalid_actions"] for g in games)
    result = {"game_count": len(games), "game_reward_mean": sum(reward)/len(games),
              "game_ante_mean": sum(ante)/len(games), "game_win_rate": sum(bool(g["won"]) for g in games)/len(games),
              "game_invalid_fraction": invalid/max(1, turns), "game_invalid_actions": invalid,
              "game_turns": turns}
    for name, values in (("game_reward", reward), ("game_ante", ante)):
        result.update({f"{name}_p{q}": percentile(values, q) for q in (10, 25, 50, 75, 90, 95)})
    # These lengths count sampled action tokens, including rejected output,
    # once per game. They do not depend on segment count or evaluation masks.
    if any(g.get("output_contract_version") == 1 for g in games):
        if not all(g.get("output_contract_version") == 1 for g in games):
            raise ValueError("Mixed output-contract versions in one batch")
        lengths = sorted(n for g in games for n in g["action_token_lengths"])
        if (len(lengths) != turns or not lengths
                or any(type(n) is not int or not 1 <= n <= 96 + g.get("thinking_budget", 0)
                       for g in games for n in g["action_token_lengths"])):
            raise ValueError("Missing or invalid sampled action lengths")
        result.update(action_count=turns, action_tokens_total=sum(lengths),
                      action_tokens_mean=sum(lengths)/turns, action_tokens_max=max(lengths))
        result.update({f"action_tokens_p{q}": percentile(lengths, q) for q in (50, 90, 95, 99)})
        if any(g.get("thinking_budget", 0) for g in games):
            for g in games:
                if (g.get("thinking_budget") != 8192
                        or len(g.get("thinking_token_lengths", [])) != g["turns"]
                        or len(g.get("final_answer_token_lengths", [])) != g["turns"]):
                    raise ValueError("Missing or mixed thinking token counters")
                for thinking, answer, total in zip(g["thinking_token_lengths"], g["final_answer_token_lengths"], g["action_token_lengths"]):
                    if (type(thinking) is not int or type(answer) is not int
                            or not 0 <= thinking <= 8192 or not 0 <= answer <= 96
                            or thinking + answer != total):
                        raise ValueError("Invalid thinking/final-answer token accounting")
            for field, label in (("thinking_token_lengths", "thinking_tokens"),
                                 ("final_answer_token_lengths", "final_answer_tokens")):
                values = sorted(n for g in games for n in g[field])
                result[f"{label}_mean"] = sum(values) / turns
                result[f"{label}_max"] = max(values)
                result.update({f"{label}_p{q}": percentile(values, q) for q in (50, 90, 95, 99)})
            result["thinking_budget_hit_fraction"] = sum(n == 8192 for g in games for n in g["thinking_token_lengths"]) / turns
            if all("forced_thinking_closures" in g for g in games):
                counts = [g["forced_thinking_closures"] for g in games]
                if any(type(n) is not int or not 0 <= n <= g["turns"] for n, g in zip(counts, games)):
                    raise ValueError("Invalid forced thinking closure count")
                result["thinking_forced_close_count"] = sum(counts)
                result["thinking_forced_close_fraction"] = sum(counts) / turns
        for field, label in (("output_format_errors", "format_invalid"),
                             ("multiple_action_responses", "multiple_objects"),
                             ("length_limit_responses", "length_limit"),
                             ("normal_stop_responses", "normal_stop")):
            counts = [g[field] for g in games]
            if any(type(n) is not int or not 0 <= n <= g["turns"] for n, g in zip(counts, games)):
                raise ValueError(f"Invalid action counter: {field}")
            result[f"action_{label}_count"] = sum(counts)
            result[f"action_{label}_fraction"] = sum(counts)/turns
    return result


def log_rollout(rollout_id, args, samples, extra_metrics, rollout_time):
    from slime.ray.rollout import compute_metrics_from_samples, compute_perf_metrics_from_samples, compute_rollout_step
    from slime.utils import logging_utils
    data = dict(extra_metrics or {})
    data.update({f"rollout/segments/{k}": v for k, v in compute_metrics_from_samples(args, samples).items()})
    data.update({f"perf/{k}": v for k, v in compute_perf_metrics_from_samples(args, samples, rollout_time).items()})
    metrics = game_metrics(samples)
    data.update({f"rollout/{k}": v for k, v in metrics.items()})
    data["rollout/raw_reward"] = metrics["game_reward_mean"]
    data["rollout/step"] = compute_rollout_step(args, rollout_id)
    logging_utils.log(args, data, step_key="rollout/step")
    return True


def log_eval(rollout_id, args, data, extra_metrics):
    from slime.ray.rollout import compute_rollout_step
    from slime.utils import logging_utils
    metrics = {}
    for name, item in data.items():
        if item.get("samples"):
            metrics.update({f"eval/{name}/{k}": v for k, v in game_metrics(item["samples"]).items()})
    metrics["eval/step"] = compute_rollout_step(args, rollout_id)
    logging_utils.log(args, metrics, step_key="eval/step")
    return False  # Retain the native eval/eval mean used by the watchdog.


def install(root=Path("/root/slime")):
    root = Path(root)
    updates = []
    data_path = root / "slime/backends/megatron_utils/data.py"
    source = data_path.read_text()
    if "BALATRO_GAME_METRIC_NAMES" not in source:
        calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.Expr, ast.Assign))
                 and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                 and n.value.func.id == "gather_log_data" and n.value.args
                 and isinstance(n.value.args[0], ast.Constant) and n.value.args[0].value == "rollout"]
        if len(calls) != 1:
            raise RuntimeError(f"Unsupported trainer source for Balatro diagnostics: {data_path}")
        call = calls[0]
        indent = " " * call.col_offset
        addition = (f'{indent}# BALATRO_GAME_METRIC_NAMES: these values average context segments.\n'
                    f'{indent}if "raw_reward" in log_dict:\n'
                    f'{indent}    log_dict["segment_weighted_raw_reward"] = log_dict.pop("raw_reward")\n')
        lines = source.splitlines(keepends=True)
        lines.insert(call.lineno - 1, addition)
        updated = "".join(lines)
        compile(updated, str(data_path), "exec")
        updates.append((data_path, updated))
    patches = [
        (root / "slime/backends/megatron_utils/loss.py",
         '        reported_loss["train_rollout_logprob_abs_diff"] = train_rollout_logprob_abs_diff.clone().detach()',
         '        reported_loss["train_rollout_logprob_abs_diff"] = train_rollout_logprob_abs_diff.clone().detach()\n'
         '        # BALATRO_PROBABILITY_TAILS: game-normalized token fractions, not averaged quantiles.\n'
         '        gap = (log_probs_to_compare - rollout_log_probs).abs()\n'
         '        for threshold, label in ((0.01, "0_01"), (0.05, "0_05"), (0.1, "0_1")):\n'
         '            reported_loss[f"sampling_gap_gt_{label}_fraction"] = sum_of_sample_mean((gap > threshold).float()).detach()\n'
         '        reported_loss["pre_update_ppo_kl"] = reported_loss.pop("ppo_kl")\n'
         '        reported_loss["pre_update_pg_clipfrac"] = reported_loss.pop("pg_clipfrac")',
         "BALATRO_PROBABILITY_TAILS"),
    ]
    for path, before, after, marker in patches:
        source = path.read_text()
        if marker in source:
            continue
        if source.count(before) != 1:
            raise RuntimeError(f"Unsupported trainer source for Balatro diagnostics: {path}")
        updated = source.replace(before, after, 1)
        compile(updated, str(path), "exec")
        updates.append((path, updated))
    for path, source in updates:
        path.write_text(source)
    destination = root / "balatro_diagnostics.py"
    if destination.resolve() != Path(__file__).resolve():
        destination.write_text(Path(__file__).read_text())


if __name__ == "__main__":
    install()
