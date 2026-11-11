"""Install checkpoint RPC recovery in the pinned Slime training image."""

import ast
from pathlib import Path

WORKER_METHOD = """
    def _checkpoint_save_once(self, operation_id, rollout_id, force_sync=False):
        from slime.utils.checkpoint_rpc import save_once
        return save_once(self, operation_id, rollout_id, force_sync=force_sync)
"""


def patch_group(source):
    tree = ast.parse(source)
    groups = [
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "RayTrainGroup"
    ]
    if len(groups) != 1:
        raise RuntimeError("Unsupported Slime source: expected RayTrainGroup")
    group = groups[0]
    methods = [
        n
        for n in group.body
        if isinstance(n, ast.FunctionDef) and n.name == "save_model"
    ]
    if len(methods) != 1:
        raise RuntimeError("Unsupported Slime source: expected save_model")
    method = methods[0]
    if "from slime.utils.checkpoint_rpc import save_group" in ast.get_source_segment(
        source, method
    ):
        return source
    calls = [
        n
        for n in ast.walk(method)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "ray"
        and n.func.attr == "get"
    ]
    expected = ast.parse(
        "ray.get([actor.save_model.remote(rollout_id, force_sync=force_sync) for actor in self._actor_handlers])",
        mode="eval",
    ).body
    if len(calls) != 1 or ast.dump(calls[0]) != ast.dump(expected):
        raise RuntimeError("Unsupported Slime checkpoint dispatch")
    # Enforce actor-local cache lifetime and serialization, rather than relying
    # on Ray defaults that might change with another patch or image version.
    options = [
        n
        for n in ast.walk(group)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "actor_options" for t in n.targets)
    ]
    if len(options) != 1 or not isinstance(options[0].value, ast.Dict):
        raise RuntimeError("Unsupported Slime actor options")
    option = options[0].value
    if any(
        isinstance(k, ast.Constant)
        and k.value in {"max_restarts", "max_concurrency", "max_task_retries"}
        for k in option.keys
    ):
        raise RuntimeError("Unexpected Slime actor retry/concurrency options")
    # Refuse additional runtime overrides, which would invalidate deduplication.
    for n in ast.walk(group):
        if isinstance(n, ast.keyword) and n.arg in {
            "max_restarts",
            "max_concurrency",
            "max_task_retries",
        }:
            raise RuntimeError("Unexpected Slime actor retry/concurrency override")
    lines = source.splitlines(keepends=True)
    call = calls[0]
    if call.lineno != call.end_lineno:
        raise RuntimeError("Unsupported multiline Slime checkpoint dispatch")
    i = call.lineno - 1
    lines[i] = (
        lines[i][: call.col_offset]
        + "save_group(self._actor_handlers, rollout_id, force_sync=force_sync)"
        + lines[i][call.end_col_offset :]
    )
    lines.insert(i, "        from slime.utils.checkpoint_rpc import save_group\n")
    i = option.lineno
    lines.insert(
        i,
        '            "max_restarts": 0, "max_concurrency": 1, "max_task_retries": 0,\n',
    )
    updated = "".join(lines)
    compile(updated, "actor_group.py", "exec")
    return updated


def patch_worker(source):
    tree = ast.parse(source)
    actors = [
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "MegatronTrainRayActor"
    ]
    if len(actors) != 1:
        raise RuntimeError("Unsupported Slime source: expected MegatronTrainRayActor")
    actor = actors[0]
    if any(
        isinstance(n, ast.FunctionDef) and n.name == "_checkpoint_save_once"
        for n in actor.body
    ):
        if WORKER_METHOD.strip() not in source:
            raise RuntimeError("Unexpected existing checkpoint wrapper")
        return source
    if not any(
        isinstance(n, ast.FunctionDef) and n.name == "save_model" for n in actor.body
    ):
        raise RuntimeError("Unsupported Slime source: no worker save_model")
    lines = source.splitlines(keepends=True)
    lines.insert(actor.end_lineno, "\n" + WORKER_METHOD)
    updated = "".join(lines)
    compile(updated, "actor.py", "exec")
    return updated


def patch_train(source):
    """Evaluate restored final weights when no optimizer updates remain."""
    original = (
        "    if args.num_rollout == 0 and args.eval_interval is not None:\n"
        "        ray.get(rollout_manager.eval.remote(rollout_id=0))"
    )
    replacement = (
        "    # A completed final save can lose its reply before final evaluation.\n"
        "    if (args.num_rollout == 0 or args.start_rollout_id == args.num_rollout) and args.eval_interval is not None:\n"
        "        ray.get(rollout_manager.eval.remote(rollout_id=max(0, args.start_rollout_id - 1)))"
    )
    if replacement in source:
        return source
    if source.count(original) != 1:
        raise RuntimeError("Unsupported Slime final-checkpoint evaluation dispatch")
    updated = source.replace(original, replacement)
    compile(updated, "train.py", "exec")
    return updated


def install(root=Path("/root/slime")):
    root = Path(root)
    group = root / "slime/ray/actor_group.py"
    actor = root / "slime/backends/megatron_utils/actor.py"
    train = root / "train.py"
    updated_group = patch_group(group.read_text())
    updated_actor = patch_worker(actor.read_text())
    updated_train = patch_train(train.read_text())
    runtime = Path(__file__).with_name("checkpoint_rpc.py").read_text()
    compile(runtime, "checkpoint_rpc.py", "exec")
    (root / "slime/utils/checkpoint_rpc.py").write_text(runtime)
    group.write_text(updated_group)
    actor.write_text(updated_actor)
    train.write_text(updated_train)
    print("Installed bounded, deduplicated checkpoint RPC retries", flush=True)


if __name__ == "__main__":
    install()
