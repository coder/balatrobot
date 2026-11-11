"""Balatro on Modal Evals: agents play a seeded run of Balatro from the terminal, through BalatroBot's JSON-RPC API,
and score the blinds they defeat. Harbor runs each trial, with the task's environment, a Harbor task per seed, and
every trial keeps a play-by-play of the game and a video of it among its artifacts.

The game isn't redistributable, so `task/` holds everything but it: the instruction, the environment's recipe and
scripts, the tests, and the reference solution. Publishing reads the game, BalatroBot's mod and launcher, and a save
that has been through the game's first run from a copy of the RL harness's `balatro-rl-assets` Volume release
(`batro_modal_rl.py --prepare-assets`), which `BALATRO_RELEASE_DIR` names, and ships them only in the release's
private task snapshot. The evaluation stays private to the environment it publishes to; see README.md.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import modal_evals as evals

from .harbor import HarborParams, HarborResult, run_trial
from .image import image

TASK = Path(__file__).parent / "task"
RELEASE_VARIABLE = "BALATRO_RELEASE_DIR"
# The release's directories, as `prepare_assets` lays them out.
RELEASE_DIRECTORIES = ("game", "mods", "python", "save")
# Seeds apart from the harness's training seeds, `BALATRO-RL-<index>`.
SEEDS = tuple(f"BALATRO-EVAL-{index:02d}" for index in range(16))
# A game's decisions take a model call each, a few hundred in a long run.
AGENT_TIMEOUT = 3 * 60 * 60
# The Image build fetches LOVE, Lovely, and Steamodded, and copies the game.
BUILD_TIMEOUT = 30 * 60
VERIFIER_TIMEOUT = 5 * 60
# Longer than the task's own limits, as Harbor applies them, so Harbor's end a slow trial.
TRIAL_TIMEOUT = 4 * 60 * 60

balatro = evals.Evaluation(
    "balatro",
    display_name="Balatro",
    description=(
        "Agents play a seeded run of Balatro from the terminal, through BalatroBot's API, scored by the blinds they"
        " defeat of the 24 in a winning run. Runs Harbor with Terminus 2 against the target."
    ),
)


class BalatroTask(evals.TaskData):
    # The Harbor task without its game: instruction, environment recipe and scripts, tests, and reference solution.
    task: evals.Directory
    # The game, BalatroBot's mod and launcher, and a save past the game's first run.
    game: evals.Directory
    seed: str


def task_config(seed: str) -> str:
    """The task's task.toml: its limits, resources, and the seed its run starts with."""
    return f"""schema_version = "1.4"

[environment]
build_timeout_sec = {BUILD_TIMEOUT}
cpus = 2
memory_mb = 4096

[environment.env]
BALATRO_SEED = "{seed}"

[agent]
timeout_sec = {AGENT_TIMEOUT}

[verifier]
timeout_sec = {VERIFIER_TIMEOUT}

# Harbor collects artifacts when the agent's turn ends, before the tests, so the video is encoded then.
[[verifier.collect]]
command = "balatro-replay"
timeout_sec = 120

[[artifacts]]
source = "/logs/artifacts/play-by-play.jsonl"
destination = "play-by-play.jsonl"

[[artifacts]]
source = "/logs/artifacts/replay.mp4"
destination = "replay.mp4"
"""


def release_directory() -> Path:
    release = os.environ.get(RELEASE_VARIABLE)
    if not release:
        raise ValueError(
            f"Set {RELEASE_VARIABLE} to a copy of a balatro-rl-assets release, which holds the game"
        )
    path = Path(release).expanduser()
    if missing := [name for name in RELEASE_DIRECTORIES if not (path / name).is_dir()]:
        raise ValueError(
            f"{RELEASE_VARIABLE}={release} lacks the release's {', '.join(missing)}"
        )
    return path


@balatro.tasks
def tasks() -> list[evals.Task[BalatroTask]]:
    game = evals.Directory(release_directory())
    return [
        evals.Task(
            seed.lower(), BalatroTask(task=evals.Directory(TASK), game=game, seed=seed)
        )
        for seed in SEEDS
    ]


class BalatroResult(HarborResult):
    """The trial's reward, the blinds defeated of the run's 24, with the count itself, as the tests write both."""

    blinds: Annotated[int, evals.HigherIsBetter, evals.Label("Blinds defeated")] = 0


@balatro.trial(
    image=image,
    cpu=1.0,
    memory=2048,
    timeout=TRIAL_TIMEOUT,
    max_concurrency=16,
    # Harbor starts each task's Sandbox.
    modal_access=True,
)
async def run(ctx: evals.TrialContext[HarborParams, BalatroTask]) -> BalatroResult:
    # Harbor builds the task's Image from `environment/`, so the game joins the task's directory for the trial.
    root = Path(tempfile.mkdtemp(prefix="balatro-"))
    try:
        task_directory = root / ctx.task.key
        shutil.copytree(ctx.task.data.task.path, task_directory)
        shutil.copytree(
            ctx.task.data.game.path, task_directory / "environment" / "release"
        )
        for path in (root, *root.rglob("*")):
            path.chmod(path.stat().st_mode | 0o700)
        (task_directory / "task.toml").write_text(task_config(ctx.task.data.seed))
        return await run_trial(ctx, task_directory, BalatroResult)
    finally:
        shutil.rmtree(root, ignore_errors=True)


balatro.report(
    evals.Card("blinds", label="Blinds defeated, of 24"),
    evals.Card("blinds", trials="max", label="Blinds defeated in the best trial"),
    evals.Card("errored", label="Errors"),
    evals.Card("agent_seconds", tasks="median", label="Agent time, median"),
    evals.Card("output_tokens", label="Output tokens"),
    evals.Table("tasks"),
)
