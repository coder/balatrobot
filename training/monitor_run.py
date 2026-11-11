"""Persist live run evidence, including failures followed by launcher retries.

This collector does not diagnose or edit jobs; its output is for the supervising
agent. A FAILED attempt is not terminal while the Modal app is still active.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from modal_dojo.common.run import TrainingRun


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--learning", action="store_true", help="Also persist metrics and game-level learning evidence")
    parser.add_argument("--eval-container", help="Ray head container for held-out episode evidence")
    parser.add_argument("--eval-driver-log", help="Ray driver log containing held-out episode events")
    parser.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if bool(args.eval_container) != bool(args.eval_driver_log):
        parser.error("Provide both --eval-container and --eval-driver-log")
    if not args.once:
        # A disconnected SDK request can hang indefinitely after the laptop
        # sleeps. Bound each poll and give the next one a fresh client/channel.
        while True:
            process = subprocess.Popen(
                [sys.executable, __file__, *sys.argv[1:], "--once"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                start_new_session=True,
            )
            try:
                output, _ = process.communicate(timeout=55)
                print(output, end="", flush=True)
                if any(line.startswith("TERMINAL ") for line in output.splitlines()):
                    return
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                output, _ = process.communicate(timeout=5)
                print(output, end="", flush=True)
                print("MONITOR_READ_TIMEOUT: restarting observer; training unchanged", flush=True)
            time.sleep(args.interval)
    root = Path(__file__).resolve().parents[1] / "reports"
    previous = None
    last_print = 0.0
    last_eval_count = 0
    summary_path = root / f"{args.run_id}-eval-summary.json"
    if summary_path.exists():
        last_eval_count = len(json.loads(summary_path.read_text()).get("completed_batches", []))
    while True:
        try:
            run = TrainingRun.from_id(args.run_id)
            metadata = run.metadata
            if args.learning:
                try:
                    from learning_snapshot import capture
                    evidence = capture(run, root)
                    for alert in evidence["alerts"]:
                        print("LEARNING_REVIEW", alert, flush=True)
                    if args.eval_container and len(evidence["eval_history"]) > last_eval_count:
                        process = subprocess.run(
                            [sys.executable, str(Path(__file__).with_name("evaluation_snapshot.py")),
                             args.run_id, "--head", args.eval_container,
                             "--driver-log", args.eval_driver_log],
                            capture_output=True, text=True, timeout=55, check=True,
                        )
                        print("HELD_OUT_EVIDENCE", process.stdout.strip(), flush=True)
                        last_eval_count = len(evidence["eval_history"])
                except Exception as exc:
                    print("LEARNING_READ_ERROR", type(exc).__name__, str(exc)[-500:], flush=True)
            progress = metadata.get("framework_progress") or {}
            now = time.time()
            row = {
                "checked_at": now,
                "run": run.training_run_id,
                "app": run.modal_app_id,
                "function_call_id": run.function_call_id,
                "status": str(run.status),
                "phase": str(run.framework_status),
                "progress": progress,
                "latest": metadata.get("latest_rollout"),
                "attempt_count": metadata.get("attempt_count"),
                "error": (run.error_message or "")[-5000:],
            }
            terminal = str(run.status).split(".")[-1] in {
                "FAILED",
                "COMPLETED",
                "CANCELLED",
                "STOPPED",
            }
            if terminal and run.modal_app_id:
                output = subprocess.check_output(
                    [sys.executable, "-m", "modal", "app", "list", "--json"],
                    text=True,
                    timeout=45,
                )
                apps = json.loads(output)
                app = next(
                    (
                        a
                        for a in apps
                        if a.get("app_id", a.get("App ID")) == run.modal_app_id
                    ),
                    None,
                )
                state = app.get("state", app.get("State")) if app else "not_listed"
                row["modal_app_state"] = state
                terminal = state in ("stopped", "not_listed")
                row["terminal"] = terminal
            with (root / f"{args.run_id}-monitor.jsonl").open("a") as file:
                file.write(json.dumps(row, default=str) + "\n")
            signature = json.dumps(
                {k: v for k, v in row.items() if k != "checked_at"}, default=str
            )
            if signature != previous or now - last_print >= 120:
                print(json.dumps(row, default=str), flush=True)
                previous, last_print = signature, now
            if terminal:
                (root / f"{args.run_id}-metadata.json").write_text(
                    json.dumps(metadata, indent=2, default=str)
                )
                (root / f"{args.run_id}-error.txt").write_text(run.error_message or "")
                if run.modal_app_id:
                    with (root / f"{args.run_id}-final.log").open("w") as file:
                        subprocess.run(
                            [
                                sys.executable,
                                "-m", "modal",
                                "app",
                                "logs",
                                run.modal_app_id,
                                "--tail",
                                "5000",
                            ],
                            stdout=file,
                            stderr=subprocess.STDOUT,
                            timeout=45,
                        )
                print("TERMINAL", args.run_id, str(run.status), flush=True)
                return
        except Exception as exc:
            print("MONITOR_READ_ERROR", type(exc).__name__, str(exc)[-500:], flush=True)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
