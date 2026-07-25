"""Canonical policy decisions accepted by native and remote AI execution."""

from __future__ import annotations

from typing import Literal, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field


class DecisionModel(BaseModel):
    """Immutable base for policy decisions."""

    model_config = ConfigDict(frozen=True)


class ExecuteIntent(DecisionModel):
    """Execute one exact row from the current decision epoch."""

    kind: Literal["execute"] = "execute"
    row_id: str = Field(description="Current decision-epoch row identity.")
    extra_target_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Additional authorized multi-target selections.",
    )
    prefer_safe: bool = Field(
        default=True,
        description="Whether movement should prefer the authorized safe path.",
    )


class EndTurnIntent(DecisionModel):
    """End the current actor's turn."""

    kind: Literal["end_turn"] = "end_turn"


PolicyIntent = Union[ExecuteIntent, EndTurnIntent]
