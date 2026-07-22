"""Low-level SQLite ownership and repository access instrumentation."""

from __future__ import annotations

import sqlite3
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from server.game_directory.contracts import RepositoryMetrics
from server.game_directory.errors import (
    HotPathDatabaseAccessError,
    InjectedRepositoryFailure,
)
from server.game_directory.migrations import apply_migrations, configure_connection

_HOT_PATH_DEPTH: ContextVar[int] = ContextVar("game_directory_hot_path_depth", default=0)
_FAILURE_DEPTH: ContextVar[int] = ContextVar("game_directory_failure_depth", default=0)


class DirectoryDatabase:
    """Own one configured SQLite connection for the directory gateway.

    The class deliberately exposes no engine-facing API. Its guards make an
    accidental repository call from an annotated hot path fail before SQLite
    is touched.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int,
        migration_time: datetime,
    ) -> None:
        """Open, configure, and migrate a game-directory database.

        Args:
            path: SQLite database file path.
            busy_timeout_ms: Maximum SQLite lock wait in milliseconds.
            migration_time: UTC timestamp used for pending migrations.
        """

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            configure_connection(self._connection, busy_timeout_ms)
            apply_migrations(self._connection, migration_time)
        except Exception:
            self._connection.close()
            raise
        self._lock = RLock()
        self._metrics_lock = RLock()
        self._total_operations = 0
        self._successful_operations = 0
        self._failed_operations = 0
        self._blocked_hot_path_operations = 0
        self._injected_failures = 0
        self._by_operation: Counter[str] = Counter()
        self._closed = False

    @contextmanager
    def read(self, operation_name: str) -> Iterator[sqlite3.Connection]:
        """Yield the connection for one instrumented read operation."""

        self._before_operation(operation_name)
        try:
            with self._lock:
                self._ensure_open()
                yield self._connection
        except Exception:
            self._record_failure()
            raise
        else:
            self._record_success()

    @contextmanager
    def transaction(self, operation_name: str) -> Iterator[sqlite3.Connection]:
        """Yield the connection inside an explicit immediate transaction."""

        self._before_operation(operation_name)
        try:
            with self._lock:
                self._ensure_open()
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    yield self._connection
                except Exception:
                    self._connection.execute("ROLLBACK")
                    raise
                else:
                    self._connection.execute("COMMIT")
        except Exception:
            self._record_failure()
            raise
        else:
            self._record_success()

    @contextmanager
    def forbid_hot_path_access(self) -> Iterator[None]:
        """Reject repository operations in the current execution context.

        This guard is intended to wrap gameplay command/event/stream paths in
        integration tests. It uses a context variable, so concurrent cold
        control-plane work in another task or thread is unaffected.
        """

        token = _HOT_PATH_DEPTH.set(_HOT_PATH_DEPTH.get() + 1)
        try:
            yield
        finally:
            _HOT_PATH_DEPTH.reset(token)

    @contextmanager
    def inject_failures(self) -> Iterator[None]:
        """Fail every repository operation before SQLite access.

        Runtime integration tests can arm this guard after attachment and
        prove that live gameplay remains independent of the directory.
        """

        token = _FAILURE_DEPTH.set(_FAILURE_DEPTH.get() + 1)
        try:
            yield
        finally:
            _FAILURE_DEPTH.reset(token)

    def metrics(self) -> RepositoryMetrics:
        """Return an immutable snapshot of repository-operation counters."""

        with self._metrics_lock:
            return RepositoryMetrics(
                total_operations=self._total_operations,
                successful_operations=self._successful_operations,
                failed_operations=self._failed_operations,
                blocked_hot_path_operations=self._blocked_hot_path_operations,
                injected_failures=self._injected_failures,
                by_operation=dict(self._by_operation),
            )

    def reset_metrics(self) -> None:
        """Reset operation counters without accessing SQLite."""

        with self._metrics_lock:
            self._total_operations = 0
            self._successful_operations = 0
            self._failed_operations = 0
            self._blocked_hot_path_operations = 0
            self._injected_failures = 0
            self._by_operation.clear()

    def close(self) -> None:
        """Close the owned SQLite connection idempotently."""

        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def _before_operation(self, operation_name: str) -> None:
        """Record and authorize an operation before acquiring SQLite."""

        with self._metrics_lock:
            self._total_operations += 1
            self._by_operation[operation_name] += 1
            if _HOT_PATH_DEPTH.get() > 0:
                self._failed_operations += 1
                self._blocked_hot_path_operations += 1
                raise HotPathDatabaseAccessError(
                    f"Directory operation '{operation_name}' attempted in a hot runtime path"
                )
            if _FAILURE_DEPTH.get() > 0:
                self._failed_operations += 1
                self._injected_failures += 1
                raise InjectedRepositoryFailure(
                    f"Injected failure before directory operation '{operation_name}'"
                )

    def _record_success(self) -> None:
        """Record one completed operation."""

        with self._metrics_lock:
            self._successful_operations += 1

    def _record_failure(self) -> None:
        """Record one operation that failed after guard checks."""

        with self._metrics_lock:
            self._failed_operations += 1

    def _ensure_open(self) -> None:
        """Reject operations after repository shutdown."""

        if self._closed:
            raise RuntimeError("Game-directory database is closed")
