"""Host-aware worker selection for isolated policy-promotion matches."""

from __future__ import annotations

import math
import os


DEFAULT_CPU_UTILIZATION = 0.75


def available_logical_cpu_count() -> int:
    """Return the logical CPUs available to this process and its workers."""
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    return max(1, os.cpu_count() or 1)


def recommended_promotion_worker_count(
    logical_cpu_count: int | None = None,
    *,
    utilization: float = DEFAULT_CPU_UTILIZATION,
) -> int:
    """Choose broad CPU use while retaining headroom for the host and UI.

    Promotion matches are single-threaded, disposable processes. Using 75 percent
    of the available logical CPUs normally occupies every physical core on an SMT
    host while leaving capacity for the coordinator, WSL, and interactive clients.
    """
    available = logical_cpu_count if logical_cpu_count is not None else available_logical_cpu_count()
    if available < 1:
        raise ValueError("logical_cpu_count must be at least one.")
    if not 0.0 < utilization <= 1.0:
        raise ValueError("utilization must be in the interval (0, 1].")
    return max(1, min(available, math.floor(available * utilization)))


def resolve_promotion_worker_count(worker_count: int | None) -> int:
    """Resolve an explicit worker limit or the host-aware automatic default."""
    if worker_count is None:
        return recommended_promotion_worker_count()
    if worker_count < 1:
        raise ValueError("worker_count must be at least one.")
    return worker_count
