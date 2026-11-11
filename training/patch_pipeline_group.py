"""Restore Megatron's pipeline group argument in the pinned Slime image.

The image drops the fourth P2POp argument in _batched_p2p_ops, so payloads
use WORLD while shapes use the pipeline subgroup. Keep independent pipelines
on their own communicators, as in upstream Megatron.
"""

import ast
from pathlib import Path


def patch_source(source: str) -> str:
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_batched_p2p_ops"
    ]
    if len(functions) != 1:
        raise RuntimeError("Unsupported Megatron source: expected _batched_p2p_ops")
    calls = [
        node
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "P2POp"
    ]
    if len(calls) != 4:
        raise RuntimeError("Unsupported Megatron source: expected four pipeline P2POps")
    missing = []
    for call in calls:
        if call.keywords or len(call.args) not in (3, 4):
            raise RuntimeError("Unsupported pipeline P2POp signature")
        if len(call.args) == 4:
            if not isinstance(call.args[3], ast.Name) or call.args[3].id != "group":
                raise RuntimeError("Unexpected pipeline P2POp group")
        else:
            missing.append(call)
    if not missing:
        return source
    if len(missing) != 4:
        raise RuntimeError("Partially patched pipeline source")
    lines = source.splitlines(keepends=True)
    # Insert at the end of the peer argument, retaining all original formatting.
    for call in sorted(
        missing, key=lambda node: (node.lineno, node.col_offset), reverse=True
    ):
        peer = call.args[2]
        index, column = peer.end_lineno - 1, peer.end_col_offset
        lines[index] = lines[index][:column] + ", group" + lines[index][column:]
    updated = "".join(lines)
    compile(updated, "p2p_communication.py", "exec")
    return updated


def install(root=Path("/root/Megatron-LM")):
    path = Path(root) / "megatron/core/pipeline_parallel/p2p_communication.py"
    source = path.read_text()
    updated = patch_source(source)
    if updated != source:
        path.write_text(updated)
    print(
        "Validated pipeline P2POps: all four use the pipeline process group", flush=True
    )


if __name__ == "__main__":
    install()
