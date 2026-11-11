"""Validate token-credit transport against the exact trainer image on CPU."""

import json
from pathlib import Path

import modal
from modal_dojo.frameworks.slime.launcher import SLIME_IMAGE

ROOT = Path(__file__).resolve().parents[1]
app = modal.App("balatro-action-credit-regression")
image = (
    modal.Image.from_registry(SLIME_IMAGE)
    .entrypoint([])
    .run_commands("python -m pip install pytest modal==1.6.1")
    .add_local_python_source("modal_dojo")
    .add_local_file(ROOT / "training/balatro_credit.py", "/tmp/credit-validation/training/balatro_credit.py")
    .add_local_file(ROOT / "tests/__init__.py", "/tmp/credit-validation/tests/__init__.py")
    .add_local_file(ROOT / "tests/test_action_credit.py", "/tmp/credit-validation/tests/test_action_credit.py")
    .add_local_file(ROOT / "training/balatro_diagnostics.py", "/tmp/credit-validation/training/balatro_diagnostics.py")
    .add_local_file(ROOT / "tests/test_balatro_diagnostics.py", "/tmp/credit-validation/tests/test_balatro_diagnostics.py")
    .add_local_file(ROOT / "batro_modal_rl.py", "/tmp/credit-validation/batro_modal_rl.py")
    .add_local_file(ROOT / "tests/test_context_management.py", "/tmp/credit-validation/tests/test_context_management.py")
    .add_local_file(ROOT / "tests/test_single_action_output.py", "/tmp/credit-validation/tests/test_single_action_output.py")
    .add_local_file(ROOT / "tests/test_thinking_output.py", "/tmp/credit-validation/tests/test_thinking_output.py")
    .add_local_file(ROOT / "training/checkpoint_group_integration.py", "/tmp/credit-validation/training/checkpoint_group_integration.py")
    .add_local_file(ROOT / "tests/fixtures/repeated_action_outputs.json", "/tmp/credit-validation/tests/fixtures/repeated_action_outputs.json")
)


@app.function(image=image, cpu=4, memory=8192, timeout=240, retries=0, serialized=True,
              volumes={"/hf-cache": modal.Volume.from_name("huggingface-cache")})
def check():
    import os
    import subprocess

    process = subprocess.run(
        ["python", "-m", "pytest", "tests/test_action_credit.py", "tests/test_balatro_diagnostics.py", "tests/test_single_action_output.py", "tests/test_thinking_output.py", "-q", "--tb=short"],
        cwd="/tmp/credit-validation",
        env={**os.environ, "BALATRO_SLIME_SOURCE": "/root/slime/slime",
             "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "BALATRO_THINKING_NATIVE": "1",
             "HF_HOME": "/hf-cache", "HF_HUB_CACHE": "/hf-cache/hub"},
        capture_output=True, text=True, timeout=210,
    )
    checkpoint = subprocess.run(
        ["python", "/tmp/credit-validation/training/checkpoint_group_integration.py"],
        env={**os.environ, "MODAL_DOJO_SLIME_SOURCE": "/root/slime/slime",
             "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        capture_output=True, text=True, timeout=90,
    )
    return {"image": SLIME_IMAGE, "returncode": process.returncode or checkpoint.returncode,
            "stdout": process.stdout, "stderr": process.stderr,
            "checkpoint_collectives": {"returncode": checkpoint.returncode,
                                       "stdout": checkpoint.stdout, "stderr": checkpoint.stderr},
            "data_logging_source": Path("/root/slime/slime/backends/megatron_utils/data.py").read_text() if process.returncode else None}


@app.local_entrypoint()
def main(out: str):
    result = check.remote()
    Path(out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    assert result["returncode"] == 0, "Action-credit trainer integration failed"
