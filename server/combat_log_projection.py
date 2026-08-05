"""Project objective combat logs into one participant's known perspective.

This module owns only combat-log visibility and sanitization. Callers resolve
ownership and authorized event-time observers before constructing a context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    damage_total_from_log_data,
    position_evidence_key,
)


SUBJECTIVE_COMBAT_LOG_ENTRY_TYPES = frozenset({
    CombatLogEntryType.ATTACK,
    CombatLogEntryType.MOVEMENT,
    CombatLogEntryType.ACTION,
    CombatLogEntryType.SAVING_THROW,
    CombatLogEntryType.DEATH_SAVE,
    CombatLogEntryType.ABILITY_CHECK,
    CombatLogEntryType.SKILL_CHECK,
    CombatLogEntryType.CONDITION_APPLIED,
    CombatLogEntryType.CONDITION_REMOVED,
    CombatLogEntryType.DAMAGE_TAKEN,
    CombatLogEntryType.HEAL,
    CombatLogEntryType.TEMPORARY_HIT_POINTS,
    CombatLogEntryType.DEATH,
    CombatLogEntryType.TURN_START,
    CombatLogEntryType.TURN_END,
    CombatLogEntryType.MULTI_ENTITY_ACTION,
    CombatLogEntryType.SPELL_SAVE,
    CombatLogEntryType.SPELL_DAMAGE,
    CombatLogEntryType.SPELL_INTERRUPTION,
    CombatLogEntryType.ENTITY_SPOTTED,
    CombatLogEntryType.HAZARD_DETECTED,
    CombatLogEntryType.ROLL_MODIFICATION,
    CombatLogEntryType.SPATIAL_EFFECT,
})
"""Entry types whose subjective projection policy has been reviewed."""


@dataclass
class CombatLogProjectionContext:
    """Reusable ownership and observer authority for one projection pass."""

    controlled_entity_uuids: FrozenSet[str]
    observer_entity_uuids: FrozenSet[str]
    _filtered_cache: Dict[int, Optional[CombatLogEntry]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )


def make_combat_log_projection_context(
    *,
    controlled_entity_uuids: Iterable[str],
    observer_entity_uuids: Optional[Iterable[str]] = None,
) -> CombatLogProjectionContext:
    """Create a context from authoritative ownership and observer scope."""
    controlled = frozenset(controlled_entity_uuids)
    return CombatLogProjectionContext(
        controlled_entity_uuids=controlled,
        observer_entity_uuids=(
            controlled
            if observer_entity_uuids is None
            else frozenset(observer_entity_uuids)
        ),
    )


def project_combat_log(
    log: Optional[CombatLogEntry],
    context: CombatLogProjectionContext,
) -> Optional[CombatLogEntry]:
    """Return a participant-subjective log tree, or ``None`` when fully hidden."""
    if log is None:
        return None
    return _project_combat_log_with_context(log, context)


def _project_combat_log_with_context(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
) -> Optional[CombatLogEntry]:
    """Project one combat-log tree using reusable participant knowledge."""
    cache_key = id(log)
    if cache_key in context._filtered_cache:
        return context._filtered_cache[cache_key]
    if log.entry_type not in SUBJECTIVE_COMBAT_LOG_ENTRY_TYPES:
        context._filtered_cache[cache_key] = None
        return None

    directly_involved = {value for value in (log.source_uuid, log.target_uuid) if value}
    visible = _has_authorized_event_time_observation(log, context) or bool(
        directly_involved & context.controlled_entity_uuids
    )

    filtered_children: List[CombatLogEntry] = []
    for child in log.sub_entries:
        filtered_child = _project_combat_log_with_context(child, context)
        if filtered_child is None:
            continue
        filtered_children.append(filtered_child)

    if not visible and not filtered_children:
        context._filtered_cache[cache_key] = None
        return None

    hidden_uuids, hidden_names = _collect_unknown_log_identities(log, context)
    sanitized_log = _sanitize_unseen_log_identity(
        log,
        context,
        hidden_uuids=hidden_uuids,
        hidden_names=hidden_names,
    )
    sanitized_log = _sanitize_unlocated_movement_step(sanitized_log, context)
    sanitized_log = _sanitize_partially_observed_movement(
        log,
        sanitized_log,
        filtered_children,
        context,
    )
    sanitized_log = _sanitize_multi_entity_log_projection(
        sanitized_log,
        filtered_children,
    )
    filtered_log = sanitized_log.model_copy(update={
        "sub_entries": filtered_children,
        "perceiver_uuids": set(),
        "revealed_entity_uuids": set(),
        "identified_entity_observer_uuids": {},
        "located_entity_observer_uuids": {},
        "located_position_observer_uuids": {},
    })
    context._filtered_cache[cache_key] = filtered_log
    return filtered_log


def _has_authorized_event_time_observation(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
) -> bool:
    """Return whether event-time evidence names an authorized observer."""
    authorized = context.observer_entity_uuids
    if log.perceiver_uuids & authorized:
        return True
    for observer_uuids in log.identified_entity_observer_uuids.values():
        if observer_uuids & authorized:
            return True
    for observer_uuids in log.located_entity_observer_uuids.values():
        if observer_uuids & authorized:
            return True
    for observer_uuids in log.located_position_observer_uuids.values():
        if observer_uuids & authorized:
            return True
    return False


def _identified_entities_for_participant(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
) -> Set[str]:
    """Return participants identified by a controlled observer at event time."""
    return {
        entity_uuid
        for entity_uuid, observer_uuids in log.identified_entity_observer_uuids.items()
        if observer_uuids & context.observer_entity_uuids
    }


def _sanitize_unseen_log_identity(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
    *,
    hidden_uuids: Optional[Set[str]] = None,
    hidden_names: Optional[Set[str]] = None,
) -> CombatLogEntry:
    """Remove identity and path facts for entities unknown to the participant."""
    identified_or_controlled = (
        context.controlled_entity_uuids
        | _identified_entities_for_participant(log, context)
    )
    source_unknown = bool(
        log.source_uuid and log.source_uuid not in identified_or_controlled
    )
    target_unknown = bool(
        log.target_uuid and log.target_uuid not in identified_or_controlled
    )
    hidden_uuids = set(hidden_uuids or set())
    hidden_names = set(hidden_names or set())
    if not source_unknown and not target_unknown and not hidden_uuids and not hidden_names:
        return log

    updates: Dict[str, Any] = {}
    hidden_uuids.update(
        uuid
        for uuid, hidden in (
            (log.source_uuid, source_unknown),
            (log.target_uuid, target_unknown),
        )
        if uuid and hidden
    )
    hidden_names.update(
        name
        for name, hidden in (
            (log.source_name, source_unknown),
            (log.target_name, target_unknown),
        )
        if name and hidden
    )
    data = _sanitize_unseen_log_data(log.data, hidden_uuids, hidden_names)
    updates["data"] = data
    updates["compact"] = _sanitize_unseen_log_text(log.compact, hidden_uuids, hidden_names)
    updates["verbose"] = _sanitize_unseen_log_text(log.verbose, hidden_uuids, hidden_names)
    updates["detailed"] = _sanitize_unseen_log_text(log.detailed, hidden_uuids, hidden_names)
    if source_unknown:
        updates.update({
            "source_name": "Unknown",
            "source_uuid": "",
        })
    if target_unknown:
        updates.update({
            "target_name": "Unknown",
            "target_uuid": "",
        })

    if log.entry_type is CombatLogEntryType.MOVEMENT and source_unknown:
        updates.update({
            "compact": "Something moves nearby",
            "verbose": "Something moves nearby",
            "detailed": "Something moves nearby",
            "data": {"type": "movement", "observed": True},
        })
    elif log.entry_type is CombatLogEntryType.TURN_START and source_unknown:
        updates.update({
            "compact": "An unknown combatant's turn begins",
            "verbose": "An unknown combatant's turn begins",
            "detailed": "An unknown combatant's turn begins",
        })
    elif log.entry_type is CombatLogEntryType.TURN_END and source_unknown:
        updates.update({
            "compact": "An unknown combatant's turn ends",
            "verbose": "An unknown combatant's turn ends",
            "detailed": "An unknown combatant's turn ends",
        })

    return log.model_copy(update=updates)


def _sanitize_unlocated_movement_step(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
) -> CombatLogEntry:
    """Keep a non-owned step only when one observer saw both endpoints."""
    if (
        log.entry_type is not CombatLogEntryType.MOVEMENT
        or log.data.get("type") != "step_movement"
        or not log.source_uuid
    ):
        return log
    if log.source_uuid in context.controlled_entity_uuids:
        return log
    from_position = log.data.get("from_position")
    to_position = log.data.get("to_position")
    if (
        isinstance(from_position, (tuple, list))
        and len(from_position) == 2
        and all(isinstance(value, int) for value in from_position)
        and isinstance(to_position, (tuple, list))
        and len(to_position) == 2
        and all(isinstance(value, int) for value in to_position)
    ):
        origin = log.located_position_observer_uuids.get(
            position_evidence_key((from_position[0], from_position[1])),
            set(),
        )
        destination = log.located_position_observer_uuids.get(
            position_evidence_key((to_position[0], to_position[1])),
            set(),
        )
        if origin & destination & set(context.observer_entity_uuids):
            return log
    source_name = log.source_name or "Known entity"
    text = f"{{cyan:{source_name}}} moves outside current perception"
    return log.model_copy(update={
        "compact": text,
        "verbose": text,
        "detailed": text,
        "data": {
            "type": "movement",
            "observation_complete": False,
        },
    })


def _sanitize_partially_observed_movement(
    original_log: CombatLogEntry,
    sanitized_log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
    context: CombatLogProjectionContext,
) -> CombatLogEntry:
    """Derive non-owned Move geometry only from authorized committed Steps."""
    if (
        original_log.entry_type is not CombatLogEntryType.MOVEMENT
        or original_log.source_uuid in context.controlled_entity_uuids
        or original_log.data.get("type") in {
            "step_movement",
            "forced_movement",
        }
        or not sanitized_log.source_uuid
    ):
        return sanitized_log
    if (
        original_log.data.get("requested_end_position") is None
        and original_log.data.get("objective_end_position") is None
        and _direct_arc_root_is_fully_authorized(
            original_log,
            filtered_children,
        )
    ):
        return sanitized_log

    original_steps = [
        child
        for child in original_log.sub_entries
        if _is_committed_path_step_log(child)
    ]
    filtered_steps = [
        child
        for child in filtered_children
        if _is_committed_path_step_log(child)
    ]

    ordered_steps = sorted(
        filtered_steps,
        key=lambda child: int(child.data.get("path_index", 0)),
    )
    segments: List[List[Tuple[int, int]]] = []
    observed_distance = 0.0
    observed_cost = 0.0
    for step in ordered_steps:
        origin = _combat_log_position(step.data.get("from_position"))
        destination = _combat_log_position(step.data.get("to_position"))
        if origin is None or destination is None:
            continue
        observed_distance += 5.0
        observed_cost += float(step.data.get("movement_cost", 0.0))
        if segments and segments[-1][-1] == origin:
            segments[-1].append(destination)
        else:
            segments.append([origin, destination])

    identity_data = {
        key: value
        for key, value in sanitized_log.data.items()
        if key in {"entity_name", "entity_uuid", "movement_type"}
    }
    data: Dict[str, Any] = {
        **identity_data,
        "type": "movement",
        "observation_complete": (
            bool(original_steps)
            and len(filtered_steps) == len(original_steps)
        ),
        "observed_path_segments": segments,
        "observed_distance_feet": observed_distance,
    }
    if len(segments) == 1:
        data.update({
            "start_position": segments[0][0],
            "end_position": segments[0][-1],
            "path": segments[0],
            "distance_feet": observed_distance,
            "movement_cost": observed_cost,
        })

    source_name = sanitized_log.source_name or "Known entity"
    if len(segments) == 1:
        destination = segments[0][-1]
        compact = (
            f"{{cyan:{source_name}}} is observed moving "
            f"{{green:{observed_distance:g}ft}} to {{yellow:{destination}}}"
        )
        verbose = f"{compact} (partial movement observation)"
        path_text = " -> ".join(str(position) for position in segments[0])
        detailed = f"{verbose}\n  Observed path: {path_text}"
    elif segments:
        compact = (
            f"{{cyan:{source_name}}} is observed moving across "
            f"{len(segments)} visible segments"
        )
        verbose = f"{compact} (partial movement observation)"
        segment_text = "; ".join(
            " -> ".join(str(position) for position in segment)
            for segment in segments
        )
        detailed = f"{verbose}\n  Observed segments: {segment_text}"
    else:
        compact = f"{{cyan:{source_name}}} moves outside current perception"
        verbose = compact
        detailed = compact

    return sanitized_log.model_copy(update={
        "compact": compact,
        "verbose": verbose,
        "detailed": detailed,
        "data": data,
    })


def _is_committed_path_step_log(log: CombatLogEntry) -> bool:
    """Classify current and legacy successful voluntary Step evidence."""
    if (
        log.entry_type is not CombatLogEntryType.MOVEMENT
        or log.data.get("type") != "step_movement"
    ):
        return False
    trajectory = log.data.get("trajectory")
    committed = log.data.get("committed")
    if trajectory is None and committed is None:
        return log.success is not False
    return trajectory == "path" and committed is True


def _direct_arc_step_signature(
    log: CombatLogEntry,
    root_source_uuid: str,
) -> Optional[Tuple[int, Tuple[int, int], Tuple[int, int], float]]:
    """Return exact Jump geometry only for a committed Step by the root mover."""
    path_index = log.data.get("path_index")
    movement_cost = log.data.get("movement_cost")
    from_position = _combat_log_position(log.data.get("from_position"))
    to_position = _combat_log_position(log.data.get("to_position"))
    if (
        log.entry_type is not CombatLogEntryType.MOVEMENT
        or log.data.get("type") != "step_movement"
        or log.source_uuid != root_source_uuid
        or log.data.get("trajectory") != "direct_arc"
        or log.data.get("committed") is not True
        or not isinstance(path_index, int)
        or isinstance(path_index, bool)
        or path_index < 1
        or not isinstance(movement_cost, (int, float))
        or isinstance(movement_cost, bool)
        or not isfinite(float(movement_cost))
        or movement_cost < 0
        or from_position is None
        or to_position is None
    ):
        return None
    return path_index, from_position, to_position, float(movement_cost)


def _direct_arc_root_is_fully_authorized(
    original_log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
) -> bool:
    """Preserve Jump geometry only when authorized Steps reconstruct the root."""
    original_steps = [
        child
        for child in original_log.sub_entries
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    if not original_steps:
        return False
    original_signatures: List[
        Tuple[int, Tuple[int, int], Tuple[int, int], float]
    ] = []
    for child in original_steps:
        signature = _direct_arc_step_signature(
            child,
            original_log.source_uuid,
        )
        if signature is None:
            return False
        original_signatures.append(signature)

    authorized_steps = [
        child
        for child in filtered_children
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    authorized_signatures: List[
        Tuple[int, Tuple[int, int], Tuple[int, int], float]
    ] = []
    for child in authorized_steps:
        signature = _direct_arc_step_signature(
            child,
            original_log.source_uuid,
        )
        if signature is None:
            return False
        authorized_signatures.append(signature)

    ordered = sorted(original_signatures)
    if sorted(authorized_signatures) != ordered or [
        signature[0] for signature in ordered
    ] != list(range(1, len(ordered) + 1)):
        return False

    arc_path = [ordered[0][1], *(signature[2] for signature in ordered)]
    if any(
        ordered[index - 1][2] != ordered[index][1]
        for index in range(1, len(ordered))
    ):
        return False

    root_path_value = original_log.data.get("path")
    if not isinstance(root_path_value, (list, tuple)):
        return False
    root_path = [_combat_log_position(position) for position in root_path_value]
    root_start = _combat_log_position(original_log.data.get("start_position"))
    root_end = _combat_log_position(original_log.data.get("end_position"))
    distance_feet = original_log.data.get("distance_feet")
    movement_cost = original_log.data.get("movement_cost")
    return (
        all(position is not None for position in root_path)
        and root_path == arc_path
        and root_start == arc_path[0]
        and root_end == arc_path[-1]
        and isinstance(distance_feet, int)
        and not isinstance(distance_feet, bool)
        and distance_feet == len(ordered) * 5
        and isinstance(movement_cost, int)
        and not isinstance(movement_cost, bool)
        and movement_cost == sum(signature[3] for signature in ordered)
    )


def _combat_log_position(value: Any) -> Optional[Tuple[int, int]]:
    """Normalize a structured combat-log position without accepting other shapes."""
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(
            isinstance(coordinate, int) and not isinstance(coordinate, bool)
            for coordinate in value
        )
    ):
        return int(value[0]), int(value[1])
    return None


def _sanitize_unseen_log_data(
    data: Dict[str, Any],
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> Dict[str, Any]:
    """Remove hidden identity values from structured combat-log data."""
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        sanitized_key = _sanitize_unseen_log_key(str(key), hidden_uuids, hidden_names)
        if sanitized_key is None:
            continue
        sanitized_value = _sanitize_unseen_log_value(
            value,
            hidden_uuids,
            hidden_names,
        )
        if sanitized_value is _DROP_HIDDEN_VALUE:
            continue
        sanitized[sanitized_key] = sanitized_value
    return sanitized


_DROP_HIDDEN_VALUE = object()


def _sanitize_unseen_log_value(
    value: Any,
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> Any:
    """Sanitize a structured combat-log value recursively."""
    if isinstance(value, str):
        if value in hidden_uuids:
            return _DROP_HIDDEN_VALUE
        return _sanitize_unseen_log_text(value, hidden_uuids, hidden_names)
    if isinstance(value, dict):
        sanitized_dict: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            sanitized_key = _sanitize_unseen_log_key(
                str(child_key),
                hidden_uuids,
                hidden_names,
            )
            if sanitized_key is None:
                continue
            sanitized_value = _sanitize_unseen_log_value(
                child_value,
                hidden_uuids,
                hidden_names,
            )
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_dict[sanitized_key] = sanitized_value
        return sanitized_dict
    if isinstance(value, list):
        sanitized_list: List[Any] = []
        for item in value:
            sanitized_value = _sanitize_unseen_log_value(
                item,
                hidden_uuids,
                hidden_names,
            )
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_list.append(sanitized_value)
        return sanitized_list
    if isinstance(value, tuple):
        sanitized_items: List[Any] = []
        for item in value:
            sanitized_value = _sanitize_unseen_log_value(
                item,
                hidden_uuids,
                hidden_names,
            )
            if sanitized_value is not _DROP_HIDDEN_VALUE:
                sanitized_items.append(sanitized_value)
        return tuple(sanitized_items)
    return value


def _sanitize_unseen_log_key(
    key: str,
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> Optional[str]:
    """Drop a structured field whose key itself discloses hidden identity."""
    if any(hidden_uuid in key for hidden_uuid in hidden_uuids):
        return None
    if any(hidden_name in key for hidden_name in hidden_names):
        return None
    return key


def _sanitize_unseen_log_text(
    text: str,
    hidden_uuids: Set[str],
    hidden_names: Set[str],
) -> str:
    """Replace hidden identity tokens in a subjective combat-log string."""
    sanitized = text
    for hidden_uuid in hidden_uuids:
        sanitized = sanitized.replace(hidden_uuid, "")
    for hidden_name in hidden_names:
        sanitized = sanitized.replace(hidden_name, "Unknown")
    return sanitized


def _collect_unknown_log_identities(
    log: CombatLogEntry,
    context: CombatLogProjectionContext,
) -> Tuple[Set[str], Set[str]]:
    """Collect unknown source and target identities from a log tree."""
    identified_or_controlled = (
        context.controlled_entity_uuids
        | _identified_entities_for_participant(log, context)
    )
    hidden_uuids: Set[str] = set()
    hidden_names: Set[str] = set()
    for uuid_value, name_value in (
        (log.source_uuid, log.source_name),
        (log.target_uuid, log.target_name),
    ):
        if uuid_value and uuid_value not in identified_or_controlled:
            hidden_uuids.add(uuid_value)
            if name_value:
                hidden_names.add(name_value)
    hidden_uuids.update(
        uuid for uuid in log.perceiver_uuids if uuid not in identified_or_controlled
    )
    for child in log.sub_entries:
        child_uuids, child_names = _collect_unknown_log_identities(
            child,
            context,
        )
        hidden_uuids.update(child_uuids)
        hidden_names.update(child_names)
    return hidden_uuids, hidden_names


def _sanitize_multi_entity_log_projection(
    log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
) -> CombatLogEntry:
    """Rebuild a multi-target summary and prose from projected children only."""
    if log.entry_type is not CombatLogEntryType.MULTI_ENTITY_ACTION:
        return log

    data = _sanitize_multi_entity_log_summary(
        log,
        filtered_children,
        dict(log.data),
    )
    source_name = log.source_name or "Unknown"
    action_name_value = data.get("action_name")
    action_name = (
        action_name_value
        if isinstance(action_name_value, str) and action_name_value
        else "an action"
    )
    target_count = len(filtered_children)
    target_word = "target" if target_count == 1 else "targets"
    compact = (
        f"{{cyan:{source_name}}} uses {{green:{action_name}}} → "
        f"{{yellow:{target_count} observed {target_word}}}"
    )
    total_damage = data.get("total_damage")
    if isinstance(total_damage, int) and not isinstance(total_damage, bool):
        compact += f", {{red:{total_damage} observed damage}}"

    return log.model_copy(update={
        "compact": compact,
        "verbose": compact,
        "detailed": compact,
        "data": data,
    })


def _sanitize_multi_entity_log_summary(
    log: CombatLogEntry,
    filtered_children: List[CombatLogEntry],
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Rebuild multi-target summary data from visible child logs only."""
    if log.entry_type is not CombatLogEntryType.MULTI_ENTITY_ACTION:
        return data

    sanitized = {
        key: data[key]
        for key in ("action_name", "caster_name", "aoe_shape")
        if key in data
    }

    target_names = _visible_target_names(filtered_children)
    per_target_logs: List[Optional[Dict[str, Any]]] = []
    per_target_damage: List[int] = []
    saves_succeeded = 0
    saves_failed = 0
    for child in filtered_children:
        child_data = dict(child.data)
        per_target_logs.append(child_data if child_data else None)
        damage = damage_total_from_log_data(child_data)
        if damage is not None:
            per_target_damage.append(damage)
        if child.entry_type is CombatLogEntryType.SPELL_SAVE:
            if bool(child_data.get("save_success")):
                saves_succeeded += 1
            else:
                saves_failed += 1

    sanitized["total_targets"] = len(filtered_children)
    if target_names:
        sanitized["target_names"] = target_names
    if per_target_damage:
        sanitized["per_target_damage"] = per_target_damage
        sanitized["total_damage"] = sum(per_target_damage)
    if per_target_logs:
        sanitized["per_target_logs"] = per_target_logs
    sanitized["saves_succeeded"] = saves_succeeded
    sanitized["saves_failed"] = saves_failed
    return sanitized


def _visible_target_names(logs: List[CombatLogEntry]) -> List[str]:
    """Return visible target names from direct projected action children."""
    names: List[str] = []
    seen: Set[str] = set()
    for log in logs:
        name = log.target_name
        if not name or name == "Unknown" or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names
