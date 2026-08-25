"""Canonical serialization of the engine's objective runtime state.

The builders in this module deliberately know nothing about HTTP routes,
sessions, or player perspective.  Callers provide the runtime objects to the
pure builders, while the ``build_current_*`` helpers read the engine-owned
singleton registries for endpoints and diagnostic tools.
"""

from collections.abc import Iterable
from typing import Any

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import GridMap, get_map
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from server.world_contracts import (
    APIEquipmentOverview,
    APIEntityVisibility,
    APIFloorObject,
    APIGameState,
    APIVisibilityResponse,
)
from server.replicated_world import ReplicatedWorld
from server.world_projection import (
    project_encounter,
    project_entity_summary,
    project_equipment_overview,
    project_grid,
)


_BASE_BLOCK_INTERNAL_FIELDS = frozenset(BaseBlock.model_fields) | {
    "use_register",
    "blocks_dict_name_uuid",
    "blocks_dict_uuid_name",
    "values_dict_name_uuid",
    "values_dict_uuid_name",
}
_FLOOR_OBJECT_TOP_LEVEL_FIELDS = frozenset({"uuid", "name", "map_char"})


def get_floor_object_state(obj: BaseBlock) -> dict[str, Any]:
    """Return concrete object fields not duplicated by ``APIFloorObject``.

    Args:
        obj: Registered floor object to serialize.

    Returns:
        JSON-compatible concrete-model fields, excluding BaseBlock internals
        and fields already represented at the floor-object envelope level.
    """
    all_fields = set(type(obj).model_fields)
    state_fields = (
        all_fields
        - _BASE_BLOCK_INTERNAL_FIELDS
        - _FLOOR_OBJECT_TOP_LEVEL_FIELDS
    )
    return obj.model_dump(mode="json", include=state_fields)


def build_objective_game_state(
    *,
    grid: GridMap,
    entities: Iterable[Entity],
    encounter: Encounter | None,
) -> APIGameState:
    """Serialize one complete objective game-state snapshot.

    Args:
        grid: Grid whose tiles and floor-object index should be serialized.
        entities: Entities to include in registry iteration order.
        encounter: Active encounter, or ``None`` outside combat.

    Returns:
        The canonical objective state DTO used by diagnostics and replay
        capture.
    """
    entity_rows = tuple(entities)
    floor_objects: list[APIFloorObject] = []
    for placement in grid.get_all_object_placements():
        obj_uuid = placement.object_uuid
        obj_pos = placement.position
        obj = BaseBlock.get(obj_uuid)
        if obj is None:
            continue
        floor_objects.append(APIFloorObject(
            uuid=str(obj_uuid),
            name=obj.name or "Object",
            position=obj_pos,
            map_char=getattr(obj, "map_char", "\u03c6"),
            state=get_floor_object_state(obj),
        ))

    return APIGameState(
        grid=project_grid(grid),
        entities=[project_entity_summary(entity) for entity in entity_rows],
        encounter=(
            project_encounter(encounter, entity_rows)
            if encounter is not None
            else None
        ),
        floor_objects=floor_objects,
    )


def build_current_objective_game_state(
    *,
    encounter: Encounter | None,
) -> APIGameState:
    """Serialize the current engine registries as objective state.

    Args:
        encounter: Active server-owned encounter, or ``None`` outside combat.

    Returns:
        Objective state for the current grid and entity registry.
    """
    return build_objective_game_state(
        grid=get_map(),
        entities=Entity.get_all_entities(),
        encounter=encounter,
    )


def build_objective_visibility(
    *,
    entities: Iterable[Entity],
) -> APIVisibilityResponse:
    """Serialize every supplied observer's current perception cache.

    Args:
        entities: Observing entities to include in iteration order.

    Returns:
        Observer-indexed objective visibility DTO.
    """
    result: dict[str, APIEntityVisibility] = {}
    for entity in entities:
        result[str(entity.uuid)] = APIEntityVisibility(
            name=entity.name,
            position=entity.position,
            visible_cells=[
                position
                for position, is_visible in entity.senses.visible.items()
                if is_visible
            ],
            visible_entities=[str(uuid) for uuid in entity.senses.entities],
            visible_objects=[str(uuid) for uuid in entity.senses.objects],
            seen_cells=list(entity.senses.seen),
            sense_modes=list(entity.senses.get_sense_modes()),
            effective_light_levels=entity.senses.get_effective_light_levels(
                entity.uuid,
            ),
        )
    return APIVisibilityResponse(root=result)


def build_current_objective_visibility() -> APIVisibilityResponse:
    """Serialize visibility for every entity in the current registry."""
    return build_objective_visibility(entities=Entity.get_all_entities())


def build_objective_equipment(
    *,
    entities: Iterable[Entity],
) -> dict[str, APIEquipmentOverview]:
    """Serialize complete equipment reducer seeds for supplied entities."""
    return {
        str(entity.uuid): project_equipment_overview(entity)
        for entity in entities
    }


def build_objective_world(
    *,
    grid: GridMap,
    entities: Iterable[Entity],
    encounter: Encounter | None,
) -> ReplicatedWorld:
    """Build one coherent objective reducer seed from explicit runtime values."""
    entity_rows = tuple(entities)
    return ReplicatedWorld(
        state=build_objective_game_state(
            grid=grid,
            entities=entity_rows,
            encounter=encounter,
        ),
        visibility=build_objective_visibility(entities=entity_rows),
        equipment_by_entity=build_objective_equipment(entities=entity_rows),
    )


def build_current_objective_world(
    *,
    encounter: Encounter | None,
) -> ReplicatedWorld:
    """Build one coherent objective reducer seed from current registries."""
    entities = tuple(Entity.get_all_entities())
    return build_objective_world(
        grid=get_map(),
        entities=entities,
        encounter=encounter,
    )


__all__ = [
    "build_current_objective_game_state",
    "build_current_objective_world",
    "build_current_objective_visibility",
    "build_objective_equipment",
    "build_objective_game_state",
    "build_objective_world",
    "build_objective_visibility",
    "get_floor_object_state",
]
