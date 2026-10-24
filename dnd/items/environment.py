"""Tile-owned boundary environment items."""

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from dnd.core.concealment_types import SEEN_WHEN_OPEN, with_plain_view
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import BaseAction, ActionEvent, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.item_types import DoorMechanism, DoorSwing, ItemDestructionProfile, ItemIntegrity
from dnd.core.events import Event, EventPhase
from dnd.core.gridmap import get_map
from dnd.types.discovery import ActorScan
from dnd.types.materials import Material
from dnd.types.physical_access import ContactPassage
from dnd.types.world import WorldEdgeChannel
from dnd.core.base_object import empty_list
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


WALL_MAP_CHAR = "W"


def wall_structure(material: Material, blocked_channels: tuple[WorldEdgeChannel, ...]) -> BoundaryStructure:
    """An intact wall's structural contribution: what it blocks, of what it is made."""
    return BoundaryStructure(structure=BoundaryStructureKind.WALL, material=material, blocked_channels=blocked_channels)


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
    armor_class: int = Field(default=17, ge=0)
    is_pickable: bool = Field(default=False, description="Whether the wall can be looted into inventory.")
    is_usable: bool = Field(default=False, description="Whether the wall exposes use actions.")
    is_targetable: bool = Field(default=True, description="Whether the wall can be directly targeted.")
    blocks_movement: bool = Field(default=False, description="Global movement blocker flag for the wall.")
    blocks_optics_field: bool = Field(default=False, description="Global optical blocker flag for the wall.")
    map_char: str = Field(default=WALL_MAP_CHAR, description="Map-editor glyph for the wall.")
    include_in_senses_objects: bool = Field(
        default=True,
        description="Whether senses expose the wall as a visible object.",
    )
    include_in_adjacent_senses_objects: bool = True
    include_in_available_object_actions: bool = Field(
        default=True,
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
        if self.is_targetable:
            if self.health is None:
                self.health = self.create_item_health(self.uuid, 18 if self.material is Material.WOOD else 27)
            if self.destruction_profile is None:
                self.destruction_profile = ItemDestructionProfile(
                    name=f"Broken {self.name}", outcome="clear",
                    placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
                        occupies_bands=False, vertical_extent_steps=1),
                    boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
                        material=self.material, blocked_channels=(), contact_passage=ContactPassage.CLEAR),
                )

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Require one explicit owner-Tile boundary side."""
        if self.integrity is ItemIntegrity.DESTROYED and self.destruction_profile is not None:
            profile = self.destruction_profile.placement_spec
            if profile is not None:
                return profile
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )

    def get_boundary_structure(self) -> BoundaryStructure:
        """Return the wall's current structural contribution."""
        if self.integrity is ItemIntegrity.DESTROYED and self.destruction_profile is not None:
            structure = self.destruction_profile.boundary_structure
            if structure is not None:
                return structure
        return wall_structure(self.material, self.blocked_channels)


class OpenDirectionalDoorAction(BaseAction):
    """Open a closed directional door."""

    name: str = Field(default="Open Door", description="Action discovery and combat-log label.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the acting entity and use source item state.",
    )
    costs: List[Cost] = Field(default_factory=empty_list, description="Open Door has no action economy cost.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the directional door opened by this action.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The linked door exists and is closed."""
        if self.source_item_uuid is None:
            return "No door linked"
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor) or not door.is_active:
            return "Door not found"
        if door.is_open:
            return "Door already open"
        if door.is_held_shut():
            return "Locked"
        return None

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
    costs: List[Cost] = Field(default_factory=empty_list, description="Close Door has no action economy cost.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the directional door closed by this action.",
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The linked door exists and is open."""
        if self.source_item_uuid is None:
            return "No door linked"
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, DirectionalDoor) or not door.is_active:
            return "Door not found"
        if not door.is_open:
            return "Door already closed"
        return None

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
        door.request_open(False, parent_event=execution_event)
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
    creates = (OpenDirectionalDoorAction, CloseDirectionalDoorAction)

    name: str = Field(default="Directional Door", description="Display name for the door object.")
    armor_class: int = Field(default=15, ge=0)
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

    def get_manual_contact_range(self) -> int:
        """Boundary handles belong to the two incident supports."""
        return 0

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
            The close action template when it is open, the open one when it is closed.
        """
        if not self.is_active:
            return []
        if self.is_open:
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

    def request_open(self, value: bool, *, parent_event: Event) -> bool:
        """Open or close it; who stands beside a door on an edge never blocks it. False: a held-shut door
        stays closed."""
        return self._request_open(value, parent_event.uuid)

    def _request_open(self, value: bool, parent_event: UUID | None) -> bool:
        if not self.is_active:
            return False
        if self.is_open == value:
            return True
        if value and self.is_held_shut():
            return False
        self._set_open(value, parent_event)
        return True

    def open(self, parent_event: Optional[UUID] = None) -> None:
        """Explicitly open the door."""
        self._request_open(True, parent_event)

    def close(self, parent_event: Optional[UUID] = None) -> None:
        """Explicitly close the door."""
        self._request_open(False, parent_event)

    def _set_open(self, value: bool, parent_event: UUID | None) -> None:
        if not self.is_active:
            return
        previous_structure = self.get_boundary_structure()
        previous_value = self.is_open
        self.is_open = value
        # An open secret door is plain to see: whoever sees it open knows it from then on. The record is
        # written before the change publishes, so the observers settling it see the door open.
        hidden = tuple((holder, holder.concealment) for holder in self.concealment_holders()
                       if holder.concealment is not None and holder.concealment.aspect in SEEN_WHEN_OPEN)
        if hidden:
            get_map().record_concealment(tuple((holder, with_plain_view(record, value)) for holder, record in hidden))
        try:
            get_map().update_object_boundary_structure(
                self.uuid,
                self.get_boundary_structure(),
                previous_structure=previous_structure,
                parent_event=parent_event,
            )
        except Exception:
            self.is_open = previous_value
            if hidden:
                get_map().record_concealment(hidden)
            raise
