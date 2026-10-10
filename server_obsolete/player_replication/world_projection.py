"""Build and diff renderer-complete worlds under one subjective perspective."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import UUID

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import GridMap
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationKind
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.world_contracts import (
    APIEntityVisibility,
    APIGrid,
    APITile,
    APIVisibilityResponse,
)
from server.world_projection import (
    project_entity_summary,
    project_equipment_overview,
    project_observed_tile,
    project_safe_item_presentation_ref,
)
from server.player_replication.journal import SubjectiveWorldProjectionContext
from server.player_replication_contract import (
    ActiveWeaponSet,
    ControlledEquipmentReplacePatch,
    DoorStatePatch,
    EncounterReplacePatch,
    EntityRemovePatch,
    EntityUpsertPatch,
    EntityVisualLoadout,
    FloorObjectBlockingChannel,
    FloorObjectDirection,
    FloorObjectProjectionKind,
    FloorObjectRemovePatch,
    FloorObjectUpsertPatch,
    ObserverVisibilityRemovePatch,
    ObserverVisibilityReplacePatch,
    SubjectiveCombatant,
    SubjectiveEncounter,
    SubjectiveFloorObject,
    SubjectiveGameState,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
    SubjectiveWorldPatch,
    TileUpsertPatch,
    VisualEquipmentLayer,
    VisualLoadoutReplacePatch,
    VisualLoadoutSlot,
)


class SubjectiveWorldProjectionError(ValueError):
    """Raised when the authorized observer perspective cannot be materialized."""


@dataclass(frozen=True)
class RememberedTileFact:
    """Immutable serialized tile facts captured while at least one observer saw it."""

    position: tuple[int, int]
    payload: str

    @classmethod
    def capture(cls, tile: APITile) -> "RememberedTileFact":
        return cls(position=(tile.x, tile.y), payload=tile.model_dump_json())

    def materialize(self, *, visible: bool) -> APITile:
        tile = APITile.model_validate_json(self.payload)
        return tile.model_copy(update={"visible": visible})


@dataclass(frozen=True)
class RememberedObjectFact:
    """Immutable serialized object facts retained until its cell is observed again."""

    object_uuid: str
    position: tuple[int, int]
    payload: str

    @classmethod
    def capture(cls, obj: SubjectiveFloorObject) -> "RememberedObjectFact":
        return cls(
            object_uuid=obj.uuid,
            position=obj.position,
            payload=obj.model_dump_json(),
        )

    def materialize(self) -> SubjectiveFloorObject:
        return SubjectiveFloorObject.model_validate_json(self.payload)


class SubjectiveSpatialMemory:
    """Perspective-epoch-owned last-observed spatial facts."""

    def __init__(self, *, perspective_epoch_id: str) -> None:
        if not perspective_epoch_id:
            raise ValueError("subjective spatial memory requires a perspective epoch")
        self.perspective_epoch_id = perspective_epoch_id
        self._tiles: dict[tuple[int, int], RememberedTileFact] = {}
        self._objects: dict[str, RememberedObjectFact] = {}

    def _working_copy(
        self,
    ) -> tuple[
        dict[tuple[int, int], RememberedTileFact],
        dict[str, RememberedObjectFact],
    ]:
        return dict(self._tiles), dict(self._objects)

    def _commit(
        self,
        *,
        tiles: dict[tuple[int, int], RememberedTileFact],
        objects: dict[str, RememberedObjectFact],
    ) -> None:
        self._tiles = tiles
        self._objects = objects


class CanonicalSubjectiveWorldProjector:
    """Stateful journal projector owning secure memory for one perspective epoch."""

    def __init__(
        self,
        *,
        perspective: SubjectivePerspective,
        grid_provider: Callable[[], GridMap],
        entities_provider: Callable[[], Iterable[Entity]],
        encounter_provider: Callable[[], Encounter | None],
    ) -> None:
        self.perspective = perspective
        self._grid_provider = grid_provider
        self._entities_provider = entities_provider
        self._encounter_provider = encounter_provider
        self.memory = SubjectiveSpatialMemory(
            perspective_epoch_id=perspective.perspective_epoch_id,
        )

    def project_world(
        self,
        context: SubjectiveWorldProjectionContext,
    ) -> SubjectiveReplicatedWorld:
        if context.perspective != self.perspective:
            raise SubjectiveWorldProjectionError(
                "world projector cannot cross a perspective epoch"
            )
        return build_subjective_world(
            perspective=self.perspective,
            grid=self._grid_provider(),
            entities=self._entities_provider(),
            encounter=self._encounter_provider(),
            memory=self.memory,
        )


def build_subjective_world(
    *,
    perspective: SubjectivePerspective,
    grid: GridMap,
    entities: Iterable[Entity],
    encounter: Encounter | None,
    memory: SubjectiveSpatialMemory,
) -> SubjectiveReplicatedWorld:
    """Project current registries without exposing unobserved entities or objects."""
    entity_rows = tuple(entities)
    entities_by_uuid = {str(entity.uuid): entity for entity in entity_rows}
    missing_observers = sorted(
        set(perspective.observer_entity_uuids) - set(entities_by_uuid)
    )
    if missing_observers:
        raise SubjectiveWorldProjectionError(
            f"authorized observers are absent from the engine registry: {missing_observers}"
        )

    observers = tuple(
        entities_by_uuid[observer_uuid]
        for observer_uuid in perspective.observer_entity_uuids
    )
    if memory.perspective_epoch_id != perspective.perspective_epoch_id:
        raise SubjectiveWorldProjectionError(
            "subjective spatial memory cannot cross a perspective epoch"
        )
    remembered_tiles, remembered_objects, visible_cells = _capture_spatial_memory(
        memory=memory,
        grid=grid,
        observers=observers,
    )
    identified_entity_uuids = (
        set(perspective.controlled_entity_uuids)
        | set(perspective.observer_entity_uuids)
        | {
            str(entity_uuid)
            for observer in observers
            for entity_uuid in observer.senses.entities
        }
    )
    projected_entities = tuple(
        project_entity_summary(entity)
        for entity in entity_rows
        if str(entity.uuid) in identified_entity_uuids
    )
    projected_grid = _project_grid(
        grid=grid,
        remembered_tiles=remembered_tiles,
        visible_cells=visible_cells,
    )
    projected_objects = tuple(
        remembered_objects[object_uuid].materialize()
        for object_uuid in sorted(remembered_objects)
    )
    projected_visibility = APIVisibilityResponse(
        root={
            str(observer.uuid): _project_observer_visibility(observer)
            for observer in observers
        }
    )
    equipment_by_entity = {
        entity_uuid: project_equipment_overview(entities_by_uuid[entity_uuid])
        for entity_uuid in perspective.controlled_entity_uuids
    }
    visual_loadout_by_entity = {
        entity.uuid: build_entity_visual_loadout(entities_by_uuid[entity.uuid])
        for entity in projected_entities
    }

    world = SubjectiveReplicatedWorld(
        state=SubjectiveGameState(
            grid=projected_grid,
            entities=projected_entities,
            encounter=_project_encounter(encounter, identified_entity_uuids),
            floor_objects=projected_objects,
        ),
        visibility=projected_visibility,
        equipment_by_entity=equipment_by_entity,
        visual_loadout_by_entity=visual_loadout_by_entity,
    )
    memory._commit(tiles=remembered_tiles, objects=remembered_objects)
    return world


def build_entity_visual_loadout(entity: Entity) -> EntityVisualLoadout:
    """Build safe actor layers from the canonical equipment overview."""
    overview = project_equipment_overview(entity)
    layers: list[VisualEquipmentLayer] = []
    for slot in overview.slots:
        item = slot.item
        if item is None:
            continue
        try:
            item_kind = ItemPresentationKind(item.item_type)
        except ValueError:
            item_kind = ItemPresentationKind.ITEM
        layers.append(
            VisualEquipmentLayer(
                slot=VisualLoadoutSlot(slot.slot),
                item_kind=item_kind,
                safe_presentation_ref=item.safe_presentation_ref,
                visual_item_name=item.visual_item_name,
                visual_variant_id=item.visual_variant_id,
                equipped_visual_policy=EquippedVisualPolicy(item.equipped_visual_policy),
            )
        )

    active_weapon_set = ActiveWeaponSet(entity.equipment.active_weapon_set.value)
    return EntityVisualLoadout(
        entity_uuid=str(entity.uuid),
        active_weapon_set=active_weapon_set,
        layers=tuple(layers),
    )


def diff_subjective_worlds(
    previous: SubjectiveReplicatedWorld,
    current: SubjectiveReplicatedWorld,
) -> tuple[SubjectiveWorldPatch, ...]:
    """Return deterministic typed replacements needed to reduce one world to another."""
    patches: list[SubjectiveWorldPatch] = []
    previous_entities = {entity.uuid: entity for entity in previous.state.entities}
    current_entities = {entity.uuid: entity for entity in current.state.entities}
    for entity_uuid in sorted(set(previous_entities) - set(current_entities)):
        patches.append(EntityRemovePatch(entity_uuid=entity_uuid))
    for entity_uuid in sorted(current_entities):
        if previous_entities.get(entity_uuid) != current_entities[entity_uuid]:
            patches.append(EntityUpsertPatch(entity=current_entities[entity_uuid]))

    previous_tiles = {(tile.x, tile.y): tile for tile in previous.state.grid.tiles}
    current_tiles = {(tile.x, tile.y): tile for tile in current.state.grid.tiles}
    for position in sorted(current_tiles):
        if previous_tiles.get(position) != current_tiles[position]:
            patches.append(TileUpsertPatch(tile=current_tiles[position]))

    previous_objects = {obj.uuid: obj for obj in previous.state.floor_objects}
    current_objects = {obj.uuid: obj for obj in current.state.floor_objects}
    for object_uuid in sorted(set(previous_objects) - set(current_objects)):
        patches.append(FloorObjectRemovePatch(object_uuid=object_uuid))
    for object_uuid in sorted(current_objects):
        previous_object = previous_objects.get(object_uuid)
        current_object = current_objects[object_uuid]
        if previous_object == current_object:
            continue
        door_patch = _door_state_change(previous_object, current_object)
        if door_patch is None or _floor_object_non_door_state_changed(
            previous_object,
            current_object,
        ):
            patches.append(FloorObjectUpsertPatch(object=current_object))
        if door_patch is not None:
            patches.append(door_patch)

    if previous.state.encounter != current.state.encounter:
        patches.append(EncounterReplacePatch(encounter=current.state.encounter))

    previous_visibility = previous.visibility.root
    current_visibility = current.visibility.root
    for observer_uuid in sorted(set(previous_visibility) - set(current_visibility)):
        patches.append(ObserverVisibilityRemovePatch(observer_uuid=observer_uuid))
    for observer_uuid in sorted(current_visibility):
        if previous_visibility.get(observer_uuid) != current_visibility[observer_uuid]:
            patches.append(
                ObserverVisibilityReplacePatch(
                    observer_uuid=observer_uuid,
                    visibility=current_visibility[observer_uuid],
                )
            )

    for entity_uuid in sorted(current.equipment_by_entity):
        equipment = current.equipment_by_entity[entity_uuid]
        if previous.equipment_by_entity.get(entity_uuid) != equipment:
            patches.append(
                ControlledEquipmentReplacePatch(
                    entity_uuid=entity_uuid,
                    equipment=equipment,
                )
            )
    for entity_uuid in sorted(current.visual_loadout_by_entity):
        loadout = current.visual_loadout_by_entity[entity_uuid]
        if previous.visual_loadout_by_entity.get(entity_uuid) != loadout:
            patches.append(VisualLoadoutReplacePatch(loadout=loadout))
    return tuple(patches)


_DOOR_STATE_FIELDS = {"is_open", "blocks_movement", "blocks_vision"}


def _door_state_change(
    previous: SubjectiveFloorObject | None,
    current: SubjectiveFloorObject,
) -> DoorStatePatch | None:
    """Return the sole typed open/close reducer fact for an existing door."""
    if (
        previous is None
        or previous.object_kind is not FloorObjectProjectionKind.DOOR
        or current.object_kind is not FloorObjectProjectionKind.DOOR
    ):
        return None
    before = (previous.is_open, previous.blocks_movement, previous.blocks_vision)
    after = (current.is_open, current.blocks_movement, current.blocks_vision)
    if before == after:
        return None
    if current.is_open is None:
        raise SubjectiveWorldProjectionError("door projection lost its open state")
    return DoorStatePatch(
        object_uuid=current.uuid,
        position=current.position,
        is_open=current.is_open,
        blocks_movement=current.blocks_movement,
        blocks_vision=current.blocks_vision,
    )


def _floor_object_non_door_state_changed(
    previous: SubjectiveFloorObject | None,
    current: SubjectiveFloorObject,
) -> bool:
    """Whether a door change also needs a full deterministic object upsert."""
    if previous is None:
        return True
    return previous.model_dump(exclude=_DOOR_STATE_FIELDS) != current.model_dump(
        exclude=_DOOR_STATE_FIELDS
    )


def _capture_spatial_memory(
    *,
    memory: SubjectiveSpatialMemory,
    grid: GridMap,
    observers: tuple[Entity, ...],
) -> tuple[
    dict[tuple[int, int], RememberedTileFact],
    dict[str, RememberedObjectFact],
    set[tuple[int, int]],
]:
    """Prepare last-observed facts without committing them to memory yet."""
    remembered_tiles, remembered_objects = memory._working_copy()
    viewers_by_position: dict[tuple[int, int], list[UUID]] = {}
    object_viewer_by_uuid: dict[UUID, UUID] = {}
    object_position_by_uuid: dict[UUID, tuple[int, int]] = {}
    for observer in observers:
        for position, is_visible in observer.senses.visible.items():
            if is_visible:
                viewers_by_position.setdefault(position, []).append(observer.uuid)
        for object_uuid, position in observer.senses.objects.items():
            previous = object_position_by_uuid.setdefault(object_uuid, position)
            if previous != position:
                raise SubjectiveWorldProjectionError(
                    "authorized observers disagree about a visible object's position"
                )
            object_viewer_by_uuid.setdefault(object_uuid, observer.uuid)

    for position, viewer_uuids in viewers_by_position.items():
        projected = project_observed_tile(
            grid,
            position,
            tuple(viewer_uuids),
        )
        remembered_tiles[position] = RememberedTileFact.capture(projected)

    visible_cells = set(viewers_by_position)
    for object_uuid, fact in tuple(remembered_objects.items()):
        if fact.position in visible_cells:
            del remembered_objects[object_uuid]

    candidates: dict[UUID, tuple[tuple[int, int], UUID]] = {
        object_uuid: (position, object_viewer_by_uuid[object_uuid])
        for object_uuid, position in object_position_by_uuid.items()
    }
    for position, viewer_uuids in viewers_by_position.items():
        for object_uuid in grid.get_objects_at(position):
            block = BaseBlock.get(object_uuid)
            if not isinstance(block, BaseItem):
                continue
            viewer_uuid = next(
                (
                    observer_uuid
                    for observer_uuid in viewer_uuids
                    if block.is_perceivable_by(observer_uuid)
                ),
                None,
            )
            if viewer_uuid is None:
                continue
            directions = _direction_values(getattr(block, "blocked_directions", ()))
            channels = _channel_values(getattr(block, "blocked_channels", ()))
            if block.get_spatial_open_state() is None and not (directions and channels):
                continue
            candidates[object_uuid] = (position, viewer_uuid)

    for object_uuid, (position, viewer_uuid) in candidates.items():
        projected = _project_floor_object(
            object_uuid,
            position,
            requesting_entity_uuid=viewer_uuid,
        )
        if projected is not None:
            remembered_objects[projected.uuid] = RememberedObjectFact.capture(projected)
    return remembered_tiles, remembered_objects, visible_cells


def _project_grid(
    *,
    grid: GridMap,
    remembered_tiles: dict[tuple[int, int], RememberedTileFact],
    visible_cells: set[tuple[int, int]],
) -> APIGrid:
    tiles = [
        remembered_tiles[position].materialize(visible=position in visible_cells)
        for position in sorted(remembered_tiles)
    ]
    min_x, min_y, max_x, max_y = grid.bounds
    return APIGrid(
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        tiles=tiles,
    )


def _project_observer_visibility(observer: Entity) -> APIEntityVisibility:
    visible_cells = [
        position
        for position, is_visible in observer.senses.visible.items()
        if is_visible
    ]
    effective_light = observer.senses.get_effective_light_levels(observer.uuid)
    return APIEntityVisibility(
        name=observer.name,
        position=observer.position,
        visible_cells=visible_cells,
        visible_entities=[str(entity_uuid) for entity_uuid in observer.senses.entities],
        visible_objects=[str(object_uuid) for object_uuid in observer.senses.objects],
        seen_cells=list(observer.senses.seen),
        sense_modes=list(observer.senses.get_sense_modes()),
        effective_light_levels={
            f"{position[0]},{position[1]}": effective_light[f"{position[0]},{position[1]}"]
            for position in visible_cells
        },
    )


def _project_encounter(
    encounter: Encounter | None,
    identified_entity_uuids: set[str],
) -> SubjectiveEncounter | None:
    if encounter is None:
        return None
    combatants: list[SubjectiveCombatant] = []
    for entity_uuid in encounter.initiative_order:
        entity_uuid_text = str(entity_uuid)
        if entity_uuid_text not in identified_entity_uuids:
            continue
        entity = Entity.get(entity_uuid)
        if entity is None:
            continue
        life_state = entity.health.life_state
        combatants.append(
            SubjectiveCombatant(
                uuid=entity_uuid_text,
                name=entity.name,
                initiative=encounter.combatants[entity_uuid].initiative_total,
                life_state=life_state,
                is_dead=life_state is LifeState.DEAD,
            )
        )
    current_entity_uuid: str | None = None
    current_turn_index: int | None = None
    if encounter.initiative_order and encounter.current_turn_index < len(encounter.initiative_order):
        candidate = str(encounter.initiative_order[encounter.current_turn_index])
        projected_order = [combatant.uuid for combatant in combatants]
        if candidate in projected_order:
            current_entity_uuid = candidate
            current_turn_index = projected_order.index(candidate)
    return SubjectiveEncounter(
        uuid=str(encounter.uuid),
        name=encounter.name,
        state=encounter.state.value,
        round_number=encounter.round_number,
        current_turn_index=current_turn_index,
        current_entity_uuid=current_entity_uuid,
        initiative_order=tuple(combatants),
    )


def _project_floor_object(
    object_uuid: UUID,
    position: tuple[int, int],
    *,
    requesting_entity_uuid: UUID,
) -> SubjectiveFloorObject | None:
    obj = BaseBlock.get(object_uuid)
    if not isinstance(obj, BaseItem):
        return None
    item_presentation = obj.to_item_presentation_state()
    is_open = obj.get_spatial_open_state()
    directions = _direction_values(getattr(obj, "blocked_directions", ()))
    channels = _channel_values(getattr(obj, "blocked_channels", ()))
    has_light_state = all(
        hasattr(obj, field_name)
        for field_name in (
            "is_lit",
            "very_bright_radius_feet",
            "bright_radius_feet",
            "dim_radius_feet",
        )
    )
    if is_open is not None:
        object_kind = FloorObjectProjectionKind.DOOR
    elif has_light_state:
        object_kind = FloorObjectProjectionKind.LIGHT_SOURCE
    elif directions and channels:
        object_kind = FloorObjectProjectionKind.DIRECTIONAL_STRUCTURE
    elif obj.get_storage_block() is not None:
        object_kind = FloorObjectProjectionKind.CONTAINER
    elif "hazard" in obj.tags:
        object_kind = FloorObjectProjectionKind.HAZARD
    elif obj.is_usable and not obj.is_pickable:
        object_kind = FloorObjectProjectionKind.INTERACTABLE
    elif obj.is_pickable:
        object_kind = FloorObjectProjectionKind.ITEM
    else:
        object_kind = FloorObjectProjectionKind.GENERIC

    return SubjectiveFloorObject(
        uuid=str(object_uuid),
        name=obj.name or "Object",
        position=position,
        map_char=obj.map_char,
        object_kind=object_kind,
        safe_presentation_ref=project_safe_item_presentation_ref(obj),
        visual_item_name=item_presentation.visual_item_name,
        visual_variant_id=item_presentation.visual_variant_id,
        blocks_movement=obj.blocks_movement,
        blocks_vision=obj.blocks_vision(requesting_entity_uuid),
        is_open=is_open,
        blocked_directions=directions if object_kind in {
            FloorObjectProjectionKind.DOOR,
            FloorObjectProjectionKind.DIRECTIONAL_STRUCTURE,
        } else (),
        blocked_channels=channels if object_kind in {
            FloorObjectProjectionKind.DOOR,
            FloorObjectProjectionKind.DIRECTIONAL_STRUCTURE,
        } else (),
        is_lit=(bool(getattr(obj, "is_lit")) if has_light_state else None),
        very_bright_radius_feet=(
            int(getattr(obj, "very_bright_radius_feet")) if has_light_state else None
        ),
        bright_radius_feet=(
            int(getattr(obj, "bright_radius_feet")) if has_light_state else None
        ),
        dim_radius_feet=(
            int(getattr(obj, "dim_radius_feet")) if has_light_state else None
        ),
    )


def _direction_values(values: object) -> tuple[FloorObjectDirection, ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    return tuple(FloorObjectDirection(value) for value in values)


def _channel_values(values: object) -> tuple[FloorObjectBlockingChannel, ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    return tuple(FloorObjectBlockingChannel(value) for value in values)


__all__ = [
    "CanonicalSubjectiveWorldProjector",
    "RememberedObjectFact",
    "RememberedTileFact",
    "SubjectiveSpatialMemory",
    "SubjectiveWorldProjectionError",
    "build_entity_visual_loadout",
    "build_subjective_world",
    "diff_subjective_worlds",
]
