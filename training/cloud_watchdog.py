"""Scheduled CPU monitoring and bounded early stopping, independent of a laptop."""

from pathlib import Path

import modal

app = modal.App("balatro-dojo-watchdog")
metadata = modal.Volume.from_name("modal-dojo-metadata", environment_name="joy-dev")
evidence = modal.Volume.from_name("balatro-dojo-watchdog-evidence", create_if_missing=True, environment_name="joy-dev")
image = (modal.Image.debian_slim(python_version="3.12")
         .add_local_file(Path(__file__).with_name("watchdog_policy.py"), "/root/watchdog_policy.py"))


@app.function(image=image, volumes={"/metadata": metadata, "/evidence": evidence},
              schedule=modal.Period(minutes=2), timeout=90, cpu=.25, memory=1024,
              max_containers=1, serialized=True)
async def tick():
    import asyncio
    import json
    import time
    from pathlib import Path
    from modal.client import _Client
    from modal_proto import api_pb2
    from watchdog_policy import assess, merge_chunks, summarize_games

    registry = modal.Dict.from_name("balatro-dojo-watchdog", create_if_missing=True, environment_name="joy-dev")
    metadata = modal.Volume.from_name("modal-dojo-metadata", environment_name="joy-dev")
    evidence = modal.Volume.from_name("balatro-dojo-watchdog-evidence", environment_name="joy-dev")

    await metadata.reload.aio()
    client = await _Client.from_env()
    summaries = []
    async for run_id, registration in registry.items.aio():
        if not registration.get("active"):
            continue
        snapshot = {"run": run_id, "checked_at": time.time()}
        try:
            record = json.loads(Path(f"/metadata/training-runs/{run_id}.json").read_text())
            app_id = registration["app_id"]
            # A registration can stop only the exact app belonging to this run.
            if record.get("training_run_id") != run_id or record.get("modal_app_id") != app_id:
                raise ValueError("Registered run/app identity does not match metadata")
            lifecycle = await asyncio.wait_for(client.stub.AppGetLifecycle(
                api_pb2.AppGetLifecycleRequest(app_id=app_id)), timeout=15)
            stopped = lifecycle.lifecycle.app_state == api_pb2.APP_STATE_STOPPED
            files = sorted(Path(f"/metadata/metric-series/{run_id}").glob("*.json"))
            table = merge_chunks([json.loads(path.read_text()) for path in files])
            assessment = assess(table)
            snapshot.update(assessment)
            snapshot.update(status=record.get("status"), progress=record.get("metadata", {}).get("framework_progress"),
                            app_stopped=stopped, attempt_count=record.get("metadata", {}).get("attempt_count"))
            latest = record.get("metadata", {}).get("latest_rollout") or {}
            if latest.get("rollout_id") is not None:
                try:
                    rollout_path = Path(f"/metadata/training-rollouts/{run_id}__{int(latest['rollout_id']):08d}.json")
                    snapshot["latest_training_games"] = summarize_games(json.loads(rollout_path.read_text()))
                except Exception as exc:
                    snapshot["game_read_error"] = f"{type(exc).__name__}: {exc}"
            if stopped:
                registration["active"] = False
            elif assessment["decision"] == "stop":
                # Persist the decision before stopping anything. Training metadata
                # is read-only here; do not race the launcher's run-record writer.
                registration["stop_reason"] = assessment["reason"]
                registration.setdefault("stop_requested_at", time.time())
                registration["latest"] = snapshot
                await registry.put.aio(run_id, registration)
                await asyncio.wait_for(client.stub.AppStop(
                    api_pb2.AppStopRequest(app_id=app_id, source=api_pb2.APP_STOP_SOURCE_CLI)), timeout=15)
                snapshot["stop_rpc_succeeded"] = True
            registration["latest"] = snapshot
        except Exception as exc:
            # Failed reads cannot establish learning failure or authorize a stop.
            snapshot["read_error"] = f"{type(exc).__name__}: {exc}"
            registration["latest"] = snapshot
        await registry.put.aio(run_id, registration)
        path = Path("/evidence") / run_id
        path.mkdir(exist_ok=True)
        (path / "latest.json").write_text(json.dumps(snapshot, indent=2))
        with (path / "history.jsonl").open("a") as output:
            output.write(json.dumps(snapshot) + "\n")
        print(json.dumps(snapshot), flush=True)
        summaries.append(snapshot)
    await evidence.commit.aio()
    return summaries


@app.function(image=image, timeout=45, cpu=.25, serialized=True)
async def verify_stop_api(stopped_app_id: str):
    """Check cloud stop permissions using an already stopped, explicit test app."""
    import asyncio
    from modal.client import _Client
    from modal_proto import api_pb2
    client = await _Client.from_env()
    result = await asyncio.wait_for(client.stub.AppGetLifecycle(
        api_pb2.AppGetLifecycleRequest(app_id=stopped_app_id)), timeout=15)
    if result.lifecycle.app_state != api_pb2.APP_STATE_STOPPED:
        raise ValueError("The stop-permission probe requires an already stopped app")
    await asyncio.wait_for(client.stub.AppStop(
        api_pb2.AppStopRequest(app_id=stopped_app_id, source=api_pb2.APP_STOP_SOURCE_CLI)), timeout=15)
    return {"stopped_app_id": stopped_app_id, "cloud_stop_rpc_verified": True}
