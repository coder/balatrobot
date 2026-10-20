"""Four-GPU regression in the pinned image; no model or game is loaded.

Run through pipeline_group_modal.py. An independent pipeline pair must work
while the other pair waits on CPU, including after Slime offload/reload.
"""

import ast
import faulthandler
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import torch
import torch.distributed as dist
import torch.multiprocessing as mp


def worker(rank, rendezvous, patched):
    faulthandler.dump_traceback_later(60, repeat=False)
    from patch_pipeline_group import patch_source
    from slime.utils import reloadable_process_group as reloadable
    from slime.utils.distributed_utils import get_gloo_group, init_gloo_group

    torch.cuda.set_device(rank)
    dist.init_process_group(
        "nccl",
        init_method="file://" + rendezvous,
        rank=rank,
        world_size=4,
        timeout=timedelta(seconds=20),
    )
    init_gloo_group()
    reloadable.register_default_process_group(timedelta(seconds=20))
    reloadable.monkey_patch_torch_dist()
    groups = [dist.new_group(ranks=ranks, backend="nccl") for ranks in ([0, 1], [2, 3])]
    group = groups[rank // 2]
    source = Path(
        "/root/Megatron-LM/megatron/core/pipeline_parallel/p2p_communication.py"
    ).read_text()
    if patched:
        source = patch_source(source)
    tree = ast.parse(source)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_batched_p2p_ops"
    )
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            fn,
        ],
        type_ignores=[],
    )
    namespace = {"torch": torch}
    exec(
        compile(ast.fix_missing_locations(module), "p2p_communication.py", "exec"),
        namespace,
    )
    transfer = namespace["_batched_p2p_ops"]
    print(f"READY rank={rank} patched={patched}", flush=True)
    transfers = 0
    for generation in range(3):
        # Only one pair initializes/uses its communicator at a time. With the
        # image defect, the first pair tries to initialize all of WORLD and hangs.
        for pair in (0, 1):
            if rank // 2 == pair:
                for step in range(12):
                    size = (step + 1) * 1024
                    sender = rank % 2 == step % 2
                    value = generation * 100 + step
                    tensor = torch.full(
                        (size,), float(value) if sender else -1.0, device="cuda"
                    )
                    kwargs = {
                        "tensor_" + name: None
                        for name in ("send_prev", "recv_prev", "send_next", "recv_next")
                    }
                    direction = "next" if rank % 2 == 0 else "prev"
                    kwargs["tensor_" + ("send_" if sender else "recv_") + direction] = (
                        tensor
                    )
                    if step == 0:
                        print(
                            f"TRANSFER rank={rank} generation={generation} pair={pair} patched={patched}",
                            flush=True,
                        )
                    reqs = transfer(
                        group=group,
                        prev_pipeline_rank=rank ^ 1,
                        next_pipeline_rank=rank ^ 1,
                        **kwargs,
                    )
                    for req in reqs:
                        req.wait()
                    torch.cuda.synchronize()
                    assert torch.all(tensor == value).item()
                    transfers += 1
            dist.barrier(group=get_gloo_group())
        if generation < 2:
            reloadable.destroy_process_groups()
            reloadable.reload_process_groups()
    print(
        f"PASS rank={rank} transfers={transfers} reloads=2 patched={patched}",
        flush=True,
    )
    faulthandler.cancel_dump_traceback_later()
    dist.barrier(group=get_gloo_group())
    dist.destroy_process_group()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as root:
        mp.spawn(
            worker,
            args=(str(Path(root) / "rendezvous"), "--patched" in sys.argv),
            nprocs=4,
            join=True,
        )
