"""Passive, response-local domains for exact player action selections."""

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from dnd.core.action_types import AvailableHandlerInfo
from dnd.core.base_actions import AvailableActionMetadata, AvailableWorldInteraction, SelectedRoute
from dnd.core.presentation_geometry import AoEAimingGeometry, AoEPresentationGeometry


Reference = Annotated[int, Field(strict=True, ge=0)]
Position = tuple[int, int]


class ChoiceSubject(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    uuid: UUID
    kind: Literal['creature', 'object']
    name: str | None = None


class ChoiceExposure(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    reactor_uuid: UUID
    reactor_name: str
    from_position: Reference
    to_position: Reference


class ChoiceBindingData(BaseModel):
    """Values attached to a native action/target pair, never to a whole tile."""

    model_config = ConfigDict(extra='forbid', frozen=True)
    index: Reference
    distance: int | None = None
    path_cost: int | None = None
    extra_target_uuids: tuple[UUID, ...] | None = None
    secondary_set: Reference | None = None
    is_path_hazardous: bool = False
    safe_path_cost: int | None = None
    path: tuple[Reference, ...] | None = None
    safe_path: tuple[Reference, ...] | None = None
    opportunity_attack_exposures: tuple[ChoiceExposure, ...] = ()
    safe_path_opportunity_attack_exposures: tuple[ChoiceExposure, ...] = ()

    @model_serializer(mode='wrap')
    def sparse(self, serialize):
        values = serialize(self)
        # None is the explicit default of optional pair data. An empty path or
        # explicit empty secondary set is meaningful and is retained.
        values = {key: value for key, value in values.items() if value is not None}
        if not self.is_path_hazardous:
            values.pop('is_path_hazardous', None)
        if not self.opportunity_attack_exposures:
            values.pop('opportunity_attack_exposures', None)
        if not self.safe_path_opportunity_attack_exposures:
            values.pop('safe_path_opportunity_attack_exposures', None)
        return values


class SubjectBinding(ChoiceBindingData):
    kind: Literal['subject']
    subject: Reference
    position: Reference | None = None


class PositionBinding(ChoiceBindingData):
    kind: Literal['position']
    position: Reference


class SelfBinding(ChoiceBindingData):
    kind: Literal['self']


ChoiceBinding = Annotated[Union[SubjectBinding, PositionBinding, SelfBinding], Field(discriminator='kind')]


class ChoiceDomains(BaseModel):
    """Every reference resolves within this single Choices or Preview value."""

    model_config = ConfigDict(extra='forbid', frozen=True)
    subjects: tuple[ChoiceSubject, ...] = ()
    positions: tuple[Position, ...] = ()
    target_sets: tuple[tuple[ChoiceBinding, ...], ...] = ()


class PlayerAction(AvailableActionMetadata):
    model_config = ConfigDict(extra='forbid', frozen=True)
    target_set: Reference
    area_preview: Literal['not_applicable', 'deferred'] = 'not_applicable'
    aiming: AoEAimingGeometry | None = None
    range_origin: Position | None = None
    area_include_self: bool | None = None
    area_target_filter: Literal['all', 'enemies', 'allies', 'self_or_allies'] | None = None
    area_include_dead: bool | None = None


class PlayerChoices(ChoiceDomains):
    discovery_generation: Reference
    entity_uuid: UUID
    entity_actions: tuple[PlayerAction, ...] = ()
    position_actions: tuple[PlayerAction, ...] = ()
    self_actions: tuple[PlayerAction, ...] = ()
    object_actions: tuple[PlayerAction, ...] = ()
    remaining_movement: int = 0
    world_interactions: tuple[AvailableWorldInteraction, ...] = ()
    handler_details: tuple[AvailableHandlerInfo, ...] = ()


class PlayerSelectionPreview(ChoiceDomains):
    can_confirm: bool
    reason: str | None = None
    effective_target_uuids: tuple[UUID, ...] = ()
    next_target_set: Reference
    next_positions: tuple[Reference, ...] = ()
    geometry: AoEPresentationGeometry | None = None
    area_preview: Literal['not_applicable', 'deferred', 'computed'] = 'not_applicable'
    affected_positions: tuple[Reference, ...] = ()
    affected_entity_uuids: tuple[UUID, ...] = ()
    affected_entity_names: tuple[str, ...] = ()
    selected_route: SelectedRoute | None = None
