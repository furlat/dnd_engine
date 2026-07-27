"""Dependency-neutral public contracts for cold game history."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from server.game_directory.contracts import GameRecord


class GameHistoryListResponse(BaseModel):
    """Directory listing of active or historical visible games."""

    model_config = ConfigDict(extra="forbid")

    games: list[GameRecord] = Field(
        description="Games visible to this directory query.",
    )
    count: int = Field(
        ge=0,
        description="Number of returned games.",
    )


__all__ = ["GameHistoryListResponse"]
