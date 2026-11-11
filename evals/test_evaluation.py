"""Balatro's own contract: a Harbor task per seed, whose game comes from a release at publish, within the trial's
timeout, and whose tests score the blinds a run defeated."""

import importlib.util
import tomllib
from pathlib import Path

import pytest
from balatro_evals.evaluation import (
    RELEASE_DIRECTORIES,
    RELEASE_VARIABLE,
    SEEDS,
    TASK,
    TRIAL_TIMEOUT,
    task_config,
    tasks,
)
from balatro_evals.harbor import TRIAL_OVERHEAD_SECONDS, task_time_limit


def test_the_task_is_a_harbor_task_whose_limits_fit_the_trial() -> None:
    for name in (
        "instruction.md",
        "environment/Dockerfile",
        "tests/test.sh",
        "solution/solve.sh",
    ):
        assert (TASK / name).is_file(), name
    config = tomllib.loads(task_config("BALATRO-EVAL-00"))
    assert config["environment"]["env"] == {"BALATRO_SEED": "BALATRO-EVAL-00"}
    assert task_time_limit("balatro", config) + TRIAL_OVERHEAD_SECONDS <= TRIAL_TIMEOUT


def test_publishing_needs_the_release_and_makes_a_task_per_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(RELEASE_VARIABLE, raising=False)
    with pytest.raises(ValueError, match=RELEASE_VARIABLE):
        tasks()
    monkeypatch.setenv(RELEASE_VARIABLE, str(tmp_path))
    with pytest.raises(ValueError, match="game, mods, python, save"):
        tasks()
    for name in RELEASE_DIRECTORIES:
        (tmp_path / name).mkdir()
    published = tasks()
    assert [task.key for task in published] == [seed.lower() for seed in SEEDS]
    assert len({task.data.seed for task in published}) == len(SEEDS)
    assert all(
        task.data.game.path == tmp_path and task.data.task.path == TASK
        for task in published
    )


def test_the_tests_score_the_blinds_a_run_defeated() -> None:
    spec = importlib.util.spec_from_file_location("score", TASK / "tests" / "score.py")
    assert spec is not None and spec.loader is not None
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)
    defeated = {"status": "DEFEATED"}
    assert score.defeated_blinds({}) == 0
    assert (
        score.defeated_blinds(
            {"ante_num": 1, "blinds": {"small": defeated, "big": {"status": "CURRENT"}}}
        )
        == 1
    )
    assert (
        score.defeated_blinds(
            {"ante_num": 3, "blinds": {"small": defeated, "big": defeated}}
        )
        == 8
    )
    assert score.defeated_blinds({"ante_num": 9, "won": True}) == 24
