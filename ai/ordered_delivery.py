"""Dependency-neutral bounded worker for ordered background delivery."""

from __future__ import annotations

import logging
from queue import Full, Queue
from threading import Condition, Thread
import time
from typing import Callable, Generic, TypeVar


logger = logging.getLogger(__name__)
DeliveryItem = TypeVar("DeliveryItem")
_CLOSE = object()


class OrderedDeliveryTimeoutError(TimeoutError):
    """Raised when a bounded enqueue, flush, or close cannot complete."""


class OrderedDeliveryWorker(Generic[DeliveryItem]):
    """Deliver accepted items in FIFO order with bounded lifecycle waits."""

    def __init__(
        self,
        destination: Callable[[DeliveryItem], None],
        *,
        name: str,
        max_depth: int,
        submit_timeout_seconds: float = 1.0,
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        if submit_timeout_seconds <= 0:
            raise ValueError("submit_timeout_seconds must be positive")
        self._destination = destination
        self._queue: Queue[DeliveryItem | object] = Queue(max_depth)
        self._state_changed = Condition()
        self._accepting = True
        self._close_enqueued = False
        self._submitted = 0
        self._completed = 0
        self._submit_timeout_seconds = submit_timeout_seconds
        self._worker = Thread(
            target=self._deliver,
            name=name,
            daemon=True,
        )
        self._worker.start()

    @property
    def worker_alive(self) -> bool:
        """Return whether the delivery thread is still alive."""
        return self._worker.is_alive()

    def submit(self, item: DeliveryItem) -> None:
        """Accept one FIFO item or fail within the configured enqueue bound."""
        with self._state_changed:
            if not self._accepting:
                raise RuntimeError("ordered delivery worker is closed")
            try:
                self._queue.put(
                    item,
                    timeout=self._submit_timeout_seconds,
                )
            except Full as exc:
                raise OrderedDeliveryTimeoutError(
                    "ordered delivery queue remained full"
                ) from exc
            self._submitted += 1

    def flush(self, timeout_seconds: float) -> None:
        """Wait for all items accepted before this call."""
        deadline = self._deadline(timeout_seconds)
        with self._state_changed:
            target = self._submitted
            while self._completed < target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OrderedDeliveryTimeoutError(
                        "ordered delivery flush timed out"
                    )
                self._state_changed.wait(timeout=remaining)

    def close(self, timeout_seconds: float) -> None:
        """Drain accepted items and stop the worker within one deadline."""
        deadline = self._deadline(timeout_seconds)
        with self._state_changed:
            self._accepting = False
            if not self._close_enqueued and self._worker.is_alive():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OrderedDeliveryTimeoutError(
                        "ordered delivery close timed out before its barrier"
                    )
                try:
                    self._queue.put(_CLOSE, timeout=remaining)
                except Full as exc:
                    raise OrderedDeliveryTimeoutError(
                        "ordered delivery close barrier could not be queued"
                    ) from exc
                self._close_enqueued = True
        remaining = deadline - time.monotonic()
        if remaining > 0:
            self._worker.join(timeout=remaining)
        if self._worker.is_alive():
            raise OrderedDeliveryTimeoutError(
                f"ordered delivery worker {self._worker.name!r} did not stop"
            )

    @staticmethod
    def _deadline(timeout_seconds: float) -> float:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        return time.monotonic() + timeout_seconds

    def _deliver(self) -> None:
        while True:
            queued = self._queue.get()
            try:
                if queued is _CLOSE:
                    return
                try:
                    self._destination(queued)  # type: ignore[arg-type]
                except Exception:
                    logger.exception("ordered background delivery failed")
            finally:
                if queued is not _CLOSE:
                    with self._state_changed:
                        self._completed += 1
                        self._state_changed.notify_all()
                self._queue.task_done()
