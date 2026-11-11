"""Token-aligned Balatro returns for the pinned Slime trainer.

Executed at image build to install this module and transport train_metadata.
No GPU or game dependencies are needed to validate the spans or install it.
"""

import math
from pathlib import Path


def expand_advantages(spans, loss_mask):
    """Reject gaps/overlaps: exactly the generated action tokens receive credit."""
    values = [0.0] * len(loss_mask)
    covered = [False] * len(loss_mask)
    for span in spans:
        start, end, value = span["start"], span["end"], float(span["advantage"])
        if not (isinstance(start, int) and isinstance(end, int)
                and 0 <= start < end <= len(values) and math.isfinite(value)):
            raise ValueError("Invalid Balatro advantage span")
        for index in range(start, end):
            if covered[index] or not loss_mask[index]:
                raise ValueError("Overlapping advantage span or credit on environment feedback")
            covered[index] = True
            values[index] = value
    if covered != [bool(x) for x in loss_mask]:
        raise ValueError("Balatro advantage spans do not cover every action token")
    return values


def compute_advantages(args, rollout_data):
    """Slime's native custom-advantage hook; preserves CP slicing and loss masks."""
    if args.kl_coef != 0:
        raise ValueError("Balatro reward-to-go expects kl_coef=0; use the separate KL loss")
    if getattr(args, "normalize_advantages", False):
        raise ValueError("Action credit requires normalize_advantages=False to preserve invalid-action penalties")
    import torch
    from slime.backends.megatron_utils.cp_utils import slice_log_prob_with_cp
    metadata = rollout_data.get("metadata")
    if metadata is None or len(metadata) != len(rollout_data["response_lengths"]):
        raise ValueError("Missing Balatro action advantages in the training batch")
    advantages = []
    for item, mask, length, total, kl in zip(
        metadata, rollout_data["loss_masks"], rollout_data["response_lengths"],
        rollout_data["total_lengths"], rollout_data["kl"], strict=True,
    ):
        if not item or "balatro_action_advantages" not in item or len(mask) != length:
            raise ValueError("Missing or misaligned Balatro action advantages")
        values = expand_advantages(item["balatro_action_advantages"], mask.tolist())
        tensor = torch.tensor(values, dtype=torch.float32, device=kl.device)
        local = slice_log_prob_with_cp(tensor, total, length)
        if local.shape != kl.shape:
            raise ValueError("Balatro advantages and trainer context-parallel chunks differ")
        advantages.append(local)
    rollout_data["advantages"] = advantages
    rollout_data["returns"] = [value.clone() for value in advantages]


def install(root=Path("/root/slime")):
    """Fail closed on a changed trainer; native hook must exist before patching."""
    root = Path(root)
    loss = (root / "slime/backends/megatron_utils/loss.py").read_text()
    if "custom_advantage_function_path" not in loss:
        raise RuntimeError("Pinned trainer lacks the custom advantage hook")
    patches = [
        (root / "slime/ray/rollout.py",
         '            rollout_data = {"partition": partition}\n            for key in [\n',
         '            rollout_data = {"partition": partition}\n            for key in [\n'
         '                "metadata",  # BALATRO_TRAIN_METADATA\n',
         "BALATRO_TRAIN_METADATA"),
        (root / "slime/backends/megatron_utils/data.py",
         '        for key, val in rollout_data.items():\n            if key in [\n',
         '        for key, val in rollout_data.items():\n            if key in [\n'
         '                "metadata",  # BALATRO_METADATA_NOT_A_METRIC\n',
         "BALATRO_METADATA_NOT_A_METRIC"),
    ]
    updates = []
    for path, before, after, marker in patches:
        source = path.read_text()
        if marker in source:
            continue
        if source.count(before) != 1:
            raise RuntimeError(f"Unsupported trainer source: {path}")
        updated = source.replace(before, after, 1)
        compile(updated, str(path), "exec")
        updates.append((path, updated))
    for path, updated in updates:
        path.write_text(updated)
    destination = root / "balatro_credit.py"
    if destination.resolve() != Path(__file__).resolve():
        destination.write_text(Path(__file__).read_text())


if __name__ == "__main__":
    install()
