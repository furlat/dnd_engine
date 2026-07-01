"""Replay helpers for session-subjective observation frames."""

from __future__ import annotations

from typing import Any, Iterable, Tuple

from ai.observation.models import (
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationFrame,
    ObservationMaterializedState,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSnapshot,
    ObservationTileFact,
)


def materialize_snapshot(snapshot: ObservationSnapshot | dict[str, Any]) -> ObservationMaterializedState:
    """Create a materialized subjective state from a full snapshot.

    Args:
        snapshot: Snapshot produced by the observation projector.

    Returns:
        Materialized state keyed for efficient replay assertions.
    """
    if not isinstance(snapshot, ObservationSnapshot):
        snapshot = ObservationSnapshot.model_validate(snapshot)

    return ObservationMaterializedState(
        observation_cursor=snapshot.observation_cursor,
        session=snapshot.session,
        encounter=snapshot.encounter,
        observers={observer.observer_uuid: observer for observer in snapshot.observers},
        known_entities={entity.uuid: entity for entity in snapshot.known_entities},
        known_objects={obj.uuid: obj for obj in snapshot.known_objects},
        known_tiles={tile.key: tile for tile in snapshot.known_tiles},
        combat_logs=[],
    )


def apply_observation_frame(
    state: ObservationMaterializedState,
    frame: ObservationFrame | dict[str, Any],
) -> ObservationMaterializedState:
    """Apply one subjective frame idempotently.

    Args:
        state: Materialized subjective state.
        frame: Observation frame to apply.

    Returns:
        Updated materialized state. Old or duplicate frames are ignored.
    """
    if not isinstance(frame, ObservationFrame):
        frame = ObservationFrame.model_validate(frame)

    if frame.observation_cursor <= state.observation_cursor:
        return state

    next_state = state.model_copy(deep=True)
    for patch in frame.patches:
        if patch.patch_type == ObservationPatchType.SESSION:
            next_state.session = ObservationSessionState.model_validate(patch.data["session"])
        elif patch.patch_type == ObservationPatchType.ENCOUNTER:
            encounter_data = patch.data.get("encounter")
            if encounter_data is not None:
                next_state.encounter = ObservationEncounterState.model_validate(encounter_data)
        elif patch.patch_type == ObservationPatchType.OBSERVER:
            _apply_observer_patch(next_state, patch.data)
        elif patch.patch_type == ObservationPatchType.ENTITY and "entity" in patch.data:
            entity = ObservationEntityFact.model_validate(patch.data["entity"])
            next_state.known_entities[entity.uuid] = entity
        elif patch.patch_type == ObservationPatchType.OBJECT and "object" in patch.data:
            obj = ObservationObjectFact.model_validate(patch.data["object"])
            next_state.known_objects[obj.uuid] = obj
        elif patch.patch_type == ObservationPatchType.TILE and "tile" in patch.data:
            tile = ObservationTileFact.model_validate(patch.data["tile"])
            next_state.known_tiles[tile.key] = tile
        elif patch.patch_type == ObservationPatchType.COMBAT_LOG and "combat_log" in patch.data:
            next_state.combat_logs.append(patch.data["combat_log"])

    if frame.combat_log is not None and frame.combat_log not in next_state.combat_logs:
        next_state.combat_logs.append(frame.combat_log)
    next_state.observation_cursor = frame.observation_cursor
    return next_state


def _apply_observer_patch(
    state: ObservationMaterializedState,
    data: dict,
) -> None:
    """Apply sensory deltas to one observer state."""
    observer_uuid = data.get("observer_uuid")
    if observer_uuid is None:
        return
    observer = state.observers.get(observer_uuid)
    if observer is None:
        observer_payload = data.get("observer")
        if observer_payload is None:
            return
        state.observers[observer_uuid] = ObservationObserverState.model_validate(observer_payload)
        return

    visible_cells = set(_positions(observer.visible_cells))
    seen_cells = set(_positions(observer.seen_cells))
    visible_entities = set(observer.visible_entity_uuids)
    visible_objects = set(observer.visible_object_uuids)

    visible_cells.update(_positions(data.get("visible_cells_added", [])))
    visible_cells.difference_update(_positions(data.get("visible_cells_removed", [])))
    seen_cells.update(_positions(data.get("seen_cells_added", [])))

    visible_entities.update(data.get("visible_entities_added", {}).keys())
    visible_entities.difference_update(data.get("visible_entities_removed", {}).keys())
    visible_entities.update(data.get("visible_entities_moved", {}).keys())

    visible_objects.update(data.get("visible_objects_added", {}).keys())
    visible_objects.difference_update(data.get("visible_objects_removed", {}).keys())
    visible_objects.update(data.get("visible_objects_moved", {}).keys())

    update = {
        "visible_cells": sorted(visible_cells),
        "seen_cells": sorted(seen_cells),
        "visible_entity_uuids": sorted(visible_entities),
        "visible_object_uuids": sorted(visible_objects),
    }
    if data.get("sense_modes") is not None:
        update["sense_modes"] = data["sense_modes"]
    state.observers[observer_uuid] = observer.model_copy(update=update)


def _positions(values: Iterable[Tuple[int, int] | list[int]]) -> list[Tuple[int, int]]:
    """Normalize JSON and Python positions to tuples."""
    return [(int(value[0]), int(value[1])) for value in values]
