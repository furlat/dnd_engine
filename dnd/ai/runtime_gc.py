"""Process-wide cyclic-GC coordination for AI runtimes."""

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


class RuntimeGcPolicy(Protocol):
    """Factory for one runtime's process-GC lease."""

    def acquire(self) -> RuntimeGcLease:
        """Acquire the process policy for one runtime lifetime."""


class AutomaticGcLease:
    """Suspend automatic cyclic collection under a process-wide lease."""

    def __init__(self) -> None:
        self._released = False

    @classmethod
    def acquire(cls) -> "AutomaticGcLease":
        """Acquire one nested-safe process-wide GC suspension lease."""
        global _active_leases, _restore_automatic_gc
        with _lease_lock:
            if _active_leases == 0:
                _restore_automatic_gc = gc.isenabled()
                if _restore_automatic_gc:
                    gc.disable()
            _active_leases += 1
        return cls()

    def release(self) -> None:
        """Restore automatic collection after the final owner releases."""
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
    """Suspend automatic collection for the lifetime of a runtime."""

    def acquire(self) -> RuntimeGcLease:
        return AutomaticGcLease.acquire()


class _PreserveAutomaticGcLease:
    """No-op lease used by embedding processes that own their GC policy."""

    def release(self) -> None:
        pass


class PreserveAutomaticGcPolicy:
    """Leave the embedding process's GC policy unchanged."""

    def acquire(self) -> RuntimeGcLease:
        return _PreserveAutomaticGcLease()


SUSPEND_AUTOMATIC_GC = SuspendAutomaticGcPolicy()
PRESERVE_AUTOMATIC_GC = PreserveAutomaticGcPolicy()


def automatic_gc_suspended() -> bool:
    """Return whether an active AI lease owns GC suspension."""
    with _lease_lock:
        return _active_leases > 0 and not gc.isenabled()
