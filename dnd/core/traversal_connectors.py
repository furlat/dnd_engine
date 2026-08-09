"""Dependency-neutral authored and live vertical-traversal facts."""

from __future__ import annotations

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

from dnd.core.content.canonical import canonical_content_sha256


ConnectorPosition = tuple[StrictInt, StrictInt]

CONNECTOR_AUTHORED_ID_PATTERN = r"^connector\.[a-z][a-z0-9_.-]*$"
CONNECTOR_PRESENTATION_KEY_PATTERN = r"^[a-z][a-z0-9_.-]*$"

_AUTHORED_ID = re.compile(CONNECTOR_AUTHORED_ID_PATTERN)
_PRESENTATION_KEY = re.compile(CONNECTOR_PRESENTATION_KEY_PATTERN)


class TraversalConnectorKind(str, Enum):
    """Closed authored presentation family; mechanics do not branch on it."""

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
    """The only nonmovement action-economy channels a connector may debit."""

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

    model_config = ConfigDict(extra="forbid", frozen=True)

    authored_id: str = Field(description="Map-local stable authored identity.")
    kind: TraversalConnectorKind = Field(description="Presentation family.")
    presentation_key: str = Field(description="Authored semantic presentation key.")
    endpoint_positions: tuple[ConnectorPosition, ConnectorPosition] = Field(
        description="Two distinct support-cell endpoints.",
    )
    movement_cost_feet: StrictInt = Field(
        ge=0,
        description="Sole movement debit for one transfer.",
    )
    action_cost_type: ConnectorActionCostType | None = Field(
        default=None,
        description="Optional actions or bonus-actions debit.",
    )
    action_cost_amount: StrictInt = Field(
        default=0,
        ge=0,
        description="Exact optional action-channel debit.",
    )
    bidirectional: StrictBool = Field(description="Whether reverse traversal is authored.")
    enabled: StrictBool = Field(description="Whether discovery and execution are enabled.")
    provocation_policy: ConnectorProvocationPolicy = Field(
        description="Authored source-exit reaction policy independent of kind.",
    )

    @field_validator("authored_id")
    @classmethod
    def _validate_authored_id(cls, value: str) -> str:
        if not _AUTHORED_ID.fullmatch(value):
            raise ValueError("authored_id must be a stable connector.* identity")
        return value

    @field_validator("presentation_key")
    @classmethod
    def _validate_presentation_key(cls, value: str) -> str:
        if not _PRESENTATION_KEY.fullmatch(value):
            raise ValueError("presentation_key must be an authored semantic key")
        return value

    @model_validator(mode="after")
    def _validate_definition(self) -> Self:
        first, second = self.endpoint_positions
        if first == second:
            raise ValueError("connector endpoints must be distinct")
        if self.action_cost_type is None:
            if self.action_cost_amount != 0:
                raise ValueError("connector action cost type is required for a positive amount")
        elif self.action_cost_amount <= 0:
            raise ValueError("connector action cost amount must be positive when typed")
        if self.kind is not TraversalConnectorKind.PASSAGE:
            if abs(first[0] - second[0]) + abs(first[1] - second[1]) != 1:
                raise ValueError("vertical connector endpoints must be cardinal-adjacent")
        return self


class TraversalConnectorEndpoint(BaseModel):
    """One live support-tile anchor and its frozen elevation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: ConnectorPosition = Field(description="Endpoint support coordinate.")
    support_tile_uuid: UUID = Field(description="Exact supporting Tile identity.")
    elevation_feet: StrictInt = Field(description="Support elevation frozen at registration.")


def _connector_digest_payload(
    *,
    connector_uuid: UUID,
    definition: TraversalConnectorDefinition,
    endpoints: tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint],
    revision: int,
) -> dict[str, object]:
    return {
        "uuid": str(connector_uuid),
        "authored_id": definition.authored_id,
        "kind": definition.kind.value,
        "presentation_key": definition.presentation_key,
        "endpoints": [endpoint.model_dump(mode="json") for endpoint in endpoints],
        "movement_cost_feet": definition.movement_cost_feet,
        "action_cost_type": (
            definition.action_cost_type.value
            if definition.action_cost_type is not None
            else None
        ),
        "action_cost_amount": definition.action_cost_amount,
        "bidirectional": definition.bidirectional,
        "enabled": definition.enabled,
        "provocation_policy": definition.provocation_policy.value,
        "revision": revision,
    }


class TraversalConnector(BaseModel):
    """Live immutable connector indexed by GridMap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uuid: UUID = Field(default_factory=uuid4, description="Encounter-local runtime identity.")
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
        endpoints: tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint],
        *,
        connector_uuid: UUID | None = None,
        revision: int = 1,
    ) -> Self:
        runtime_uuid = connector_uuid or uuid4()
        digest = canonical_content_sha256(_connector_digest_payload(
            connector_uuid=runtime_uuid,
            definition=definition,
            endpoints=endpoints,
            revision=revision,
        ))
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
            objective_digest=digest,
        )

    def definition(self) -> TraversalConnectorDefinition:
        """Return the stable authored facts represented by this live record."""
        return TraversalConnectorDefinition(
            authored_id=self.authored_id,
            kind=self.kind,
            presentation_key=self.presentation_key,
            endpoint_positions=(self.endpoints[0].position, self.endpoints[1].position),
            movement_cost_feet=self.movement_cost_feet,
            action_cost_type=self.action_cost_type,
            action_cost_amount=self.action_cost_amount,
            bidirectional=self.bidirectional,
            enabled=self.enabled,
            provocation_policy=self.provocation_policy,
        )

    @model_validator(mode="after")
    def _validate_runtime(self) -> Self:
        definition = self.definition()
        first, second = self.endpoints
        if first.support_tile_uuid == second.support_tile_uuid:
            raise ValueError("connector endpoints require distinct support tiles")
        if (
            self.kind is not TraversalConnectorKind.PASSAGE
            and first.elevation_feet == second.elevation_feet
        ):
            raise ValueError("vertical connector endpoints require nonzero elevation delta")
        expected = canonical_content_sha256(_connector_digest_payload(
            connector_uuid=self.uuid,
            definition=definition,
            endpoints=self.endpoints,
            revision=self.revision,
        ))
        if self.objective_digest != expected:
            raise ValueError("objective_digest does not authenticate connector facts")
        return self


class TraversalConnectorCommand(BaseModel):
    """Collision-free engine command selected from current discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_uuid: UUID
    connector_revision: StrictInt = Field(ge=1)
    connector_digest: str = Field(min_length=64, max_length=64)
    source_position: ConnectorPosition
    destination_position: ConnectorPosition


class ConnectorTraversalDiscovery(BaseModel):
    """Actor-specific typed connector action semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    "CONNECTOR_AUTHORED_ID_PATTERN",
    "CONNECTOR_PRESENTATION_KEY_PATTERN",
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
