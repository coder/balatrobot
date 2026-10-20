"""Prepare the pinned Dojo source and Balatro checkpoint recovery fixes."""

import argparse
import subprocess
from pathlib import Path

REVISION = "0bd6789d1be43c1eb10928d3d69be55de2d2533e"
ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="https://github.com/modal-projects/modal-dojo.git",
                        help="Git URL or existing local Dojo repository to clone")
    args = parser.parse_args()
    target = ROOT / ".dojo"
    patch = ROOT / "dojo-checkpoint-recovery.patch"
    if not target.exists():
        subprocess.run(["git", "clone", "--no-checkout", "--no-hardlinks", args.source, str(target)], check=True)
        subprocess.run(["git", "checkout", "--detach", REVISION], cwd=target, check=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
    if revision != REVISION:
        raise RuntimeError(f"Expected Dojo {REVISION}; found {revision}. Existing checkout was not changed.")
    applied = subprocess.run(["git", "apply", "--reverse", "--check", str(patch)],
                             cwd=target, capture_output=True).returncode == 0
    if not applied:
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=target, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=target, check=True)
    print(f"Dojo ready: {target} ({REVISION}, checkpoint recovery patch applied)")
    print("Install: uv sync --project training")


if __name__ == "__main__":
    main()
