"""Replay helpers for session-subjective observation frames."""

from __future__ import annotations

from typing import Any, Iterable, Tuple, cast

from dnd.core.life_types import LifeState
from server.agent_protocol.observation import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFrameType,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSnapshot,
    ObservationStateReplacement,
    SubjectiveWorldState,
    ObservationTileFact,
)
from server.agent_protocol.observation_legacy import (
    migrate_legacy_frame_semantics,
    migrate_legacy_snapshot_semantics,
)


def materialize_snapshot(snapshot: ObservationSnapshot | dict[str, Any]) -> SubjectiveWorldState:
    """Create a materialized subjective state from a full snapshot.

    Args:
        snapshot: Snapshot produced by the observation projector.

    Returns:
        Materialized state keyed for efficient replay assertions.
    """
    if not isinstance(snapshot, ObservationSnapshot):
        snapshot = cast(dict[str, Any], migrate_legacy_snapshot_semantics(snapshot))
        snapshot = ObservationSnapshot.model_validate(snapshot)

    return SubjectiveWorldState(
        observation_cursor=snapshot.observation_cursor,
        session=snapshot.session,
        encounter=snapshot.encounter,
        observers={observer.observer_uuid: observer for observer in snapshot.observers},
        known_entities={entity.uuid: entity for entity in snapshot.known_entities},
        known_objects={obj.uuid: obj for obj in snapshot.known_objects},
        known_tiles={tile.key: tile for tile in snapshot.known_tiles},
        combat_logs=list(snapshot.combat_logs),
        current_epoch=snapshot.current_epoch,
        epoch_cursor=snapshot.current_epoch.epoch_index if snapshot.current_epoch is not None else 0,
    )


def apply_observation_frame(
    state: SubjectiveWorldState,
    frame: ObservationFrame | dict[str, Any],
) -> SubjectiveWorldState:
    """Apply one subjective frame idempotently.

    Args:
        state: Materialized subjective state.
        frame: Observation frame to apply.

    Returns:
        Updated materialized state. Old or duplicate frames are ignored.
    """
    if not isinstance(frame, ObservationFrame):
        frame = cast(dict[str, Any], migrate_legacy_frame_semantics(frame))
        frame = ObservationFrame.model_validate(frame)

    if frame.observation_cursor <= state.observation_cursor:
        return state

    next_state = state.model_copy(
        update={
            "observers": dict(state.observers),
            "known_entities": dict(state.known_entities),
            "known_objects": dict(state.known_objects),
            "known_tiles": dict(state.known_tiles),
            "combat_logs": list(state.combat_logs),
        },
        deep=False,
    )
    if frame.state_replacement is not None:
        _apply_state_replacement(next_state, frame.state_replacement)
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
            next_state.known_entities[entity.uuid] = _merge_entity_fact(
                next_state.known_entities.get(entity.uuid),
                entity,
            )
        elif patch.patch_type == ObservationPatchType.ENTITY and "entity_update" in patch.data:
            _apply_entity_update_patch(next_state, patch.data["entity_update"])
        elif patch.patch_type == ObservationPatchType.OBJECT and "object" in patch.data:
            obj = ObservationObjectFact.model_validate(patch.data["object"])
            next_state.known_objects[obj.uuid] = obj
        elif patch.patch_type == ObservationPatchType.TILE and "tiles" in patch.data:
            for tile_payload in patch.data["tiles"]:
                tile = ObservationTileFact.model_validate(tile_payload)
                next_state.known_tiles[tile.key] = _merge_tile_fact(
                    next_state.known_tiles.get(tile.key),
                    tile,
                )
        elif patch.patch_type == ObservationPatchType.TILE and "tile" in patch.data:
            tile = ObservationTileFact.model_validate(patch.data["tile"])
            next_state.known_tiles[tile.key] = _merge_tile_fact(
                next_state.known_tiles.get(tile.key),
                tile,
            )
        elif patch.patch_type == ObservationPatchType.COMBAT_LOG and "combat_log" in patch.data:
            next_state.combat_logs.append(patch.data["combat_log"])

    if frame.combat_log is not None and frame.combat_log not in next_state.combat_logs:
        next_state.combat_logs.append(frame.combat_log)
    if frame.frame_type == ObservationFrameType.DECISION_EPOCH:
        next_state.current_epoch = frame.decision_epoch
        next_state.epoch_cursor = frame.decision_epoch.epoch_index if frame.decision_epoch is not None else 0
    next_state.observation_cursor = frame.observation_cursor
    return next_state


def _apply_state_replacement(
    state: SubjectiveWorldState,
    replacement: ObservationStateReplacement,
) -> None:
    """Atomically replace subjective state at a session-control boundary."""
    state.session = replacement.session
    state.encounter = replacement.encounter
    state.observers = {
        observer.observer_uuid: observer
        for observer in replacement.observers
    }
    state.known_entities = {
        entity.uuid: entity
        for entity in replacement.known_entities
    }
    state.known_objects = {
        obj.uuid: obj
        for obj in replacement.known_objects
    }
    state.known_tiles = {
        tile.key: tile
        for tile in replacement.known_tiles
    }
    state.combat_logs = list(replacement.combat_logs)
    state.current_epoch = replacement.current_epoch
    state.epoch_cursor = (
        replacement.current_epoch.epoch_index
        if replacement.current_epoch is not None
        else 0
    )


def _apply_entity_update_patch(
    state: SubjectiveWorldState,
    data: dict,
) -> None:
    """Apply a partial entity update to an existing known fact."""
    entity_uuid = data.get("uuid")
    if not isinstance(entity_uuid, str):
        return
    previous = state.known_entities.get(entity_uuid)
    if previous is None:
        return
    update = {
        key: value
        for key, value in data.items()
        if key != "uuid"
    }
    position = update.get("position")
    if isinstance(position, list):
        update["position"] = tuple(position)
    knowledge_state = update.get("knowledge_state")
    if isinstance(knowledge_state, str):
        update["knowledge_state"] = KnowledgeState(knowledge_state)
    life_state = update.get("life_state")
    if isinstance(life_state, str):
        update["life_state"] = LifeState(life_state)
    state.known_entities[entity_uuid] = previous.model_copy(update=update)


def _merge_entity_fact(
    previous: ObservationEntityFact | None,
    current: ObservationEntityFact,
) -> ObservationEntityFact:
    """Merge monotonic knowledge into a replacement entity fact.

    Args:
        previous: Previously materialized subjective fact, when any.
        current: Newly projected full fact.

    Returns:
        Current fact with terminal knowledge retained across redaction.
    """
    if previous is None:
        return current

    retained: dict[str, object] = {}
    if previous.life_state is LifeState.DEAD and current.life_state is None:
        retained["life_state"] = LifeState.DEAD
        retained["is_dead"] = True
    if (
        current.knowledge_state in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED}
        and current.faction is None
        and previous.faction is not None
    ):
        retained["faction"] = previous.faction
    if retained:
        return current.model_copy(update=retained)
    return current


def _merge_tile_fact(
    previous: ObservationTileFact | None,
    current: ObservationTileFact,
) -> ObservationTileFact:
    """Merge remembered spatial boundary knowledge into sparse tile deltas."""
    if previous is None:
        return current
    if (
        current.knowledge_state in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED}
        and not current.adjacent_domain
        and previous.adjacent_domain
    ):
        return current.model_copy(update={"adjacent_domain": previous.adjacent_domain})
    return current


def _apply_observer_patch(
    state: SubjectiveWorldState,
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
    position = data.get("position")
    if isinstance(position, (list, tuple)) and len(position) == 2:
        update["position"] = (int(position[0]), int(position[1]))
    passive_perception = data.get("passive_perception")
    if isinstance(passive_perception, int) and not isinstance(passive_perception, bool):
        update["passive_perception"] = passive_perception
    if data.get("sense_modes") is not None:
        update["sense_modes"] = data["sense_modes"]
    state.observers[observer_uuid] = observer.model_copy(update=update)


def _positions(values: Iterable[Tuple[int, int] | list[int]]) -> list[Tuple[int, int]]:
    """Normalize JSON and Python positions to tuples."""
    return [(int(value[0]), int(value[1])) for value in values]
