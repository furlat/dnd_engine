"""Pure event-time projection of combat logs for one observer scope."""

from __future__ import annotations

import re
from math import isfinite
from typing import Any, Optional

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    position_evidence_key,
)
from dnd.core.elevation import support_distance_feet


def project_combat_log(
    log: CombatLogEntry | None,
    *,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
) -> CombatLogEntry | None:
    """Return one same-model subjective log tree without reading live state."""
    if log is None:
        return None
    memo: dict[int, CombatLogEntry | None] = {}
    return _project_combat_log(
        log,
        controlled_entity_uuids,
        observer_entity_uuids,
        memo,
    )


def _project_combat_log(
    log: CombatLogEntry,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
    memo: dict[int, CombatLogEntry | None],
) -> CombatLogEntry | None:
    cache_key = id(log)
    if cache_key in memo:
        return memo[cache_key]

    participants = {
        entity_uuid
        for entity_uuid in (log.source_uuid, log.target_uuid)
        if entity_uuid
    }
    visible = bool(participants & controlled_entity_uuids) or (
        _has_authorized_event_time_observation(
            log,
            observer_entity_uuids,
        )
    )
    projected_children = [
        projected
        for child in log.sub_entries
        if (
            projected := _project_combat_log(
                child,
                controlled_entity_uuids,
                observer_entity_uuids,
                memo,
            )
        )
        is not None
    ]
    if not visible and not projected_children:
        memo[cache_key] = None
        return None

    hidden_uuids, hidden_names, hidden_positions = _collect_hidden_facts(
        log,
        controlled_entity_uuids,
        observer_entity_uuids,
    )
    projected = _sanitize_log(
        log,
        controlled_entity_uuids,
        observer_entity_uuids,
        hidden_uuids,
        hidden_names,
        hidden_positions,
    )
    projected = _sanitize_unlocated_movement_step(
        projected,
        controlled_entity_uuids,
        observer_entity_uuids,
    )
    projected = _rebuild_noncontrolled_movement(
        log,
        projected,
        projected_children,
        controlled_entity_uuids,
    )
    projected = _rebuild_multi_entity_summary(
        projected,
        projected_children,
    )
    projected = projected.model_copy(update={
        "sub_entries": projected_children,
        "perceiver_uuids": set(),
        "revealed_entity_uuids": set(),
        "identified_entity_observer_uuids": {},
        "located_entity_observer_uuids": {},
        "located_position_observer_uuids": {},
    })
    memo[cache_key] = projected
    return projected


def _has_authorized_event_time_observation(
    log: CombatLogEntry,
    observer_entity_uuids: frozenset[str],
) -> bool:
    if log.perceiver_uuids & observer_entity_uuids:
        return True
    return any(
        observers & observer_entity_uuids
        for evidence in (
            log.identified_entity_observer_uuids,
            log.located_entity_observer_uuids,
            log.located_position_observer_uuids,
        )
        for observers in evidence.values()
    )


def _identified_entities(
    log: CombatLogEntry,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
) -> set[str]:
    return set(controlled_entity_uuids) | {
        entity_uuid
        for entity_uuid, observers in (
            log.identified_entity_observer_uuids.items()
        )
        if observers & observer_entity_uuids
    }


def _collect_hidden_facts(
    log: CombatLogEntry,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
) -> tuple[set[str], set[str], set[tuple[int, int]]]:
    known_entities = _identified_entities(
        log,
        controlled_entity_uuids,
        observer_entity_uuids,
    )
    hidden_uuids = {
        entity_uuid
        for entity_uuid in (
            log.source_uuid,
            log.target_uuid,
            *log.perceiver_uuids,
            *log.revealed_entity_uuids,
            *log.identified_entity_observer_uuids,
            *log.located_entity_observer_uuids,
        )
        if entity_uuid and entity_uuid not in known_entities
    }
    hidden_names = {
        name
        for entity_uuid, name in (
            (log.source_uuid, log.source_name),
            (log.target_uuid, log.target_name),
        )
        if entity_uuid in hidden_uuids and name
    }
    authorized_positions = {
        position
        for key, observers in log.located_position_observer_uuids.items()
        if observers & observer_entity_uuids
        if (position := _position_from_evidence_key(key)) is not None
    }
    candidate_positions = _collect_candidate_positions(log.data)
    for text in (log.compact, log.verbose, log.detailed):
        candidate_positions.update(_positions_in_text(text))
    hidden_positions = candidate_positions - authorized_positions
    for child in log.sub_entries:
        child_uuids, child_names, _ = _collect_hidden_facts(
            child,
            controlled_entity_uuids,
            observer_entity_uuids,
        )
        hidden_uuids.update(child_uuids)
        hidden_names.update(child_names)
    return hidden_uuids, hidden_names, hidden_positions


def _sanitize_log(
    log: CombatLogEntry,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
    hidden_uuids: set[str],
    hidden_names: set[str],
    hidden_positions: set[tuple[int, int]],
) -> CombatLogEntry:
    known_entities = _identified_entities(
        log,
        controlled_entity_uuids,
        observer_entity_uuids,
    )
    source_unknown = bool(
        log.source_uuid and log.source_uuid not in known_entities
    )
    target_unknown = bool(
        log.target_uuid and log.target_uuid not in known_entities
    )
    positions_to_hide = hidden_positions
    if (
        log.entry_type is CombatLogEntryType.MOVEMENT
        and log.source_uuid in controlled_entity_uuids
    ):
        positions_to_hide = hidden_positions - _owned_movement_positions(log)
    updates: dict[str, Any] = {
        "data": _sanitize_data(
            log.data,
            hidden_uuids,
            hidden_names,
            positions_to_hide,
        ),
        "compact": _sanitize_text(
            log.compact,
            hidden_uuids,
            hidden_names,
            positions_to_hide,
        ),
        "verbose": _sanitize_text(
            log.verbose,
            hidden_uuids,
            hidden_names,
            positions_to_hide,
        ),
        "detailed": _sanitize_text(
            log.detailed,
            hidden_uuids,
            hidden_names,
            positions_to_hide,
        ),
    }
    if source_unknown:
        updates.update(source_name="Unknown", source_uuid="")
    if target_unknown:
        updates.update(target_name="Unknown", target_uuid="")

    if log.entry_type is CombatLogEntryType.MOVEMENT and source_unknown:
        updates.update(
            compact="Something moves nearby",
            verbose="Something moves nearby",
            detailed="Something moves nearby",
            data={"type": "movement", "observed": True},
        )
    elif log.entry_type is CombatLogEntryType.TURN_START and source_unknown:
        updates.update(
            compact="An unknown combatant's turn begins",
            verbose="An unknown combatant's turn begins",
            detailed="An unknown combatant's turn begins",
        )
    elif log.entry_type is CombatLogEntryType.TURN_END and source_unknown:
        updates.update(
            compact="An unknown combatant's turn ends",
            verbose="An unknown combatant's turn ends",
            detailed="An unknown combatant's turn ends",
        )
    return log.model_copy(update=updates)


def _sanitize_unlocated_movement_step(
    log: CombatLogEntry,
    controlled_entity_uuids: frozenset[str],
    observer_entity_uuids: frozenset[str],
) -> CombatLogEntry:
    if (
        log.entry_type is not CombatLogEntryType.MOVEMENT
        or log.data.get("type") != "step_movement"
        or not log.source_uuid
        or log.source_uuid in controlled_entity_uuids
    ):
        return log
    origin = _combat_log_position(log.data.get("from_position"))
    destination = _combat_log_position(log.data.get("to_position"))
    positions: list[tuple[int, int]] | None = None
    if origin is not None and destination is not None:
        positions = [origin, destination]
        if log.data.get("trajectory") == "direct_arc":
            disclosed = log.data.get("disclosed_path")
            normalized = (
                [_combat_log_position(value) for value in disclosed]
                if isinstance(disclosed, (list, tuple))
                else []
            )
            if (
                normalized
                and all(value is not None for value in normalized)
                and normalized[0] == origin
                and normalized[-1] == destination
            ):
                positions = [
                    value for value in normalized if value is not None
                ]
            else:
                positions = None
    common_observers = set(observer_entity_uuids)
    if positions is not None:
        for position in positions:
            common_observers.intersection_update(
                log.located_position_observer_uuids.get(
                    position_evidence_key(position),
                    set(),
                )
            )
    if positions is not None and common_observers:
        return log
    source_name = log.source_name or "Known entity"
    text = f"{{cyan:{source_name}}} moves outside current perception"
    return log.model_copy(update={
        "compact": text,
        "verbose": text,
        "detailed": text,
        "data": {"type": "movement", "observation_complete": False},
    })


def _rebuild_noncontrolled_movement(
    original: CombatLogEntry,
    projected: CombatLogEntry,
    projected_children: list[CombatLogEntry],
    controlled_entity_uuids: frozenset[str],
) -> CombatLogEntry:
    if (
        original.entry_type is not CombatLogEntryType.MOVEMENT
        or original.source_uuid in controlled_entity_uuids
        or original.data.get("type") in {"step_movement", "forced_movement"}
        or not projected.source_uuid
    ):
        return projected

    movement_type = original.data.get("movement_type")
    if movement_type in {"jump", "connector"}:
        if _atomic_root_is_fully_authorized(
            original,
            projected_children,
            movement_type,
        ):
            detached_original = original.model_copy(deep=True)
            return projected.model_copy(update={
                "compact": original.compact,
                "verbose": original.verbose,
                "detailed": original.detailed,
                "data": detached_original.data,
            })
        projected_children = []

    original_steps = [
        child for child in original.sub_entries
        if _is_committed_path_step(child)
    ]
    visible_steps = sorted(
        (
            child for child in projected_children
            if _is_committed_path_step(child)
        ),
        key=lambda child: int(child.data.get("path_index", 0)),
    )
    segments: list[list[tuple[int, int]]] = []
    observed_distance = 0.0
    observed_cost = 0.0
    for step in visible_steps:
        origin = _combat_log_position(step.data.get("from_position"))
        destination = _combat_log_position(step.data.get("to_position"))
        if origin is None or destination is None:
            continue
        from_elevation = step.data.get("from_elevation_feet")
        to_elevation = step.data.get("to_elevation_feet")
        observed_distance += float(
            support_distance_feet(
                origin,
                from_elevation,
                destination,
                to_elevation,
            )
            if type(from_elevation) is int and type(to_elevation) is int
            else 5
        )
        movement_cost = step.data.get("movement_cost", 0.0)
        if isinstance(movement_cost, (int, float)) and not isinstance(
            movement_cost,
            bool,
        ):
            observed_cost += float(movement_cost)
        if segments and segments[-1][-1] == origin:
            segments[-1].append(destination)
        else:
            segments.append([origin, destination])

    data: dict[str, Any] = {
        key: value
        for key, value in projected.data.items()
        if key in {"entity_name", "entity_uuid", "movement_type"}
    }
    data.update({
        "type": "movement",
        "observation_complete": (
            bool(original_steps) and len(visible_steps) == len(original_steps)
        ),
        "observed_path_segments": segments,
        "observed_distance_feet": observed_distance,
    })
    if len(segments) == 1:
        data.update({
            "start_position": segments[0][0],
            "end_position": segments[0][-1],
            "path": segments[0],
            "distance_feet": observed_distance,
            "movement_cost": observed_cost,
        })

    source_name = projected.source_name or "Known entity"
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
    return projected.model_copy(update={
        "compact": compact,
        "verbose": verbose,
        "detailed": detailed,
        "data": data,
    })


def _is_committed_path_step(log: CombatLogEntry) -> bool:
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


def _atomic_root_is_fully_authorized(
    original: CombatLogEntry,
    projected_children: list[CombatLogEntry],
    movement_type: str,
) -> bool:
    original_steps = [
        child for child in original.sub_entries
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    projected_steps = [
        child for child in projected_children
        if child.entry_type is CombatLogEntryType.MOVEMENT
        and child.data.get("type") == "step_movement"
    ]
    if not original_steps or len(original_steps) != len(projected_steps):
        return False
    trajectory = (
        "direct_arc" if movement_type == "jump" else "connector_transfer"
    )
    if any(
        child.source_uuid != original.source_uuid
        or child.data.get("trajectory") != trajectory
        or child.data.get("committed") is not True
        for child in original_steps
    ):
        return False
    if any(
        projected_child.data != original_child.data
        for original_child, projected_child in zip(
            original_steps,
            projected_steps,
            strict=True,
        )
    ):
        return False

    path: list[tuple[int, int]] = []
    for index, step in enumerate(original_steps):
        origin = _combat_log_position(step.data.get("from_position"))
        destination = _combat_log_position(step.data.get("to_position"))
        if origin is None or destination is None:
            return False
        disclosed = step.data.get("disclosed_path")
        leg = (
            [_combat_log_position(value) for value in disclosed]
            if isinstance(disclosed, (list, tuple)) and disclosed
            else [origin, destination]
        )
        if (
            any(value is None for value in leg)
            or leg[0] != origin
            or leg[-1] != destination
            or index and path[-1] != origin
        ):
            return False
        path.extend(
            value for value in (leg if index == 0 else leg[1:])
            if value is not None
        )
    root_path = original.data.get("path")
    if (
        not isinstance(root_path, (list, tuple))
        or [_combat_log_position(value) for value in root_path] != path
        or _combat_log_position(original.data.get("start_position")) != path[0]
        or _combat_log_position(original.data.get("end_position")) != path[-1]
    ):
        return False
    root_positions = _collect_candidate_positions(original.data)
    for text in (original.compact, original.verbose, original.detailed):
        root_positions.update(_positions_in_text(text))
    if not root_positions.issubset(path):
        return False
    for key in ("requested_end_position", "objective_end_position"):
        value = original.data.get(key)
        if value is not None and _combat_log_position(value) != path[-1]:
            return False

    first_elevation = original_steps[0].data.get("from_elevation_feet")
    final_elevation = original_steps[-1].data.get("to_elevation_feet")
    if type(first_elevation) is not int or type(final_elevation) is not int:
        return False
    if (
        original.data.get("start_elevation_feet") != first_elevation
        or original.data.get("end_elevation_feet") != final_elevation
    ):
        return False
    requested_elevation = original.data.get("requested_end_elevation_feet")
    if requested_elevation is not None and requested_elevation != final_elevation:
        return False

    costs = [step.data.get("movement_cost") for step in original_steps]
    if any(
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or not isfinite(float(cost))
        or cost < 0
        for cost in costs
    ):
        return False
    total_cost = sum(float(cost) for cost in costs)
    if original.data.get("movement_cost") != total_cost:
        return False
    if movement_type == "jump":
        return original.data.get("distance_feet") == total_cost
    if len(original_steps) != 1:
        return False
    origin = _combat_log_position(original_steps[0].data.get("from_position"))
    destination = _combat_log_position(original_steps[0].data.get("to_position"))
    return (
        origin is not None
        and destination is not None
        and original.data.get("distance_feet")
        == support_distance_feet(
            origin,
            first_elevation,
            destination,
            final_elevation,
        )
        and type(original.data.get("connector_uuid")) is str
        and type(original.data.get("connector_authored_id")) is str
    )


def _rebuild_multi_entity_summary(
    log: CombatLogEntry,
    projected_children: list[CombatLogEntry],
) -> CombatLogEntry:
    if log.entry_type is not CombatLogEntryType.MULTI_ENTITY_ACTION:
        return log
    data = {
        key: log.data[key]
        for key in ("action_name", "caster_name", "aoe_shape")
        if key in log.data
    }
    target_names: list[str] = []
    per_target_logs: list[dict[str, Any] | None] = []
    per_target_damage: list[int] = []
    saves_succeeded = 0
    saves_failed = 0
    for child in projected_children:
        if (
            child.target_name
            and child.target_name != "Unknown"
            and child.target_name not in target_names
        ):
            target_names.append(child.target_name)
        child_data = dict(child.data)
        per_target_logs.append(child_data or None)
        damage = _damage_from_log_data(child_data)
        if damage is not None:
            per_target_damage.append(damage)
        if child.entry_type is CombatLogEntryType.SPELL_SAVE:
            if bool(child_data.get("save_success")):
                saves_succeeded += 1
            else:
                saves_failed += 1
    data["total_targets"] = len(projected_children)
    if target_names:
        data["target_names"] = target_names
    if per_target_damage:
        data["per_target_damage"] = per_target_damage
        data["total_damage"] = sum(per_target_damage)
    if per_target_logs:
        data["per_target_logs"] = per_target_logs
    data["saves_succeeded"] = saves_succeeded
    data["saves_failed"] = saves_failed

    source_name = log.source_name or "Unknown"
    action_name = data.get("action_name")
    if not isinstance(action_name, str) or not action_name:
        action_name = "an action"
    target_count = len(projected_children)
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


def _sanitize_data(
    data: dict[str, Any],
    hidden_uuids: set[str],
    hidden_names: set[str],
    hidden_positions: set[tuple[int, int]],
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        sanitized_key = _sanitize_key(
            str(key),
            hidden_uuids,
            hidden_names,
            hidden_positions,
        )
        if sanitized_key is None:
            continue
        sanitized_value = _sanitize_value(
            value,
            hidden_uuids,
            hidden_names,
            hidden_positions,
        )
        if sanitized_value is not _DROP:
            sanitized[sanitized_key] = sanitized_value
    return sanitized


_DROP = object()


def _sanitize_value(
    value: Any,
    hidden_uuids: set[str],
    hidden_names: set[str],
    hidden_positions: set[tuple[int, int]],
) -> Any:
    position = _combat_log_position(value)
    if position is not None and position in hidden_positions:
        return _DROP
    if isinstance(value, str):
        if value in hidden_uuids:
            return _DROP
        return _sanitize_text(
            value,
            hidden_uuids,
            hidden_names,
            hidden_positions,
        )
    if isinstance(value, dict):
        return _sanitize_data(
            value,
            hidden_uuids,
            hidden_names,
            hidden_positions,
        )
    if isinstance(value, (list, tuple)):
        sanitized = [
            item
            for child in value
            if (
                item := _sanitize_value(
                    child,
                    hidden_uuids,
                    hidden_names,
                    hidden_positions,
                )
            )
            is not _DROP
        ]
        return tuple(sanitized) if isinstance(value, tuple) else sanitized
    if isinstance(value, (set, frozenset)):
        sanitized_set = {
            item
            for child in value
            if (
                item := _sanitize_value(
                    child,
                    hidden_uuids,
                    hidden_names,
                    hidden_positions,
                )
            )
            is not _DROP
        }
        return frozenset(sanitized_set) if isinstance(value, frozenset) else sanitized_set
    return value


def _sanitize_key(
    key: str,
    hidden_uuids: set[str],
    hidden_names: set[str],
    hidden_positions: set[tuple[int, int]],
) -> str | None:
    if any(value in key for value in (*hidden_uuids, *hidden_names)):
        return None
    if _positions_in_text(key) & hidden_positions:
        return None
    return key


def _sanitize_text(
    text: str,
    hidden_uuids: set[str],
    hidden_names: set[str],
    hidden_positions: set[tuple[int, int]],
) -> str:
    sanitized = text
    for hidden_uuid in hidden_uuids:
        sanitized = sanitized.replace(hidden_uuid, "")
    for hidden_name in hidden_names:
        sanitized = sanitized.replace(hidden_name, "Unknown")
    return _POSITION_TEXT.sub(
        lambda match: (
            match.group(0)
            if _is_dice_pair(sanitized, match.start())
            else (
                "Unknown position"
                if (int(match.group(1)), int(match.group(2)))
                in hidden_positions
                else match.group(0)
            )
        ),
        sanitized,
    )


def _combat_log_position(value: Any) -> tuple[int, int] | None:
    if (
        type(value) is tuple
        and len(value) == 2
        and all(type(coordinate) is int for coordinate in value)
    ):
        return value[0], value[1]
    return None


_POSITION_TEXT = re.compile(
    r"(?<!\w)(?:\(\s*|\[\s*)?(-?\d+)\s*,\s*(-?\d+)"
    r"(?:\s*\)|\s*\])?(?!\w)"
)


def _positions_in_text(text: str) -> set[tuple[int, int]]:
    return {
        (int(match.group(1)), int(match.group(2)))
        for match in _POSITION_TEXT.finditer(text)
        if not _is_dice_pair(text, match.start())
    }


_DICE_PAIR_PREFIX = re.compile(
    r"(?:\d+)?d\d+\(\s*(?:\{[^{}:]+:)?$",
    re.IGNORECASE,
)


def _is_dice_pair(text: str, start: int) -> bool:
    return _DICE_PAIR_PREFIX.search(text[:start]) is not None


def _collect_candidate_positions(value: Any) -> set[tuple[int, int]]:
    position = _combat_log_position(value)
    if position is not None:
        return {position}
    if isinstance(value, str):
        return _positions_in_text(value)
    if isinstance(value, dict):
        positions: set[tuple[int, int]] = set()
        for key, child in value.items():
            positions.update(_positions_in_text(str(key)))
            positions.update(_collect_candidate_positions(child))
        return positions
    if isinstance(value, (list, tuple, set, frozenset)):
        positions = set()
        for child in value:
            positions.update(_collect_candidate_positions(child))
        return positions
    return set()


def _owned_movement_positions(log: CombatLogEntry) -> set[tuple[int, int]]:
    data = log.data
    movement_type = data.get("type")
    if movement_type == "step_movement":
        origin = _combat_log_position(data.get("from_position"))
        destination = _combat_log_position(data.get("to_position"))
        if origin is None or destination is None:
            return set()
        disclosed = data.get("disclosed_path")
        disclosed_positions = (
            [_combat_log_position(value) for value in disclosed]
            if isinstance(disclosed, (list, tuple))
            else []
        )
        if disclosed_positions and (
            any(value is None for value in disclosed_positions)
            or disclosed_positions[0] != origin
            or disclosed_positions[-1] != destination
        ):
            return set()
        return {
            value
            for value in (origin, destination, *disclosed_positions)
            if value is not None
        }
    if movement_type == "forced_movement":
        return {
            position
            for key in ("start_position", "end_position")
            if (position := _combat_log_position(data.get(key))) is not None
        }

    path_value = data.get("path")
    path = (
        [_combat_log_position(value) for value in path_value]
        if isinstance(path_value, (list, tuple))
        else []
    )
    if not path or any(position is None for position in path):
        return set()
    start = _combat_log_position(data.get("start_position"))
    end = _combat_log_position(data.get("end_position"))
    if start is None or end is None or path[0] != start or path[-1] != end:
        return set()
    owned = {position for position in path if position is not None}
    for key in ("requested_end_position", "objective_end_position"):
        position = _combat_log_position(data.get(key))
        if position is not None:
            owned.add(position)
    return owned


def _position_from_evidence_key(key: str) -> tuple[int, int] | None:
    parts = key.split(",", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _damage_from_log_data(data: dict[str, Any]) -> Optional[int]:
    for key in ("final_damage", "total_damage", "damage"):
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


__all__ = ["project_combat_log"]
