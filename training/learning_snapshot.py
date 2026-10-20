"""Read-only learning evidence for the supervising agent, not an efficacy verdict."""

import json
import math
import statistics
import time

from modal_dojo.common.metric_series import RunMetrics, metric_series_store
from modal_dojo.utils.metadata import MetadataStore, vol_get, vol_list


def capture(run, root):
    metrics = RunMetrics()
    for chunk in vol_list(metric_series_store(run.training_run_id)):
        metrics.load_chunk(chunk)
    rows = [metrics.table[key] for key in sorted(metrics.table)]
    train = {int(row["train/step"]): row for row in rows if "train/step" in row}
    evaluations = {int(row["eval/step"]): row["eval/eval"]
                   for row in rows if "eval/step" in row and "eval/eval" in row}
    selected = sorted(train)
    alerts = []
    for step, row in train.items():
        for key in ("train/loss", "train/grad_norm", "train/train_rollout_logprob_abs_diff"):
            if key in row and not math.isfinite(row[key]):
                alerts.append(f"Nonfinite {key} at update {step + 1}")
    latest_train = train[selected[-1]] if selected else {}
    if latest_train.get("train/train_rollout_logprob_abs_diff", 0) > .05:
        alerts.append("Sampling/training log-probability gap exceeds 0.05; inspect")
    if selected:
        initial = train[selected[0]].get("train/entropy_loss", 0)
        current = latest_train.get("train/entropy_loss", 0)
        if initial > 0 and current < .3 * initial:
            alerts.append("Token entropy fell over 70%; inspect action diversity and evaluation")
    eval_history = [{"eval_step": step, "reward": evaluations[step]} for step in sorted(evaluations)]
    if len(eval_history) >= 3:
        baseline = eval_history[0]["reward"]
        if baseline > 0 and all(item["reward"] < .8 * baseline for item in eval_history[-2:]):
            alerts.append("Two held-out evaluations are over 20% below baseline; inspect paired games")
    latest = (run.metadata or {}).get("latest_rollout") or {}
    rollout_id = latest.get("rollout_id")
    summary = None
    if rollout_id is not None:
        path = root / f"{run.training_run_id}-rollout-{rollout_id}.json"
        if path.exists():
            rollout = json.loads(path.read_text())
        else:
            rollout = vol_get(MetadataStore.TRAINING_ROLLOUTS,
                              f"{run.training_run_id}__{int(rollout_id):08d}")
            if rollout:
                path.write_text(json.dumps(rollout))
        games = {}
        if rollout:
            for sample in rollout.get("samples", []):
                metadata = sample.get("metadata") or {}
                game = metadata.get("balatro") or {}
                if "episode_id" in game:
                    games[game["episode_id"]] = (game, metadata)
        if games:
            values = list(games.values())
            turns = sum(game["turns"] for game, _ in values)
            invalid = sum(game["invalid_actions"] for game, _ in values)
            summary = {
                "rollout_id": rollout_id, "observed_training_games": len(values),
                "mean_reward": statistics.mean(game["episode_reward"] for game, _ in values),
                "mean_ante": statistics.mean(game["final_ante"] for game, _ in values),
                "wins": sum(bool(game["won"]) for game, _ in values),
                "invalid_actions": invalid, "turns": turns,
                "invalid_fraction": invalid / max(1, turns),
                "mean_policy_reward": statistics.mean(m["policy_episode_reward"] for _, m in values),
                "mean_intervention_reward_excluded": statistics.mean(
                    game["episode_reward"] - m["policy_episode_reward"] for game, m in values),
            }
    result = {
        "checked_at": time.time(), "run": run.training_run_id,
        "completed_updates": max(selected) + 1 if selected else 0,
        "eval_history": eval_history,
        "latest_train": {key: value for key, value in latest_train.items() if key.startswith("train/")},
        "latest_training_games": summary, "alerts": alerts,
        "interpretation": "Held-out means require paired-game and trajectory review; training reward alone does not establish learning.",
    }
    (root / f"{run.training_run_id}-metrics.json").write_text(json.dumps(metrics.table, indent=2))
    (root / f"{run.training_run_id}-learning-latest.json").write_text(json.dumps(result, indent=2))
    with (root / f"{run.training_run_id}-learning-monitor.jsonl").open("a") as file:
        file.write(json.dumps(result) + "\n")
    return result
