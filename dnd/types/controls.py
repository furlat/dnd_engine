"""Private authored environment connections; never part of observed fixture state."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ControlLink(BaseModel):
    """An engaged sensor/handle requests one exact door or light value."""

    model_config = ConfigDict(frozen=True)
    target_item_uuid: UUID
    target_kind: Literal["light", "door"]
    engaged_value: bool = True


class ActivationLink(BaseModel):
    """One new contact requests a finite activation of an installed mechanism."""

    model_config = ConfigDict(frozen=True)
    target_condition_uuid: UUID
