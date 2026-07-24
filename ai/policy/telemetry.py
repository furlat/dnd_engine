"""Non-blocking delivery for canonical policy telemetry."""

from __future__ import annotations

from typing import Protocol

from ai.ordered_delivery import OrderedDeliveryWorker
from ai.policy.contracts import PolicyDecisionTelemetry


DEFAULT_TELEMETRY_CLOSE_TIMEOUT_SECONDS = 4.0


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
        session_id = str(getattr(destination, "session_id", "unscoped"))
        self._delivery = OrderedDeliveryWorker(
            destination.emit_policy_decision,
            name=f"policy-telemetry-{session_id}",
            max_depth=max_depth,
        )

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Enqueue one immutable decision without serializing its payload."""
        self._delivery.submit(event)

    def flush(
        self,
        timeout_seconds: float = DEFAULT_TELEMETRY_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        """Wait until every previously enqueued decision is delivered."""
        self._delivery.flush(timeout_seconds)

    def close(
        self,
        timeout_seconds: float = DEFAULT_TELEMETRY_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        """Flush pending decisions and stop the delivery worker once."""
        self._delivery.close(timeout_seconds)

    @property
    def worker_alive(self) -> bool:
        """Return whether the delivery worker remains alive."""
        return self._delivery.worker_alive
