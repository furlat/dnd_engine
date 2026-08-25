"""Authoritative observer-local perception and navigation state."""

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, List, Optional, Self, Set, Tuple, TypeVar
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.base_block import BaseBlock
from dnd.core.elevation import support_distance_feet
from dnd.core.events.encounter_events import DeathEvent
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.types.senses import OpticalObscurement, PerceivedContact, SenseMode, SensesType
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel


K = TypeVar("K")
Position = Tuple[int, int]


class Senses(BaseBlock):
    """Materialized subjective perception plus derived navigation caches."""

    visual_access: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID(int=0),
            base_value=1,
            value_name="Visual Access",
        ),
        description="Neutral 1/0 gate for visual perception.",
    )
    entities: Dict[UUID, PerceivedContact] = Field(
        default_factory=dict,
        description="Identified creature contacts keyed by UUID.",
    )
    objects: Dict[UUID, PerceivedContact] = Field(
        default_factory=dict,
        description="Identified world-object contacts keyed by UUID.",
    )
    visible: Dict[Position, bool] = Field(
        default_factory=dict,
        description="Cells visually accessible after optics, light, and senses.",
    )
    effective_light_levels: Dict[Position, LightLevel] = Field(
        default_factory=dict,
        description="Subjective light after-values for visually accessible cells.",
    )
    walkable: Dict[Position, bool] = Field(
        default_factory=dict,
        description="Derived subjective walkability keyed by position.",
    )
    paths: DefaultDict[Position, List[Position]] = Field(
        default_factory=lambda: defaultdict(list),
        description="Derived subjective paths keyed by destination.",
    )
    path_costs: Dict[Position, int] = Field(
        default_factory=dict,
        description="Derived subjective movement costs keyed by destination.",
    )
    safe_paths: Dict[Position, List[Position]] = Field(
        default_factory=dict,
        description="Derived paths avoiding hazards known to the observer.",
    )
    safe_path_costs: Dict[Position, int] = Field(
        default_factory=dict,
        description="Derived safe-path costs keyed by destination.",
    )
    sense_modes: List[SenseMode] = Field(
        default_factory=list,
        description="Innate special senses and their exact ranges.",
    )
    sense_mode_sources: Dict[UUID, SenseMode] = Field(
        default_factory=dict,
        description="Temporary source-owned sense grants keyed by source UUID.",
    )
    seen: Set[Position] = Field(
        default_factory=set,
        description="Cells this observer has visually explored.",
    )
    collision_blocked: Set[Position] = Field(
        default_factory=set,
        description="Positions learned blocked by movement collision.",
    )
    directional_collision_blocked: Set[Tuple[Position, str]] = Field(
        default_factory=set,
        description="Directional transitions learned blocked by collision.",
    )

    _paths_dirty: bool = PrivateAttr(default=False)
    _last_passive_perception: int = PrivateAttr(default=0)
    _last_sense_modes_hash: int = PrivateAttr(default_factory=lambda: hash(()))
    _last_visual_access: int = PrivateAttr(default=1)
    _path_revision: int = PrivateAttr(default=0)
    _path_max_distance: Optional[int] = PrivateAttr(default=None)

    @property
    def path_revision(self) -> int:
        """Return the revision of materialized navigation facts."""
        return self._path_revision

    @property
    def path_max_distance(self) -> Optional[int]:
        """Return the movement-cost radius covered by cached paths."""
        return self._path_max_distance

    def has_clean_paths_for_distance(self, max_distance: int) -> bool:
        """Return whether navigation facts are current for the requested radius."""
        return (
            not self._paths_dirty
            and self._path_max_distance is not None
            and self._path_max_distance >= max_distance
        )

    def compute_sense_modes_hash(self) -> int:
        """Return a stable-in-process hash of effective sense modes."""
        return hash(tuple(
            (mode.sense_type.value, mode.range_feet)
            for mode in self.get_sense_modes()
        ))

    def has_sense(self, sense_type: SensesType) -> bool:
        """Return whether any effective mode provides this sense."""
        return any(mode.sense_type is sense_type for mode in self.get_sense_modes())

    def get_sense_range(self, sense_type: SensesType) -> int:
        """Return the effective range, or -1 when the sense is absent."""
        for mode in self.get_sense_modes():
            if mode.sense_type is sense_type:
                return mode.range_feet
        return -1

    def get_sense_modes(self) -> List[SenseMode]:
        """Combine innate and source-owned modes using their widest range."""
        ranges: Dict[SensesType, int] = {}
        for mode in (*self.sense_modes, *self.sense_mode_sources.values()):
            current = ranges.get(mode.sense_type)
            if current is None:
                ranges[mode.sense_type] = mode.range_feet
            elif current == 0 or mode.range_feet == 0:
                ranges[mode.sense_type] = 0
            else:
                ranges[mode.sense_type] = max(current, mode.range_feet)
        return [
            SenseMode(sense_type=sense_type, range_feet=ranges[sense_type])
            for sense_type in sorted(ranges, key=lambda value: value.value)
        ]

    def add_sense_mode_source(self, source_id: UUID, mode: SenseMode) -> None:
        """Install one exact source-owned special-sense contribution."""
        existing = self.sense_mode_sources.get(source_id)
        if existing is not None and existing != mode:
            raise ValueError(f"sense source {source_id} already owns a different mode")
        self.sense_mode_sources[source_id] = mode

    def remove_sense_mode_source(self, source_id: UUID) -> bool:
        """Remove one source-owned sense contribution if present."""
        return self.sense_mode_sources.pop(source_id, None) is not None

    def get_distance(self, position: Position) -> int:
        """Return support-aware distance in five-foot cells."""
        return self.get_feet_distance(position) // 5

    def get_feet_distance(self, position: Position) -> int:
        """Return support-aware distance in rules feet."""
        grid = get_map()
        source_tile = grid.get_tile(*self.position)
        target_tile = grid.get_tile(*position)
        if source_tile is None or target_tile is None:
            raise ValueError("distance requires both support tiles")
        return support_distance_feet(
            self.position,
            source_tile.height * 5,
            position,
            target_tile.height * 5,
        )

    def update_seen(self, visible: Dict[Position, bool]) -> None:
        """Add currently visible cells to explored memory."""
        self.seen.update(position for position, value in visible.items() if value)

    def replace_perception(
        self,
        *,
        position: Position,
        visible: Dict[Position, bool],
        seen: Set[Position],
        entities: Dict[UUID, PerceivedContact],
        objects: Dict[UUID, PerceivedContact],
        effective_light_levels: Dict[Position, LightLevel],
        passive_perception: int,
        sense_modes_hash: int,
        visual_access: int,
    ) -> None:
        """Replace the replay-owned observer projection in one operation."""
        self.position = position
        self.visible = visible
        self.seen = seen
        self.entities = entities
        self.objects = objects
        self.effective_light_levels = effective_light_levels
        self._last_passive_perception = passive_perception
        self._last_sense_modes_hash = sense_modes_hash
        self._last_visual_access = visual_access

    def apply_sensory_update(self, event: SensoryUpdateEvent) -> None:
        """Reduce one recorded after-value delta without querying live world state."""
        if event.observer_uuid != self.source_entity_uuid:
            raise ValueError("sensory update belongs to a different observer")

        visible = dict(self.visible)
        for position in event.visible_cells_removed:
            visible.pop(position, None)
        for position in event.visible_cells_added:
            visible[position] = True

        entities = dict(self.entities)
        for entity_uuid in event.entity_contacts_removed:
            entities.pop(entity_uuid, None)
        entities.update(event.entity_contacts_changed)

        objects = dict(self.objects)
        for object_uuid in event.object_contacts_removed:
            objects.pop(object_uuid, None)
        objects.update(event.object_contacts_changed)

        light_levels = dict(self.effective_light_levels)
        for position in event.visible_cells_removed:
            light_levels.pop(position, None)
        for key, level in event.effective_light_levels_changed.items():
            x_text, y_text = key.split(",", maxsplit=1)
            light_levels[(int(x_text), int(y_text))] = LightLevel(level)

        if event.sense_modes_changed and event.sense_modes is not None:
            event_modes = [mode.model_copy(deep=True) for mode in event.sense_modes]
            if self.get_sense_modes() != event_modes:
                self.sense_modes = event_modes
                self.sense_mode_sources.clear()

        self.replace_perception(
            position=(
                event.observer_position
                if event.observer_position_changed
                else self.position
            ),
            visible=visible,
            seen=set(self.seen) | set(event.seen_cells_added),
            entities=entities,
            objects=objects,
            effective_light_levels=light_levels,
            passive_perception=(
                event.passive_perception
                if event.passive_perception_changed
                and event.passive_perception is not None
                else self._last_passive_perception
            ),
            sense_modes_hash=(
                self.compute_sense_modes_hash()
                if event.sense_modes_changed
                else self._last_sense_modes_hash
            ),
            visual_access=(
                event.visual_access
                if event.visual_access_changed and event.visual_access is not None
                else self._last_visual_access
            ),
        )
        if event.paths_dirty:
            self._paths_dirty = True

    def replace_navigation(
        self,
        *,
        walkable: Dict[Position, bool],
        paths: DefaultDict[Position, List[Position]],
        path_costs: Dict[Position, int],
        safe_paths: Dict[Position, List[Position]],
        safe_path_costs: Dict[Position, int],
        path_max_distance: int,
    ) -> None:
        """Replace only derived navigation caches; perception is untouched."""
        self.walkable = walkable
        self.paths = paths
        self.path_costs = path_costs
        self.safe_paths = safe_paths
        self.safe_path_costs = safe_path_costs
        self._path_max_distance = path_max_distance
        self._paths_dirty = False
        self._path_revision += 1

    def get_threathened_positions(self) -> List[Position]:
        position = self.position
        neighbors = {
            (position[0] + dx, position[1] + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if dx != 0 or dy != 0
        }
        visible = {cell for cell, value in self.visible.items() if value}
        walkable = {cell for cell, value in self.walkable.items() if value}
        grid = get_map()
        return [
            cell
            for cell in neighbors & visible & walkable
            if grid.can_propagate_transition(position, cell, self.source_entity_uuid)
        ]

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        name: str = "Senses",
        source_entity_name: Optional[str] = None,
        target_entity_uuid: Optional[UUID] = None,
        target_entity_name: Optional[str] = None,
        position: Position = (0, 0),
    ) -> Self:
        return cls(
            source_entity_uuid=source_entity_uuid,
            name=name,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            position=position,
        )


@dataclass(frozen=True)
class SensesSnapshot:
    """Frozen perception state used to derive a replayable sensory delta."""

    position: Position
    visible: Set[Position]
    seen: Set[Position]
    entities: Dict[UUID, PerceivedContact]
    objects: Dict[UUID, PerceivedContact]
    effective_light_levels: Dict[Position, LightLevel]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    visual_access: int


def capture_senses_snapshot(senses: Senses) -> SensesSnapshot:
    """Capture the replay-owned fields needed to derive one delta."""
    return SensesSnapshot(
        position=senses.position,
        visible={position for position, value in senses.visible.items() if value},
        seen=set(senses.seen),
        entities=dict(senses.entities),
        objects=dict(senses.objects),
        effective_light_levels=dict(senses.effective_light_levels),
        paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception,
        sense_modes_hash=senses._last_sense_modes_hash,
        visual_access=senses._last_visual_access,
    )


def _sorted_contacts(values: Dict[UUID, PerceivedContact]) -> Dict[UUID, PerceivedContact]:
    return {contact_uuid: values[contact_uuid] for contact_uuid in sorted(values, key=str)}


def emit_sensory_update_delta(
    senses: Senses,
    owner_uuid: UUID,
    cause_event: Event,
    before: SensesSnapshot,
    after: SensesSnapshot,
    reason: SensoryUpdateReason,
    *,
    register_event: bool = True,
) -> Optional[SensoryUpdateEvent]:
    """Create one cold after-value delta for an observer projection change."""
    visible_added = after.visible - before.visible
    visible_removed = before.visible - after.visible
    seen_added = after.seen - before.seen
    entity_changed = {
        contact_uuid: contact
        for contact_uuid, contact in after.entities.items()
        if before.entities.get(contact_uuid) != contact
    }
    object_changed = {
        contact_uuid: contact
        for contact_uuid, contact in after.objects.items()
        if before.objects.get(contact_uuid) != contact
    }
    entity_removed = set(before.entities) - set(after.entities)
    object_removed = set(before.objects) - set(after.objects)
    light_changed = {
        f"{position[0]},{position[1]}": level.value
        for position, level in sorted(after.effective_light_levels.items())
        if before.effective_light_levels.get(position) != level
    }
    passive_changed = before.passive_perception != after.passive_perception
    modes_changed = before.sense_modes_hash != after.sense_modes_hash
    visual_access_changed = before.visual_access != after.visual_access
    position_changed = before.position != after.position
    paths_dirty = not before.paths_dirty and after.paths_dirty
    if not any((
        visible_added,
        visible_removed,
        seen_added,
        entity_changed,
        entity_removed,
        object_changed,
        object_removed,
        light_changed,
        passive_changed,
        modes_changed,
        visual_access_changed,
        position_changed,
        paths_dirty,
    )):
        return None

    event = SensoryUpdateEvent(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        observer_uuid=owner_uuid,
        observer_position=after.position,
        observer_position_changed=position_changed,
        cause_event_uuid=cause_event.uuid,
        update_reason=reason,
        parent_event=cause_event.uuid,
        parent_lineage=cause_event.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
        visible_cells_added=sorted(visible_added),
        visible_cells_removed=sorted(visible_removed),
        seen_cells_added=sorted(seen_added),
        entity_contacts_changed=_sorted_contacts(entity_changed),
        entity_contacts_removed=entity_removed,
        object_contacts_changed=_sorted_contacts(object_changed),
        object_contacts_removed=object_removed,
        effective_light_levels_changed=light_changed,
        paths_dirty=paths_dirty,
        passive_perception_changed=passive_changed,
        passive_perception=after.passive_perception if passive_changed else None,
        sense_modes_changed=modes_changed,
        sense_modes=(
            [mode.model_copy(deep=True) for mode in senses.get_sense_modes()]
            if modes_changed
            else None
        ),
        visual_access_changed=visual_access_changed,
        visual_access=after.visual_access if visual_access_changed else None,
    )
    if register_event:
        EventQueue.register(event)
    return event


@dataclass(frozen=True)
class ObserverFootprint:
    """Indexed cells and contacts used only for candidate selection."""

    known_path_positions: frozenset[Position]
    entity_uuids: frozenset[UUID]
    object_uuids: frozenset[UUID]


class SpatialSensesSystem:
    """Single perception reducer and observer-evidence authority."""

    SYSTEM_NAME = "spatial_senses"
    DEFAULT_VISUAL_RADIUS_CELLS = 20
    SPATIAL_EVENTS = {
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_TILE_CHANGED,
        EventType.SPATIAL_OBJECT_PLACED,
        EventType.SPATIAL_OBJECT_REMOVED,
        EventType.SPATIAL_OBJECT_CHANGED,
        EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        EventType.SPATIAL_LIGHT_CHANGED,
        EventType.SPATIAL_EFFECT_CHANGED,
    }
    EVENT_TYPES = {
        EventType.DEATH,
        EventType.CONDITION_APPLICATION,
        EventType.CONDITION_REMOVAL,
        EventType.LIFE_STATE_CHANGE,
        EventType.TURN_START,
        *SPATIAL_EVENTS,
    }

    def __init__(self) -> None:
        self.senses_by_observer: Dict[UUID, Senses] = {}
        self.footprints_by_observer: Dict[UUID, ObserverFootprint] = {}
        self.observers_by_known_position: DefaultDict[Position, Set[UUID]] = defaultdict(set)
        self.observers_by_entity: DefaultDict[UUID, Set[UUID]] = defaultdict(set)
        self.observers_by_object: DefaultDict[UUID, Set[UUID]] = defaultdict(set)

    def attach(self) -> None:
        EventQueue.add_pre_completion_system(self.SYSTEM_NAME, self, self.EVENT_TYPES)
        EventQueue.set_perceiver_computer(self.compute_perceivers)
        EventQueue.set_revealed_computer(self.compute_revealed_entities)
        EventQueue.set_identified_entity_observer_computer(
            self.compute_identified_entity_observers,
        )

    def reset(self) -> None:
        self.senses_by_observer.clear()
        self.footprints_by_observer.clear()
        self.observers_by_known_position.clear()
        self.observers_by_entity.clear()
        self.observers_by_object.clear()

    def register_observer(self, observer_uuid: UUID, senses: Senses) -> None:
        """Register an observer without reducing its subjective footprint."""
        self.senses_by_observer[observer_uuid] = senses

    def unregister_observer(self, observer_uuid: UUID) -> None:
        self.senses_by_observer.pop(observer_uuid, None)
        footprint = self.footprints_by_observer.pop(observer_uuid, None)
        if footprint is not None:
            self._remove_footprint(observer_uuid, footprint)
        get_map().unsubscribe_entity(observer_uuid)

    def compute_identified_entity_observers(
        self,
        event: Event,
    ) -> Dict[str, Set[str]]:
        """Capture event-time participant identity from typed contacts."""
        grants: Dict[str, Set[str]] = {}
        for participant_uuid in event.get_participant_entity_uuids():
            if BaseBlock.get(participant_uuid) is None:
                continue
            observers = {
                str(observer_uuid)
                for observer_uuid in self.observers_by_entity.get(
                    participant_uuid,
                    set(),
                )
            }
            observers.add(str(participant_uuid))
            grants[str(participant_uuid)] = observers
        return grants

    def position_observer_evidence(
        self,
        positions: Set[Position],
    ) -> Dict[str, Set[str]]:
        """Freeze exact observer grants for event-time positions."""
        evidence: Dict[str, Set[str]] = {}
        grid = get_map()
        registered = set(self.senses_by_observer)
        for position in positions:
            observers: Set[str] = set()
            for observer_uuid in grid.get_subscribers_at(position) & registered:
                senses = self.senses_by_observer[observer_uuid]
                if (
                    position in senses.visible
                    or any(contact.position == position for contact in senses.entities.values())
                    or any(contact.position == position for contact in senses.objects.values())
                ):
                    observers.add(str(observer_uuid))
            evidence[f"{position[0]},{position[1]}"] = observers
        return evidence

    def compute_perceivers(self, event: Event) -> Set[str]:
        """Derive terminal combat-log perceivers from frozen event evidence."""
        perceivers = {
            observer_uuid
            for observers in event.located_position_observer_uuids.values()
            for observer_uuid in observers
        }
        for participant_uuid in event.get_participant_entity_uuids():
            perceivers.add(str(participant_uuid))
            perceivers.update(
                event.located_entity_observer_uuids.get(str(participant_uuid), set()),
            )
        return perceivers

    def compute_revealed_entities(
        self,
        event: Event,
        _child_logs: List[object],
    ) -> Set[str]:
        """Derive reveals from recorded final perceivability and sensory facts."""
        revealed: Set[str] = set()
        pending = list(event.children_events)
        seen: Set[UUID] = set()
        recorded: List[Event] = []
        while pending:
            child_uuid = pending.pop()
            if child_uuid in seen:
                continue
            seen.add(child_uuid)
            child = EventQueue.get_event_by_uuid(child_uuid)
            if child is None:
                continue
            recorded.append(child)
            pending.extend(child.children_events)
        contact_additions = {
            str(contact_uuid)
            for child in recorded
            if isinstance(child, SensoryUpdateEvent)
            for contact_uuid in child.entity_contacts_changed
        }
        for child in recorded:
            if not isinstance(child, SpatialChangeEvent):
                continue
            if child.event_type is not EventType.SPATIAL_PERCEIVABILITY_CHANGED:
                continue
            changed_uuid = child.perceivability_block_uuid
            if (
                changed_uuid is not None
                and not child.changed_block_is_invisible
                and child.changed_block_stealth_dc is None
                and str(changed_uuid) in contact_additions
            ):
                revealed.add(str(changed_uuid))
        return revealed

    def recompute_observer(
        self,
        observer_uuid: UUID,
        *,
        max_distance: int = DEFAULT_VISUAL_RADIUS_CELLS,
    ) -> None:
        """Replace one observer's exact visual cells and typed contacts."""
        senses = self.senses_by_observer.get(observer_uuid)
        owner = BaseBlock.get(observer_uuid)
        if senses is None or owner is None:
            return
        grid = get_map()
        origin = owner.position
        senses.position = origin
        modes = {mode.sense_type: mode.range_feet for mode in senses.get_sense_modes()}
        visual_access = senses.visual_access.normalized_score > 0
        ordinary_sight = owner.has_ordinary_visual_sight()
        optical_radius = max_distance if ordinary_sight else 0
        for sense_type in (SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT):
            sense_range = modes.get(sense_type)
            if sense_range is not None:
                optical_radius = max(
                    optical_radius,
                    max_distance if sense_range == 0 else (sense_range + 4) // 5,
                )

        optical_candidates = (
            set(grid.compute_fov(origin, optical_radius))
            if visual_access and optical_radius > 0
            else set()
        )
        visible: Dict[Position, bool] = {}
        effective_light: Dict[Position, LightLevel] = {}
        visual_modes_by_position: Dict[Position, Set[SensesType]] = {}
        has_conditional_optics = any(
            grid.get_optical_obscurements_at(position)
            for position in optical_candidates
        )
        for position in optical_candidates:
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            distance = senses.get_feet_distance(position)
            obscurements = (
                grid.get_optical_obscurements_on_route(origin, position)
                if has_conditional_optics
                else set()
            )
            establishing_modes: Set[SensesType] = set()
            ordinary_establishes = (
                ordinary_sight
                and OpticalObscurement.HEAVY not in obscurements
                and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
                and tile.resolved_light_level.value > LightLevel.DARKNESS.value
            )
            if self._sense_in_range(modes, SensesType.DARKVISION, distance):
                if (
                    OpticalObscurement.HEAVY not in obscurements
                    and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
                ):
                    establishing_modes.add(SensesType.DARKVISION)
            if self._sense_in_range(modes, SensesType.DEVILS_SIGHT, distance):
                if OpticalObscurement.HEAVY not in obscurements:
                    establishing_modes.add(SensesType.DEVILS_SIGHT)
            if self._sense_in_range(modes, SensesType.TRUESIGHT, distance):
                if OpticalObscurement.HEAVY not in obscurements:
                    establishing_modes.add(SensesType.TRUESIGHT)
            if not ordinary_establishes and not establishing_modes:
                continue
            visible[position] = True
            visual_modes_by_position[position] = establishing_modes
            resolved = tile.resolved_light_level
            if (
                resolved is LightLevel.DARKNESS
                and establishing_modes
                & {SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT}
            ):
                resolved = LightLevel.BRIGHT_LIGHT
            elif (
                resolved is LightLevel.DARKNESS
                and SensesType.DARKVISION in establishing_modes
            ):
                resolved = LightLevel.DIM_LIGHT
            elif resolved is LightLevel.DIM_LIGHT and SensesType.DARKVISION in establishing_modes:
                resolved = LightLevel.BRIGHT_LIGHT
            effective_light[position] = resolved

        nonvisual_positions: Dict[SensesType, Set[Position]] = {}
        for sense_type in (SensesType.BLINDSIGHT, SensesType.TREMORSENSE):
            sense_range = modes.get(sense_type)
            if sense_range is None:
                continue
            radius = max_distance if sense_range == 0 else (sense_range + 4) // 5
            nonvisual_positions[sense_type] = set(grid.compute_propagation_fov(origin, radius))

        boundary_route_evidence: Dict[
            UUID,
            Set[Tuple[Position, bool, Tuple[SensesType, ...]]],
        ] = defaultdict(set)

        def collect_boundary_route_evidence(
            source_positions: Set[Position],
            channel: WorldEdgeChannel,
            *,
            visual: bool,
            evidence_senses_by_position: Optional[
                Dict[Position, Set[SensesType]]
            ] = None,
            evidence_senses: Tuple[SensesType, ...] = (),
        ) -> None:
            for source_position in sorted(source_positions):
                route_senses = (
                    tuple(sorted(
                        evidence_senses_by_position.get(source_position, set()),
                        key=lambda value: value.value,
                    ))
                    if evidence_senses_by_position is not None
                    else evidence_senses
                )
                for direction in CardinalDirection:
                    exit_layer, entry_layer = grid.get_boundary_route_layers(
                        source_position,
                        direction,
                        channel,
                    )
                    for object_uuid in (*exit_layer, *entry_layer):
                        boundary_route_evidence[object_uuid].add(
                            (source_position, visual, route_senses),
                        )

        collect_boundary_route_evidence(
            set(visible),
            WorldEdgeChannel.OPTICAL,
            visual=True,
            evidence_senses_by_position=visual_modes_by_position,
        )
        for sense_type, positions in nonvisual_positions.items():
            collect_boundary_route_evidence(
                positions,
                WorldEdgeChannel.PROPAGATION,
                visual=False,
                evidence_senses=(sense_type,),
            )

        entity_contacts: Dict[UUID, PerceivedContact] = {}
        object_contacts: Dict[UUID, PerceivedContact] = {}
        candidate_positions = set(visible)
        for positions in nonvisual_positions.values():
            candidate_positions.update(positions)
        for position in candidate_positions:
            for entity_uuid in sorted(grid.get_entities_at(position), key=str):
                if entity_uuid == observer_uuid:
                    continue
                block = BaseBlock.get(entity_uuid)
                if block is None or not block.appears_in_entity_contacts():
                    continue
                contact = self._resolve_contact(
                    owner, senses, block, position, position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions, modes,
                )
                if contact is not None:
                    entity_contacts[entity_uuid] = contact
            for object_uuid in sorted(grid.get_center_objects_at(position), key=str):
                block = BaseBlock.get(object_uuid)
                if block is None or not block.should_include_in_senses_objects():
                    continue
                contact = self._resolve_contact(
                    owner, senses, block, position, position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions, modes,
                )
                if contact is not None:
                    object_contacts[object_uuid] = contact

        for object_uuid in sorted(boundary_route_evidence, key=str):
            block = BaseBlock.get(object_uuid)
            placement = grid.get_object_placement(object_uuid)
            if (
                block is None
                or placement is None
                or placement.boundary_direction is None
                or not block.should_include_in_senses_objects()
            ):
                continue
            evidence = tuple(sorted(
                boundary_route_evidence[object_uuid],
                key=lambda row: (
                    row[0],
                    not row[1],
                    tuple(sense.value for sense in row[2]),
                ),
            ))
            contact = self._resolve_contact(
                owner,
                senses,
                block,
                placement.position,
                False,
                set(),
                nonvisual_positions,
                modes,
                route_evidence=evidence,
                contact_position=placement.position,
            )
            if contact is not None:
                object_contacts[object_uuid] = contact

        senses.replace_perception(
            position=origin,
            visible=visible,
            seen=set(senses.seen) | set(visible),
            entities=entity_contacts,
            objects=object_contacts,
            effective_light_levels=effective_light,
            passive_perception=owner.get_passive_perception(),
            sense_modes_hash=senses.compute_sense_modes_hash(),
            visual_access=senses.visual_access.normalized_score,
        )
        subscribed = set(optical_candidates)
        for positions in nonvisual_positions.values():
            subscribed.update(positions)
        grid.subscribe_to_cells(observer_uuid, subscribed)
        self.refresh_observer(observer_uuid)

    @staticmethod
    def _sense_in_range(
        modes: Dict[SensesType, int],
        sense_type: SensesType,
        distance_feet: int,
    ) -> bool:
        sense_range = modes.get(sense_type)
        return sense_range is not None and (sense_range == 0 or distance_feet <= sense_range)

    def _resolve_contact(
        self,
        owner: BaseBlock,
        senses: Senses,
        subject: BaseBlock,
        position: Position,
        cell_visual: bool,
        visual_modes: Set[SensesType],
        nonvisual_positions: Dict[SensesType, Set[Position]],
        modes: Dict[SensesType, int],
        route_evidence: Optional[
            Tuple[Tuple[Position, bool, Tuple[SensesType, ...]], ...]
        ] = None,
        contact_position: Optional[Position] = None,
    ) -> Optional[PerceivedContact]:
        if subject.stealth_dc is not None and subject.stealth_dc >= owner.get_passive_perception():
            return None
        evidence = route_evidence or ((
            position,
            cell_visual,
            tuple(sorted(visual_modes, key=lambda value: value.value)),
        ),)
        visual = False
        special: Set[SensesType] = set()
        nonvisual_types = {
            SensesType.BLINDSIGHT,
            SensesType.TREMORSENSE,
        }
        for evidence_position, evidence_visual, evidence_modes in evidence:
            distance = senses.get_feet_distance(evidence_position)
            invisibility_bypassed = not subject.is_invisible or any((
                self._sense_in_range(modes, SensesType.TRUESIGHT, distance),
                self._sense_in_range(modes, SensesType.SEE_INVISIBLE, distance),
            ))
            route_visual = evidence_visual and invisibility_bypassed
            route_special = {
                sense_type
                for sense_type, positions in nonvisual_positions.items()
                if evidence_position in positions
            }
            route_special.update(
                sense_type
                for sense_type in evidence_modes
                if sense_type in nonvisual_types
            )
            if route_visual:
                visual = True
                special.update(evidence_modes)
            special.update(route_special)
        if not visual and not special:
            return None
        return PerceivedContact(
            position=contact_position or position,
            visual=visual,
            special_senses=tuple(sorted(special, key=lambda value: value.value)),
        )

    def refresh_observer(self, observer_uuid: UUID) -> None:
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None:
            return
        new = ObserverFootprint(
            known_path_positions=frozenset(
                set(senses.visible) | senses.seen | set(senses.paths) | set(senses.safe_paths),
            ),
            entity_uuids=frozenset(senses.entities),
            object_uuids=frozenset(senses.objects),
        )
        old = self.footprints_by_observer.get(observer_uuid)
        if old == new:
            return
        if old is not None:
            self._remove_footprint(observer_uuid, old, retained=new)
        self._add_footprint(observer_uuid, new, previous=old)
        self.footprints_by_observer[observer_uuid] = new

    def candidate_observer_uuids(self, event: Event) -> Set[UUID]:
        if event.event_type is EventType.TURN_START:
            return (
                {event.source_entity_uuid}
                if event.source_entity_uuid in self.senses_by_observer
                else set()
            )
        registered = set(self.senses_by_observer)
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
            EventType.LIFE_STATE_CHANGE,
        }:
            target = event.target_entity_uuid
            return {target} if target in registered else set()
        if isinstance(event, DeathEvent):
            return set(self.observers_by_entity.get(event.entity_uuid, set()))
        if isinstance(event, SpatialEffectChangeEvent):
            candidates: Set[UUID] = set()
            for position in event.get_affected_positions():
                candidates.update(get_map().get_subscribers_at(position))
            return candidates & registered
        if not isinstance(event, SpatialChangeEvent):
            return set()
        if (
            event.event_type in {
                EventType.SPATIAL_ENTITY_LEFT,
                EventType.SPATIAL_OBJECT_REMOVED,
            }
            and event.old_position is not None
        ):
            return set()
        positions = {event.position}
        if event.old_position is not None:
            positions.add(event.old_position)
        hint = event.senses_hint
        if hint is not None:
            if hint.light_changed_positions:
                positions.update(hint.light_changed_positions)
            if hint.directional_positions:
                positions.update(hint.directional_positions)
            if hint.directional_neighbors:
                positions.update(hint.directional_neighbors)
            for row in (
                hint.entity_entered, hint.entity_left, hint.entity_died,
                hint.object_placed, hint.object_removed,
            ):
                if row is not None:
                    positions.add(row[1])
        candidates: Set[UUID] = set()
        grid = get_map()
        for position in positions:
            candidates.update(grid.get_subscribers_at(position))
        if event.entity_uuid in registered and event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
            candidates.add(event.entity_uuid)
        if hint is not None:
            if hint.entity_left is not None:
                candidates.update(self.observers_by_entity.get(hint.entity_left[0], set()))
            if hint.entity_died is not None:
                candidates.update(self.observers_by_entity.get(hint.entity_died[0], set()))
            if hint.object_removed is not None:
                candidates.update(self.observers_by_object.get(hint.object_removed[0], set()))
            if hint.perceivability_block is not None:
                changed_uuid = hint.perceivability_block
                candidates.update(self.observers_by_entity.get(changed_uuid, set()))
                candidates.update(self.observers_by_object.get(changed_uuid, set()))
                placement = grid.get_object_placement(changed_uuid)
                if placement is not None and placement.boundary_direction is not None:
                    owner_position = placement.position
                    candidates.update(grid.get_subscribers_at(owner_position))
                    offsets = {
                        CardinalDirection.NORTH: (0, 1),
                        CardinalDirection.SOUTH: (0, -1),
                        CardinalDirection.EAST: (1, 0),
                        CardinalDirection.WEST: (-1, 0),
                    }
                    offset_x, offset_y = offsets[placement.boundary_direction]
                    neighbor_position = (
                        owner_position[0] + offset_x,
                        owner_position[1] + offset_y,
                    )
                    if grid.get_tile(*neighbor_position) is not None:
                        candidates.update(grid.get_subscribers_at(neighbor_position))
            if hint.requires_paths:
                for position in positions:
                    candidates.update(self.observers_by_known_position.get(position, set()))
        return candidates & registered

    def __call__(self, event: Event) -> None:
        sensory_events: List[SensoryUpdateEvent] = []
        for observer_uuid in sorted(self.candidate_observer_uuids(event), key=str):
            senses = self.senses_by_observer.get(observer_uuid)
            if senses is None:
                continue
            before = capture_senses_snapshot(senses)
            self.recompute_observer(observer_uuid)
            if event.event_type is EventType.TURN_START:
                after = capture_senses_snapshot(senses)
                navigation_projection_changed = (
                    before.position != after.position
                    or before.visible != after.visible
                    or before.seen != after.seen
                    or before.entities != after.entities
                    or before.objects != after.objects
                )
                if navigation_projection_changed:
                    senses._paths_dirty = True
                    after = capture_senses_snapshot(senses)
            else:
                senses._paths_dirty = True
                after = capture_senses_snapshot(senses)
            sensory_event = emit_sensory_update_delta(
                senses,
                observer_uuid,
                event,
                before,
                after,
                self._reason_for(event, observer_uuid),
                register_event=False,
            )
            if sensory_event is not None:
                sensory_events.append(sensory_event)
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)

    @staticmethod
    def _reason_for(event: Event, observer_uuid: UUID) -> SensoryUpdateReason:
        if event.event_type is EventType.TURN_START:
            return SensoryUpdateReason.TURN_START
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED:
            return SensoryUpdateReason.LIGHT
        if event.event_type is EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return SensoryUpdateReason.PERCEIVABILITY
        if event.event_type is EventType.DEATH:
            return SensoryUpdateReason.DEATH
        if event.event_type is EventType.LIFE_STATE_CHANGE:
            return SensoryUpdateReason.LIFE_STATE
        if event.event_type in {EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL}:
            return SensoryUpdateReason.CONDITION
        if isinstance(event, SpatialChangeEvent) and event.entity_uuid == observer_uuid:
            return SensoryUpdateReason.SELF_MOVEMENT
        return SensoryUpdateReason.SPATIAL

    def _remove_footprint(
        self,
        observer_uuid: UUID,
        footprint: ObserverFootprint,
        *,
        retained: Optional[ObserverFootprint] = None,
    ) -> None:
        retained_positions = retained.known_path_positions if retained else frozenset()
        retained_entities = retained.entity_uuids if retained else frozenset()
        retained_objects = retained.object_uuids if retained else frozenset()
        for position in footprint.known_path_positions - retained_positions:
            self._discard_reverse(self.observers_by_known_position, position, observer_uuid)
        for entity_uuid in footprint.entity_uuids - retained_entities:
            self._discard_reverse(self.observers_by_entity, entity_uuid, observer_uuid)
        for object_uuid in footprint.object_uuids - retained_objects:
            self._discard_reverse(self.observers_by_object, object_uuid, observer_uuid)

    def _add_footprint(
        self,
        observer_uuid: UUID,
        footprint: ObserverFootprint,
        *,
        previous: Optional[ObserverFootprint],
    ) -> None:
        previous_positions = previous.known_path_positions if previous else frozenset()
        previous_entities = previous.entity_uuids if previous else frozenset()
        previous_objects = previous.object_uuids if previous else frozenset()
        for position in footprint.known_path_positions - previous_positions:
            self.observers_by_known_position[position].add(observer_uuid)
        for entity_uuid in footprint.entity_uuids - previous_entities:
            self.observers_by_entity[entity_uuid].add(observer_uuid)
        for object_uuid in footprint.object_uuids - previous_objects:
            self.observers_by_object[object_uuid].add(observer_uuid)

    @staticmethod
    def _discard_reverse(
        index: DefaultDict[K, Set[UUID]],
        key: K,
        observer_uuid: UUID,
    ) -> None:
        observers = index.get(key)
        if observers is None:
            return
        observers.discard(observer_uuid)
        if not observers:
            index.pop(key, None)


spatial_senses_system = SpatialSensesSystem()
