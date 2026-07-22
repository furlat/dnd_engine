"""Typed failures raised by the game-directory control plane."""


class DirectoryError(RuntimeError):
    """Base class for game-directory failures."""


class MigrationError(DirectoryError):
    """Raised when the database migration history is invalid."""


class NotFoundError(DirectoryError):
    """Raised when a requested directory record does not exist."""


class ConflictError(DirectoryError):
    """Raised when a uniqueness or lifecycle invariant is violated."""


class StaleVersionError(ConflictError):
    """Raised when compare-and-swap lifecycle state is stale."""


class ImmutableRecordError(ConflictError):
    """Raised when immutable evidence is replaced with different content."""


class CapabilityError(DirectoryError):
    """Raised when a capability is invalid, expired, exhausted, or revoked."""


class HotPathDatabaseAccessError(DirectoryError):
    """Raised before a database operation inside a declared hot path."""


class InjectedRepositoryFailure(DirectoryError):
    """Raised by the repository fail-injection guard used in tests."""
