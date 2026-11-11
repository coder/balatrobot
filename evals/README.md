# Balatro on Modal Evals

`balatro_evals/evaluation.py` publishes Balatro to [Modal Evals](https://modal.com/evaluations)
as a private evaluation: 16 tasks, each a seeded run (Red Deck, White Stake), played
by a Harbor agent (Terminus 2 by default) from the terminal through BalatroBot's
JSON-RPC API, and scored by the blinds the run defeats of a winning run's 24.
It runs on the same headless LOVE + Lovely + Steamodded image and `balatro-rl-assets`
release as the training harness in `batro_modal_rl.py`.

Each task is a Harbor task assembled from [`balatro_evals/task`](balatro_evals/task),
which holds everything but the game (Balatro isn't redistributable): the instruction,
`environment/Dockerfile` and scripts, `tests/`, and `solution/`. `task.toml` is
generated per seed with `BALATRO_SEED` in the environment, a 3-hour agent timeout,
and 2 CPUs / 4 GiB.

## What a trial leaves behind

- `artifacts/play-by-play.jsonl`: one line per action the agent took: `turn`,
  `time`, `method`, `params`, `error`, the full game `state` it led to, and the
  `frame` of the game after it. Enough to replay the game.
- `artifacts/replay.mp4`: the frames at two per second, encoded by `balatro-replay`, a
  Harbor collect hook, when the agent's turn ends (Harbor collects artifacts before the tests).
- Harbor's trajectory (`agent/trajectory.json`), the terminal pane, and the tests'
  output, with the reward and the blinds defeated in `verifier/reward.json`.

The `balatro` command the agent uses starts the seeded run on its first use, prints
the state after every action, refuses the game's debug methods (`add`, `set`,
`save`, `load`, `start`, `menu`), and keeps the play-by-play and frames.

## Publishing and running

```sh
uv run --no-project --python 3.12 --with grpcio-tools==1.71.2 evals/setup_modal_evals.py
uv sync --project evals --group test
uv run --project evals pytest evals/test_evaluation.py

# The game, from the harness's asset Volume (CURRENT names the release).
modal volume get balatro-rl-assets releases/<release> ~/balatro-release -e joy-dev

# Publish privately to joy-dev, then run a seed against a Flash endpoint.
BALATRO_RELEASE_DIR=~/balatro-release/<release> ./evals/modal_evals.sh modal-evals publish balatro_evals.evaluation:balatro
./evals/modal_evals.sh modal-evals run balatro --task balatro-eval-01 --endpoint ep-... --deployment ed-...
# Or the oracle, which checks the environment with a fixed policy and no model:
./evals/modal_evals.sh modal-evals run balatro --task balatro-eval-00 --params '{"agent":"oracle"}' \
  --target-url https://oracle.invalid/v1 --target-model oracle
```

The SDK comes from `modal-labs/modal` (`flash_eval/modal_evals`, pinned in
`pyproject.toml`); `balatro_evals/harbor.py` and `image.py` are copies of its Harbor
adapter and runner Image, since the runner Image carries only this package.
