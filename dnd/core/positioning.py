"""Typed failures at the Entity position commit boundary."""


class PositionCommitError(RuntimeError):
    """Position staging failed and objective state was restored."""

    position_committed = False

    def __init__(self, cause: BaseException):
        self.cause = cause
        super().__init__(f"position staging failed: {cause}")


class PositionPublicationError(RuntimeError):
    """Position committed, but publishing its spatial facts failed."""

    position_committed = True

    def __init__(self, cause: BaseException):
        self.cause = cause
        super().__init__(f"committed position publication failed: {cause}")


__all__ = ["PositionCommitError", "PositionPublicationError"]
