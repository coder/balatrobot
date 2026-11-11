"""Fetch the Modal Evals SDK (`flash_eval/modal_evals` of modal-labs/modal, at the pinned revision) into
`.modal-evals`, which pyproject.toml installs from, and drop its workspace source for `modal`, which the monorepo
builds itself, so the release on PyPI is used instead.

    uv run --no-project --python 3.12 --with grpcio-tools==1.71.2 evals/setup_modal_evals.py

The SDK's gRPC stubs aren't committed, so this generates them too, with the grpcio-tools of the SDK's grpcio.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = "https://github.com/modal-labs/modal.git"
REVISION = "72bc50c897c2760b255e7d756681e0e98559a421"
SUBDIRECTORY = "flash_eval/modal_evals"
TARGET = Path(__file__).resolve().parent / ".modal-evals"


def main() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        clone = Path(scratch) / "modal"
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--sparse",
                "--no-checkout",
                REPOSITORY,
                clone,
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", clone, "sparse-checkout", "set", SUBDIRECTORY], check=True
        )
        subprocess.run(
            ["git", "-C", clone, "checkout", "--quiet", REVISION], check=True
        )
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(clone / SUBDIRECTORY, TARGET)
    pyproject = TARGET / "pyproject.toml"
    text = re.sub(r"\n\[tool\.uv\.sources\]\n(?:.+\n)*", "\n", pyproject.read_text())
    pyproject.write_text(text)
    import grpc_tools
    from grpc_tools import protoc

    source = TARGET / "src"
    well_known = Path(grpc_tools.__file__).parent / "_proto"
    status = protoc.main(
        [
            "protoc",
            f"-I{source}",
            f"-I{well_known}",
            f"--python_out={source}",
            f"--pyi_out={source}",
            f"--grpc_python_out={source}",
            str(source / "modal_evals" / "proto" / "flash_eval_api.proto"),
        ]
    )
    if status != 0:
        raise SystemExit(f"protoc failed with {status}")
    (TARGET / "REVISION").write_text(REVISION + "\n")
    print(f"Modal Evals SDK {REVISION[:12]} in {TARGET}")


if __name__ == "__main__":
    main()
