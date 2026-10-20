"""CPU regression against trainer source; set MODAL_DOJO_SLIME_SOURCE."""

import importlib.util
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from types import ModuleType
import torch.distributed as dist
import torch.multiprocessing as mp


def worker(rank, rendezvous):
    from modal_dojo.common import torch_dist_checkpoint as ckpt

    for name in ["slime", "slime.utils"]:
        sys.modules[name] = ModuleType(name)
    memory = ModuleType("slime.utils.memory_utils")
    memory.available_memory = lambda: {"free_GB": 100}
    memory.clear_memory = lambda: None
    memory.print_memory = lambda *a: {}
    sys.modules[memory.__name__] = memory
    for name in ["distributed_utils", "reloadable_process_group"]:
        full = "slime.utils." + name
        spec = importlib.util.spec_from_file_location(
            full,
            str(
                Path(os.environ["MODAL_DOJO_SLIME_SOURCE"]) / "utils" / (name + ".py")
            ),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full] = module
        spec.loader.exec_module(module)
    reloadable = sys.modules["slime.utils.reloadable_process_group"]
    dist.init_process_group(
        "gloo", init_method="file://" + rendezvous, rank=rank, world_size=2
    )
    reloadable.register_default_process_group(timedelta(seconds=30))
    reloadable.monkey_patch_torch_dist()
    # Reproduce the exact failure from the previous implementation.
    proxy = dist.new_group(backend="gloo")
    try:
        dist.destroy_process_group(proxy)
    except ValueError as error:
        assert "Invalid process group" in str(error)
    else:
        raise AssertionError("Expected old cleanup to fail")
    dist.destroy_process_group(proxy.group)
    reloadable.ReloadableProcessGroup.GROUPS[os.getpid()].remove(proxy)
    os.environ["LOCAL_RANK"] = "0"
    os.environ["MODAL_DOJO_CHECKPOINTS_VOLUME_NAME"] = "test"
    ckpt._commit_volume = lambda name: None
    ckpt._validate_committed_checkpoint = lambda *args: None
    for _ in range(3):
        ckpt.commit_latest_checkpoint_volume("/test")
        assert not reloadable.ReloadableProcessGroup.GROUPS[os.getpid()]
    dist.barrier()
    dist.destroy_process_group()
    print(
        f"rank {rank}: old error reproduced; three corrected saves passed", flush=True
    )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as root:
        mp.spawn(worker, args=(str(Path(root) / "rendezvous"),), nprocs=2, join=True)
