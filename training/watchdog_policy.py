"""Deterministic stop rules for a registered Balatro training run."""

import math
import statistics


def summarize_games(rollout):
    """Count each game once even when its trajectory spans multiple samples."""
    games = {}
    for sample in rollout.get("samples", []):
        game = (sample.get("metadata") or {}).get("balatro") or {}
        if "episode_id" in game:
            games[game["episode_id"]] = game
    if not games:
        return None
    values = list(games.values())
    turns = sum(game["turns"] for game in values)
    invalid = sum(game["invalid_actions"] for game in values)
    return {"rollout_id": rollout.get("rollout_id"), "games": len(values),
            "mean_reward": statistics.mean(game["episode_reward"] for game in values),
            "mean_ante": statistics.mean(game["final_ante"] for game in values),
            "wins": sum(bool(game["won"]) for game in values),
            "turns": turns, "invalid_actions": invalid,
            "invalid_fraction": invalid / max(1, turns)}


def merge_chunks(chunks):
    """Match Modal Dojo's last-writer-wins scalar metric mirror."""
    table, written = {}, {}
    for chunk in chunks:
        for key, metrics in chunk.get("steps", {}).items():
            step = int(key)
            row, stamps = table.setdefault(step, {}), written.setdefault(step, {})
            incoming = chunk.get("written", {}).get(key, {})
            for name, value in metrics.items():
                at = incoming.get(name, 0)
                if name not in row or at > stamps.get(name, -1):
                    row[name], stamps[name] = value, at
    return table


def assess(table):
    train, evaluations, outputs = {}, {}, {}
    for step in sorted(table):
        row = table[step]
        if "train/step" in row:
            train[int(row["train/step"])] = row
        if "eval/step" in row and "eval/eval" in row:
            evaluations[int(row["eval/step"])] = row["eval/eval"]
        if "rollout/step" in row and "rollout/action_count" in row:
            outputs.setdefault(int(row["rollout/step"]), {}).update(row)
    completed = max(train) + 1 if train else 0
    history = [{"eval_step": step, "reward": evaluations[step]} for step in sorted(evaluations)]
    result = {"completed_updates": completed, "evaluations": history,
              "decision": "continue", "reason": None}
    for step, row in train.items():
        for name in ("train/loss", "train/grad_norm", "train/train_rollout_logprob_abs_diff"):
            if name in row and not math.isfinite(row[name]):
                return {**result, "decision": "stop", "reason": f"Nonfinite {name} at update {step + 1}"}
    if any(not math.isfinite(item["reward"]) for item in history):
        return {**result, "decision": "stop", "reason": "Nonfinite held-out reward"}
    # Output collapse is actionable even when reward rises or no eval exists.
    # Missing legacy metrics do not count as either healthy or failed batches.
    if outputs:
        latest = max(outputs)
        recent = [outputs[k] for k in range(latest-2, latest+1) if k in outputs]
        result["latest_output_metrics"] = {k: v for k, v in outputs[latest].items()
                                           if k.startswith(("rollout/action_", "rollout/thinking_", "rollout/final_answer_"))}
        for name, threshold in (("multiple_objects", .05), ("length_limit", .25), ("format_invalid", .10)):
            key = f"rollout/action_{name}_fraction"
            last = outputs[latest]
            if last.get("rollout/action_count", 0) >= 32 and last.get(key, 0) >= .5:
                return {**result, "decision": "stop", "reason": f"Output collapse: {name} in at least half of responses at rollout {latest}"}
            if len(recent) == 3 and all(r.get("rollout/action_count", 0) >= 32
                                      and r.get(key, -1) >= threshold for r in recent):
                return {**result, "decision": "stop", "reason": f"Sustained output failure: {name} >= {threshold:.0%} for three rollouts"}
    # A missing baseline is an observation failure, not evidence of regression.
    if 0 not in evaluations:
        return {**result, "reason": "Awaiting baseline evaluation"}
    baseline = evaluations[0]
    post = [item for item in history if item["eval_step"] > 0]
    if baseline > 0 and len(post) >= 2 and all(item["reward"] < .8 * baseline for item in post[-2:]):
        return {**result, "decision": "stop", "reason": "Two consecutive held-out evaluations more than 20% below baseline"}
    if (completed >= 50 and len(post) >= 3 and post[-1]["eval_step"] >= 49
            and all(item["reward"] <= baseline for item in post[-3:])):
        return {**result, "decision": "stop", "reason": "At least 50 updates with the latest three held-out evaluations at or below baseline"}
    return result
