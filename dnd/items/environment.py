"""Tile-owned directional environment items."""

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.base_actions import BaseAction, ActionEvent, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map


DIRECTIONS: Tuple[str, ...] = ("north", "south", "east", "west")
DIRECTIONAL_CHANNELS: Tuple[str, ...] = ("movement", "vision", "light", "propagation")


def _validate_directions(directions: Tuple[str, ...]) -> None:
    for direction in directions:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported direction: {direction}")


def _validate_channels(channels: Tuple[str, ...]) -> None:
    for channel in channels:
        if channel not in DIRECTIONAL_CHANNELS:
            raise ValueError(f"Unsupported directional blocking channel: {channel}")


class DirectionalWall(BaseItem):
    """A tile-resident structural wall that blocks configured directions only."""

    name: str = Field(default="Directional Wall")
    is_pickable: bool = Field(default=False)
    is_usable: bool = Field(default=False)
    is_targetable: bool = Field(default=False)
    blocks_movement: bool = Field(default=False)
    blocks_vision_field: bool = Field(default=False)
    map_char: str = Field(default="W")
    include_in_senses_objects: bool = Field(default=False)
    include_in_available_object_actions: bool = Field(default=False)

    blocked_directions: Tuple[str, ...] = Field(default_factory=lambda: DIRECTIONS)
    blocked_channels: Tuple[str, ...] = Field(default_factory=lambda: DIRECTIONAL_CHANNELS)

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        _validate_directions(self.blocked_directions)
        _validate_channels(self.blocked_channels)
        for channel in self.blocked_channels:
            for direction in self.blocked_directions:
                self._set_directional_blocking_field(channel, direction, True)


class OpenDirectionalDoorAction(BaseAction):
    """Open a closed directional door."""

    name: str = Field(default="Open Door")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return declaration_event.cancel(status_message="Door not found")
        if door.is_open:
            return declaration_event.cancel(status_message="Door already open")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return execution_event.cancel(status_message="Door not found")
        door.open(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door opened")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door opened")


class CloseDirectionalDoorAction(BaseAction):
    """Close an open directional door."""

    name: str = Field(default="Close Door")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return declaration_event.cancel(status_message="Door not found")
        if not door.is_open:
            return declaration_event.cancel(status_message="Door already closed")
        door_pos = get_map().get_object_position(door.uuid)
        if door_pos and get_map().get_entities_at(door_pos):
            return declaration_event.cancel(status_message="Can't close door - someone is standing in the doorway")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return execution_event.cancel(status_message="Door not found")
        door.close(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door closed")


class DirectionalDoor(UsableItem):
    """A tile-resident structural door that toggles configured directional blockers."""

    name: str = Field(default="Directional Door")
    is_pickable: bool = Field(default=False)
    is_targetable: bool = Field(default=False)
    blocks_movement: bool = Field(default=False)
    blocks_vision_field: bool = Field(default=False)
    map_char: str = Field(default="D")
    include_in_senses_objects: bool = Field(default=True)
    include_in_available_object_actions: bool = Field(default=True)

    is_open: bool = Field(default=False)
    blocked_directions: Tuple[str, ...] = Field(default_factory=lambda: DIRECTIONS)
    blocked_channels: Tuple[str, ...] = Field(default_factory=lambda: DIRECTIONAL_CHANNELS)

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        _validate_directions(self.blocked_directions)
        _validate_channels(self.blocked_channels)
        for channel, direction, blocked in self._directional_updates(closed=not self.is_open):
            self._set_directional_blocking_field(channel, direction, blocked)

    def get_spatial_open_state(self) -> Optional[bool]:
        return self.is_open

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if self.is_open:
            door_pos = get_map().get_object_position(self.uuid)
            if door_pos and get_map().get_entities_at(door_pos):
                return []
            return [
                CloseDirectionalDoorAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                    template=True,
                )
            ]
        return [
            OpenDirectionalDoorAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
                template=True,
            )
        ]

    def open(self, parent_event: Optional[UUID] = None) -> None:
        if self.is_open:
            return
        self.is_open = True
        self.set_directional_blocking_bulk(self._directional_updates(closed=False), parent_event=parent_event)

    def close(self, parent_event: Optional[UUID] = None) -> None:
        if not self.is_open:
            return
        self.is_open = False
        self.set_directional_blocking_bulk(self._directional_updates(closed=True), parent_event=parent_event)

    def _directional_updates(self, closed: bool) -> List[Tuple[str, str, bool]]:
        return [
            (channel, direction, closed)
            for channel in self.blocked_channels
            for direction in self.blocked_directions
        ]

