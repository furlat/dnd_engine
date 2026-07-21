"""Process-level performance policy for latency-sensitive agent runtimes."""

from __future__ import annotations

from contextlib import contextmanager
import gc
from typing import Iterator


MINIMUM_FULL_COLLECTION_INTERVAL = 1000


@contextmanager
def latency_sensitive_gc() -> Iterator[None]:
    """Defer expensive full-heap scans while preserving young collections.

    The engine retains a large live Pydantic object graph. CPython's default
    generation-two cadence repeatedly scans that graph during short turns even
    when no old cyclic garbage exists. Process entrypoints use this scope so
    generation-zero and generation-one cleanup remain automatic while full
    scans move outside normal gameplay cadence.

    Yields:
        Control with latency-oriented garbage-collection thresholds active.
    """
    previous = gc.get_threshold()
    gc.collect(2)
    gc.set_threshold(
        previous[0],
        previous[1],
        max(previous[2], MINIMUM_FULL_COLLECTION_INTERVAL),
    )
    try:
        yield
    finally:
        gc.set_threshold(*previous)
