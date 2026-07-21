"""Non-blocking delivery for canonical policy telemetry."""

from __future__ import annotations

import logging
from queue import Queue
from threading import Lock, Thread
from typing import Protocol

from ai.policy.contracts import PolicyDecisionTelemetry


logger = logging.getLogger(__name__)
_CLOSE = object()


class PolicyTelemetryDestination(Protocol):
    """Synchronous destination receiving canonical policy events."""

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Deliver one canonical policy decision."""
        ...


class QueuedPolicyTelemetrySink:
    """Move telemetry serialization and transport off the decision path.

    Events retain their source order. ``flush()`` is the explicit durability
    boundary used by artifact collection and controller shutdown.
    """

    def __init__(
        self,
        destination: PolicyTelemetryDestination,
        *,
        max_depth: int = 256,
    ) -> None:
        """Create a bounded delivery queue.

        Args:
            destination: Synchronous telemetry transport run by the worker.
            max_depth: Maximum undelivered canonical decisions. Producers
                apply backpressure only if this exceptional bound is reached.
        """
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self.destination = destination
        self._queue: Queue[PolicyDecisionTelemetry | object] = Queue(max_depth)
        self._state_lock = Lock()
        self._closed = False
        self._worker = Thread(
            target=self._deliver,
            name="policy-telemetry-delivery",
            daemon=True,
        )
        self._worker.start()

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Enqueue one immutable decision without serializing its payload."""
        with self._state_lock:
            if self._closed:
                raise RuntimeError("policy telemetry sink is closed")
            self._queue.put(event)

    def flush(self) -> None:
        """Wait until every previously enqueued decision is delivered."""
        self._queue.join()

    def close(self) -> None:
        """Flush pending decisions and stop the delivery worker once."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._queue.put(_CLOSE)
        self._worker.join()

    def _deliver(self) -> None:
        """Deliver queued decisions in strict source order."""
        while True:
            queued = self._queue.get()
            try:
                if queued is _CLOSE:
                    return
                assert isinstance(queued, PolicyDecisionTelemetry)
                try:
                    self.destination.emit_policy_decision(queued)
                except Exception:
                    logger.exception("policy telemetry delivery failed")
            finally:
                self._queue.task_done()
