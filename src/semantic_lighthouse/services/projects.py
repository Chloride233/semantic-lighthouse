"""Phase 14.1 — business pilot project stage helper.

Stage progression is backend-controlled:
  goal → data → model → validate → pilot

No skipping. No reversing. No external API in 14.1.
"""

from __future__ import annotations

_STAGE_ORDER = ("goal", "data", "model", "validate", "pilot")


def next_stage(current_stage: str) -> str | None:
    """Return the next valid stage, or None if already at pilot.

    Raises ValueError for unknown stages.
    """
    if current_stage not in _STAGE_ORDER:
        raise ValueError(f"Unknown stage: {current_stage!r}")
    idx = _STAGE_ORDER.index(current_stage)
    if idx >= len(_STAGE_ORDER) - 1:
        return None
    return _STAGE_ORDER[idx + 1]


def advance_stage(current_stage: str, target_stage: str) -> str:
    """Advance to target_stage if it follows the current stage in order.

    Returns target_stage on success.

    Raises ValueError if:
      - target_stage is not strictly the next stage
      - target_stage is earlier or equal to current_stage
      - either stage is unknown
    """
    if current_stage not in _STAGE_ORDER:
        raise ValueError(f"Unknown current stage: {current_stage!r}")
    if target_stage not in _STAGE_ORDER:
        raise ValueError(f"Unknown target stage: {target_stage!r}")

    current_idx = _STAGE_ORDER.index(current_stage)
    target_idx = _STAGE_ORDER.index(target_stage)

    if target_idx < current_idx:
        raise ValueError(
            f"Cannot move backward from {current_stage!r} to {target_stage!r}"
        )
    if target_idx == current_idx:
        raise ValueError(
            f"Already at stage {current_stage!r}"
        )
    if target_idx > current_idx + 1:
        raise ValueError(
            f"Cannot skip from {current_stage!r} to {target_stage!r}. "
            f"Next valid stage is {_STAGE_ORDER[current_idx + 1]!r}"
        )

    return target_stage
