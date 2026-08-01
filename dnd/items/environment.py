"""Tile-owned directional environment items."""

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.base_actions import BaseAction, ActionEvent, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map
from dnd.core.item_types import (
    ItemBlockingChannel,
    ItemDirection,
    ItemDirectionalStructureState,
)

DIRECTIONS: Tuple[ItemDirection, ...] = ("north", "south", "east", "west")
DIRECTIONAL_CHANNELS: Tuple[ItemBlockingChannel, ...] = (
    "movement",
    "vision",
    "light",
    "propagation",
)


def _validate_directions(directions: Tuple[ItemDirection, ...]) -> None:
    """Validate directional blocker names.

    Args:
        directions: Direction names to validate.

    Raises:
        ValueError: If any direction is outside the supported cardinal set.
    """
    for direction in directions:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported direction: {direction}")


def _validate_channels(channels: Tuple[ItemBlockingChannel, ...]) -> None:
    """Validate directional blocking channel names.

    Args:
        channels: Directional channel names to validate.

    Raises:
        ValueError: If any channel is outside the supported channel set.
    """
    for channel in channels:
        if channel not in DIRECTIONAL_CHANNELS:
            raise ValueError(f"Unsupported directional blocking channel: {channel}")


class DirectionalWall(BaseItem):
    """Tile-resident structural wall that blocks configured directions only.

    Attributes:
        name: Display name for the wall object.
        is_pickable: Whether the wall can be looted into inventory.
        is_usable: Whether the wall exposes use actions.
        is_targetable: Whether the wall can be directly targeted.
        blocks_movement: Global movement blocker flag.
        blocks_vision_field: Global vision blocker flag.
        map_char: Map-editor glyph.
        include_in_senses_objects: Whether senses expose the wall as an object.
        include_in_available_object_actions: Whether object action discovery
            includes the wall.
        blocked_directions: Cardinal directions blocked from the wall tile.
        blocked_channels: Spatial channels blocked in those directions.
    """

    name: str = Field(default="Directional Wall", description="Display name for the wall object.")
    is_pickable: bool = Field(default=False, description="Whether the wall can be looted into inventory.")
    is_usable: bool = Field(default=False, description="Whether the wall exposes use actions.")
    is_targetable: bool = Field(default=False, description="Whether the wall can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the wall.")
    blocks_vision_field: bool = Field(default=False, description="Global vision blocker flag for the wall.")
    map_char: str = Field(default="W", description="Map-editor glyph for the wall.")
    include_in_senses_objects: bool = Field(
        default=False,
        description="Whether senses expose the wall as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=False,
        description="Whether object action discovery includes the wall.",
    )

    blocked_directions: Tuple[ItemDirection, ...] = Field(
        default_factory=lambda: DIRECTIONS,
        description="Cardinal directions blocked from the wall tile.",
    )
    blocked_channels: Tuple[ItemBlockingChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked in each configured direction.",
    )

    def model_post_init(self, __context) -> None:
        """Validate and project directional blockers after model initialization.

        Args:
            __context: Pydantic post-init context.
        """
        super().model_post_init(__context)
        _validate_directions(self.blocked_directions)
        _validate_channels(self.blocked_channels)
        for channel in self.blocked_channels:
            for direction in self.blocked_directions:
                self._set_directional_blocking_field(channel, direction, True)

    def get_directional_structure_state(
        self,
    ) -> ItemDirectionalStructureState:
        """Return the wall's exact authored directional topology."""
        return ItemDirectionalStructureState(
            blocked_directions=self.blocked_directions,
            blocked_channels=self.blocked_channels,
        )


class OpenDirectionalDoorAction(BaseAction):
    """Open a closed directional door."""

    name: str = Field(default="Open Door", description="Action discovery and combat-log label.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the acting entity and use source item state.",
    )
    costs: List[Cost] = Field(default_factory=list, description="Open Door has no action economy cost.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the directional door opened by this action.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate that the linked door exists and is closed.

        Args:
            declaration_event: Declaration event to advance or cancel.

        Returns:
            Execution event for a closed linked door, otherwise a canceled event.
        """
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return declaration_event.cancel(status_message="Door not found")
        if door.is_open:
            return declaration_event.cancel(status_message="Door already open")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Open the linked door and complete the action.

        Args:
            execution_event: Validated execution event.

        Returns:
            Completion event after opening the door, otherwise a canceled event.
        """
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

    name: str = Field(default="Close Door", description="Action discovery and combat-log label.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the acting entity and use source item state.",
    )
    costs: List[Cost] = Field(default_factory=list, description="Close Door has no action economy cost.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the directional door closed by this action.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate that the linked door exists, is open, and is unoccupied.

        Args:
            declaration_event: Declaration event to advance or cancel.

        Returns:
            Execution event for a closeable linked door, otherwise a canceled
            event.
        """
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
        """Close the linked door and complete the action.

        Args:
            execution_event: Validated execution event.

        Returns:
            Completion event after closing the door, otherwise a canceled event.
        """
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor):
            return execution_event.cancel(status_message="Door not found")
        door.close(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door closed")


class DirectionalDoor(UsableItem):
    """Tile-resident structural door that toggles configured directional blockers.

    Attributes:
        name: Display name for the door object.
        is_pickable: Whether the door can be looted into inventory.
        is_targetable: Whether the door can be directly targeted.
        blocks_movement: Global movement blocker flag.
        blocks_vision_field: Global vision blocker flag.
        map_char: Map-editor glyph.
        include_in_senses_objects: Whether senses expose the door as an object.
        include_in_adjacent_senses_objects: Whether adjacent senses expose the
            door as an object.
        include_in_available_object_actions: Whether object action discovery
            includes the door.
        is_open: Current door state.
        blocked_directions: Cardinal directions blocked while closed.
        blocked_channels: Spatial channels blocked in those directions.
    """

    name: str = Field(default="Directional Door", description="Display name for the door object.")
    is_pickable: bool = Field(default=False, description="Whether the door can be looted into inventory.")
    is_targetable: bool = Field(default=False, description="Whether the door can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the door.")
    blocks_vision_field: bool = Field(default=False, description="Global vision blocker flag for the door.")
    map_char: str = Field(default="D", description="Map-editor glyph for the door.")
    include_in_senses_objects: bool = Field(
        default=True,
        description="Whether senses expose the door as a visible object.",
    )
    include_in_adjacent_senses_objects: bool = Field(
        default=True,
        description="Whether adjacent senses expose the door as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=True,
        description="Whether object action discovery includes the door.",
    )

    is_open: bool = Field(default=False, description="Current open or closed state of the door.")
    blocked_directions: Tuple[ItemDirection, ...] = Field(
        default_factory=lambda: DIRECTIONS,
        description="Cardinal directions blocked while the door is closed.",
    )
    blocked_channels: Tuple[ItemBlockingChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked in each configured direction.",
    )

    def model_post_init(self, __context) -> None:
        """Validate and project the initial directional door state.

        Args:
            __context: Pydantic post-init context.
        """
        super().model_post_init(__context)
        _validate_directions(self.blocked_directions)
        _validate_channels(self.blocked_channels)
        for channel, direction, blocked in self._directional_updates(closed=not self.is_open):
            self._set_directional_blocking_field(channel, direction, blocked)

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door state used by spatial serialization.

        Returns:
            True when open, False when closed.
        """
        return self.is_open

    def get_directional_structure_state(
        self,
    ) -> ItemDirectionalStructureState:
        """Return the door's exact authored directional topology."""
        return ItemDirectionalStructureState(
            blocked_directions=self.blocked_directions,
            blocked_channels=self.blocked_channels,
        )

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Build use-action templates available from the door's current state.

        Args:
            user_entity_uuid: Entity UUID that would execute the action.

        Returns:
            Open or close action templates, or an empty list when an open door is
            occupied and cannot be closed.
        """
        if self.is_open:
            door_pos = get_map().get_object_position(self.uuid)
            if door_pos and get_map().get_entities_at(door_pos):
                return []
            return [
                self.bind_dynamic_use_action(
                    CloseDirectionalDoorAction(
                        source_entity_uuid=user_entity_uuid,
                        source_item_uuid=self.uuid,
                        template=True,
                    ),
                )
            ]
        return [
            self.bind_dynamic_use_action(
                OpenDirectionalDoorAction(
                    source_entity_uuid=user_entity_uuid,
                    source_item_uuid=self.uuid,
                    template=True,
                ),
            )
        ]

    def open(self, parent_event: Optional[UUID] = None) -> None:
        """Open the door and remove configured directional blockers.

        Args:
            parent_event: Optional parent event UUID for spatial updates.
        """
        if self.is_open:
            return
        self.is_open = True
        self.set_directional_blocking_bulk(self._directional_updates(closed=False), parent_event=parent_event)

    def close(self, parent_event: Optional[UUID] = None) -> None:
        """Close the door and restore configured directional blockers.

        Args:
            parent_event: Optional parent event UUID for spatial updates.
        """
        if not self.is_open:
            return
        self.is_open = False
        self.set_directional_blocking_bulk(self._directional_updates(closed=True), parent_event=parent_event)

    def _directional_updates(self, closed: bool) -> List[Tuple[str, str, bool]]:
        """Build bulk directional blocking updates for the requested state.

        Args:
            closed: Whether the door should block its configured directions.

        Returns:
            Tuples of channel, direction, and blocked state.
        """
        return [
            (channel, direction, closed)
            for channel in self.blocked_channels
            for direction in self.blocked_directions
        ]
