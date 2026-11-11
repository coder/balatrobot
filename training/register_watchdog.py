"""Register a submitted Dojo run with Balatro's deployed cloud watchdog."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import modal


def register(run_id, app_id, *, updates=200, thinking_budget=8192):
    environment = os.environ.get("MODAL_ENVIRONMENT", "joy-dev")
    if environment != "joy-dev":
        raise ValueError("Deploy a watchdog for the selected environment before registering this run")
    from modal_dojo.common.run import TrainingRun
    run = TrainingRun.from_id(run_id)
    if run.modal_app_id != app_id:
        raise ValueError("Run/app identity mismatch; watchdog registration refused")
    registration = {
        "active": True, "app_id": app_id, "registered_at": time.time(),
        "policy_version": 3, "requested_updates": updates,
        "thinking_budget": thinking_budget,
        "policy_sha256": hashlib.sha256(Path(__file__).with_name("watchdog_policy.py").read_bytes()).hexdigest(),
    }
    registry = modal.Dict.from_name("balatro-dojo-watchdog", create_if_missing=True, environment_name=environment)
    registry.put(run_id, registration)
    checks = modal.Function.from_name("balatro-dojo-watchdog", "tick", environment_name=environment).remote()
    return {"registration": registration, "first_check": [x for x in checks if x.get("run") == run_id]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--updates", type=int, default=200)
    parser.add_argument("--thinking-budget", type=int, default=8192)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    if receipt.get("state") != "submitted":
        raise ValueError("Expected a submitted launch receipt")
    result = register(receipt["training_run_id"], receipt["modal_app_id"],
                      updates=args.updates, thinking_budget=args.thinking_budget)
    path = args.receipt.with_suffix(".watchdog.json")
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
