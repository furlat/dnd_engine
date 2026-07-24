"""Same-boundary parity between objective state and the subjective render seed.

This file deliberately does not reuse the subjective projector's private
helpers.  Its expectation is authored from the public objective DTO plus the
documented censorship policy:

* observer knowledge is combined by set union;
* only currently known entities and tiles enter a fresh player seed;
* a physical vision edge remains visible from its visible side;
* full equipment is private to controlled actors;
* safe visual loadouts cover every projected actor; and
* floor objects require either explicit perception or a visible structural
  boundary.

The result is a regression oracle for ``subjective == objective + censorship``
at one observation boundary, rather than a second production projector.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.test_items import create_torch
from dnd.items.weapons import create_dagger, create_shortbow
from dnd.runtime_reset import reset_engine_runtime
from server.objective_state import build_objective_world
from server.player_replication.world_projection import (
    SubjectiveSpatialMemory,
    build_subjective_world,
)
from server.player_replication_contract import (
    PlayerReplicationWatermarks,
    PerspectiveKind,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
)
from server.replicated_world import ReplicatedWorld
from server.subjective_parity_diagnostics import (
    build_subjective_render_parity_diagnostics,
)
from server.world_contracts import (
    APIDirectionalBlockMap,
    APIEntityVisibility,
    APIEquipmentOverview,
    APIFloorObject,
    APITile,
)


_DIRECTION_DELTAS: dict[str, tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
}
_OPPOSITE_DIRECTION: dict[str, str] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}
_MELEE_SLOTS = frozenset({"weapon_melee_main", "weapon_melee_off"})
_RANGED_SLOTS = frozenset({"weapon_ranged_main", "weapon_ranged_off"})


def _position_key(position: tuple[int, int]) -> str:
    return f"{position[0]},{position[1]}"


def _canonical_visibility(row: APIEntityVisibility) -> dict[str, Any]:
    """Normalize ordering and retain light only where this observer sees."""
    visible_cells = sorted(row.visible_cells)
    visible_light_keys = {_position_key(position) for position in visible_cells}
    return {
        "name": row.name,
        "position": row.position,
        "visible_cells": visible_cells,
        "visible_entities": sorted(row.visible_entities),
        "visible_objects": sorted(row.visible_objects),
        "seen_cells": sorted(row.seen_cells),
        "sense_modes": sorted(
            (mode.sense_type.value, mode.range_feet)
            for mode in row.sense_modes
        ),
        "effective_light_levels": {
            key: value
            for key, value in sorted(row.effective_light_levels.items())
            if key in visible_light_keys
        },
    }


def _tile_with_observable_reciprocal_vision_edges(
    tile: APITile,
    *,
    objective_tiles: Mapping[tuple[int, int], APITile],
) -> dict[str, Any]:
    """Censor a tile while preserving a boundary visible from this side.

    A wall authored on an unseen neighbor is still the edge that terminated
    sight from the visible tile.  No other hidden-neighbor channel is promoted.
    """
    payload = tile.model_dump(mode="json")
    payload["visible"] = True
    vision = dict(payload["directional_blocks_vision"])
    structural_edges = dict(payload["directional_structural_edges"])
    for direction, (dx, dy) in _DIRECTION_DELTAS.items():
        neighbor = objective_tiles.get((tile.x + dx, tile.y + dy))
        if neighbor is None:
            continue
        neighbor_vision = neighbor.directional_blocks_vision
        if getattr(neighbor_vision, _OPPOSITE_DIRECTION[direction]):
            vision[direction] = True
            reciprocal = getattr(
                neighbor.directional_structural_edges,
                _OPPOSITE_DIRECTION[direction],
            )
            if reciprocal is not None:
                structural_edges[direction] = reciprocal.model_dump(mode="json")
    payload["directional_blocks_vision"] = vision
    payload["directional_structural_edges"] = structural_edges
    return payload


def _expected_floor_object_kind(state: Mapping[str, Any]) -> str:
    if "is_open" in state:
        return "door"
    if all(
        field in state
        for field in (
            "is_lit",
            "very_bright_radius_feet",
            "bright_radius_feet",
            "dim_radius_feet",
        )
    ):
        return "light_source"
    if state.get("blocked_directions") and state.get("blocked_channels"):
        return "directional_structure"
    if state.get("storage") is not None:
        return "container"
    if "hazard" in state.get("tags", ()):
        return "hazard"
    if state.get("is_usable") and not state.get("is_pickable"):
        return "interactable"
    if state.get("is_pickable"):
        return "item"
    return "generic"


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise AssertionError("objective directional state must be a string sequence")
    return tuple(value)


def _required_int(state: Mapping[str, Any], field_name: str) -> int:
    value = state.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AssertionError(f"objective {field_name} must be an integer")
    return value


def _expected_floor_object_manifest(obj: APIFloorObject) -> dict[str, Any]:
    """Normalize the objective envelope into the public subjective fields."""
    state = obj.state
    kind = _expected_floor_object_kind(state)
    has_directional_state = kind in {"door", "directional_structure"}
    has_light_state = kind == "light_source"
    return {
        "uuid": obj.uuid,
        "name": obj.name,
        "position": list(obj.position),
        "map_char": obj.map_char,
        "object_kind": kind,
        "visual_item_name": state.get("visual_item_name") or obj.name,
        "visual_variant_id": state.get("visual_variant_id"),
        "blocks_movement": bool(state.get("blocks_movement", False)),
        "blocks_vision": bool(state.get("blocks_vision_field", False)),
        "is_open": state.get("is_open") if kind == "door" else None,
        "blocked_directions": (
            _string_tuple(state.get("blocked_directions", ()))
            if has_directional_state
            else ()
        ),
        "blocked_channels": (
            _string_tuple(state.get("blocked_channels", ()))
            if has_directional_state
            else ()
        ),
        "is_lit": bool(state.get("is_lit")) if has_light_state else None,
        "very_bright_radius_feet": (
            _required_int(state, "very_bright_radius_feet")
            if has_light_state
            else None
        ),
        "bright_radius_feet": (
            _required_int(state, "bright_radius_feet")
            if has_light_state
            else None
        ),
        "dim_radius_feet": (
            _required_int(state, "dim_radius_feet")
            if has_light_state
            else None
        ),
    }


def _expected_visual_loadout(
    entity_uuid: str,
    equipment: APIEquipmentOverview,
) -> dict[str, Any]:
    """Derive renderer-safe layers solely from the objective equipment DTO."""
    layers: list[dict[str, Any]] = []
    occupied_slots: set[str] = set()
    for slot in equipment.slots:
        if slot.item is None:
            continue
        occupied_slots.add(slot.slot)
        layers.append(
            {
                "slot": slot.slot,
                "item_kind": slot.item.item_type,
                "visual_item_name": slot.item.visual_item_name,
                "visual_variant_id": slot.item.visual_variant_id,
                "equipped_visual_policy": slot.item.equipped_visual_policy,
            }
        )
    active_weapon_set = "none"
    if occupied_slots & _MELEE_SLOTS:
        active_weapon_set = "melee"
    elif occupied_slots & _RANGED_SLOTS:
        active_weapon_set = "ranged"
    return {
        "entity_uuid": entity_uuid,
        "active_weapon_set": active_weapon_set,
        "layers": layers,
    }


def _expected_encounter_manifest(
    objective: ReplicatedWorld,
    *,
    identified_entity_uuids: set[str],
) -> dict[str, Any] | None:
    encounter = objective.state.encounter
    if encounter is None:
        return None
    initiative_order = [
        row.model_dump(mode="json")
        for row in encounter.initiative_order
        if row.uuid in identified_entity_uuids
    ]
    projected_order = [row["uuid"] for row in initiative_order]
    current_entity_uuid = encounter.current_entity_uuid
    if current_entity_uuid not in projected_order:
        current_entity_uuid = None
        current_turn_index = None
    else:
        current_turn_index = projected_order.index(current_entity_uuid)
    return {
        "uuid": encounter.uuid,
        "name": encounter.name,
        "state": encounter.state,
        "round_number": encounter.round_number,
        "current_turn_index": current_turn_index,
        "current_entity_uuid": current_entity_uuid,
        "initiative_order": initiative_order,
    }


def _independent_censorship_manifest(
    objective: ReplicatedWorld,
    *,
    perspective: SubjectivePerspective,
) -> dict[str, Any]:
    """Apply the documented information policy to one objective checkpoint."""
    observer_rows = {
        observer_uuid: objective.visibility.root[observer_uuid]
        for observer_uuid in perspective.observer_entity_uuids
    }
    visible_cells = {
        position
        for visibility in observer_rows.values()
        for position in visibility.visible_cells
    }
    visible_object_uuids = {
        object_uuid
        for visibility in observer_rows.values()
        for object_uuid in visibility.visible_objects
    }
    identified_entity_uuids = (
        set(perspective.controlled_entity_uuids)
        | set(perspective.observer_entity_uuids)
        | {
            entity_uuid
            for visibility in observer_rows.values()
            for entity_uuid in visibility.visible_entities
        }
    )

    objective_tiles = {
        (tile.x, tile.y): tile
        for tile in objective.state.grid.tiles
    }
    expected_tiles = {
        _position_key(position): _tile_with_observable_reciprocal_vision_edges(
            objective_tiles[position],
            objective_tiles=objective_tiles,
        )
        for position in sorted(visible_cells)
    }

    expected_objects: dict[str, dict[str, Any]] = {}
    for obj in objective.state.floor_objects:
        if obj.position not in visible_cells:
            continue
        state = obj.state
        is_structural = (
            "is_open" in state
            or bool(state.get("blocked_directions") and state.get("blocked_channels"))
        )
        if obj.uuid not in visible_object_uuids and not is_structural:
            continue
        expected_objects[obj.uuid] = _expected_floor_object_manifest(obj)

    return {
        "bounds": (
            objective.state.grid.min_x,
            objective.state.grid.min_y,
            objective.state.grid.max_x,
            objective.state.grid.max_y,
        ),
        "tiles": expected_tiles,
        "entities": {
            entity.uuid: entity.model_dump(mode="json")
            for entity in objective.state.entities
            if entity.uuid in identified_entity_uuids
        },
        "encounter": _expected_encounter_manifest(
            objective,
            identified_entity_uuids=identified_entity_uuids,
        ),
        "floor_objects": expected_objects,
        "visibility": {
            observer_uuid: _canonical_visibility(row)
            for observer_uuid, row in observer_rows.items()
        },
        "equipment": {
            entity_uuid: objective.equipment_by_entity[
                entity_uuid
            ].model_dump(mode="json")
            for entity_uuid in perspective.controlled_entity_uuids
        },
        "visual_loadouts": {
            entity_uuid: _expected_visual_loadout(
                entity_uuid,
                objective.equipment_by_entity[entity_uuid],
            )
            for entity_uuid in sorted(identified_entity_uuids)
        },
    }


def _subjective_manifest(world: SubjectiveReplicatedWorld) -> dict[str, Any]:
    """Put the actual player world in the same deterministic comparison shape."""
    grid = world.state.grid
    return {
        "bounds": (grid.min_x, grid.min_y, grid.max_x, grid.max_y),
        "tiles": {
            _position_key((tile.x, tile.y)): tile.model_dump(mode="json")
            for tile in grid.tiles
        },
        "entities": {
            entity.uuid: entity.model_dump(mode="json")
            for entity in world.state.entities
        },
        "encounter": (
            world.state.encounter.model_dump(mode="json")
            if world.state.encounter is not None
            else None
        ),
        "floor_objects": {
            obj.uuid: {
                **obj.model_dump(mode="json"),
                "blocked_directions": tuple(
                    direction.value for direction in obj.blocked_directions
                ),
                "blocked_channels": tuple(
                    channel.value for channel in obj.blocked_channels
                ),
            }
            for obj in world.state.floor_objects
        },
        "visibility": {
            observer_uuid: _canonical_visibility(row)
            for observer_uuid, row in world.visibility.root.items()
        },
        "equipment": {
            entity_uuid: equipment.model_dump(mode="json")
            for entity_uuid, equipment in world.equipment_by_entity.items()
        },
        "visual_loadouts": {
            entity_uuid: loadout.model_dump(mode="json")
            for entity_uuid, loadout in world.visual_loadout_by_entity.items()
        },
    }


def _equip(
    entity: Entity,
    *,
    slot: WeaponSlot,
) -> None:
    weapon = (
        create_shortbow(entity.uuid)
        if slot is WeaponSlot.RANGED_MAIN
        else create_dagger(entity.uuid)
    )
    assert entity.loot_item(weapon)
    assert entity.equip_item(weapon.uuid, slot)


def test_subjective_seed_equals_objective_checkpoint_plus_censorship() -> None:
    """One non-trivial player seed matches the independently censored objective."""
    grid = reset_engine_runtime(grid_size=(7, 5))
    observer_a = Entity.create(
        source_entity_uuid=uuid4(),
        name="West observer",
        config=EntityConfig(position=(0, 2), faction="heroes"),
    )
    observer_b = Entity.create(
        source_entity_uuid=uuid4(),
        name="East observer",
        config=EntityConfig(position=(6, 2), faction="heroes"),
    )
    west_contact = Entity.create(
        source_entity_uuid=uuid4(),
        name="West contact",
        config=EntityConfig(position=(1, 2), faction="monsters"),
    )
    east_contact = Entity.create(
        source_entity_uuid=uuid4(),
        name="East contact",
        config=EntityConfig(position=(5, 2), faction="monsters"),
    )
    hidden_contact = Entity.create(
        source_entity_uuid=uuid4(),
        name="Unknown contact",
        config=EntityConfig(position=(3, 4), faction="monsters"),
    )
    entities = (
        observer_a,
        observer_b,
        west_contact,
        east_contact,
        hidden_contact,
    )
    for entity, slot in (
        (observer_a, WeaponSlot.MELEE_MAIN),
        (observer_b, WeaponSlot.RANGED_MAIN),
        (west_contact, WeaponSlot.MELEE_MAIN),
        (east_contact, WeaponSlot.RANGED_MAIN),
        (hidden_contact, WeaponSlot.MELEE_MAIN),
    ):
        _equip(entity, slot=slot)

    west_cells = {(0, 1), (0, 2), (0, 3), (1, 2)}
    east_cells = {(5, 2), (6, 1), (6, 2), (6, 3)}
    observer_a.senses.visible = {position: True for position in west_cells}
    observer_a.senses.seen = set(west_cells)
    observer_a.senses.entities = {
        west_contact.uuid: west_contact.position,
    }
    observer_a.senses.objects = {}
    observer_b.senses.visible = {position: True for position in east_cells}
    observer_b.senses.seen = set(east_cells)
    observer_b.senses.entities = {
        east_contact.uuid: east_contact.position,
    }
    observer_b.senses.objects = {}

    visible_door = DirectionalDoor(
        source_entity_uuid=observer_a.uuid,
        blocked_directions=("north",),
        blocked_channels=("movement", "vision"),
        visual_item_name="VisibleDoor",
    )
    hidden_door = DirectionalDoor(
        source_entity_uuid=hidden_contact.uuid,
        blocked_directions=("east",),
        blocked_channels=("movement", "vision"),
        visual_item_name="HiddenDoor",
    )
    torch = create_torch(observer_b.uuid)
    torch.is_lit = True
    grid.place_object(visible_door.uuid, (0, 3))
    grid.place_object(hidden_door.uuid, (3, 4))
    grid.place_object(torch.uuid, (6, 1))
    observer_b.senses.objects = {torch.uuid: (6, 1)}

    perspective = SubjectivePerspective(
        perspective_epoch_id="party-parity-epoch",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(
            str(observer_a.uuid),
            str(observer_b.uuid),
        ),
        observer_entity_uuids=(
            str(observer_a.uuid),
            str(observer_b.uuid),
        ),
        active_observer_uuid=str(observer_b.uuid),
    )

    try:
        objective = build_objective_world(
            grid=grid,
            entities=entities,
            encounter=None,
        )
        subjective = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=entities,
            encounter=None,
            memory=SubjectiveSpatialMemory(
                perspective_epoch_id=perspective.perspective_epoch_id,
            ),
        )

        expected = _independent_censorship_manifest(
            objective,
            perspective=perspective,
        )
        actual = _subjective_manifest(subjective)

        # Anti-empty checks ensure equality cannot pass through an empty scene.
        assert len(objective.state.grid.tiles) == 35
        assert len(expected["tiles"]) == len(west_cells | east_cells) == 8
        assert len(objective.state.entities) == 5
        assert len(expected["entities"]) == 4
        assert len(objective.state.floor_objects) == 3
        assert len(expected["floor_objects"]) == 2
        assert len(expected["visibility"]) == 2
        assert len(expected["equipment"]) == 2
        assert len(expected["visual_loadouts"]) == 4

        # Prove that censorship, union, and privacy are all exercised.
        assert str(hidden_contact.uuid) in objective.equipment_by_entity
        assert str(hidden_contact.uuid) not in expected["entities"]
        assert str(hidden_door.uuid) in {
            obj.uuid for obj in objective.state.floor_objects
        }
        assert str(hidden_door.uuid) not in expected["floor_objects"]
        assert str(visible_door.uuid) in expected["floor_objects"]
        assert str(torch.uuid) in expected["floor_objects"]
        assert str(west_contact.uuid) in expected["entities"]
        assert str(east_contact.uuid) in expected["entities"]
        assert str(west_contact.uuid) not in expected["equipment"]
        assert str(east_contact.uuid) not in expected["equipment"]
        assert str(west_contact.uuid) in expected["visual_loadouts"]
        assert str(east_contact.uuid) in expected["visual_loadouts"]

        assert actual == expected
        diagnostic = build_subjective_render_parity_diagnostics(
            objective=objective,
            subjective=subjective,
            perspective=perspective,
            watermarks=PlayerReplicationWatermarks(
                source_event_cursor=0,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            source_stream_id="parity-fixture",
            generation_id="generation-fixture",
            grid=grid,
        )
        assert diagnostic.matches is True
        assert diagnostic.mismatches == ()
        assert diagnostic.compared_path_count > 1
        assert diagnostic.visible_tile_count == 8
        assert diagnostic.structural_edge_count > 0
        assert diagnostic.door_edge_count > 0

        altered_tiles = list(subjective.state.grid.tiles)
        altered_tiles[0] = altered_tiles[0].model_copy(
            update={"visual_key": "diagnostic-mismatch.png"},
        )
        altered = subjective.model_copy(update={
            "state": subjective.state.model_copy(update={
                "grid": subjective.state.grid.model_copy(update={
                    "tiles": altered_tiles,
                }),
            }),
        })
        mismatch = build_subjective_render_parity_diagnostics(
            objective=objective,
            subjective=altered,
            perspective=perspective,
            watermarks=PlayerReplicationWatermarks(
                source_event_cursor=0,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            source_stream_id="parity-fixture",
            generation_id="generation-fixture",
            grid=grid,
        )
        assert mismatch.matches is False
        assert mismatch.expected_digest != mismatch.actual_digest
        assert any(
            row.path.endswith(".visual_key")
            for row in mismatch.mismatches
        )
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize(
    ("neighbor_position", "neighbor_direction", "visible_direction"),
    (
        ((1, 2), "south", "north"),
        ((1, 0), "north", "south"),
        ((2, 1), "west", "east"),
        ((0, 1), "east", "west"),
    ),
)
def test_each_hidden_neighbor_door_edge_matches_objective_censorship(
    neighbor_position: tuple[int, int],
    neighbor_direction: str,
    visible_direction: str,
) -> None:
    """All four reciprocal door edges survive independent objective censorship."""
    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Boundary observer",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    door = DirectionalDoor(
        source_entity_uuid=observer.uuid,
        blocked_directions=(neighbor_direction,),
        blocked_channels=("movement", "vision"),
        visual_item_name="HiddenNeighborDoor",
    )
    grid.place_object(door.uuid, neighbor_position)
    perspective = SubjectivePerspective(
        perspective_epoch_id=f"edge-{visible_direction}",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(str(observer.uuid),),
        observer_entity_uuids=(str(observer.uuid),),
        active_observer_uuid=str(observer.uuid),
    )

    try:
        objective = build_objective_world(
            grid=grid,
            entities=(observer,),
            encounter=None,
        )
        subjective = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=(observer,),
            encounter=None,
            memory=SubjectiveSpatialMemory(
                perspective_epoch_id=perspective.perspective_epoch_id,
            ),
        )
        expected = _independent_censorship_manifest(
            objective,
            perspective=perspective,
        )
        actual = _subjective_manifest(subjective)

        assert len(objective.state.grid.tiles) == 9
        assert len(expected["tiles"]) == 1
        assert len(expected["entities"]) == 1
        assert expected["floor_objects"] == {}
        assert str(door.uuid) in {
            obj.uuid for obj in objective.state.floor_objects
        }
        assert expected["tiles"]["1,1"]["directional_blocks_vision"][
            visible_direction
        ] is True
        assert expected["tiles"]["1,1"]["directional_structural_edges"][
            visible_direction
        ] == {"kind": "door", "is_open": False}
        assert actual == expected
    finally:
        reset_engine_runtime()


def test_live_oracle_censors_an_imperceivable_structural_object() -> None:
    """The independent check does not mistake objective topology for player knowledge."""

    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Private-edge observer",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    private_door = DirectionalDoor(
        source_entity_uuid=observer.uuid,
        blocked_directions=("west",),
        blocked_channels=("movement", "vision"),
        is_invisible=True,
    )
    grid.place_object(private_door.uuid, (2, 1))
    perspective = SubjectivePerspective(
        perspective_epoch_id="private-edge",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(str(observer.uuid),),
        observer_entity_uuids=(str(observer.uuid),),
        active_observer_uuid=str(observer.uuid),
    )

    try:
        objective = build_objective_world(
            grid=grid,
            entities=(observer,),
            encounter=None,
        )
        subjective = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=(observer,),
            encounter=None,
            memory=SubjectiveSpatialMemory(
                perspective_epoch_id=perspective.perspective_epoch_id,
            ),
        )
        report = build_subjective_render_parity_diagnostics(
            objective=objective,
            subjective=subjective,
            perspective=perspective,
            watermarks=PlayerReplicationWatermarks(
                source_event_cursor=0,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            source_stream_id="private-edge",
            generation_id="private-edge-generation",
            grid=grid,
        )

        assert report.matches is True
        assert report.structural_edge_count == 0
        assert report.door_edge_count == 0
        assert report.non_empty_structural_edges is False
    finally:
        reset_engine_runtime()


def test_directional_block_model_is_closed_for_parity_fixture() -> None:
    """Guard the test oracle against silently missing a new cardinal field."""
    assert set(APIDirectionalBlockMap.model_fields) == set(_DIRECTION_DELTAS)
