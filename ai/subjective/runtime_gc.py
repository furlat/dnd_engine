"""Process-wide cyclic-GC coordination for latency-sensitive agent runtimes."""

from __future__ import annotations

import gc
from threading import Lock
from typing import Protocol


_lease_lock = Lock()
_active_leases = 0
_restore_automatic_gc = False


class RuntimeGcLease(Protocol):
    """One acquired process-GC policy lease."""

    def release(self) -> None:
        """Release the policy exactly once."""
        ...


class RuntimeGcPolicy(Protocol):
    """Factory for one runtime's process-GC lease."""

    def acquire(self) -> RuntimeGcLease:
        """Acquire the process policy for one runtime lifetime."""
        ...


class AutomaticGcLease:
    """Suspend automatic cyclic collection while agent runtimes are active.

    Subjective runtime state is bounded and overwhelmingly acyclic. Reference
    counting therefore reclaims obsolete frames immediately, while an
    automatic cyclic scan can otherwise pause a decision stream for hundreds
    of milliseconds. The lease is process-wide because CPython's GC switch is
    process-wide; nested runtimes share one suspension and the final release
    restores the caller's original setting.
    """

    def __init__(self) -> None:
        self._released = False

    @classmethod
    def acquire(cls) -> "AutomaticGcLease":
        """Acquire one process-wide low-latency runtime lease."""
        global _active_leases, _restore_automatic_gc
        with _lease_lock:
            if _active_leases == 0:
                _restore_automatic_gc = gc.isenabled()
                if _restore_automatic_gc:
                    gc.disable()
            _active_leases += 1
        return cls()

    def release(self) -> None:
        """Release this lease and restore automatic GC after the last owner."""
        global _active_leases, _restore_automatic_gc
        with _lease_lock:
            if self._released:
                return
            self._released = True
            _active_leases -= 1
            if _active_leases == 0:
                if _restore_automatic_gc:
                    gc.enable()
                _restore_automatic_gc = False


class SuspendAutomaticGcPolicy:
    """Use the external-process low-latency GC policy."""

    def acquire(self) -> RuntimeGcLease:
        """Suspend automatic cyclic collection for one runtime lifetime."""
        return AutomaticGcLease.acquire()


class _PreserveAutomaticGcLease:
    """No-op lease that leaves the embedding process policy untouched."""

    def release(self) -> None:
        """Preserve the process policy on release."""


class PreserveAutomaticGcPolicy:
    """Keep the embedding process's automatic-GC setting unchanged."""

    def acquire(self) -> RuntimeGcLease:
        """Acquire a no-op lease."""
        return _PreserveAutomaticGcLease()


SUSPEND_AUTOMATIC_GC = SuspendAutomaticGcPolicy()
PRESERVE_AUTOMATIC_GC = PreserveAutomaticGcPolicy()


def automatic_gc_suspended() -> bool:
    """Return whether a runtime lease currently owns GC suspension."""
    with _lease_lock:
        return _active_leases > 0 and not gc.isenabled()
