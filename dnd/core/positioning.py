"""Typed failure facts for the existing entity-position commit boundary."""


class PositionCommitError(RuntimeError):
    """Position staging failed and every positional owner was restored."""

    position_committed = False

    def __init__(self, cause: BaseException):
        self.cause = cause
        super().__init__(f"position staging failed: {cause}")


class PositionPublicationError(RuntimeError):
    """Position committed, but a subsequent spatial publication failed."""

    position_committed = True

    def __init__(self, cause: BaseException):
        self.cause = cause
        super().__init__(f"committed position publication failed: {cause}")
