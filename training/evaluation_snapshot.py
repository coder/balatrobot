"""Extract held-out episode results and paired-seed comparisons from a Ray log."""

import argparse
import json
import math
import statistics
import subprocess
from pathlib import Path


def summarize(episodes, size=32):
    ordered = sorted({e["episode_id"]: e for e in episodes}.values(), key=lambda e: e["episode_id"])
    batches = []
    baseline = None
    for offset in range(0, len(ordered), size):
        batch = ordered[offset:offset + size]
        if len(batch) != size:
            break
        by_seed = {e["seed"]: e for e in batch}
        if len(by_seed) != size:
            raise ValueError("Incomplete or overlapping evaluation batches; inspect episode log")
        baseline = baseline or by_seed
        if by_seed.keys() != baseline.keys():
            raise ValueError("Evaluation seed sets differ")
        delta = [by_seed[seed]["reward"] - baseline[seed]["reward"] for seed in baseline]
        batches.append({
            "batch_index": len(batches), "games": size,
            "mean_reward": statistics.mean(e["reward"] for e in batch),
            "mean_ante": statistics.mean(e["ante"] for e in batch),
            "wins": sum(e["won"] for e in batch),
            "capped": sum(e["capped"] for e in batch),
            "invalid_actions": sum(e["invalid_actions"] for e in batch),
            "turns": sum(e["turns"] for e in batch),
            "paired_reward_delta": statistics.mean(delta),
            "paired_delta_standard_error": statistics.stdev(delta) / math.sqrt(size),
            "seeds_better": sum(value > 0 for value in delta),
            "seeds_worse": sum(value < 0 for value in delta),
        })
    return {"completed_batches": batches, "partial_batch_games": len(ordered) % size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--head", required=True)
    parser.add_argument("--driver-log", required=True)
    args = parser.parse_args()
    remote = f'''
import json, time
from pathlib import Path
episodes = {{}}
for line in Path({args.driver_log!r}).read_text().splitlines():
    marker = "BALATRO_EPISODE "
    if marker not in line:
        continue
    try:
        event, _ = json.JSONDecoder().raw_decode(line.split(marker, 1)[1])
    except ValueError:
        continue
    if event.get("seed", "").startswith("BALATRO-EVAL-"):
        episodes[event["episode_id"]] = event
print(json.dumps(list(episodes.values())), flush=True)
time.sleep(.3)
'''
    process = subprocess.run(
        ["modal", "container", "exec", args.head, "--", "python", "-c", remote],
        text=True, capture_output=True, timeout=45, check=True,
    )
    episodes = json.loads(process.stdout)
    root = Path(__file__).resolve().parents[1] / "reports"
    (root / f"{args.run_id}-eval-episodes.json").write_text(json.dumps(episodes, indent=2))
    result = summarize(episodes)
    result["note"] = "Batch indices follow this Ray attempt's episode order; map to recorded eval steps before comparing across retries."
    (root / f"{args.run_id}-eval-summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
