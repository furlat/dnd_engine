"""Tile-owned directional environment items."""

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from dnd.blocks.base_item import (
    BaseItem,
    UsableItem,
)
from dnd.core.base_actions import (
    BaseAction,
    Cost,
    TargetType,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_block import BaseBlock
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.core.gridmap import get_map
from dnd.types.world import WorldEdgeChannel
from dnd.types.materials import Material
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
    """Tile-resident structural wall that blocks configured directions only.

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
        blocked_channels: Spatial channels blocked in those directions.
    """

    name: str = Field(default="Directional Wall", description="Display name for the wall object.")
    is_pickable: bool = Field(default=False, description="Whether the wall can be looted into inventory.")
    is_usable: bool = Field(default=False, description="Whether the wall exposes use actions.")
    is_targetable: bool = Field(default=False, description="Whether the wall can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the wall.")
    blocks_optics_field: bool = Field(default=False, description="Global optical blocker flag for the wall.")
    include_in_senses_objects: bool = Field(
        default=True,
        description="Whether senses expose the wall as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=False,
        description="Whether object action discovery includes the wall.",
    )

    blocked_channels: tuple[WorldEdgeChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked in each configured direction.",
    )

    def model_post_init(self, __context) -> None:
        """Validate the one-side wall contract."""
        super().model_post_init(__context)
        _validate_channels(self.blocked_channels)

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the fixed support-relative two-band capability."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return the current wall structure."""
        return BoundaryStructure(
            structure=BoundaryStructureKind.WALL,
            material=Material.STONE,
            blocked_channels=self.blocked_channels,
        )


class CliffFace(BaseItem):
    """A fixed, movement-only cliff boundary."""

    name: str = Field(default="Cliff Face", description="Display name for the cliff object.")
    is_pickable: bool = Field(default=False, description="Cliffs are fixed environment objects.")
    is_usable: bool = Field(default=False, description="Cliffs do not expose use actions.")
    is_targetable: bool = Field(default=False, description="Cliffs are not direct targets.")
    include_in_senses_objects: bool = Field(
        default=True,
        description="Whether senses expose the cliff as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=False,
        description="Whether object action discovery includes the cliff.",
    )

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the fixed two-band boundary capability."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return the movement-only cliff structure."""
        return BoundaryStructure(
            structure=BoundaryStructureKind.CLIFF,
            material=Material.STONE,
            blocked_channels=(WorldEdgeChannel.MOVEMENT,),
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
        blocks_optics_field: Global optical blocker flag.
        include_in_senses_objects: Whether senses expose the door as an object.
        include_in_available_object_actions: Whether object action discovery
            includes the door.
        is_open: Current door state.
        blocked_channels: Spatial channels blocked in those directions.
    """

    name: str = Field(default="Directional Door", description="Display name for the door object.")
    is_pickable: bool = Field(default=False, description="Whether the door can be looted into inventory.")
    is_targetable: bool = Field(default=False, description="Whether the door can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the door.")
    blocks_optics_field: bool = Field(default=False, description="Global optical blocker flag for the door.")
    include_in_senses_objects: bool = Field(
        default=True,
        description="Whether senses expose the door as a visible object.",
    )
    include_in_available_object_actions: bool = Field(
        default=True,
        description="Whether object action discovery includes the door.",
    )

    is_open: bool = Field(default=False, description="Current open or closed state of the door.")
    blocked_channels: tuple[WorldEdgeChannel, ...] = Field(
        default_factory=lambda: DIRECTIONAL_CHANNELS,
        description="Spatial channels blocked in each configured direction.",
    )

    def model_post_init(self, __context) -> None:
        """Validate the one-side door contract."""
        super().model_post_init(__context)
        _validate_channels(self.blocked_channels)

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door state used by spatial serialization.

        Returns:
            True when open, False when closed.
        """
        return self.is_open

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the fixed support-relative two-band capability."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return the closed channels or empty open-door structure."""
        return BoundaryStructure(
            structure=BoundaryStructureKind.DOOR,
            material=Material.WOOD,
            blocked_channels=() if self.is_open else self.blocked_channels,
        )

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Build use-action templates available from the door's current state."""
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
        """Open the door without changing its exact placement."""
        if self.is_open:
            return
        previous_structure = self.get_boundary_structure()
        self.is_open = True
        try:
            get_map().update_object_boundary_structure(
                self.uuid,
                self.get_boundary_structure(),
                previous_structure=previous_structure,
                parent_event=parent_event,
            )
        except Exception:
            self.is_open = False
            raise

    def close(self, parent_event: Optional[UUID] = None) -> None:
        """Close the door without re-admitting or rewriting its bands."""
        if not self.is_open:
            return
        previous_structure = self.get_boundary_structure()
        self.is_open = False
        try:
            get_map().update_object_boundary_structure(
                self.uuid,
                self.get_boundary_structure(),
                previous_structure=previous_structure,
                parent_event=parent_event,
            )
        except Exception:
            self.is_open = True
            raise

    # The action surface above is intentionally the sole lifecycle owner.
    # No directional boolean projection or side-expansion helper remains.
