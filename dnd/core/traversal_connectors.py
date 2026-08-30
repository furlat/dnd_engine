"""Dependency-neutral authored and live vertical-traversal facts."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


ConnectorPosition = tuple[StrictInt, StrictInt]
_AUTHORED_ID = re.compile(r"^connector\.[a-z][a-z0-9_.-]*$")
_PRESENTATION_KEY = re.compile(r"^[a-z][a-z0-9_.-]*$")


class TraversalConnectorKind(str, Enum):
    """Closed presentation family; mechanics do not branch on it."""

    LADDER = "ladder"
    ROPE = "rope"
    LIFT = "lift"
    VERTICAL_STAIRS = "vertical_stairs"
    PASSAGE = "passage"


class ConnectorProvocationPolicy(str, Enum):
    """Whether transfer exposes the real source-exit reaction boundary."""

    PROVOKES_SOURCE_EXIT = "provokes_source_exit"
    DOES_NOT_PROVOKE = "does_not_provoke"


class ConnectorActionCostType(str, Enum):
    """Nonmovement action-economy channels a connector may debit."""

    ACTIONS = "actions"
    BONUS_ACTIONS = "bonus_actions"


class TraversalConnectorChangeOperation(str, Enum):
    """Closed GridMap connector mutation operations."""

    REGISTER = "register"
    REPLACE = "replace"
    ENABLE = "enable"
    DISABLE = "disable"
    REMOVE = "remove"


class ConnectorDestinationStatus(str, Enum):
    """Requester-subjective destination occupancy status."""

    KNOWN_CLEAR = "known_clear"
    KNOWN_BLOCKED = "known_blocked"
    UNKNOWN = "unknown"


class TraversalConnectorDefinition(BaseModel):
    """Stable map-authored connector identity and mechanics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    endpoint_positions: tuple[ConnectorPosition, ConnectorPosition]
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: ConnectorActionCostType | None = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    bidirectional: StrictBool
    enabled: StrictBool
    provocation_policy: ConnectorProvocationPolicy

    @field_validator("authored_id")
    @classmethod
    def validate_authored_id(cls, value: str) -> str:
        if not _AUTHORED_ID.fullmatch(value):
            raise ValueError("authored_id must be a stable connector.* identity")
        return value

    @field_validator("presentation_key")
    @classmethod
    def validate_presentation_key(cls, value: str) -> str:
        if not _PRESENTATION_KEY.fullmatch(value):
            raise ValueError("presentation_key must be a stable semantic key")
        return value

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        first, second = self.endpoint_positions
        if first == second:
            raise ValueError("connector endpoints must be distinct")
        if self.action_cost_type is None:
            if self.action_cost_amount != 0:
                raise ValueError(
                    "positive action cost requires an action cost type"
                )
        elif self.action_cost_amount <= 0:
            raise ValueError(
                "typed connector action cost amount must be positive"
            )
        if self.kind is not TraversalConnectorKind.PASSAGE:
            if abs(first[0] - second[0]) + abs(first[1] - second[1]) != 1:
                raise ValueError(
                    "vertical connector endpoints must be cardinal-adjacent"
                )
        return self


class TraversalConnectorEndpoint(BaseModel):
    """One exact support-Tile anchor and its registration elevation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    position: ConnectorPosition
    support_tile_uuid: UUID
    elevation_feet: StrictInt


def _connector_digest(
    connector_uuid: UUID,
    definition: TraversalConnectorDefinition,
    endpoints: tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint],
    revision: int,
) -> str:
    payload = {
        "uuid": str(connector_uuid),
        "definition": definition.model_dump(mode="json"),
        "endpoints": [endpoint.model_dump(mode="json") for endpoint in endpoints],
        "revision": revision,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class TraversalConnector(BaseModel):
    """Live immutable connector indexed by GridMap."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    uuid: UUID = Field(default_factory=uuid4)
    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    endpoints: tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint]
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: ConnectorActionCostType | None = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    bidirectional: StrictBool
    enabled: StrictBool
    provocation_policy: ConnectorProvocationPolicy
    revision: StrictInt = Field(ge=1)
    objective_digest: str = Field(min_length=64, max_length=64)

    @classmethod
    def create(
        cls,
        definition: TraversalConnectorDefinition,
        endpoints: tuple[
            TraversalConnectorEndpoint,
            TraversalConnectorEndpoint,
        ],
        *,
        connector_uuid: UUID | None = None,
        revision: int = 1,
    ) -> Self:
        runtime_uuid = connector_uuid or uuid4()
        return cls(
            uuid=runtime_uuid,
            authored_id=definition.authored_id,
            kind=definition.kind,
            presentation_key=definition.presentation_key,
            endpoints=endpoints,
            movement_cost_feet=definition.movement_cost_feet,
            action_cost_type=definition.action_cost_type,
            action_cost_amount=definition.action_cost_amount,
            bidirectional=definition.bidirectional,
            enabled=definition.enabled,
            provocation_policy=definition.provocation_policy,
            revision=revision,
            objective_digest=_connector_digest(
                runtime_uuid,
                definition,
                endpoints,
                revision,
            ),
        )

    def definition(self) -> TraversalConnectorDefinition:
        return TraversalConnectorDefinition(
            authored_id=self.authored_id,
            kind=self.kind,
            presentation_key=self.presentation_key,
            endpoint_positions=(
                self.endpoints[0].position,
                self.endpoints[1].position,
            ),
            movement_cost_feet=self.movement_cost_feet,
            action_cost_type=self.action_cost_type,
            action_cost_amount=self.action_cost_amount,
            bidirectional=self.bidirectional,
            enabled=self.enabled,
            provocation_policy=self.provocation_policy,
        )

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        definition = self.definition()
        first, second = self.endpoints
        if first.support_tile_uuid == second.support_tile_uuid:
            raise ValueError("connector endpoints require distinct support Tiles")
        if (
            self.kind is not TraversalConnectorKind.PASSAGE
            and first.elevation_feet == second.elevation_feet
        ):
            raise ValueError(
                "vertical connector endpoints require an elevation difference"
            )
        if self.objective_digest != _connector_digest(
            self.uuid,
            definition,
            self.endpoints,
            self.revision,
        ):
            raise ValueError("objective_digest does not match connector facts")
        return self


class TraversalConnectorCommand(BaseModel):
    """Collision-free engine command selected from current discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    connector_uuid: UUID
    connector_revision: StrictInt = Field(ge=1)
    connector_digest: str = Field(min_length=64, max_length=64)
    source_position: ConnectorPosition
    destination_position: ConnectorPosition


class ConnectorTraversalDiscovery(BaseModel):
    """Actor-specific typed connector action semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    command: TraversalConnectorCommand
    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    source_elevation_feet: StrictInt
    destination_elevation_feet: StrictInt
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: ConnectorActionCostType | None = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    bidirectional: StrictBool
    provocation_policy: ConnectorProvocationPolicy
    destination_status: ConnectorDestinationStatus


__all__ = [
    "ConnectorActionCostType",
    "ConnectorDestinationStatus",
    "ConnectorProvocationPolicy",
    "ConnectorTraversalDiscovery",
    "TraversalConnector",
    "TraversalConnectorChangeOperation",
    "TraversalConnectorCommand",
    "TraversalConnectorDefinition",
    "TraversalConnectorEndpoint",
    "TraversalConnectorKind",
]
