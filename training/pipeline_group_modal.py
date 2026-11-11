"""Bounded GPU communication reproduction and regression, without training."""

import json
from pathlib import Path

import modal
from modal_dojo.frameworks.slime.launcher import SLIME_IMAGE

ROOT = Path(__file__).resolve().parent
app = modal.App("balatro-pipeline-group-regression")
image = (
    modal.Image.from_registry(SLIME_IMAGE)
    .entrypoint([])
    .add_local_file(
        ROOT / "pipeline_group_integration.py", "/tmp/pipeline_group_integration.py"
    )
    .add_local_file(ROOT / "patch_pipeline_group.py", "/tmp/patch_pipeline_group.py")
)


@app.function(image=image, gpu="H100:4", timeout=360, retries=0, serialized=True)
def check():
    import os
    import signal
    import subprocess

    env = {
        **os.environ,
        "PYTHONPATH": "/root/slime:/root/Megatron-LM:/tmp",
        "NCCL_RAS_ENABLE": "0",
        "TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC": "45",
    }
    results = []
    for patched in (False, True):
        command = ["python", "/tmp/pipeline_group_integration.py"] + (
            ["--patched"] if patched else []
        )
        proc = subprocess.Popen(
            command,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=140)
            result = {
                "patched": patched,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            result = {
                "patched": patched,
                "returncode": "timeout",
                "stdout": stdout,
                "stderr": stderr,
            }
        results.append(result)
        print(json.dumps(result), flush=True)
    return results


@app.local_entrypoint()
def main(out: str):
    results = check.remote()
    Path(out).write_text(json.dumps(results, indent=2))
    assert results[0]["returncode"] != 0, (
        "Expected unpatched image to reproduce the failure"
    )
    assert results[0]["stdout"].count("READY rank=") == 4, (
        "Unpatched test failed before all workers initialized"
    )
    assert "_batched_p2p_ops" in results[0]["stderr"], (
        "Unpatched test did not establish a pipeline-transfer stall"
    )
    assert results[1]["returncode"] == 0, "Corrected pipeline test failed"
    assert results[1]["stdout"].count("PASS rank=") == 4
