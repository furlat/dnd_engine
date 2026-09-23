"""Tile-owned boundary environment items."""

from typing import List, Optional
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.base_actions import BaseAction, ActionEvent, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.item_types import DoorMechanism, DoorSwing, ItemDestructionProfile, ItemIntegrity
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SpatialHandler
from dnd.core.gridmap import get_map
from dnd.types.materials import Material
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import (
    BoundaryStructure,
    BoundaryStructureKind,
    WorldPlacementKind,
    WorldPlacementSpec,
)

DIRECTIONAL_CHANNELS: tuple[WorldEdgeChannel, ...] = (
    WorldEdgeChannel.MOVEMENT,
    WorldEdgeChannel.OPTICAL,
    WorldEdgeChannel.PROPAGATION,
)


def _validate_channels(channels: tuple[WorldEdgeChannel, ...]) -> None:
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
    """One boundary-side structural wall.

    Attributes:
        name: Display name for the wall object.
        is_pickable: Whether the wall can be looted into inventory.
        is_usable: Whether the wall exposes use actions.
        is_targetable: Whether the wall can be directly targeted.
        blocks_movement: Global movement blocker flag.
        blocks_optics_field: Global optical blocker flag.
        include_in_senses_objects: Whether senses expose the wall as an object.
        include_in_available_object_actions: Whether object action discovery
            includes the wall.
        blocked_channels: Spatial channels blocked at the wall's placement side.
    """

    name: str = Field(default="Directional Wall", description="Display name for the wall object.")
    is_pickable: bool = Field(default=False, description="Whether the wall can be looted into inventory.")
    is_usable: bool = Field(default=False, description="Whether the wall exposes use actions.")
    is_targetable: bool = Field(default=False, description="Whether the wall can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the wall.")
    blocks_optics_field: bool = Field(default=False, description="Global optical blocker flag for the wall.")
    map_char: str = Field(default="W", description="Map-editor glyph for the wall.")
    include_in_senses_objects: bool = Field(
        default=False,
        description="Whether senses expose the wall as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=False,
        description="Whether object action discovery includes the wall.",
    )

    blocked_channels: tuple[WorldEdgeChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked at the placed boundary side.",
    )
    material: Material = Field(
        default=Material.STONE,
        description="Physical material of this authored wall.",
    )

    def model_post_init(self, __context) -> None:
        """Validate the provider's structural channels."""
        super().model_post_init(__context)
        _validate_channels(self.blocked_channels)

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Require one explicit owner-Tile boundary side."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return the wall's current structural contribution."""
        return BoundaryStructure(
            structure=BoundaryStructureKind.WALL,
            material=self.material,
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
        if not isinstance(door, DirectionalDoor) or not door.is_active:
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
        if not isinstance(door, DirectionalDoor) or not door.is_active:
            return execution_event.cancel(status_message="Door not found")
        door.request_open(True, parent_event=execution_event)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door opened")
        return effect.with_updates(status_message="Door opened")


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
        if not isinstance(door, DirectionalDoor) or not door.is_active:
            return declaration_event.cancel(status_message="Door not found")
        if not door.is_open:
            return declaration_event.cancel(status_message="Door already closed")
        if door._doorway_occupied():
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
        if not isinstance(door, DirectionalDoor) or not door.is_active:
            return execution_event.cancel(status_message="Door not found")
        if not door.request_open(False, parent_event=execution_event):
            return execution_event.cancel(status_message="Can't close door - someone is standing in the doorway")
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.with_updates(status_message="Door closed")


class DirectionalDoor(UsableItem):
    """One boundary-side door whose current structure follows its open state.

    Attributes:
        name: Display name for the door object.
        is_pickable: Whether the door can be looted into inventory.
        is_targetable: Whether the door can be directly targeted.
        blocks_movement: Global movement blocker flag.
        blocks_optics_field: Global optical blocker flag.
        include_in_senses_objects: Whether senses expose the door as an object.
        include_in_adjacent_senses_objects: Whether adjacent senses expose the
            door as an object.
        include_in_available_object_actions: Whether object action discovery
            includes the door.
        is_open: Current door state.
        blocked_channels: Spatial channels blocked while closed.
    """

    name: str = Field(default="Directional Door", description="Display name for the door object.")
    is_pickable: bool = Field(default=False, description="Whether the door can be looted into inventory.")
    is_targetable: bool = Field(default=True, description="Whether the door can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the door.")
    blocks_optics_field: bool = Field(default=False, description="Global optical blocker flag for the door.")
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
    material: Material = Material.WOOD
    vertical_extent_steps: int = Field(default=2, ge=1, frozen=True)
    mechanism: DoorMechanism = DoorMechanism.SINGLE_HINGED
    swing: DoorSwing = DoorSwing.OUTWARD
    blocked_channels: tuple[WorldEdgeChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked at the placed boundary side while closed.",
    )
    _pending_close_controller_uuid: UUID | None = PrivateAttr(default=None)
    _pending_close_request_uuid: UUID | None = PrivateAttr(default=None)
    _pending_close_handler_uuid: UUID | None = PrivateAttr(default=None)

    def model_post_init(self, __context) -> None:
        """Validate the provider's structural channels."""
        super().model_post_init(__context)
        _validate_channels(self.blocked_channels)
        if self.health is None:
            self.health = self.create_item_health(self.uuid, 18)
        if self.destruction_profile is None:
            self.destruction_profile = ItemDestructionProfile(
                name=f"Broken {self.name}", outcome="clear",
                placement_spec=self.get_world_placement_spec(),
                boundary_structure=BoundaryStructure(
                    structure=BoundaryStructureKind.DOOR, material=self.material, blocked_channels=()),
            )

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door state used by spatial serialization.

        Returns:
            True when open, False when closed.
        """
        return self.is_open

    def get_door_mechanism(self) -> DoorMechanism:
        return self.mechanism

    def get_door_swing(self) -> DoorSwing:
        return self.swing

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Require one explicit owner-Tile boundary side."""
        if self.integrity is ItemIntegrity.DESTROYED and self.destruction_profile is not None:
            profile = self.destruction_profile.placement_spec
            if profile is not None:
                return profile
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=self.vertical_extent_steps,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return an empty open-door or blocked closed-door contribution."""
        if self.integrity is ItemIntegrity.DESTROYED and self.destruction_profile is not None:
            structure = self.destruction_profile.boundary_structure
            if structure is not None:
                return structure
        return BoundaryStructure(
            structure=BoundaryStructureKind.DOOR,
            material=self.material,
            blocked_channels=() if self.is_open else self.blocked_channels,
        )

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Build use-action templates available from the door's current state.

        Args:
            user_entity_uuid: Entity UUID that would execute the action.

        Returns:
            Open or close action templates, or an empty list when an open door is
            occupied and cannot be closed.
        """
        if not self.is_active:
            return []
        if self.is_open:
            if self._doorway_occupied():
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

    def _doorway_occupied(self) -> bool:
        position = get_map().get_object_position(self.uuid)
        return position is not None and bool(get_map().get_entities_at(position))

    def request_open(
        self,
        value: bool,
        *,
        parent_event: Event,
        controller_uuid: UUID | None = None,
        defer_close: bool = False,
    ) -> bool:
        """Request a native state, optionally waiting for the doorway to clear.

        Each request supersedes the previous one. False means the doorway is
        occupied; it remains open even when the close was retained for retry.
        """
        return self._request_open(value, parent_event.uuid, controller_uuid, defer_close)

    def _request_open(
        self,
        value: bool,
        parent_event: UUID | None,
        controller_uuid: UUID | None = None,
        defer_close: bool = False,
    ) -> bool:
        if not self.is_active:
            return False
        self._clear_pending_close()
        if self.is_open == value:
            return True
        position = get_map().get_object_position(self.uuid)
        if not value and self._doorway_occupied():
            if defer_close and position is not None:
                self._pending_close_controller_uuid = controller_uuid
                self._pending_close_request_uuid = parent_event
                handler = SpatialHandler(
                    name="Close cleared doorway",
                    source_entity_uuid=self.uuid,
                    positions={position},
                    event_type=EventType.SPATIAL_ENTITY_LEFT,
                    event_phase=EventPhase.EFFECT,
                    event_processor=self._retry_pending_close,
                )
                EventQueue.add_spatial_handler(handler)
                self._pending_close_handler_uuid = handler.uuid
            return False
        self._set_open(value, parent_event)
        return True

    def _retry_pending_close(self, event: Event, _source_entity_uuid: UUID) -> None:
        if not self.is_active or self._pending_close_handler_uuid is None or self._doorway_occupied():
            return
        self._clear_pending_close()
        # The current departure owns this consequence. The old control request
        # was completed already and must never gain another child lineage.
        self._set_open(False, event.uuid)

    def cancel_pending_close(self, controller_uuid: UUID) -> None:
        """Withdraw this controller's pending request without changing state."""
        if self._pending_close_controller_uuid == controller_uuid:
            self._clear_pending_close()

    def _clear_pending_close(self) -> None:
        if self._pending_close_handler_uuid is not None:
            EventQueue.remove_spatial_handler(self._pending_close_handler_uuid)
        self._pending_close_controller_uuid = None
        self._pending_close_request_uuid = None
        self._pending_close_handler_uuid = None

    def on_grid_object_removed(self, position: tuple[int, int], clear_location: bool = True) -> None:
        if clear_location:
            self._clear_pending_close()
        super().on_grid_object_removed(position, clear_location)

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        self._clear_pending_close()
        super()._on_destroy(parent_event)

    def open(self, parent_event: Optional[UUID] = None) -> None:
        """Explicitly open the door, superseding any pending control request."""
        self._request_open(True, parent_event)

    def close(self, parent_event: Optional[UUID] = None) -> None:
        """Explicitly close an unoccupied door without scheduling a retry."""
        self._request_open(False, parent_event)

    def _set_open(self, value: bool, parent_event: UUID | None) -> None:
        if not self.is_active:
            return
        previous_structure = self.get_boundary_structure()
        previous_value = self.is_open
        self.is_open = value
        try:
            get_map().update_object_boundary_structure(
                self.uuid,
                self.get_boundary_structure(),
                previous_structure=previous_structure,
                parent_event=parent_event,
            )
        except Exception:
            self.is_open = previous_value
            raise
