"""CPU fault injection using the pinned image's Ray and Gloo collectives."""

import ast
import inspect
import json
import os
import socket
import tempfile
import time
from pathlib import Path

import ray
import torch
import torch.distributed as dist
from slime.utils.checkpoint_rpc import save_group


def extracted_method(path, class_name, method_name):
    tree = ast.parse(Path(path).read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name
    )
    namespace = {"ray": ray}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
            path,
            "exec",
        ),
        namespace,
    )
    return namespace[method_name]


class Worker:
    def __init__(self, rank, rendezvous, root):
        from datetime import timedelta

        torch.set_num_threads(1)
        dist.init_process_group(
            "gloo",
            init_method=rendezvous,
            rank=rank,
            world_size=2,
            timeout=timedelta(seconds=30),
        )
        self.rank, self.root, self.count = rank, root, 0

    def save_model(self, rollout_id, force_sync=False):
        self.count += 1
        if rollout_id == -1:
            raise ValueError("injected disk failure")
        if rollout_id == -2:
            os._exit(1)
        dist.barrier()
        time.sleep(0.2)
        torch.save(
            {"step": rollout_id, "count": self.count},
            f"{self.root}/rank-{self.rank}.pt",
        )
        dist.barrier()

    def counts(self):
        return self.count


Worker._checkpoint_save_once = extracted_method(
    "/root/slime/slime/backends/megatron_utils/actor.py",
    "MegatronTrainRayActor",
    "_checkpoint_save_once",
)


class Group:
    def __init__(self, actors):
        self._actor_handlers = actors

    def _release_train_enabled(self):
        return False


Group.save_model = extracted_method(
    "/root/slime/slime/ray/actor_group.py", "RayTrainGroup", "save_model"
)


def main():
    ray.init(
        num_cpus=4,
        object_store_memory=128 * 1024 * 1024,
        include_dashboard=False,
        log_to_driver=False,
    )
    real_get = ray.get
    results = []
    # The exception is injected at the driver transport boundary, not raised
    # inside the worker method (which would instead be a RayTaskError).
    print(
        "ActorUnavailableError",
        inspect.signature(ray.exceptions.ActorUnavailableError),
        flush=True,
    )
    for mode in (
        "before",
        "during",
        "after",
        "application_error",
        "worker_death",
        "exhausted",
    ):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as root:
            cls = ray.remote(
                num_cpus=1, max_restarts=0, max_concurrency=1, max_task_retries=0
            )(Worker)
            actors = [cls.remote(i, f"tcp://127.0.0.1:{port}", root) for i in range(2)]
            real_get([a.counts.remote() for a in actors], timeout=40)
            injected = {}
            submissions = [0, 0]

            class Method:
                def __init__(self, index):
                    self.index = index

                def options(self, **kwargs):
                    self.kwargs = kwargs
                    return self

                def remote(self, *args, **kwargs):
                    index = self.index
                    submissions[index] += 1
                    fail = index == 1 and (
                        submissions[index] == 1 or mode == "exhausted"
                    )
                    if fail and mode in ("before", "exhausted"):
                        ref = ray.put(None)
                    else:
                        ref = (
                            actors[index]
                            ._checkpoint_save_once.options(**self.kwargs)
                            .remote(*args, **kwargs)
                        )
                        if fail and mode == "during":
                            # Lose the response while the original is still in flight.
                            ref = ray.put(None)
                    if fail and mode in ("before", "during", "after", "exhausted"):
                        injected[ref] = True
                    return ref

            class Proxy:
                def __init__(self, index):
                    self._checkpoint_save_once = Method(index)

            def transport_get(ref, *args, **kwargs):
                value = real_get(ref, *args, **kwargs)
                if ref in injected:
                    del injected[ref]
                    raise ray.exceptions.ActorUnavailableError(
                        "injected RPC connection reset", b"\x01" * 16
                    )
                return value

            ray.get = transport_get
            expected_error = None
            try:
                proxies = [Proxy(i) for i in range(2)]
                if mode == "application_error":
                    expected_error = ray.exceptions.RayTaskError
                    save_group(proxies, -1, retry_delay=0.01, timeout=10)
                elif mode == "worker_death":
                    expected_error = ray.exceptions.RayActorError
                    save_group(proxies, -2, retry_delay=0.01, timeout=20)
                elif mode == "exhausted":
                    expected_error = ray.exceptions.ActorUnavailableError
                    save_group(proxies, 19, max_retries=2, retry_delay=0.01, timeout=10)
                else:
                    # Exercise the patched Slime group method, including its
                    # unchanged post-save work, with the default retry policy.
                    Group(proxies).save_model(19, force_sync=True)
                assert expected_error is None, "Expected failure was swallowed"
            except Exception as exc:
                if expected_error is None or not isinstance(exc, expected_error):
                    raise
            finally:
                ray.get = real_get
            result = {"mode": mode, "submissions": submissions}
            if expected_error is None:
                counts = real_get([a.counts.remote() for a in actors], timeout=10)
                assert counts == [1, 1], counts
                assert submissions == [1, 2], submissions
                for rank in range(2):
                    assert torch.load(f"{root}/rank-{rank}.pt", weights_only=True) == {
                        "step": 19,
                        "count": 1,
                    }
                # Both actors must still communicate after recovery.
                Group(actors).save_model(29, force_sync=True)
                assert real_get([a.counts.remote() for a in actors]) == [2, 2]
                result["save_counts_after_recovery"] = counts
                result["next_collective_passed"] = True
            else:
                result["surfaced"] = expected_error.__name__
                if mode == "application_error":
                    assert submissions == [1, 1]
                if mode == "exhausted":
                    assert submissions == [1, 3]
            for actor in actors:
                ray.kill(actor)
            results.append(result)
            print(json.dumps(result), flush=True)
    ray.shutdown()
    print(
        json.dumps(
            {"passed": len(results), "ray_version": ray.__version__, "results": results}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
