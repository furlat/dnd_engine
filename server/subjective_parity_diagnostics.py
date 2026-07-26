"""Independent live oracle for subjective render-state parity.

This module intentionally does not import the player world projector.  It
derives the expected currently-visible render manifest from the objective DTO
and the authorized perspective, then compares that value with the retained
subjective reducer state at the same source cursor.

Remembered, currently-unseen spatial facts are excluded: reconstructing those
from the current objective world would require the player's observation
history and would turn the canonical projector into its own oracle.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any
from uuid import UUID

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import GridMap
from server.agent_protocol.objective_diagnostics import (
    SubjectiveParityMismatch,
    SubjectiveRenderParityDiagnosticsResponse,
)
from server.canonical_json import canonical_json, canonical_json_bytes
from server.player_replication_contract import (
    PlayerReplicationWatermarks,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
)
from server.replicated_world import ReplicatedWorld
from server.world_contracts import (
    APIEntityVisibility,
    APIEquipmentOverview,
    APIFloorObject,
    APITile,
)


class SubjectiveParityDiagnosticsError(ValueError):
    """The two worlds cannot be compared at one safe, coherent boundary."""


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
_MISSING = object()
_MAX_MISMATCHES = 100


def build_subjective_render_parity_diagnostics(
    *,
    objective: ReplicatedWorld,
    subjective: SubjectiveReplicatedWorld,
    perspective: SubjectivePerspective,
    watermarks: PlayerReplicationWatermarks,
    source_stream_id: str,
    generation_id: str,
    grid: GridMap | None = None,
) -> SubjectiveRenderParityDiagnosticsResponse:
    """Compare one retained subjective boundary with independent censorship."""

    expected, visible_cells = _independent_censorship_manifest(
        objective,
        perspective=perspective,
        observed_tiles=(
            _independent_observed_tiles(
                grid,
                objective=objective,
                perspective=perspective,
            )
            if grid is not None
            else None
        ),
    )
    visible_object_uuids = {
        object_uuid
        for observer_uuid in perspective.observer_entity_uuids
        for object_uuid in objective.visibility.root[observer_uuid].visible_objects
    }
    actual = _subjective_visible_manifest(
        subjective,
        visible_cells=visible_cells,
        visible_object_uuids=visible_object_uuids,
    )

    expected_json = canonical_json(expected)
    actual_json = canonical_json(actual)
    mismatches: list[SubjectiveParityMismatch] = []
    compared_path_count = _collect_mismatches(
        expected,
        actual,
        path="$",
        mismatches=mismatches,
    )
    structural_edges = _canonical_structural_edges(expected["tiles"])
    door_edge_count = sum(
        appearance["kind"] == "door"
        for appearance in structural_edges.values()
    )
    expected_digest = sha256(canonical_json_bytes(expected)).hexdigest()
    actual_digest = sha256(canonical_json_bytes(actual)).hexdigest()
    return SubjectiveRenderParityDiagnosticsResponse(
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        perspective_epoch_id=perspective.perspective_epoch_id,
        source_event_cursor=watermarks.source_event_cursor,
        observation_cursor=watermarks.observation_cursor,
        presentation_cursor=watermarks.presentation_cursor,
        combat_log_cursor=watermarks.combat_log_cursor,
        expected_digest=expected_digest,
        actual_digest=actual_digest,
        matches=expected_json == actual_json,
        compared_path_count=max(1, compared_path_count),
        visible_tile_count=len(expected["tiles"]),
        structural_edge_count=len(structural_edges),
        door_edge_count=door_edge_count,
        non_empty_structural_edges=bool(structural_edges),
        mismatches=tuple(mismatches),
    )


def _independent_censorship_manifest(
    objective: ReplicatedWorld,
    *,
    perspective: SubjectivePerspective,
    observed_tiles: Mapping[tuple[int, int], Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], set[tuple[int, int]]]:
    """Apply the documented current-knowledge policy to an objective DTO."""

    missing_observers = sorted(
        set(perspective.observer_entity_uuids) - set(objective.visibility.root)
    )
    if missing_observers:
        raise SubjectiveParityDiagnosticsError(
            f"objective checkpoint lacks authorized observers: {missing_observers}"
        )
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
    missing_tiles = sorted(visible_cells - set(objective_tiles))
    if missing_tiles:
        raise SubjectiveParityDiagnosticsError(
            f"objective checkpoint lacks visible tiles: {missing_tiles}"
        )
    missing_equipment = sorted(
        identified_entity_uuids - set(objective.equipment_by_entity)
    )
    if missing_equipment:
        raise SubjectiveParityDiagnosticsError(
            f"objective checkpoint lacks render equipment: {missing_equipment}"
        )

    return {
        "bounds": [
            objective.state.grid.min_x,
            objective.state.grid.min_y,
            objective.state.grid.max_x,
            objective.state.grid.max_y,
        ],
        "tiles": {
            _position_key(position): (
                dict(observed_tiles[position])
                if observed_tiles is not None
                else _tile_with_observable_reciprocal_vision_edges(
                    objective_tiles[position],
                    objective_tiles=objective_tiles,
                )
            )
            for position in sorted(visible_cells)
        },
        "entities": {
            entity.uuid: entity.model_dump(mode="json")
            for entity in objective.state.entities
            if entity.uuid in identified_entity_uuids
        },
        "encounter": _expected_encounter_manifest(
            objective,
            identified_entity_uuids=identified_entity_uuids,
        ),
        # Object identity is included only when an authorized observer's public
        # visibility row names it. Structural rendering is compared separately
        # through anonymous tile-edge appearances.
        "floor_objects": {
            obj.uuid: _expected_floor_object_manifest(obj)
            for obj in objective.state.floor_objects
            if obj.position in visible_cells and obj.uuid in visible_object_uuids
        },
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
    }, visible_cells


def _subjective_visible_manifest(
    world: SubjectiveReplicatedWorld,
    *,
    visible_cells: set[tuple[int, int]],
    visible_object_uuids: set[str],
) -> dict[str, Any]:
    """Normalize only current-visible facts from the retained player reducer."""

    grid = world.state.grid
    return {
        "bounds": [grid.min_x, grid.min_y, grid.max_x, grid.max_y],
        "tiles": {
            _position_key((tile.x, tile.y)): tile.model_dump(mode="json")
            for tile in grid.tiles
            if (tile.x, tile.y) in visible_cells
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
                # The objective debug envelope does not own the player-safe
                # catalog reference. Its authentication is validated at the
                # dedicated content/player transport boundary.
                **{
                    key: value
                    for key, value in obj.model_dump(mode="json").items()
                    if key != "safe_presentation_ref"
                },
                "blocked_directions": [
                    direction.value for direction in obj.blocked_directions
                ],
                "blocked_channels": [
                    channel.value for channel in obj.blocked_channels
                ],
            }
            for obj in world.state.floor_objects
            if obj.position in visible_cells and obj.uuid in visible_object_uuids
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


def _independent_observed_tiles(
    grid: GridMap,
    *,
    objective: ReplicatedWorld,
    perspective: SubjectivePerspective,
) -> dict[tuple[int, int], dict[str, Any]]:
    """Rebuild observer-relative tiles without calling the player projector."""

    objective_tiles = {
        (tile.x, tile.y): tile
        for tile in objective.state.grid.tiles
    }
    viewers_by_position: dict[tuple[int, int], list[UUID]] = {}
    for observer_uuid_text in perspective.observer_entity_uuids:
        row = objective.visibility.root[observer_uuid_text]
        try:
            observer_uuid = UUID(observer_uuid_text)
        except ValueError as exc:
            raise SubjectiveParityDiagnosticsError(
                f"observer UUID is malformed: {observer_uuid_text!r}"
            ) from exc
        if BaseBlock.get(observer_uuid) is None:
            raise SubjectiveParityDiagnosticsError(
                f"observer is absent from the runtime: {observer_uuid_text}"
            )
        for position in row.visible_cells:
            viewers_by_position.setdefault(position, []).append(observer_uuid)

    observed: dict[tuple[int, int], dict[str, Any]] = {}
    for position, viewer_uuids in viewers_by_position.items():
        objective_tile = objective_tiles.get(position)
        tile = grid.get_tile(*position)
        if objective_tile is None or tile is None:
            raise SubjectiveParityDiagnosticsError(
                f"visible tile is absent from the objective runtime: {position}"
            )
        directional_rows: list[dict[str, dict[str, bool]]] = []
        structural_rows: list[dict[str, dict[str, Any] | None]] = []
        observer_perceptions: list[int] = []
        for observer_uuid in viewer_uuids:
            observer = BaseBlock.get(observer_uuid)
            if observer is None:
                raise SubjectiveParityDiagnosticsError(
                    f"observer disappeared during parity capture: {observer_uuid}"
                )
            observer_perceptions.append(observer.get_passive_perception())
            directional = grid.get_subjective_directional_block_map(
                position,
                observer_uuid,
            )
            structural = _independent_structural_edges(
                grid,
                position,
                observer_uuid,
            )
            for direction, (dx, dy) in _DIRECTION_DELTAS.items():
                neighbor_position = (position[0] + dx, position[1] + dy)
                neighbor = grid.get_subjective_directional_block_map(
                    neighbor_position,
                    observer_uuid,
                )
                opposite = _OPPOSITE_DIRECTION[direction]
                if neighbor["vision"][opposite]:
                    directional["vision"][direction] = True
                    reciprocal = _independent_structural_edges(
                        grid,
                        neighbor_position,
                        observer_uuid,
                    )[opposite]
                    structural[direction] = _prefer_appearance(
                        structural[direction],
                        reciprocal,
                    )
            directional_rows.append(directional)
            structural_rows.append(structural)

        payload = objective_tile.model_dump(mode="json")
        payload["visible"] = True
        payload["is_hazardous"] = any(
            grid.is_position_hazardous_for(*position, observer_uuid)
            for observer_uuid in viewer_uuids
        )
        payload["conditions"] = sorted({
            condition_name
            for observer_perception in observer_perceptions
            for condition_name, condition in tile.active_conditions.items()
            if condition.condition_category.value != "internal"
            and (
                condition.condition_stealth_dc is None
                or condition.condition_stealth_dc < observer_perception
            )
        })
        for channel in ("movement", "vision", "light", "propagation"):
            payload[f"directional_blocks_{channel}"] = {
                direction: any(
                    row[channel][direction]
                    for row in directional_rows
                )
                for direction in _DIRECTION_DELTAS
            }
        payload["directional_structural_edges"] = {
            direction: _merge_appearances(
                row[direction] for row in structural_rows
            )
            for direction in _DIRECTION_DELTAS
        }
        observed[position] = payload
    return observed


def _independent_structural_edges(
    grid: GridMap,
    position: tuple[int, int],
    observer_uuid: UUID,
) -> dict[str, dict[str, Any] | None]:
    """Derive anonymous edge appearance from intrinsic and perceivable facts."""

    tile = grid.get_tile(*position)
    edges: dict[str, dict[str, Any] | None] = {
        direction: None for direction in _DIRECTION_DELTAS
    }
    if tile is None:
        return edges
    for direction in _DIRECTION_DELTAS:
        if any(
            not tile.allows_direction(
                direction,
                channel,
                include_derived=False,
            )
            for channel in ("movement", "vision", "light", "propagation")
        ):
            edges[direction] = {"kind": "wall", "is_open": None}
    for object_uuid in sorted(grid.get_objects_at(position), key=str):
        block = BaseBlock.get(object_uuid)
        if not isinstance(block, BaseItem) or not block.is_perceivable_by(observer_uuid):
            continue
        directions = tuple(
            direction.value if hasattr(direction, "value") else str(direction)
            for direction in getattr(block, "blocked_directions", ())
        )
        channels = tuple(getattr(block, "blocked_channels", ()))
        if not directions or not channels:
            continue
        is_open = block.get_spatial_open_state()
        appearance = {
            "kind": "door" if is_open is not None else "wall",
            "is_open": is_open,
        }
        for direction in directions:
            if direction in edges:
                edges[direction] = _prefer_appearance(
                    edges[direction],
                    appearance,
                )
    return edges


def _merge_appearances(
    candidates: Any,
) -> dict[str, Any] | None:
    merged: dict[str, Any] | None = None
    for candidate in candidates:
        merged = _prefer_appearance(merged, candidate)
    return merged


def _prefer_appearance(
    current: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if candidate is None:
        return current
    if current is None or current == candidate:
        return candidate
    if current["kind"] == "door" and candidate["kind"] == "door":
        return {"kind": "door", "is_open": False}
    if current["kind"] == "door":
        return current
    if candidate["kind"] == "door":
        return candidate
    return current


def _tile_with_observable_reciprocal_vision_edges(
    tile: APITile,
    *,
    objective_tiles: Mapping[tuple[int, int], APITile],
) -> dict[str, Any]:
    payload = tile.model_dump(mode="json")
    payload["visible"] = True
    vision = dict(payload["directional_blocks_vision"])
    structural_edges = dict(payload["directional_structural_edges"])
    for direction, (dx, dy) in _DIRECTION_DELTAS.items():
        neighbor = objective_tiles.get((tile.x + dx, tile.y + dy))
        if neighbor is None:
            continue
        opposite = _OPPOSITE_DIRECTION[direction]
        if getattr(neighbor.directional_blocks_vision, opposite):
            vision[direction] = True
            reciprocal = getattr(neighbor.directional_structural_edges, opposite)
            if reciprocal is not None:
                structural_edges[direction] = reciprocal.model_dump(mode="json")
    payload["directional_blocks_vision"] = vision
    payload["directional_structural_edges"] = structural_edges
    return payload


def _canonical_visibility(row: APIEntityVisibility) -> dict[str, Any]:
    visible_cells = sorted(row.visible_cells)
    visible_light_keys = {_position_key(position) for position in visible_cells}
    return {
        "name": row.name,
        "position": list(row.position),
        "visible_cells": [list(position) for position in visible_cells],
        "visible_entities": sorted(row.visible_entities),
        "visible_objects": sorted(row.visible_objects),
        "seen_cells": [list(position) for position in sorted(row.seen_cells)],
        "sense_modes": sorted(
            (
                mode.sense_type.value,
                mode.range_feet,
            )
            for mode in row.sense_modes
        ),
        "effective_light_levels": {
            key: value
            for key, value in sorted(row.effective_light_levels.items())
            if key in visible_light_keys
        },
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


def _expected_visual_loadout(
    entity_uuid: str,
    equipment: APIEquipmentOverview,
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    for slot in equipment.slots:
        if slot.item is None:
            continue
        layers.append(
            {
                "slot": slot.slot,
                "item_kind": slot.item.item_type,
                "safe_presentation_ref": (
                    slot.item.safe_presentation_ref.model_dump(mode="json")
                ),
                "visual_item_name": slot.item.visual_item_name,
                "visual_variant_id": slot.item.visual_variant_id,
                "equipped_visual_policy": slot.item.equipped_visual_policy,
            }
        )
    return {
        "entity_uuid": entity_uuid,
        "active_weapon_set": equipment.active_weapon_set.value,
        "layers": layers,
    }


def _expected_floor_object_manifest(obj: APIFloorObject) -> dict[str, Any]:
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
            list(_string_tuple(state.get("blocked_directions", ())))
            if has_directional_state
            else []
        ),
        "blocked_channels": (
            list(_string_tuple(state.get("blocked_channels", ())))
            if has_directional_state
            else []
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


def _canonical_structural_edges(
    tiles: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Canonicalize cardinal tile halves into one north/east physical edge."""

    edges: dict[str, dict[str, Any]] = {}
    for payload in tiles.values():
        x = payload["x"]
        y = payload["y"]
        appearances = payload["directional_structural_edges"]
        for direction in _DIRECTION_DELTAS:
            appearance = appearances[direction]
            if appearance is None:
                continue
            owner_x, owner_y, owner_direction = _canonical_edge_owner(
                x,
                y,
                direction,
            )
            key = f"{owner_x},{owner_y}:{owner_direction}"
            previous = edges.get(key)
            if previous is not None and previous != appearance:
                raise SubjectiveParityDiagnosticsError(
                    f"objective checkpoint has conflicting appearance for edge {key}"
                )
            edges[key] = appearance
    return edges


def _canonical_edge_owner(
    x: int,
    y: int,
    direction: str,
) -> tuple[int, int, str]:
    if direction == "west":
        return x - 1, y, "east"
    if direction == "south":
        return x, y - 1, "north"
    return x, y, direction


def _collect_mismatches(
    expected: Any,
    actual: Any,
    *,
    path: str,
    mismatches: list[SubjectiveParityMismatch],
) -> int:
    """Recursively count comparison paths and retain a bounded diff."""

    compared = 1
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            compared += _collect_mismatches(
                expected.get(key, _MISSING),
                actual.get(key, _MISSING),
                path=f"{path}.{key}",
                mismatches=mismatches,
            )
        return compared
    if isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            compared += _collect_mismatches(
                expected[index] if index < len(expected) else _MISSING,
                actual[index] if index < len(actual) else _MISSING,
                path=f"{path}[{index}]",
                mismatches=mismatches,
            )
        return compared
    if expected != actual and len(mismatches) < _MAX_MISMATCHES:
        mismatches.append(
            SubjectiveParityMismatch(
                path=path,
                expected_json=_bounded_json(expected),
                actual_json=_bounded_json(actual),
            )
        )
    return compared


def _bounded_json(value: Any) -> str:
    if value is _MISSING:
        return '"<missing>"'
    encoded = canonical_json(value)
    if len(encoded) <= 4096:
        return encoded
    return canonical_json({
        "truncated": True,
        "sha256": sha256(encoded.encode("utf-8")).hexdigest(),
        "prefix": encoded[:1000],
    })


def _position_key(position: tuple[int, int]) -> str:
    return f"{position[0]},{position[1]}"


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise SubjectiveParityDiagnosticsError(
            "objective directional state must be a string sequence"
        )
    return tuple(value)


def _required_int(state: Mapping[str, Any], field_name: str) -> int:
    value = state.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SubjectiveParityDiagnosticsError(
            f"objective {field_name} must be an integer"
        )
    return value


__all__ = [
    "SubjectiveParityDiagnosticsError",
    "build_subjective_render_parity_diagnostics",
]
