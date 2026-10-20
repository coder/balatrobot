"""Retry lost checkpoint RPCs without repeating completed distributed saves.

Training actors must remain single-threaded and must not restart in place: the
completion records live alongside their model/optimizer state. A dead actor or
an application error still requires recovery of the whole training group.
"""

import logging
import math
import time
import uuid

logger = logging.getLogger(__name__)


def save_once(actor, operation_id, rollout_id, force_sync=False):
    """Actor-side acknowledgement cache; one collective per operation ID."""
    records = actor.__dict__.setdefault("_checkpoint_rpc_records", {})
    arguments = (rollout_id, force_sync)
    if operation_id in records:
        saved_arguments, state, value = records[operation_id]
        if saved_arguments != arguments:
            raise ValueError("Checkpoint operation ID reused with different arguments")
        if state != "complete":
            raise RuntimeError(
                f"Checkpoint operation is {state}; group recovery required"
            )
        return value
    records[operation_id] = (arguments, "incomplete", None)
    try:
        value = actor.save_model(rollout_id, force_sync=force_sync)
    except BaseException:
        records[operation_id] = (arguments, "failed", None)
        raise
    records[operation_id] = (arguments, "complete", value)
    return value


def save_group(
    actors,
    rollout_id,
    force_sync=False,
    *,
    max_retries=5,
    retry_delay=2.0,
    timeout=1800.0,
):
    """Resubmit only unavailable RPCs, retaining the same operation ID.

    Consume whichever worker finishes first. Waiting on workers sequentially
    could hide an unavailable worker behind peers blocked in its collective.
    Never retry a RayTaskError, worker death, or a mere get timeout: those do
    not establish a recoverable lost acknowledgement.
    """
    import ray

    if (
        not isinstance(max_retries, int)
        or max_retries < 0
        or not math.isfinite(retry_delay)
        or retry_delay < 0
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("Checkpoint retry bounds must be finite and nonnegative")
    operation_id = uuid.uuid4().hex
    deadline = time.monotonic() + timeout
    pending = {}
    scheduled = {}
    retries = [0] * len(actors)
    results = [None] * len(actors)

    def submit(index):
        # Explicitly disable Ray's own resubmission. Only this coordinator may
        # retry, and the worker must not restart with an empty completion cache.
        ref = (
            actors[index]
            ._checkpoint_save_once.options(max_task_retries=0)
            .remote(operation_id, rollout_id, force_sync=force_sync)
        )
        pending[ref] = index

    for index in range(len(actors)):
        submit(index)
    while pending or scheduled:
        now = time.monotonic()
        if now >= deadline:
            raise TimeoutError(
                f"Checkpoint {rollout_id} did not complete on all workers within {timeout}s"
            )
        for index, due in list(scheduled.items()):
            if due <= now:
                del scheduled[index]
                submit(index)
        wait_seconds = min(1.0, deadline - now)
        if scheduled:
            wait_seconds = min(wait_seconds, max(0.0, min(scheduled.values()) - now))
        if not pending:
            time.sleep(wait_seconds)
            continue
        ready, _ = ray.wait(list(pending), num_returns=1, timeout=wait_seconds)
        for ref in ready:
            index = pending.pop(ref)
            try:
                results[index] = ray.get(ref)
            except ray.exceptions.RayTaskError:
                # Ray may make this also inherit the exception raised inside
                # the method. An application-raised ActorUnavailableError is
                # not evidence that this save's request/reply was lost.
                raise
            except ray.exceptions.ActorUnavailableError:
                if retries[index] >= max_retries:
                    raise
                delay = min(retry_delay * 2 ** retries[index], 30.0)
                retries[index] += 1
                scheduled[index] = time.monotonic() + delay
                logger.warning(
                    "Checkpoint %s worker %s RPC unavailable; retry %s/%s in %.1fs "
                    "with operation %s (completed saves are acknowledged without rerunning)",
                    rollout_id,
                    index,
                    retries[index],
                    max_retries,
                    delay,
                    operation_id,
                )
    return results
