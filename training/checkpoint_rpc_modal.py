"""Run checkpoint RPC fault injection on CPU in the exact Slime image."""

import json
from pathlib import Path

import modal
from modal_dojo.frameworks.slime.launcher import SLIME_IMAGE

ROOT = Path(__file__).resolve().parent
app = modal.App("balatro-checkpoint-rpc-regression")
image = modal.Image.from_registry(SLIME_IMAGE).entrypoint([])
for name in (
    "checkpoint_rpc.py",
    "patch_checkpoint_rpc.py",
    "checkpoint_rpc_integration.py",
):
    image = image.add_local_file(ROOT / name, f"/tmp/{name}", copy=True)
image = image.run_commands("python /tmp/patch_checkpoint_rpc.py")


@app.function(image=image, cpu=4, memory=8192, timeout=240, retries=0, serialized=True)
def check():
    import os
    import subprocess

    process = subprocess.run(
        ["python", "/tmp/checkpoint_rpc_integration.py"],
        env={
            **os.environ,
            "PYTHONPATH": "/root/slime:/root/Megatron-LM:/tmp",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        },
        capture_output=True,
        text=True,
        timeout=210,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


@app.local_entrypoint()
def main(out: str):
    result = check.remote()
    Path(out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    assert result["returncode"] == 0, "Checkpoint RPC fault injection failed"
