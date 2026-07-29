"""Dependency-neutral runtime support authority for character origins."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class OriginRuntimeSupportStatus(str, Enum):
    """Whether one exact origin definition is executable by this runtime."""

    AVAILABLE = "available"
    BLOCKED = "blocked"


class OriginRuntimeSupport(BaseModel):
    """One closed origin-execution status with an exact blocked reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OriginRuntimeSupportStatus
    blocked_reason: str | None = None

    @classmethod
    def available(cls) -> Self:
        """Return an origin support fact that permits validation."""

        return cls(status=OriginRuntimeSupportStatus.AVAILABLE)

    @classmethod
    def blocked(cls, reason: str) -> Self:
        """Return an unavailable origin support fact with its exact reason."""

        return cls(
            status=OriginRuntimeSupportStatus.BLOCKED,
            blocked_reason=reason,
        )

    @field_validator("blocked_reason")
    @classmethod
    def _normalize_blocked_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("blocked origin support requires an exact reason")
        return normalized

    @model_validator(mode="after")
    def _validate_status(self) -> Self:
        if (
            self.status is OriginRuntimeSupportStatus.BLOCKED
            and self.blocked_reason is None
        ):
            raise ValueError("blocked origin support requires an exact reason")
        if (
            self.status is OriginRuntimeSupportStatus.AVAILABLE
            and self.blocked_reason is not None
        ):
            raise ValueError(
                "available origin support cannot carry a blocked reason",
            )
        return self


__all__ = [
    "OriginRuntimeSupport",
    "OriginRuntimeSupportStatus",
]
