"""Sensory, spatial, terrain, and low-level movement event facts."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Self, Set, Tuple, cast
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from dnd.core.action_execution import MovementProvocationPolicy
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    SpatialEffectInteractionLogData,
    SpatialEffectLogData,
    md_color,
    position_evidence_key,
)
from dnd.core.content.identities import ContentRef
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    SpatiallyIndexedEvent,
    _exact_event_evidence_equal,
)
from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnector,
    TraversalConnectorChangeOperation,
    TraversalConnectorKind,
)
from dnd.core.events.item_events import ItemState
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.damage import DamageType
from dnd.types.senses import SenseMode
from dnd.types.spatial_effects import (
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
)
from dnd.types.world import CardinalDirection, LightLevel


class WorldTileState(BaseModel):
    """Complete renderer-independent initial state of one world tile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tile_uuid: UUID
    position: Tuple[int, int]
    name: str
    walkable: bool
    visible: bool
    walking_cost: float
    flying_cost: float
    swimming_cost: float
    burrowing_cost: float
    elevation_steps: int
    surface_kind: ElevationSurfaceKind
    slope_axis: Optional[SlopeAxis] = None
    default_light: LightLevel
    resolved_light: LightLevel
    movement_open: Tuple[CardinalDirection, ...]
    vision_open: Tuple[CardinalDirection, ...]
    light_open: Tuple[CardinalDirection, ...]
    propagation_open: Tuple[CardinalDirection, ...]


class WorldObjectState(BaseModel):
    """Initial floor object and any item state stored inside it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: Tuple[int, int]
    item: ItemState
    contained_items: Tuple[ItemState, ...] = ()


class WorldConnectorState(BaseModel):
    """Initial traversal connector without renderer binding or digest fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_uuid: UUID
    authored_id: str
    kind: TraversalConnectorKind
    endpoints: Tuple[Tuple[int, int], Tuple[int, int]]
    endpoint_elevations_feet: Tuple[int, int]
    movement_cost_feet: int
    action_cost_type: Optional[ConnectorActionCostType] = None
    action_cost_amount: int = 0
    bidirectional: bool
    enabled: bool
    provocation_policy: ConnectorProvocationPolicy


class WorldInitializedEvent(Event):
    """Single terminal fact for deterministic map bootstrap."""

    name: str = Field(default="World Initialized")
    event_type: EventType = Field(default=EventType.WORLD_INITIALIZED, frozen=True)
    battlefield_id: str
    battlefield_name: str
    bounds: Tuple[int, int, int, int]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    tiles: Tuple[WorldTileState, ...]
    objects: Tuple[WorldObjectState, ...] = ()
    connectors: Tuple[WorldConnectorState, ...] = ()

def _preserve_nullable_unique_array_schema(schema: Dict[str, Any]) -> None:
    """Retain set uniqueness metadata after a JSON-only list serializer."""
    schema["default"] = None
    for option in schema.get("anyOf", []):
        if isinstance(option, dict) and option.get("type") == "array":
            option["uniqueItems"] = True

class MovementTrajectory(str, Enum):
    """Geometry used to present an ordered voluntary movement transition."""

    PATH = "path"
    DIRECT_ARC = "direct_arc"
    CONNECTOR_TRANSFER = "connector_transfer"

class SpatialChangeType(str, Enum):
    """Types of spatial changes that can occur."""
    ENTITY_ENTERED = "entity_entered"
    ENTITY_LEFT = "entity_left"
    TILE_CHANGED = "tile_changed"
    TILE_CREATED = "tile_created"
    TILE_REMOVED = "tile_removed"
    OBJECT_PLACED = "object_placed"
    OBJECT_REMOVED = "object_removed"
    PERCEIVABILITY_CHANGED = "perceivability_changed"
    LIGHT_CHANGED = "light_changed"
    OBJECT_CHANGED = "object_changed"
    MOVEMENT_COLLISION = "movement_collision"

class SensoryUpdateReason(str, Enum):
    """Why an observer's sensory state changed."""
    SPATIAL = "spatial"
    SELF_MOVEMENT = "self_movement"
    LIGHT = "light"
    PERCEIVABILITY = "perceivability"
    DEATH = "death"
    CONDITION = "condition"
    LIFE_STATE = "life_state"
    TURN_START = "turn_start"
    UNKNOWN = "unknown"

class SensesUpdateHint(BaseModel):
    """Incremental recomputation hint carried by spatial events.

    The hints separate field-of-view geometry, movement topology, light/filter
    updates, object dictionaries, and directional blocking so observers can
    update only the senses layers affected by a spatial change.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    requires_fov: bool = Field(
        default=False,
        description="Whether vision geometry must be recomputed.",
    )
    requires_paths: bool = Field(
        default=False,
        description="Whether movement/path topology must be recomputed.",
    )
    entity_entered: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for an O(1) visible-entity insertion.",
    )
    entity_left: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for an O(1) visible-entity removal.",
    )
    light_changed_positions: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Positions whose resolved light should be re-filtered.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    perceivability_entity: Optional[UUID] = Field(
        default=None,
        description="Entity UUID whose hidden/invisible perceivability should be rechecked.",
    )
    object_placed: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Object UUID and position for an O(1) visible-object insertion.",
    )
    object_removed: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Object UUID and position for an O(1) visible-object removal.",
    )
    entity_died: Optional[Tuple[UUID, Tuple[int, int]]] = Field(
        default=None,
        description="Entity UUID and position for path updates after death stops blocking movement.",
    )
    directional_positions: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Tiles whose directional blocking metadata changed.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    directional_neighbors: Optional[Set[Tuple[int, int]]] = Field(
        default=None,
        description="Neighbor cells affected by directional blocking metadata.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    directional_channels_changed: Optional[Set[str]] = Field(
        default=None,
        description="Directional channels affected, such as movement, vision, light, or propagation.",
        json_schema_extra=_preserve_nullable_unique_array_schema,
    )
    requires_light_recompute: bool = Field(
        default=False,
        description="Whether light propagation must be recomputed.",
    )
    requires_propagation_recompute: bool = Field(
        default=False,
        description="Whether non-light propagation fields must be recomputed.",
    )

    @field_serializer(
        "light_changed_positions",
        "directional_positions",
        "directional_neighbors",
        when_used="json",
    )
    def serialize_position_sets(
        self,
        value: Optional[Set[Tuple[int, int]]],
    ) -> Optional[List[Tuple[int, int]]]:
        """Emit unordered coordinate hints in canonical wire order."""
        return None if value is None else sorted(value)

    @field_serializer("directional_channels_changed", when_used="json")
    def serialize_directional_channels(
        self,
        value: Optional[Set[str]],
    ) -> Optional[List[str]]:
        """Emit unordered directional channels in canonical wire order."""
        return None if value is None else sorted(value)

class SensoryUpdateEvent(Event):
    """Observer-specific sensory state delta.

    This event records the backend-authoritative change to one observer's
    visibility/fog/entity/object perception. It is emitted before the causative
    parent completes, so clients can animate perception changes from the event
    tree without recomputing FOV or polling snapshots for timing.
    """
    name: str = Field(default="Sensory Update", description="Observer sensory state changed.")
    event_type: EventType = Field(
        default=EventType.SENSORY_UPDATE,
        description="Event category for observer-specific sensory deltas.",
    )
    observer_uuid: UUID = Field(description="Observer whose sensory state changed.")
    observer_position: Tuple[int, int] = Field(
        default=(0, 0),
        description="Observer grid position after the sensory update.",
    )
    observer_position_changed: bool = Field(
        default=False,
        description="Whether this update changed the observer's grid position.",
    )
    effective_light_levels: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Backend-resolved subjective light levels for every currently visible "
            "cell, keyed as 'x,y'."
        ),
    )
    cause_event_uuid: UUID = Field(description="Event UUID that caused this sensory update.")
    update_reason: SensoryUpdateReason = Field(
        default=SensoryUpdateReason.UNKNOWN,
        description="Reason category used by clients to interpret the delta.",
    )
    visible_cells_added: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells newly visible to the observer.",
    )
    visible_cells_removed: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells no longer visible to the observer.",
    )
    seen_cells_added: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Cells newly added to the observer's explored area.",
    )
    visible_entities_added: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Entity UUIDs and positions newly visible to the observer.",
    )
    visible_entities_removed: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Entity UUIDs and last positions no longer visible to the observer.",
    )
    visible_entities_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Entity UUIDs mapped to old and new visible positions.",
    )
    visible_objects_added: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Object UUIDs and positions newly visible to the observer.",
    )
    visible_objects_removed: Dict[UUID, Tuple[int, int]] = Field(
        default_factory=dict,
        description="Object UUIDs and last positions no longer visible to the observer.",
    )
    visible_objects_moved: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Object UUIDs mapped to old and new visible positions.",
    )
    sense_modes_changed: bool = Field(
        default=False,
        description="Whether the observer's sense modes changed.",
    )
    sense_modes: Optional[List[SenseMode]] = Field(
        default=None,
        description="Typed sense modes after a sense-mode change.",
    )
    passive_perception_changed: bool = Field(
        default=False,
        description="Whether the observer's passive perception changed.",
    )
    passive_perception: Optional[int] = Field(
        default=None,
        description="Current passive perception value when it changed.",
    )
    paths_dirty: bool = Field(
        default=False,
        description="Whether the observer should refresh cached path data.",
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return every grid cell referenced by this sensory delta."""
        positions: Set[Tuple[int, int]] = set(self.visible_cells_added)
        positions.update(self.visible_cells_removed)
        positions.update(self.seen_cells_added)
        positions.update(self.visible_entities_added.values())
        positions.update(self.visible_entities_removed.values())
        for old_pos, new_pos in self.visible_entities_moved.values():
            positions.add(old_pos)
            positions.add(new_pos)
        positions.update(self.visible_objects_added.values())
        positions.update(self.visible_objects_removed.values())
        for old_pos, new_pos in self.visible_objects_moved.values():
            positions.add(old_pos)
            positions.add(new_pos)
        return positions

_DIRECTION_DELTAS: Dict[str, Tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
}

def _directional_neighbors(position: Tuple[int, int], directions: Optional[List[str]]) -> Set[Tuple[int, int]]:
    """Return neighboring cells touched by directional tile metadata.

    Args:
        position: Origin tile for the directional metadata.
        directions: Direction labels such as north, south, east, and west.

    Returns:
        Neighboring grid positions for recognized direction labels.
    """
    neighbors: Set[Tuple[int, int]] = set()
    if not directions:
        return neighbors
    for direction in directions:
        delta = _DIRECTION_DELTAS.get(direction)
        if delta is not None:
            neighbors.add((position[0] + delta[0], position[1] + delta[1]))
    return neighbors

class SpatialEffectChangeEvent(SpatiallyIndexedEvent):
    """Observable lifecycle fact for one independent spatial phenomenon."""

    name: str = Field(
        default="Spatial Effect Change",
        description="Spatial-effect lifecycle event name.",
    )
    event_type: EventType = Field(
        default=EventType.SPATIAL_EFFECT_CHANGED,
        frozen=True,
        description="Dedicated spatial-effect lifecycle event category.",
    )
    operation: SpatialEffectChangeOperation
    spatial_effect_uuid: UUID
    spatial_effect_content_ref: ContentRef
    spatial_effect_name: str = Field(min_length=1)
    layer: SpatialEffectLayer
    anchor_position: Tuple[int, int] = Field(
        description="Authoritative effect anchor at this lifecycle boundary.",
    )
    affected_positions: Tuple[Tuple[int, int], ...] = ()
    previous_positions: Tuple[Tuple[int, int], ...] = ()

    @model_validator(mode="after")
    def validate_positions(self) -> "SpatialEffectChangeEvent":
        """Keep lifecycle geometry unique and canonically ordered."""
        if self.affected_positions != tuple(sorted(set(self.affected_positions))):
            raise ValueError(
                "spatial-effect affected positions must be unique and sorted",
            )
        if self.previous_positions != tuple(sorted(set(self.previous_positions))):
            raise ValueError(
                "spatial-effect previous positions must be unique and sorted",
            )
        return self

    def generate_combat_log(self) -> CombatLogEntry:
        """Describe effect creation, movement, transformation, or removal."""
        source_name = self.source_entity_name or "Unknown"
        if self.operation is SpatialEffectChangeOperation.CREATED:
            verb = "creates"
        elif self.operation is SpatialEffectChangeOperation.REVEALED:
            verb = "reveals"
        elif self.operation is SpatialEffectChangeOperation.REMOVED:
            verb = "removes"
        elif self.operation is SpatialEffectChangeOperation.TRANSFORMED:
            verb = "transforms"
        else:
            verb = "changes"
        reported_positions = (
            self.previous_positions
            if self.operation is SpatialEffectChangeOperation.REMOVED
            else self.affected_positions
        )
        cell_count = len(reported_positions)
        compact = (
            f"{{cyan:{source_name}}} {verb} "
            f"{{yellow:{self.spatial_effect_name}}}"
        )
        verbose = (
            f"{compact} on {cell_count} "
            f"{'cell' if cell_count == 1 else 'cells'}"
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPATIAL_EFFECT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=SpatialEffectLogData(
                operation=self.operation.value,
                content_identity=self.spatial_effect_content_ref.identity_key,
                layer=self.layer.value,
                affected_positions=reported_positions,
            ).model_dump(mode="json"),
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Expose former and resulting cells to projection and perception."""
        return set(self.affected_positions) | set(self.previous_positions)

    def spatial_dispatch_positions(self) -> tuple[Tuple[int, int], ...]:
        """Dispatch over both the former and resulting effect footprint."""
        return tuple(sorted(
            set(self.affected_positions) | set(self.previous_positions),
        ))

class SpatialEffectInteractionEvent(SpatiallyIndexedEvent):
    """One typed environmental operation applied across exact world cells."""

    name: str = Field(
        default="Spatial Effect Interaction",
        description="Environmental interaction event name.",
    )
    event_type: EventType = Field(
        default=EventType.SPATIAL_EFFECT_INTERACTION,
        frozen=True,
        description="Dedicated environmental interaction event category.",
    )
    operation: SpatialEffectInteractionOperation
    positions: Tuple[Tuple[int, int], ...]
    intensity: SpatialEffectInteractionIntensity = (
        SpatialEffectInteractionIntensity.MINOR
    )
    duration_rounds: Optional[int] = Field(default=None, ge=1)
    damage_type: Optional[DamageType] = None
    source_object_uuid: Optional[UUID] = None
    source_content_ref: Optional[ContentRef] = None

    @model_validator(mode="after")
    def validate_positions(self) -> "SpatialEffectInteractionEvent":
        """Require a nonempty unique canonical interaction footprint."""
        if not self.positions:
            raise ValueError("spatial-effect interaction requires positions")
        if self.positions != tuple(sorted(set(self.positions))):
            raise ValueError(
                "spatial-effect interaction positions must be unique and sorted",
            )
        return self

    def spatial_dispatch_positions(self) -> tuple[Tuple[int, int], ...]:
        """Return exact positions consumed by the spatial-handler index."""
        return self.positions

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Expose exact interaction cells to projection and perception."""
        return set(self.positions)

    def generate_combat_log(self) -> CombatLogEntry:
        """Describe the environmental operation without inferring outcomes."""
        source_name = self.source_entity_name or "Environment"
        operation_label = self.operation.value.replace("_", " ")
        compact = (
            f"{{cyan:{source_name}}} causes "
            f"{{yellow:{operation_label}}}"
        )
        verbose = (
            f"{compact} across {len(self.positions)} "
            f"{'cell' if len(self.positions) == 1 else 'cells'}"
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPATIAL_EFFECT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=SpatialEffectInteractionLogData(
                operation=self.operation.value,
                intensity=self.intensity.value,
                affected_positions=self.positions,
                source_content_identity=(
                    self.source_content_ref.identity_key
                    if self.source_content_ref is not None
                    else None
                ),
            ).model_dump(mode="json"),
        )

class SpatialChangeEvent(SpatiallyIndexedEvent):
    """Event fired when grid occupancy, tile state, light, or blocking changes.

    GridMap creates these as declaration events and controls registration as it
    advances the event lifecycle. The payload is consumed by senses, spatial
    handlers, combat logs, and frontend reducers.
    """

    name: str = Field(default="Spatial Change", description="A spatial change event")
    event_type: EventType = Field(default=EventType.SPATIAL_ENTITY_ENTERED, description="Type of spatial change")
    change_type: SpatialChangeType = Field(description="Specific type of spatial change")
    position: Tuple[int, int] = Field(description="Grid position where change occurred")
    entity_uuid: Optional[UUID] = Field(default=None, description="UUID of entity involved (if any)")
    object_uuid: Optional[UUID] = Field(default=None, description="UUID of object involved (if any)")
    old_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Secondary movement position: previous position on enter events, destination on leave events.",
    )
    tile_walkable: Optional[bool] = Field(default=None, description="New walkable state (for tile changes)")
    tile_visible: Optional[bool] = Field(default=None, description="New visible state (for tile changes)")
    senses_hint: Optional[SensesUpdateHint] = Field(default=None, description="Hint for incremental senses updates")

    new_light_level: Optional[int] = Field(default=None, description="Resolved light level at position after change")
    light_level_map: Optional[Dict[str, int]] = Field(default=None, description="Map of 'x,y' -> resolved light_level for all changed positions in batch")

    object_name: Optional[str] = Field(default=None, description="Object name (e.g. 'Door', 'Torch')")
    object_map_char: Optional[str] = Field(default=None, description="Object map character (e.g. 'D', 'φ')")
    object_blocks_movement: Optional[bool] = Field(default=None, description="Object blocks_movement after change")
    object_blocks_vision: Optional[bool] = Field(default=None, description="Object blocks_vision after change")
    object_is_open: Optional[bool] = Field(default=None, description="Object is_open state (doors)")

    directional_position: Optional[Tuple[int, int]] = Field(default=None, description="Tile whose directional state changed")
    directional_directions: Optional[List[str]] = Field(default=None, description="Tile-relative directions changed")
    directional_channels: Optional[List[str]] = Field(default=None, description="Directional channels changed")
    directional_blocks_movement: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> movement blocked")
    directional_blocks_vision: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> vision blocked")
    directional_blocks_light: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> light blocked")
    directional_blocks_propagation: Optional[Dict[str, bool]] = Field(default=None, description="Direction -> propagation blocked")
    transition_from: Optional[Tuple[int, int]] = Field(default=None, description="Transition source for directional movement/collision")
    transition_to: Optional[Tuple[int, int]] = Field(default=None, description="Transition destination for directional movement/collision")

    @classmethod
    def entity_entered(cls, position: Tuple[int, int], entity_uuid: UUID,
                       old_position: Optional[Tuple[int, int]] = None,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity entering a cell.

        Event starts at DECLARATION phase to allow full lifecycle:
        DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Handlers can react at EFFECT phase (entry damage, saves, etc.)
        Callbacks fire at COMPLETION for passive updates (senses).

        Args:
            position: Grid position being entered
            entity_uuid: UUID of entity entering
            old_position: Previous position (if moving)
            source_entity_uuid: Source entity for event (defaults to entity_uuid)
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov="vision" in directional_channels_set,
            requires_paths=True,
            entity_entered=(entity_uuid, position),
            entity_left=(entity_uuid, old_position) if old_position is not None else None,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=position,
            entity_uuid=entity_uuid,
            old_position=old_position,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def entity_left(cls, position: Tuple[int, int], entity_uuid: UUID,
                    new_position: Optional[Tuple[int, int]] = None,
                    source_entity_uuid: Optional[UUID] = None,
                    parent_event: Optional[UUID] = None,
                    directional_position: Optional[Tuple[int, int]] = None,
                    directional_directions: Optional[List[str]] = None,
                    directional_channels: Optional[List[str]] = None,
                    directional_blocks_movement: Optional[Dict[str, bool]] = None,
                    directional_blocks_vision: Optional[Dict[str, bool]] = None,
                    directional_blocks_light: Optional[Dict[str, bool]] = None,
                    directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity leaving a cell.

        Event starts at DECLARATION phase to allow full lifecycle:
        DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Note: old_position field stores the new_position for reference.

        Args:
            position: Grid position being left
            entity_uuid: UUID of entity leaving
            new_position: New position (if moving)
            source_entity_uuid: Source entity for event (defaults to entity_uuid)
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov="vision" in directional_channels_set,
            requires_paths=True,
            entity_left=(entity_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            change_type=SpatialChangeType.ENTITY_LEFT,
            position=position,
            entity_uuid=entity_uuid,
            old_position=new_position,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def tile_changed(cls, position: Tuple[int, int], walkable: bool, visible: bool,
                     source_entity_uuid: Optional[UUID] = None,
                     senses_hint: Optional['SensesUpdateHint'] = None,
                     parent_event: Optional[UUID] = None,
                     directional_position: Optional[Tuple[int, int]] = None,
                     directional_directions: Optional[List[str]] = None,
                     directional_channels: Optional[List[str]] = None,
                     directional_blocks_movement: Optional[Dict[str, bool]] = None,
                     directional_blocks_vision: Optional[Dict[str, bool]] = None,
                     directional_blocks_light: Optional[Dict[str, bool]] = None,
                     directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile property change.

        Event starts at DECLARATION phase to allow full lifecycle.
        If no senses_hint is provided, one is auto-generated from walkable/visible flags
        requiring FOV if visible changed and paths if walkable changed.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        if senses_hint is None:
            senses_hint = SensesUpdateHint(
                requires_fov=True or "vision" in directional_channels_set,
                requires_paths=True or "movement" in directional_channels_set,
                directional_positions={directional_pos} if directional_channels_set else None,
                directional_neighbors=directional_neighbors or None,
                directional_channels_changed=directional_channels_set or None,
                requires_light_recompute="light" in directional_channels_set,
                requires_propagation_recompute="propagation" in directional_channels_set,
            )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_TILE_CHANGED,
            change_type=SpatialChangeType.TILE_CHANGED,
            position=position,
            tile_walkable=walkable,
            tile_visible=visible,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=senses_hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def object_placed(cls, position: Tuple[int, int], object_uuid: UUID,
                      source_entity_uuid: Optional[UUID] = None,
                      parent_event: Optional[UUID] = None,
                      blocks_vision: bool = False,
                      blocks_walking: bool = False,
                      object_name: Optional[str] = None,
                      object_map_char: Optional[str] = None,
                      directional_position: Optional[Tuple[int, int]] = None,
                      directional_directions: Optional[List[str]] = None,
                      directional_channels: Optional[List[str]] = None,
                      directional_blocks_movement: Optional[Dict[str, bool]] = None,
                      directional_blocks_vision: Optional[Dict[str, bool]] = None,
                      directional_blocks_light: Optional[Dict[str, bool]] = None,
                      directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object being placed on the grid."""
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision or "vision" in directional_channels_set,
            requires_paths=blocks_walking or "movement" in directional_channels_set,
            object_placed=(object_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_OBJECT_PLACED,
            change_type=SpatialChangeType.OBJECT_PLACED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            object_name=object_name,
            object_map_char=object_map_char,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def object_removed(cls, position: Tuple[int, int], object_uuid: UUID,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       blocks_vision: bool = False,
                       blocks_walking: bool = False,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object being removed from the grid."""
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision or "vision" in directional_channels_set,
            requires_paths=blocks_walking or "movement" in directional_channels_set,
            object_removed=(object_uuid, position),
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or uuid4(),
            event_type=EventType.SPATIAL_OBJECT_REMOVED,
            change_type=SpatialChangeType.OBJECT_REMOVED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def perceivability_changed(cls, position: Tuple[int, int], entity_uuid: UUID,
                               source_entity_uuid: Optional[UUID] = None,
                               parent_event: Optional[UUID] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity's perceivability changing (hidden/invisible).

        This is a lightweight event that only triggers senses re-evaluation
        on observers subscribed to this cell. Does NOT trigger SpatialHandlers (zone effects).
        """
        hint = SensesUpdateHint(
            perceivability_entity=entity_uuid,
            requires_paths=True,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or entity_uuid,
            event_type=EventType.SPATIAL_PERCEIVABILITY_CHANGED,
            change_type=SpatialChangeType.PERCEIVABILITY_CHANGED,
            position=position,
            entity_uuid=entity_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
        )

    @classmethod
    def light_changed(cls, position: Tuple[int, int], tile_uuid: UUID,
                      source_entity_uuid: Optional[UUID] = None,
                      senses_hint: Optional['SensesUpdateHint'] = None,
                      parent_event: Optional[UUID] = None,
                      new_light_level: Optional[int] = None,
                      light_level_map: Optional[Dict[str, int]] = None) -> 'SpatialChangeEvent':
        """Create an event for a tile's resolved light level changing.

        Triggers senses re-evaluation on observers subscribed to this cell.
        Does NOT trigger SpatialHandlers (zone effects).
        """
        if senses_hint is None:
            senses_hint = SensesUpdateHint(
                light_changed_positions={position},
            )
        return cls(
            source_entity_uuid=source_entity_uuid or tile_uuid,
            event_type=EventType.SPATIAL_LIGHT_CHANGED,
            change_type=SpatialChangeType.LIGHT_CHANGED,
            position=position,
            entity_uuid=tile_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=senses_hint,
            new_light_level=new_light_level,
            light_level_map=light_level_map,
        )

    @classmethod
    def object_changed(cls, position: Tuple[int, int], object_uuid: UUID,
                       blocks_vision_changed: bool = False,
                       blocks_walking_changed: bool = False,
                       source_entity_uuid: Optional[UUID] = None,
                       parent_event: Optional[UUID] = None,
                       object_name: Optional[str] = None,
                       object_map_char: Optional[str] = None,
                       object_blocks_movement: Optional[bool] = None,
                       object_blocks_vision: Optional[bool] = None,
                       object_is_open: Optional[bool] = None,
                       directional_position: Optional[Tuple[int, int]] = None,
                       directional_directions: Optional[List[str]] = None,
                       directional_channels: Optional[List[str]] = None,
                       directional_blocks_movement: Optional[Dict[str, bool]] = None,
                       directional_blocks_vision: Optional[Dict[str, bool]] = None,
                       directional_blocks_light: Optional[Dict[str, bool]] = None,
                       directional_blocks_propagation: Optional[Dict[str, bool]] = None) -> 'SpatialChangeEvent':
        """Create an event for an object's blocking state changing (door open/close).

        Fires when an object's blocks_movement or blocks_vision_field changes
        while on the grid. Carries hint indicating which senses layers are affected.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_fov=blocks_vision_changed or "vision" in directional_channels_set,
            requires_paths=blocks_walking_changed or "movement" in directional_channels_set,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
            requires_light_recompute="light" in directional_channels_set,
            requires_propagation_recompute="propagation" in directional_channels_set,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or object_uuid,
            event_type=EventType.SPATIAL_OBJECT_CHANGED,
            change_type=SpatialChangeType.OBJECT_CHANGED,
            position=position,
            object_uuid=object_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            object_name=object_name,
            object_map_char=object_map_char,
            object_blocks_movement=object_blocks_movement,
            object_blocks_vision=object_blocks_vision,
            object_is_open=object_is_open,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
            directional_blocks_movement=directional_blocks_movement,
            directional_blocks_vision=directional_blocks_vision,
            directional_blocks_light=directional_blocks_light,
            directional_blocks_propagation=directional_blocks_propagation,
        )

    @classmethod
    def movement_collision(cls, position: Tuple[int, int], mover_uuid: UUID,
                           source_entity_uuid: Optional[UUID] = None,
                           parent_event: Optional[UUID] = None,
                           transition_from: Optional[Tuple[int, int]] = None,
                           transition_to: Optional[Tuple[int, int]] = None,
                           directional_position: Optional[Tuple[int, int]] = None,
                           directional_directions: Optional[List[str]] = None,
                           directional_channels: Optional[List[str]] = None) -> 'SpatialChangeEvent':
        """Create an event for an entity bumping into an imperceivable blocker.

        Fired when objective walkability blocks but subjective would allow.
        Hidden entities at this position will be de-stealthed by their reveal handler.
        """
        directional_channels_set = set(directional_channels or [])
        directional_pos = directional_position or position
        directional_neighbors = _directional_neighbors(directional_pos, directional_directions)
        hint = SensesUpdateHint(
            requires_paths=True,
            directional_positions={directional_pos} if directional_channels_set else None,
            directional_neighbors=directional_neighbors or None,
            directional_channels_changed=directional_channels_set or None,
        )
        return cls(
            source_entity_uuid=source_entity_uuid or mover_uuid,
            event_type=EventType.MOVEMENT_COLLISION,
            change_type=SpatialChangeType.MOVEMENT_COLLISION,
            position=position,
            entity_uuid=mover_uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=parent_event,
            senses_hint=hint,
            transition_from=transition_from,
            transition_to=transition_to,
            directional_position=directional_position,
            directional_directions=directional_directions,
            directional_channels=directional_channels,
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        positions = {self.position}
        if self.old_position:
            positions.add(self.old_position)
        if self.directional_position:
            positions.add(self.directional_position)
            positions.update(_directional_neighbors(self.directional_position, self.directional_directions))
        if self.transition_from:
            positions.add(self.transition_from)
        if self.transition_to:
            positions.add(self.transition_to)
        if self.senses_hint:
            if self.senses_hint.directional_positions:
                positions.update(self.senses_hint.directional_positions)
            if self.senses_hint.directional_neighbors:
                positions.update(self.senses_hint.directional_neighbors)
        return positions

    def spatial_dispatch_positions(self) -> tuple[Tuple[int, int], ...]:
        """Dispatch the spatial transition at its committed event position.

        ``get_affected_positions`` is deliberately broader: it is sensory and
        evidence metadata and may include the former cell, directional
        neighbours, or both transition endpoints.  Zone-entry/leave handlers
        must only receive the cell where this event actually occurred.
        """
        return (self.position,)

class TileElevationChangeEvent(SpatialChangeEvent):
    """Guarded precommit proposal for one Tile support-tuple mutation."""

    name: str = Field(default="Tile Elevation Change")
    event_type: EventType = Field(default=EventType.SPATIAL_TILE_CHANGED)
    change_type: SpatialChangeType = Field(default=SpatialChangeType.TILE_CHANGED)
    senses_hint: Optional[SensesUpdateHint] = Field(
        default_factory=lambda: SensesUpdateHint(requires_paths=True)
    )
    position: Tuple[int, int]
    tile_uuid: UUID
    old_height_steps: int
    new_height_steps: int
    old_surface_kind: ElevationSurfaceKind
    new_surface_kind: ElevationSurfaceKind
    old_slope_axis: Optional[SlopeAxis] = None
    new_slope_axis: Optional[SlopeAxis] = None

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Detach guarded proposals from queue-owned mutable evidence."""
        return super().model_copy(update=update, deep=True)

    def validate_handler_result(self, result: Event) -> Event:
        """Allow vetoes while freezing the authored support mutation."""
        active_proposal = EventQueue.is_active_handler_proposal(result)

        def cancellation(status_message: str) -> TileElevationChangeEvent:
            canceled = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(
                TileElevationChangeEvent,
                canceled.model_copy(
                    update={
                        "use_register": False if active_proposal else self.use_register,
                    }
                ),
            )

        if type(result) is not TileElevationChangeEvent:
            return cancellation(
                "Tile elevation handler returned an incompatible event type."
            )
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and (
                result.status_message is None
                or type(result.status_message) is str
            )
            and type(result.use_register) is bool
        ):
            return cancellation(
                "Tile elevation handler returned malformed queue evidence."
            )
        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(update={"use_register": True})
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return cancellation("Tile elevation handler changed lifecycle evidence.")
        if result.canceled:
            return cancellation(result.status_message or "Tile elevation change canceled.")

        handler_mutable_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
            "use_register",
        }

        def exact_evidence_equal(expected: Any, candidate: Any) -> bool:
            if type(candidate) is not type(expected):
                return False
            if isinstance(expected, BaseModel):
                return all(
                    exact_evidence_equal(
                        getattr(expected, field_name),
                        getattr(candidate, field_name),
                    )
                    for field_name in type(expected).model_fields
                )
            if isinstance(expected, (list, tuple)):
                return len(expected) == len(candidate) and all(
                    exact_evidence_equal(left, right)
                    for left, right in zip(expected, candidate)
                )
            if isinstance(expected, dict):
                if len(expected) != len(candidate):
                    return False
                unmatched = list(candidate.items())
                for expected_key, expected_value in expected.items():
                    match_index = next(
                        (
                            index
                            for index, (candidate_key, _candidate_value)
                            in enumerate(unmatched)
                            if exact_evidence_equal(expected_key, candidate_key)
                        ),
                        None,
                    )
                    if match_index is None:
                        return False
                    _candidate_key, candidate_value = unmatched.pop(match_index)
                    if not exact_evidence_equal(expected_value, candidate_value):
                        return False
                return True
            if isinstance(expected, (set, frozenset)):
                return len(expected) == len(candidate) and all(
                    any(
                        exact_evidence_equal(expected_item, candidate_item)
                        for candidate_item in candidate
                    )
                    for expected_item in expected
                )
            return candidate == expected

        if any(
            not exact_evidence_equal(
                getattr(self, field_name),
                getattr(result, field_name),
            )
            for field_name in type(self).model_fields
            if field_name not in handler_mutable_fields
        ):
            return cancellation(
                "Tile elevation handler changed authored or queue evidence."
            )
        return result

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.position}

class ForcedMovementEvent(Event):
    """Forced movement event for pushes, pulls, and similar displacement.

    This uses `FORCED_MOVEMENT` rather than `MOVEMENT`, so opportunity-attack
    handlers that listen to voluntary movement do not trigger. GridMap still
    emits spatial enter/leave events when the target position changes.
    """

    name: str = Field(default="Forced Movement", description="Human-readable forced-movement label.")
    event_type: EventType = Field(
        default=EventType.FORCED_MOVEMENT,
        description="Event category for forced displacement.",
    )
    start_position: Tuple[int, int] = Field(description="Target position before displacement.")
    end_position: Tuple[int, int] = Field(description="Target position after displacement.")
    direction: Tuple[int, int] = Field(description="Displacement direction as (dx, dy).")
    intended_distance: int = Field(description="Requested displacement distance in feet.")
    actual_distance: int = Field(default=0, description="Distance actually moved in feet.")
    blocked_by_obstacle: bool = Field(default=False, description="Whether an obstacle stopped movement early.")
    blocked_by: Optional[str] = Field(default=None, description="Obstacle or entity that blocked movement.")
    cause: str = Field(default="shove", description="Mechanic that caused the displacement.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for forced movement."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        blocked_suffix = ""
        if self.blocked_by_obstacle:
            if self.blocked_by:
                blocked_suffix = f" (blocked by {self.blocked_by})"
            else:
                blocked_suffix = " (blocked)"

        if self.actual_distance == 0:
            compact_text = f"{md_color(target_name, 'yellow')} resists being pushed"
        elif self.blocked_by_obstacle:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}{blocked_suffix}"
        else:
            compact_text = f"{md_color(target_name, 'yellow')} pushed {md_color(f'{self.actual_distance}ft', 'green')}"

        verbose_text = f"{md_color(source_name, 'cyan')} pushes {md_color(target_name, 'yellow')}"
        if self.actual_distance > 0:
            verbose_text += f" {md_color(f'{self.actual_distance}ft', 'green')}"
            verbose_text += f": {self.start_position} \u2192 {self.end_position}"
            if self.blocked_by_obstacle:
                verbose_text += blocked_suffix
        else:
            verbose_text += f" - {md_color('resisted', 'red')}"

        detailed_text = verbose_text
        detailed_text += f"\n  Direction: {self.direction}"
        detailed_text += f"\n  {self.start_position} → {self.end_position}"
        if self.actual_distance != self.intended_distance:
            detailed_text += f"\n  Intended: {self.intended_distance}ft, Actual: {self.actual_distance}ft"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "type": "forced_movement",
                "cause": self.cause,
                "direction": list(self.direction),
                "intended_distance": self.intended_distance,
                "actual_distance": self.actual_distance,
                "blocked": self.blocked_by_obstacle,
                "blocked_by": self.blocked_by,
                "start_position": list(self.start_position),
                "end_position": list(self.end_position)
            },
            success=self.actual_distance > 0
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.start_position, self.end_position}

    def completion_position_observer_evidence(
        self,
        completion_locations: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        """Freeze independent pre-displacement and post-displacement grants."""
        if (
            self.target_entity_uuid is None
            or self.phase is not EventPhase.EFFECT
        ):
            return super().completion_position_observer_evidence(
                completion_locations
            )
        entity_key = str(self.target_entity_uuid)
        evidence = super().completion_position_observer_evidence(
            completion_locations
        )
        evidence[position_evidence_key(self.start_position)] = set(
            self.located_entity_observer_uuids.get(entity_key, set())
        )
        evidence[position_evidence_key(self.end_position)] = set(
            completion_locations.get(entity_key, set())
        )
        return evidence

class TraversalConnectorChangeEvent(Event):
    """Guarded precommit lifecycle for one GridMap connector mutation."""

    name: str = Field(default="Traversal Connector Change")
    event_type: EventType = Field(default=EventType.TRAVERSAL_CONNECTOR_CHANGED)
    operation: TraversalConnectorChangeOperation
    connector_uuid: UUID
    authored_id: str
    old_connector: Optional[TraversalConnector] = None
    new_connector: Optional[TraversalConnector] = None

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Detach the small connector proposal from queue-owned evidence."""
        del deep
        return super().model_copy(update=update, deep=True)

    def validate_handler_result(self, result: Event) -> Event:
        """Permit exact vetoes while freezing every connector mutation fact."""
        active_proposal = EventQueue.is_active_handler_proposal(result)

        def cancellation(status_message: str) -> TraversalConnectorChangeEvent:
            canceled = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(
                TraversalConnectorChangeEvent,
                canceled.model_copy(update={
                    "use_register": False if active_proposal else self.use_register,
                }),
            )

        if type(result) is not TraversalConnectorChangeEvent:
            return cancellation(
                "Connector change handler returned an incompatible event type."
            )
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and type(result.use_register) is bool
            and (
                result.status_message is None
                or type(result.status_message) is str
            )
        ):
            return cancellation(
                "Connector change handler returned malformed queue evidence."
            )
        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(update={"use_register": True})
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return cancellation("Connector change handler changed lifecycle evidence.")
        if result.canceled:
            return cancellation(result.status_message or "Connector change canceled.")

        mutable_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
            "use_register",
        }
        if any(
            not _exact_event_evidence_equal(
                getattr(self, field_name),
                getattr(result, field_name),
            )
            for field_name in type(self).model_fields
            if field_name not in mutable_fields
        ):
            return cancellation(
                "Connector change handler changed authored or queue evidence."
            )
        return result

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return both old and new endpoint coordinates."""
        return {
            endpoint.position
            for connector in (self.old_connector, self.new_connector)
            if connector is not None
            for endpoint in connector.endpoints
        }

class StepMovementEvent(Event):
    """Single cell transition within a movement path.

    Fires for each step during cell-by-cell movement. Opportunity attacks
    and terrain effects trigger on this event type.

    The source_entity_uuid is the entity moving.
    """
    name: str = Field(default="Step Movement")
    event_type: EventType = Field(default=EventType.STEP_MOVEMENT)

    from_position: Tuple[int, int] = Field(description="Position before this step")
    to_position: Tuple[int, int] = Field(description="Position after this step")
    path_index: int = Field(default=0, description="Index of this step in the overall path")
    total_path_length: int = Field(default=0, description="Total number of positions in path")
    movement_cost: float = Field(default=5.0, description="Movement cost in feet for this step")
    trajectory: MovementTrajectory = Field(
        default=MovementTrajectory.PATH,
        description="Typed trajectory shared by every step in the movement action.",
    )
    disclosed_path: Tuple[Tuple[int, int], ...] = Field(
        default_factory=tuple,
        description="Authorized presentation geometry for this one movement leg.",
    )
    from_elevation_feet: int = Field(
        default=0,
        description="Support elevation at the objective source endpoint.",
    )
    to_elevation_feet: int = Field(
        default=0,
        description="Support elevation at the objective destination endpoint.",
    )
    provocation_policy: MovementProvocationPolicy = Field(
        default=MovementProvocationPolicy.ORDINARY_EXIT,
        description="Source-exit opportunity-attack policy for this leg.",
    )
    committed: bool = Field(
        default=False,
        description="Whether the entity position was committed to the destination cell.",
    )

    def guards_handler_result(self) -> bool:
        """Guard every authored movement leg before handler publication."""
        return True

    def guarded_related_queue_inputs(self) -> tuple[Event, ...]:
        """Keep the queue-owned movement root immutable between Step handlers."""
        if self.parent_event is None:
            return ()
        parent = EventQueue.get_event_by_uuid(self.parent_event)
        return (parent,) if parent is not None else ()

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Copy a small leg proposal without aliasing causal evidence."""
        del deep
        return super().model_copy(update=update, deep=True)

    def validate_handler_result(self, result: Event) -> Event:
        """Reject handlers that rewrite the pending movement-leg contract."""
        active_proposal = EventQueue.is_active_handler_proposal(result)
        safe_status = (
            result.status_message
            if isinstance(result.status_message, str)
            or result.status_message is None
            else self.status_message
        )
        queue_updates: Dict[str, Any] = {
            "lineage_children_events": list(self.lineage_children_events),
            "children_events": list(self.children_events),
            "children_lineages": list(self.children_lineages),
            "identified_entity_observer_uuids": {
                key: set(observer_uuids)
                for key, observer_uuids in (
                    self.identified_entity_observer_uuids.items()
                )
            },
            "located_entity_observer_uuids": {
                key: set(observer_uuids)
                for key, observer_uuids in (
                    self.located_entity_observer_uuids.items()
                )
            },
            "located_position_observer_uuids": {
                key: set(observer_uuids)
                for key, observer_uuids in (
                    self.located_position_observer_uuids.items()
                )
            },
        }

        def cancellation(status_message: str) -> StepMovementEvent:
            canceled = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(StepMovementEvent, canceled.model_copy(update={
                **queue_updates,
                "use_register": (
                    False if active_proposal else self.use_register
                ),
            }))

        def effect_stop(status_message: str) -> StepMovementEvent:
            stopped = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(StepMovementEvent, stopped.model_copy(update={
                **queue_updates,
                "phase": EventPhase.EFFECT,
                "canceled": False,
                "canceled_from_phase": self.canceled_from_phase,
                "committed": False,
                "outcome_code": "movement.step_stopped",
                "use_register": False if active_proposal else self.use_register,
            }))

        def reject(status_message: str) -> StepMovementEvent:
            if (
                self.phase is EventPhase.EFFECT
                and self.trajectory is not MovementTrajectory.PATH
            ):
                return effect_stop(status_message)
            return cancellation(status_message)

        if type(result) is not StepMovementEvent:
            return reject(
                "Movement step handler returned an incompatible event type."
            )
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and type(result.use_register) is bool
            and (
                result.status_message is None
                or type(result.status_message) is str
            )
        ):
            return reject(
                "Movement step handler returned malformed queue evidence."
            )
        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(
                update={"use_register": True}
            )
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return reject(
                "Movement step handler changed lifecycle evidence."
            )
        if result.canceled:
            return reject(
                safe_status or "Movement step canceled by handler."
            )

        allowed_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
            "use_register",
        }
        if (
            self.committed is not False
            or type(result.committed) is not bool
            or result.committed is not False
            or any(
                not _exact_event_evidence_equal(
                    getattr(self, field_name),
                    getattr(result, field_name),
                )
                for field_name in type(self).model_fields
                if field_name not in allowed_fields
            )
        ):
            return reject(
                "Movement step evidence changed before settlement."
            )

        if (
            not active_proposal
            and result.uuid == self.uuid
            and result.timestamp == self.timestamp
            and result.modified == self.modified
            and safe_status == self.status_message
        ):
            return self

        result_uuid = result.uuid
        result_changed = (
            safe_status != self.status_message
            or result.timestamp != self.timestamp
        )
        if result_uuid == self.uuid and result_changed:
            result_uuid = uuid4()
        return self.model_copy(update={
            **queue_updates,
            "uuid": result_uuid,
            "timestamp": result.timestamp,
            "modified": result.modified or result_changed,
            "status_message": safe_status,
            "use_register": False if active_proposal else self.use_register,
        })

    def handler_result_stops_dispatch(self, result: Event) -> bool:
        """Keep a rejected accepted-EFFECT leg terminal within dispatch."""
        return (
            super().handler_result_stops_dispatch(result)
            or type(result) is StepMovementEvent
            and result.phase is EventPhase.EFFECT
            and result.trajectory is not MovementTrajectory.PATH
            and result.outcome_code == "movement.step_stopped"
        )

    def completion_position_observer_evidence(
        self,
        completion_locations: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        """Freeze committed occupancy or the exact perceived attempted edge."""
        if self.trajectory is MovementTrajectory.DIRECT_ARC:
            entity_key = str(self.source_entity_uuid)
            evidence = super().completion_position_observer_evidence(
                completion_locations
            )
            evidence[position_evidence_key(self.from_position)] = set(
                self.located_position_observer_uuids.get(
                    position_evidence_key(self.from_position),
                    self.located_entity_observer_uuids.get(entity_key, set()),
                )
            )
            evidence[position_evidence_key(self.to_position)] = set(
                completion_locations.get(entity_key, set())
                if self.committed
                else self.located_position_observer_uuids.get(
                    position_evidence_key(self.to_position),
                    set(),
                )
            )
            return evidence

        entity_key = str(self.source_entity_uuid)
        evidence = super().completion_position_observer_evidence(
            completion_locations
        )
        evidence[position_evidence_key(self.from_position)] = set(
            self.located_position_observer_uuids.get(
                position_evidence_key(self.from_position),
                self.located_entity_observer_uuids.get(entity_key, set()),
            )
        )
        evidence[position_evidence_key(self.to_position)] = set(
            self.located_position_observer_uuids.get(
                position_evidence_key(self.to_position), set()
            )
        )
        return evidence

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for a movement step (usually not logged individually)."""
        if not self.committed:
            return None
        source_name = self.source_entity_name or "Unknown"

        compact_text = f"{md_color(source_name, 'cyan')} steps to {self.to_position}"
        verbose_text = f"{md_color(source_name, 'cyan')} {self.from_position} → {self.to_position}"
        detailed_text = f"{verbose_text} (step {self.path_index}/{self.total_path_length - 1}, {self.movement_cost}ft)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "type": "step_movement",
                "from_position": list(self.from_position),
                "to_position": list(self.to_position),
                "path_index": self.path_index,
                "movement_cost": self.movement_cost,
                "trajectory": self.trajectory.value,
                "disclosed_path": [list(position) for position in self.disclosed_path],
                "from_elevation_feet": self.from_elevation_feet,
                "to_elevation_feet": self.to_elevation_feet,
                "provocation_policy": self.provocation_policy.value,
                "committed": self.committed,
            },
            success=True
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.from_position, self.to_position}
