"""Project objective engine state into session-subjective observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from uuid import UUID

from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.session import GameSession, PlayerSession, SessionManager

from ai.observation.models import (
    KnowledgeState,
    ObservationCombatantState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationFrame,
    ObservationFramesResponse,
    ObservationFrameType,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationPatch,
    ObservationPatchType,
    ObservationSessionState,
    ObservationSnapshot,
    ObservationTileFact,
)


class ObservationAccessError(ValueError):
    """Raised when an observation request cannot be authorized or resolved."""

    def __init__(self, code: str, message: str) -> None:
        """Create a structured observation access error.

        Args:
            code: Machine-readable error code.
            message: Human-readable error message.
        """
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class _ProjectionCacheEntry:
    """Cached subjective frame projection for one session."""

    source_event_cursor: int = 0
    controlled_key: Tuple[str, ...] = ()
    encounter_uuid: Optional[str] = None
    frames: List[ObservationFrame] = field(default_factory=list)


_projection_cache: Dict[str, _ProjectionCacheEntry] = {}


def clear_observation_projection_cache() -> None:
    """Clear cached subjective frame projections."""
    _projection_cache.clear()


def build_observation_snapshot(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> ObservationSnapshot:
    """Build the current strict subjective snapshot for one session.

    Args:
        session_id: Session UUID string or object.

    Returns:
        Snapshot containing the session's currently known world facts.

    Raises:
        ObservationAccessError: If the session cannot be resolved.
    """
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    observers = _controlled_observers(session)
    observation_cursor = _current_observation_cursor(session, game, encounter)

    return ObservationSnapshot(
        observation_cursor=observation_cursor,
        source_event_cursor=EventQueue.event_cursor(),
        source_combat_log_cursor=len(encounter.combat_log) if encounter else 0,
        session=_session_state(session, game),
        encounter=_encounter_state(encounter, session, observers) if encounter else None,
        observers=[_observer_state(observer) for observer in observers],
        known_entities=_known_entity_facts(session, observers),
        known_objects=_known_object_facts(observers),
        known_tiles=_known_tile_facts(observers),
    )


def get_observation_cursor(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> int:
    """Return the current session-local observation cursor."""
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    return _current_observation_cursor(session, game, encounter)


def iter_observation_frames(
    session_id: str | UUID,
    since: int = 0,
    limit: int = 50,
    session_manager: Optional[SessionManager] = None,
) -> ObservationFramesResponse:
    """Return projected subjective frames after a session-local cursor.

    Args:
        session_id: Session UUID string or object.
        since: Session-local observation cursor already consumed by the client.
        limit: Maximum frames to return. A value of 0 means no limit.

    Returns:
        Cursor-addressed frame page.

    Raises:
        ObservationAccessError: If the session cannot be resolved.
    """
    session, game = _resolve_session(session_id, session_manager)
    encounter = game.encounter if game else Encounter.get_active()
    all_frames = _project_all_frames(session, game, encounter)
    start = max(0, since)
    frames = [frame for frame in all_frames if frame.observation_cursor > start]
    if limit > 0:
        frames = frames[:limit]
    next_cursor = frames[-1].observation_cursor if frames else start
    return ObservationFramesResponse(
        frames=frames,
        count=len(frames),
        total=len(all_frames),
        next_observation_cursor=next_cursor,
    )


def _resolve_session(
    session_id: str | UUID,
    session_manager: Optional[SessionManager] = None,
) -> tuple[PlayerSession, Optional[GameSession]]:
    """Resolve a session and active game for observation requests."""
    try:
        sid = session_id if isinstance(session_id, UUID) else UUID(session_id)
    except ValueError as exc:
        raise ObservationAccessError("invalid_session_uuid", "Invalid session ID format") from exc

    manager = session_manager or SessionManager.get()
    session = manager.get_session(sid)
    if session is None:
        raise ObservationAccessError("session_not_found", "Session not found")
    return session, manager.get_active_game()


def _current_observation_cursor(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
) -> int:
    """Return the current session-local observation cursor."""
    return len(_project_all_frames(session, game, encounter))


def _project_all_frames(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
) -> List[ObservationFrame]:
    """Project all currently visible event frames for a session."""
    return list(_update_projection_cache(session, game, encounter).frames)


def _update_projection_cache(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
) -> _ProjectionCacheEntry:
    """Incrementally update cached subjective frames for one session."""
    current_event_cursor = EventQueue.event_cursor()
    cache_key = str(session.session_id)
    controlled_key = tuple(sorted(str(uuid) for uuid in session.controlled_entities))
    encounter_uuid = str(encounter.uuid) if encounter is not None else None
    entry = _projection_cache.get(cache_key)
    if (
        entry is None
        or entry.source_event_cursor > current_event_cursor
        or entry.controlled_key != controlled_key
        or entry.encounter_uuid != encounter_uuid
    ):
        entry = _ProjectionCacheEntry(
            controlled_key=controlled_key,
            encounter_uuid=encounter_uuid,
        )
        _projection_cache[cache_key] = entry

    observers = _controlled_observers(session)
    for source_index, event in EventQueue.iter_events_since(entry.source_event_cursor):
        frame = _project_event(session, game, encounter, observers, source_index, event)
        if frame is None:
            continue
        entry.frames.append(frame.model_copy(update={"observation_cursor": len(entry.frames) + 1}))
    entry.source_event_cursor = current_event_cursor
    return entry


def _project_event(
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    observers: List[Entity],
    source_index: int,
    event: Event,
) -> Optional[ObservationFrame]:
    """Project one engine event into a safe subjective frame when visible."""
    if event.phase != EventPhase.COMPLETION:
        return None

    patches: List[ObservationPatch] = []
    if event.event_type == EventType.SENSORY_UPDATE and isinstance(event, SensoryUpdateEvent):
        if event.observer_uuid not in session.controlled_entities:
            return None
        patches.extend(_sensory_patches(event, session, observers))
    elif _event_visible_to_session(event, session, observers):
        patches.extend(_event_state_patches(event, session, game, encounter, observers))
    else:
        combat_log = _filtered_combat_log(event.combat_log, session, observers)
        if combat_log is None:
            return None
        patches.append(_combat_log_patch(combat_log))

    combat_log = _filtered_combat_log(event.combat_log, session, observers)
    if combat_log is not None and not any(p.patch_type == ObservationPatchType.COMBAT_LOG for p in patches):
        patches.append(_combat_log_patch(combat_log))

    if not patches:
        return None

    return ObservationFrame(
        observation_cursor=0,
        frame_type=ObservationFrameType.EVENT,
        event_type=event.event_type.value,
        event_uuid=str(event.uuid),
        lineage_uuid=str(event.lineage_uuid),
        phase=event.phase.value,
        source_event_cursor=source_index + 1,
        source_combat_log_cursor=_combat_log_cursor(event.combat_log, encounter),
        patches=patches,
        combat_log=combat_log.model_dump(mode="json") if combat_log is not None else None,
    )


def _session_state(
    session: PlayerSession,
    game: Optional[GameSession],
) -> ObservationSessionState:
    """Build session state visible to the controller."""
    active_uuid = game.active_entity_uuid if game else None
    active_entity = Entity.get(active_uuid) if active_uuid else None
    active_known = active_uuid in session.controlled_entities if active_uuid else False
    if active_uuid and not active_known:
        active_known = _entity_visible_to_session(active_uuid, _controlled_observers(session))
    return ObservationSessionState(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name,
        connection_status=session.connection_status.value,
        controlled_entity_uuids=sorted(str(uuid) for uuid in session.controlled_entities),
        active_entity_uuid=str(active_uuid) if active_uuid and active_known else None,
        active_entity_name=active_entity.name if active_entity and active_known else None,
        is_my_turn=game.is_player_turn(session.session_id) if game else False,
    )


def _encounter_state(
    encounter: Encounter,
    session: PlayerSession,
    observers: List[Entity],
) -> ObservationEncounterState:
    """Build encounter state with unknown placeholders for unseen combatants."""
    rows: List[ObservationCombatantState] = []
    for combatant_uuid in encounter.initiative_order:
        entity = Entity.get(combatant_uuid)
        controlled = combatant_uuid in session.controlled_entities
        observer_uuids = _observers_that_see(combatant_uuid, observers)
        visible = bool(observer_uuids) or controlled
        combatant = encounter.combatants.get(combatant_uuid)
        if visible and entity is not None:
            rows.append(ObservationCombatantState(
                uuid=str(combatant_uuid),
                name=entity.name,
                initiative=combatant.initiative_total if combatant else None,
                is_dead=not entity.has_hp,
                is_controlled=controlled,
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=observer_uuids,
            ))
        else:
            rows.append(ObservationCombatantState(
                name="Unknown Combatant",
                is_controlled=False,
                knowledge_state=KnowledgeState.UNKNOWN,
            ))

    current_uuid = encounter.initiative_order[encounter.current_turn_index] if encounter.initiative_order else None
    current_entity = Entity.get(current_uuid) if current_uuid else None
    current_known = current_uuid in session.controlled_entities if current_uuid else False
    if current_uuid and not current_known:
        current_known = _entity_visible_to_session(current_uuid, observers)

    return ObservationEncounterState(
        uuid=str(encounter.uuid),
        name=encounter.name,
        state=encounter.state.value,
        round_number=encounter.round_number,
        current_turn_index=encounter.current_turn_index,
        current_entity_uuid=str(current_uuid) if current_uuid and current_known else None,
        current_entity_name=current_entity.name if current_entity and current_known else None,
        initiative_order=rows,
    )


def _controlled_observers(session: PlayerSession) -> List[Entity]:
    """Return controlled entities that can act as subjective observers."""
    observers: List[Entity] = []
    for entity_uuid in sorted(session.controlled_entities, key=str):
        entity = Entity.get(entity_uuid)
        if entity is not None:
            observers.append(entity)
    return observers


def _observer_state(observer: Entity) -> ObservationObserverState:
    """Serialize one controlled entity's senses cache."""
    visible_cells = sorted(
        [position for position, visible in observer.senses.visible.items() if visible],
        key=_position_sort_key,
    )
    seen_cells = sorted(observer.senses.seen, key=_position_sort_key)
    return ObservationObserverState(
        observer_uuid=str(observer.uuid),
        entity_name=observer.name,
        position=observer.position,
        passive_perception=observer.get_passive_perception(),
        sense_modes=[
            {"sense_type": mode.sense_type.value, "range_feet": mode.range_feet}
            for mode in observer.senses.get_sense_modes()
        ],
        visible_cells=visible_cells,
        seen_cells=seen_cells,
        visible_entity_uuids=sorted(str(uuid) for uuid in observer.senses.entities),
        visible_object_uuids=sorted(str(uuid) for uuid in observer.senses.objects),
    )


def _known_entity_facts(
    session: PlayerSession,
    observers: List[Entity],
) -> List[ObservationEntityFact]:
    """Build entity facts known to the session."""
    known_uuids: Set[UUID] = set(session.controlled_entities)
    for observer in observers:
        known_uuids.update(observer.senses.entities.keys())
    facts = [
        _entity_fact(entity_uuid, session, observers, KnowledgeState.VISIBLE)
        for entity_uuid in sorted(known_uuids, key=str)
        if Entity.get(entity_uuid) is not None
    ]
    return [fact for fact in facts if fact is not None]


def _entity_fact(
    entity_uuid: UUID,
    session: PlayerSession,
    observers: List[Entity],
    fallback_state: KnowledgeState = KnowledgeState.VISIBLE,
    remembered_position: Optional[Tuple[int, int]] = None,
) -> Optional[ObservationEntityFact]:
    """Create an entity fact when the entity is currently known."""
    entity = Entity.get(entity_uuid)
    if entity is None:
        return None
    controlled = entity_uuid in session.controlled_entities
    observer_uuids = _observers_that_see(entity_uuid, observers)
    visible = bool(observer_uuids) or controlled
    knowledge_state = KnowledgeState.VISIBLE if visible else fallback_state
    if not visible and knowledge_state == KnowledgeState.UNKNOWN:
        return None
    include_live_details = visible or knowledge_state == KnowledgeState.VISIBLE
    position = entity.position if include_live_details else remembered_position
    return ObservationEntityFact(
        uuid=str(entity.uuid),
        name=entity.name,
        knowledge_state=knowledge_state,
        observer_uuids=observer_uuids,
        controlled=controlled,
        position=position,
        hp=entity.get_hp() if include_live_details else None,
        max_hp=_max_hp(entity) if include_live_details else None,
        ac=entity.ac_bonus().normalized_score if include_live_details else None,
        conditions=list(entity.active_conditions.keys()) if include_live_details else [],
        faction=entity.faction if include_live_details else None,
        is_dead=not entity.has_hp if include_live_details else None,
    )


def _known_object_facts(observers: List[Entity]) -> List[ObservationObjectFact]:
    """Build object facts known to the session."""
    object_observers: Dict[UUID, Set[str]] = {}
    object_positions: Dict[UUID, Tuple[int, int]] = {}
    for observer in observers:
        for object_uuid, position in observer.senses.objects.items():
            object_observers.setdefault(object_uuid, set()).add(str(observer.uuid))
            object_positions[object_uuid] = position

    facts: List[ObservationObjectFact] = []
    for object_uuid in sorted(object_observers, key=str):
        fact = _object_fact(object_uuid, object_positions.get(object_uuid), object_observers[object_uuid])
        if fact is not None:
            facts.append(fact)
    return facts


def _object_fact(
    object_uuid: UUID,
    position: Optional[Tuple[int, int]],
    observer_uuids: Iterable[str],
) -> Optional[ObservationObjectFact]:
    """Create an object fact from current engine state."""
    obj = BaseBlock.get(object_uuid)
    if obj is None:
        return None
    return ObservationObjectFact(
        uuid=str(object_uuid),
        name=obj.name or "Object",
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=sorted(observer_uuids),
        position=position or obj.position,
        map_char=getattr(obj, "map_char", None),
        state=_object_state(obj),
    )


def _known_tile_facts(observers: List[Entity]) -> List[ObservationTileFact]:
    """Build tile facts visible or previously seen by controlled observers."""
    visible_by_pos: Dict[Tuple[int, int], Set[str]] = {}
    seen_by_pos: Dict[Tuple[int, int], Set[str]] = {}
    for observer in observers:
        observer_id = str(observer.uuid)
        for position, visible in observer.senses.visible.items():
            if visible:
                visible_by_pos.setdefault(position, set()).add(observer_id)
        for position in observer.senses.seen:
            seen_by_pos.setdefault(position, set()).add(observer_id)

    facts: List[ObservationTileFact] = []
    all_positions = set(visible_by_pos) | set(seen_by_pos)
    for position in sorted(all_positions, key=_position_sort_key):
        if position in visible_by_pos:
            facts.append(_visible_tile_fact(position, visible_by_pos[position]))
        else:
            facts.append(ObservationTileFact(
                key=_tile_key(position),
                position=position,
                knowledge_state=KnowledgeState.SEEN,
                observer_uuids=sorted(seen_by_pos[position]),
            ))
    return facts


def _visible_tile_fact(
    position: Tuple[int, int],
    observer_uuids: Iterable[str],
) -> ObservationTileFact:
    """Create a visible tile fact with current public tile data."""
    observer_ids = sorted(observer_uuids)
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        return ObservationTileFact(
            key=_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.VISIBLE,
            observer_uuids=observer_ids,
        )
    first_observer = observer_ids[0] if observer_ids else None
    return ObservationTileFact(
        key=_tile_key(position),
        position=position,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=observer_ids,
        name=tile.name,
        walkable=tile.walkable,
        walking_cost=int(tile.walking_cost.normalized_score) if hasattr(tile, "walking_cost") else 1,
        is_hazardous=grid.is_position_hazardous_for(position[0], position[1], UUID(first_observer) if first_observer else None),
        conditions=list(getattr(tile, "active_conditions", {}).keys()),
        light_level=tile.resolved_light_level.value,
        directional_blocks_movement=_directional_blocks(tile, "movement"),
        directional_blocks_vision=_directional_blocks(tile, "vision"),
        directional_blocks_light=_directional_blocks(tile, "light"),
        directional_blocks_propagation=_directional_blocks(tile, "propagation"),
    )


def _sensory_patches(
    event: SensoryUpdateEvent,
    session: PlayerSession,
    observers: List[Entity],
) -> List[ObservationPatch]:
    """Build observer and fact patches from a sensory update event."""
    data = {
        "observer_uuid": str(event.observer_uuid),
        "update_reason": event.update_reason.value,
        "visible_cells_added": [list(position) for position in event.visible_cells_added],
        "visible_cells_removed": [list(position) for position in event.visible_cells_removed],
        "seen_cells_added": [list(position) for position in event.seen_cells_added],
        "visible_entities_added": _uuid_position_json(event.visible_entities_added),
        "visible_entities_removed": _uuid_position_json(event.visible_entities_removed),
        "visible_entities_moved": _uuid_move_json(event.visible_entities_moved),
        "visible_objects_added": _uuid_position_json(event.visible_objects_added),
        "visible_objects_removed": _uuid_position_json(event.visible_objects_removed),
        "visible_objects_moved": _uuid_move_json(event.visible_objects_moved),
        "paths_dirty": event.paths_dirty,
        "passive_perception": event.passive_perception,
        "sense_modes": event.sense_modes,
    }
    patches = [
        ObservationPatch(
            patch_type=ObservationPatchType.OBSERVER,
            reason=event.update_reason.value,
            observer_uuid=str(event.observer_uuid),
            data=data,
        )
    ]

    for entity_uuid, position in event.visible_entities_added.items():
        fact = _entity_fact(entity_uuid, session, observers, KnowledgeState.VISIBLE, position)
        if fact is not None:
            patches.append(_entity_patch(fact, event.update_reason.value))
    for entity_uuid, positions in event.visible_entities_moved.items():
        fact = _entity_fact(entity_uuid, session, observers, remembered_position=positions[1])
        if fact is not None:
            patches.append(_entity_patch(fact, event.update_reason.value))
    for entity_uuid, position in event.visible_entities_removed.items():
        fact = _entity_fact(entity_uuid, session, observers, KnowledgeState.REMEMBERED, position)
        if fact is not None:
            patches.append(_entity_patch(fact, event.update_reason.value))

    for object_uuid, position in event.visible_objects_added.items():
        fact = _object_fact(object_uuid, position, [str(event.observer_uuid)])
        if fact is not None:
            patches.append(_object_patch(fact, event.update_reason.value))
    for object_uuid, position in event.visible_objects_removed.items():
        fact = _object_fact(object_uuid, position, [str(event.observer_uuid)])
        if fact is not None:
            remembered = fact.model_copy(update={"knowledge_state": KnowledgeState.REMEMBERED})
            patches.append(_object_patch(remembered, event.update_reason.value))

    for position in set(event.visible_cells_added) | set(event.seen_cells_added):
        patches.append(_tile_patch(_visible_tile_fact(position, [str(event.observer_uuid)]), event.update_reason.value))
    for position in event.visible_cells_removed:
        patches.append(_tile_patch(ObservationTileFact(
            key=_tile_key(position),
            position=position,
            knowledge_state=KnowledgeState.SEEN,
            observer_uuids=[str(event.observer_uuid)],
        ), event.update_reason.value))
    return patches


def _event_state_patches(
    event: Event,
    session: PlayerSession,
    game: Optional[GameSession],
    encounter: Optional[Encounter],
    observers: List[Entity],
) -> List[ObservationPatch]:
    """Build state patches from a visible completion event."""
    patches: List[ObservationPatch] = []
    if event.event_type in {
        EventType.ENCOUNTER_START,
        EventType.ENCOUNTER_END,
        EventType.ROUND_START,
        EventType.ROUND_END,
        EventType.TURN_START,
        EventType.TURN_END,
    }:
        patches.append(_session_patch(_session_state(session, game), event.event_type.value))
        if encounter is not None:
            patches.append(_encounter_patch(_encounter_state(encounter, session, observers), event.event_type.value))

    for entity_uuid in _entity_uuids_referenced_by(event):
        fact = _entity_fact(entity_uuid, session, observers)
        if fact is not None:
            patches.append(_entity_patch(fact, event.event_type.value))

    position = getattr(event, "position", None)
    if isinstance(position, tuple) and _position_visible_to_session(position, observers):
        patches.append(_tile_patch(_visible_tile_fact(position, _observers_that_see_position(position, observers)), event.event_type.value))

    object_uuid = getattr(event, "object_uuid", None)
    if object_uuid and position and _position_visible_to_session(position, observers):
        fact = _object_fact(object_uuid, position, _observers_that_see_position(position, observers))
        if fact is not None:
            patches.append(_object_patch(fact, event.event_type.value))

    return patches


def _event_visible_to_session(
    event: Event,
    session: PlayerSession,
    observers: List[Entity],
) -> bool:
    """Return whether a source event should produce any subjective frame."""
    if event.event_type in {
        EventType.ENCOUNTER_START,
        EventType.ENCOUNTER_END,
        EventType.ROUND_START,
        EventType.ROUND_END,
        EventType.TURN_START,
        EventType.TURN_END,
    }:
        return True
    if _filtered_combat_log(event.combat_log, session, observers) is not None:
        return True
    for entity_uuid in _entity_uuids_referenced_by(event):
        if entity_uuid in session.controlled_entities or _entity_visible_to_session(entity_uuid, observers):
            return True
    for position in event.get_affected_positions():
        if _position_visible_to_session(position, observers):
            return True
    return False


def _filtered_combat_log(
    log: Optional[CombatLogEntry],
    session: PlayerSession,
    observers: List[Entity],
) -> Optional[CombatLogEntry]:
    """Return a combat log filtered to this session, or None when hidden."""
    if log is None:
        return None
    known_entity_uuids = {str(uuid) for uuid in session.controlled_entities}
    for observer in observers:
        known_entity_uuids.update(str(uuid) for uuid in observer.senses.entities)

    controlled = {str(uuid) for uuid in session.controlled_entities}
    perceivers = set(log.perceiver_uuids)
    directly_involved = {value for value in (log.source_uuid, log.target_uuid) if value}
    visible = bool(perceivers & controlled) or bool(directly_involved & controlled)
    if not perceivers:
        visible = visible or bool(directly_involved & known_entity_uuids)

    filtered_children = [
        child for child in (
            _filtered_combat_log(child, session, observers)
            for child in log.sub_entries
        )
        if child is not None
    ]
    if not visible and not filtered_children:
        return None
    return log.model_copy(update={"sub_entries": filtered_children})


def _entity_uuids_referenced_by(event: Event) -> Set[UUID]:
    """Collect entity UUIDs directly referenced by an event."""
    values: Set[UUID] = set()
    for attr in ("source_entity_uuid", "target_entity_uuid", "entity_uuid", "killer_uuid"):
        value = getattr(event, attr, None)
        if isinstance(value, UUID):
            values.add(value)
    return values


def _entity_visible_to_session(entity_uuid: UUID, observers: List[Entity]) -> bool:
    """Return whether any controlled observer currently sees an entity."""
    return any(entity_uuid in observer.senses.entities for observer in observers)


def _position_visible_to_session(position: Tuple[int, int], observers: List[Entity]) -> bool:
    """Return whether any controlled observer currently sees a position."""
    return any(observer.senses.visible.get(position, False) for observer in observers)


def _observers_that_see(entity_uuid: UUID, observers: List[Entity]) -> List[str]:
    """Return controlled observer UUIDs that currently see an entity."""
    return sorted(str(observer.uuid) for observer in observers if entity_uuid in observer.senses.entities or entity_uuid == observer.uuid)


def _observers_that_see_position(position: Tuple[int, int], observers: List[Entity]) -> List[str]:
    """Return controlled observer UUIDs that currently see a position."""
    return sorted(str(observer.uuid) for observer in observers if observer.senses.visible.get(position, False))


def _entity_patch(fact: ObservationEntityFact, reason: str) -> ObservationPatch:
    """Create an entity patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.ENTITY,
        reason=reason,
        entity_uuid=fact.uuid,
        data={"entity": fact.model_dump(mode="json")},
    )


def _object_patch(fact: ObservationObjectFact, reason: str) -> ObservationPatch:
    """Create an object patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.OBJECT,
        reason=reason,
        object_uuid=fact.uuid,
        data={"object": fact.model_dump(mode="json")},
    )


def _tile_patch(fact: ObservationTileFact, reason: str) -> ObservationPatch:
    """Create a tile patch from a fact."""
    return ObservationPatch(
        patch_type=ObservationPatchType.TILE,
        reason=reason,
        tile_key=fact.key,
        data={"tile": fact.model_dump(mode="json")},
    )


def _session_patch(state: ObservationSessionState, reason: str) -> ObservationPatch:
    """Create a session patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.SESSION,
        reason=reason,
        data={"session": state.model_dump(mode="json")},
    )


def _encounter_patch(state: ObservationEncounterState, reason: str) -> ObservationPatch:
    """Create an encounter patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.ENCOUNTER,
        reason=reason,
        data={"encounter": state.model_dump(mode="json")},
    )


def _combat_log_patch(log: CombatLogEntry) -> ObservationPatch:
    """Create a visible combat-log patch."""
    return ObservationPatch(
        patch_type=ObservationPatchType.COMBAT_LOG,
        reason="combat_log",
        data={"combat_log": log.model_dump(mode="json")},
    )


def _combat_log_cursor(
    log: Optional[CombatLogEntry],
    encounter: Optional[Encounter],
) -> Optional[int]:
    """Return the combat-log cursor for a visible log when known."""
    if log is None or encounter is None:
        return None
    for index, entry in enumerate(encounter.combat_log):
        if entry is log or entry == log:
            return index + 1
    return len(encounter.combat_log)


def _max_hp(entity: Entity) -> int:
    """Return current maximum hit points for an entity."""
    con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
    base_max = entity.health.get_max_hit_dices_points(constitution_modifier=con_mod)
    return base_max + entity.health.max_hit_points_bonus.normalized_score


def _object_state(obj: BaseBlock) -> Dict[str, Any]:
    """Return stable public object state fields when present."""
    state: Dict[str, Any] = {}
    for field_name in (
        "is_open",
        "blocked_directions",
        "blocked_channels",
        "blocks_movement",
        "blocks_vision",
        "blocks_vision_field",
        "is_pickable",
        "is_usable",
        "charges",
        "stack_count",
    ):
        if hasattr(obj, field_name):
            value = getattr(obj, field_name)
            if value is not None:
                safe_value = _json_safe_state_value(value)
                if safe_value is not None:
                    state[field_name] = safe_value
    return state


def _json_safe_state_value(value: Any) -> Any:
    """Return a JSON-safe public state value or None when unsupported."""
    if callable(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        ]
    if isinstance(value, list):
        return [
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        ]
    if isinstance(value, set):
        return sorted(
            safe_item for item in value
            if (safe_item := _json_safe_state_value(item)) is not None
        )
    if isinstance(value, dict):
        return {
            str(key): safe_value
            for key, item in value.items()
            if (safe_value := _json_safe_state_value(item)) is not None
        }
    return None


def _directional_blocks(tile: Any, channel: str) -> Dict[str, bool]:
    """Return visible directional blockers for a tile and movement channel."""
    return {
        direction: not tile.allows_direction(direction, channel)
        for direction in ("north", "south", "east", "west")
    }


def _uuid_position_json(values: Dict[UUID, Tuple[int, int]]) -> Dict[str, List[int]]:
    """Serialize UUID-position mappings to JSON-safe dictionaries."""
    return {str(uuid): [position[0], position[1]] for uuid, position in values.items()}


def _uuid_move_json(values: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]]) -> Dict[str, List[List[int]]]:
    """Serialize UUID movement mappings to JSON-safe dictionaries."""
    return {
        str(uuid): [[old[0], old[1]], [new[0], new[1]]]
        for uuid, (old, new) in values.items()
    }


def _tile_key(position: Tuple[int, int]) -> str:
    """Return a stable string key for a grid position."""
    return f"{position[0]},{position[1]}"


def _position_sort_key(position: Tuple[int, int]) -> Tuple[int, int]:
    """Sort grid positions by x and y."""
    return position
