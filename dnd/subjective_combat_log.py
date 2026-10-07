"""Pure projection of typed event-time logs; no live entity or geometry lookup."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re
from dnd.core.combat_log import (
    ActionLogData, AttackLogData, CombatLogData, CombatLogEntry, CombatLogEntryType,
    ConditionRemovedLogData, ConnectorMovementLogData, DamageRollDisplay,
    DamageTakenLogData, DeathLogData, DeathSaveLogData, EmptyLogData,
    EntitySpottedLogData, ForcedMovementLogData, HazardDetectedLogData, HealLogData,
    JumpMovementLogData, ModifierBreakdown, MovementLogData, MultiEntityLogData,
    ObservedMovementLogData, RollModificationLogData, SavingThrowLogData,
    ShoveLogData, SkillCheckLogData, SpatialChangeLogData, SpatialInteractionLogData,
    SpellDamageLogData, SpellInterruptionLogData, SpellSaveLogData, StepMovementLogData,
    TurnLogData, UnknownMovementLogData, UnlocatedMovementLogData,
    position_evidence_key, summarize_target_entries,
)
from dnd.core.elevation import support_distance_feet
from dnd.types.event_facts import MovementTrajectory


def project_combat_log(log: CombatLogEntry | None, *,
                      controlled_entity_uuids: frozenset[str],
                      observer_entity_uuids: frozenset[str],
                      known_entity_names: Mapping[str, str] | None = None,
                      known_connector_uuids: frozenset[str] = frozenset(),
                      known_content_ids: frozenset[str] = frozenset(),
                      retained_entries: dict[int, CombatLogEntry | None] | None = None,
                      ) -> CombatLogEntry | None:
    """Retained identity can name an admitted occurrence; it cannot admit one."""
    if log is None:
        return None
    return _project(log, controlled_entity_uuids, observer_entity_uuids,
                    known_entity_names or {}, known_connector_uuids, known_content_ids,
                    retained_entries if retained_entries is not None else {})


def _project(log: CombatLogEntry, controlled: frozenset[str], observers: frozenset[str],
             known: Mapping[str, str], connectors: frozenset[str],
             content_ids: frozenset[str],
             memo: dict[int, CombatLogEntry | None]) -> CombatLogEntry | None:
    if id(log) in memo:
        return memo[id(log)]
    participants = {value for value in (log.source_uuid, log.target_uuid) if value}
    visible = bool(participants & controlled or log.perceiver_uuids & observers
                   or any(grants & observers for grants in log.located_entity_observer_uuids.values())
                   or any(grants & observers for grants in log.located_position_observer_uuids.values())
                   or (log.data.kind == "turn" and bool(log.identified_entity_observer_uuids.get(log.source_uuid, set()) & observers)))
    children = []
    child_indices = {}
    for index, child in enumerate(log.sub_entries):
        projected = _project(child, controlled, observers, known, connectors, content_ids, memo)
        if projected is not None:
            child_indices[index] = len(children)
            children.append(projected)
    if not visible and not children:
        memo[id(log)] = None
        return None
    identified = set(controlled) | {
        identity for identity, grants in log.identified_entity_observer_uuids.items() if grants & observers}
    # A previously known name can label an admitted death/turn closure, but is
    # not evidence about the source or equipment of a newly hidden attack.
    if log.data.kind in {"turn", "death"}:
        identified.update(known)
    hidden_ids, hidden_names = _hidden_identities(log, identified, controlled, observers, known)
    source_known = not log.source_uuid or log.source_uuid in identified
    target_known = not log.target_uuid or log.target_uuid in identified
    source = (known.get(log.source_uuid, log.source_name) if source_known else "Unknown")
    target = known.get(log.target_uuid, log.target_name) if target_known and log.target_uuid else log.target_name if target_known else "Unknown"
    positions = _positions(log.data)
    admitted = {position for position in positions
                if log.located_position_observer_uuids.get(position_evidence_key(position), set()) & observers}
    owned_movement = log.entry_type is CombatLogEntryType.MOVEMENT and (
        log.source_uuid in controlled or (log.data.kind == "forced_movement" and log.target_uuid in controlled))
    if owned_movement:
        admitted.update(positions)
    hidden_positions = positions - admitted
    clean = lambda text: _sanitize_text(text, hidden_ids, hidden_names, hidden_positions)
    data = _project_data(log.data, clean, hidden_ids, admitted, source_known, content_ids)
    success = log.success
    compact, verbose, detailed = (clean(value) for value in (log.compact, log.verbose, log.detailed))

    # A child occurrence does not authorize its hidden cause's name, roll or gear.
    if not visible or (not source_known and log.data.kind in {
            "attack", "action", "multi_entity_action", "spell_save", "spell_damage", "spell_interruption", "roll_modification"}):
        data = EmptyLogData()
        source, target = "Unknown", None
        compact = verbose = detailed = "Observed effects" if children else "An unseen source acts"
        category = CombatLogEntryType.ACTION
        source_uuid, target_uuid = "", None
        success = None
    else:
        category = log.entry_type
        source_uuid = log.source_uuid if source_known else ""
        target_uuid = log.target_uuid if target_known else ""
        if category is CombatLogEntryType.MOVEMENT:
            if not source_known:
                data = UnknownMovementLogData()
                compact = verbose = detailed = "Something moves nearby"
            elif not owned_movement:
                data, compact, verbose, detailed, children = _movement(
                    log, data, source, target, admitted, children, connectors, (compact, verbose, detailed))
        if data.kind == "damage_taken" and not source_known:
            compact = verbose = detailed = f"{{yellow:{data.target_name}}} takes {{red:{data.damage} {data.damage_type} damage}}"
        if data.kind == "multi_entity_action" and log.data.kind == "multi_entity_action":
            indices = tuple(child_indices[i] for i in log.data.target_entry_indices if i in child_indices
                and children[child_indices[i]].data.kind != "empty")
            data = summarize_target_entries(data, children, indices)
            text = (f"{{cyan:{source}}} uses {{green:{data.action_name}}} → "
                    f"{{yellow:{data.total_targets} observed targets}}, {{red:{data.total_damage} observed damage}}")
            compact = verbose = detailed = text
        if data.kind == "spatial_change" or data.kind == "spatial_interaction":
            operation = data.operation.value.replace("_", " ")
            compact = f"{{cyan:{source}}} causes {{yellow:{operation}}}"
            verbose = detailed = f"{compact} across {len(data.affected_positions)} observed cells"

    result = log.model_copy(update={
        "entry_type": category, "source_name": source, "source_uuid": source_uuid,
        "target_name": target, "target_uuid": target_uuid, "data": data,
        "success": success,
        "compact": compact, "verbose": verbose, "detailed": detailed,
        "sub_entries": children, "perceiver_uuids": set(), "revealed_entity_uuids": set(),
        "identified_entity_observer_uuids": {}, "located_entity_observer_uuids": {},
        "located_position_observer_uuids": {},
    })
    memo[id(log)] = result
    return result


def _hidden_identities(log: CombatLogEntry, identified: set[str], controlled: frozenset[str],
                       observers: frozenset[str], known: Mapping[str, str]) -> tuple[set[str], set[str]]:
    hidden_ids = {identity for identity in (
        log.source_uuid, log.target_uuid, *log.perceiver_uuids, *log.revealed_entity_uuids,
        *log.identified_entity_observer_uuids, *log.located_entity_observer_uuids)
        if identity and identity not in identified}
    hidden_names = {name for identity, name in ((log.source_uuid, log.source_name),
        (log.target_uuid, log.target_name)) if identity in hidden_ids and name}
    for child in log.sub_entries:
        child_known = set(controlled) | set(known) | {identity for identity, grants
            in child.identified_entity_observer_uuids.items() if grants & observers}
        child_ids, child_names = _hidden_identities(child, child_known, controlled, observers, known)
        hidden_ids.update(child_ids)
        hidden_names.update(child_names)
    return hidden_ids, hidden_names


def _positions(data: CombatLogData) -> set[tuple[int, int]]:
    """Only declared geometry fields are coordinates; dice and vectors never are."""
    match data:
        case MovementLogData() | JumpMovementLogData() | ConnectorMovementLogData():
            values = {*data.path, data.start_position, data.end_position, data.requested_end_position}
            if data.kind == "jump_movement" or data.kind == "connector_movement":
                values.add(data.objective_end_position)
            return {p for p in values if p is not None}
        case StepMovementLogData():
            return {data.from_position, data.to_position, *data.disclosed_path}
        case ForcedMovementLogData():
            return {p for p in (data.start_position, data.end_position) if p is not None}
        case ShoveLogData():
            return {data.end_position} if data.end_position is not None else set()
        case MultiEntityLogData():
            return {data.aoe_center} if data.aoe_center is not None else set()
        case EntitySpottedLogData():
            return {data.target_position} if data.target_position is not None else set()
        case HazardDetectedLogData():
            return {data.position} if data.position is not None else set()
        case SpatialChangeLogData() | SpatialInteractionLogData():
            return set(data.affected_positions)
        case _:
            return set()


def _movement(log: CombatLogEntry, data: CombatLogData, source: str, target: str | None, admitted: set[tuple[int, int]],
              children: list[CombatLogEntry], connectors: frozenset[str], texts: tuple[str, str, str]
              ) -> tuple[CombatLogData, str, str, str, list[CombatLogEntry]]:
    if data.kind == "step_movement":
        if _positions(data) <= admitted:
            text = f"{{cyan:{source}}} {data.from_position} → {data.to_position}"
            return data.model_copy(update={"path_index": 0}), text, text, f"{text} ({data.movement_cost:g}ft)", children
        text = f"{{cyan:{source}}} moves outside current perception"
        return UnlocatedMovementLogData(), text, text, text, children
    if data.kind == "forced_movement":
        permitted = data.model_copy(update={
            "start_position": data.start_position if data.start_position in admitted else None,
            "end_position": data.end_position if data.end_position in admitted else None})
        if not _positions(data) <= admitted:
            text = f"{{yellow:{target or source}}} is pushed outside current perception"
            return UnlocatedMovementLogData(), text, text, text, children
        text = f"{{yellow:{target or source}}} is pushed {data.actual_distance}ft"
        return permitted, text, text, f"{text}: {data.start_position} → {data.end_position}", children
    if data.kind not in ("movement", "jump_movement", "connector_movement"):
        return data, *texts, children
    if data.kind == "jump_movement" or data.kind == "connector_movement":
        steps = [child.data for child in children if child.data.kind == "step_movement"]
        originals = [child.data for child in log.sub_entries if child.data.kind == "step_movement"]
        geometry = bool(steps) and len(steps) == len(originals) and all(step.committed for step in steps)
        # Atomic travel is disclosed only when its complete route was observed.
        # Child grants establish geometry, never connector identity or hidden goals.
        path = tuple(point for index, step in enumerate(steps)
                     for point in (step.disclosed_path if index == 0 else step.disclosed_path[1:]))
        geometry = geometry and all(
            step.model_copy(update={"path_index": original.path_index}) == original
            for step, original in zip(steps, originals))
        geometry = geometry and all(left.to_position == right.from_position
            and left.to_elevation_feet == right.from_elevation_feet for left, right in zip(steps, steps[1:]))
        geometry = geometry and bool(path) and _positions(data) <= set(path)
        geometry = geometry and tuple(data.path) == path
        if geometry:
            geometry = (steps[0].from_position == data.start_position
                and steps[-1].to_position == data.end_position
                and steps[0].from_elevation_feet == data.start_elevation_feet
                and steps[-1].to_elevation_feet == data.end_elevation_feet
                and sum(step.movement_cost for step in steps) == data.movement_cost)
        connector_known = data.kind != "connector_movement" or str(data.connector_uuid) in connectors
        if geometry and connector_known:
            # Preserve the already sanitized typed value, never restore native secrets.
            text = f"{{cyan:{source}}} {'jumps' if data.kind == 'jump_movement' else 'traverses'} {data.start_position} → {data.end_position}"
            return data, text, text, f"{text} ({data.movement_cost:g}ft)", children
        text = f"{{cyan:{source}}} moves outside current perception"
        return UnlocatedMovementLogData(), text, text, text, children
    segments: list[list[tuple[int, int]]] = []
    observed_distance = 0.0
    observed_cost = 0.0
    visible_steps = [(child, child.data) for child in children if child.data.kind == "step_movement"
                     and child.data.committed and child.data.trajectory is MovementTrajectory.PATH]
    remapped: dict[int, CombatLogEntry] = {}
    for index, (child, step) in enumerate(visible_steps):
        observed_distance += support_distance_feet(step.from_position, step.from_elevation_feet,
                                                   step.to_position, step.to_elevation_feet)
        observed_cost += step.movement_cost
        if segments and segments[-1][-1] == step.from_position:
            segments[-1].append(step.to_position)
        else:
            segments.append([step.from_position, step.to_position])
        remapped[id(child)] = child.model_copy(update={"data": step.model_copy(update={"path_index": index})})
    children = [remapped.get(id(child), child) for child in children]
    original_steps = [child for child in log.sub_entries if child.data.kind == "step_movement"
                      and child.data.committed and child.data.trajectory is MovementTrajectory.PATH]
    complete = bool(original_steps) and len(original_steps) == len(visible_steps)
    path = tuple(segments[0]) if len(segments) == 1 else ()
    result = ObservedMovementLogData(entity_name=source, entity_uuid=log.source_uuid,
        observation_complete=complete, observed_path_segments=tuple(tuple(leg) for leg in segments),
        observed_distance_feet=observed_distance, path=path,
        start_position=path[0] if path else None, end_position=path[-1] if path else None,
        distance_feet=observed_distance if path else None, movement_cost=observed_cost if path else None)
    if path:
        text = f"{{cyan:{source}}} is observed moving {{green:{observed_distance:g}ft}} to {{yellow:{path[-1]}}}"
        detail = text + "\n  Observed path: " + " -> ".join(str(p) for p in path)
    elif segments:
        text = f"{{cyan:{source}}} is observed moving across {len(segments)} visible segments"
        detail = text + "\n  Observed segments: " + "; ".join(" -> ".join(str(p) for p in leg) for leg in segments)
    else:
        text = detail = f"{{cyan:{source}}} moves outside current perception"
    return result, text, text, detail, children


def _breakdowns(values: list[ModifierBreakdown], clean: Callable[[str], str]) -> list[ModifierBreakdown]:
    return [value.model_copy(update={"name": clean(value.name), "source": clean(value.source)}) for value in values]


def _damage_rolls(values: list[DamageRollDisplay], clean: Callable[[str], str]) -> list[DamageRollDisplay]:
    return [value.model_copy(update={"bonus_breakdown": _breakdowns(value.bonus_breakdown, clean)}) for value in values]


def _project_data(data: CombatLogData, clean: Callable[[str], str], hidden_ids: set[str], admitted: set[tuple[int, int]],
                  source_known: bool, content_ids: frozenset[str]) -> CombatLogData:
    identity = lambda value: "" if value in hidden_ids else value
    position = lambda value: value if value in admitted else None
    match data:
        case AttackLogData():
            return data.model_copy(update={
                "attacker_name": clean(data.attacker_name) if data.attacker_name is not None else None,
                "target_name": clean(data.target_name) if data.target_name is not None else None,
                "weapon_name": clean(data.weapon_name) if data.weapon_name is not None else None,
                "attacker_uuid": identity(data.attacker_uuid),
                "target_uuid": identity(data.target_uuid),
                "ac_breakdown": _breakdowns(data.ac_breakdown, clean),
                "advantage_breakdown": _breakdowns(data.advantage_breakdown, clean),
                "attack_breakdown": _breakdowns(data.attack_breakdown, clean),
                "damage_rolls": _damage_rolls(data.damage_rolls, clean),
            })
        case SavingThrowLogData():
            return data.model_copy(update={
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "source_name": clean(data.source_name) if data.source_name is not None else None,
                "entity_uuid": identity(data.entity_uuid),
                "advantage_breakdown": _breakdowns(data.advantage_breakdown, clean),
                "bonus_breakdown": _breakdowns(data.bonus_breakdown, clean),
            })
        case SpellSaveLogData():
            return data.model_copy(update={
                "caster_name": clean(data.caster_name) if data.caster_name is not None else None,
                "spell_name": clean(data.spell_name) if data.spell_name is not None else None,
                "target_name": clean(data.target_name) if data.target_name is not None else None,
                "caster_uuid": identity(data.caster_uuid),
                "target_uuid": identity(data.target_uuid),
                "save_advantage_breakdown": _breakdowns(data.save_advantage_breakdown, clean),
                "save_bonus_breakdown": _breakdowns(data.save_bonus_breakdown, clean),
                "damage_rolls": _damage_rolls(data.damage_rolls, clean),
            })
        case SpellInterruptionLogData():
            return data.model_copy(update={
                "counterspeller_name": clean(data.counterspeller_name) if data.counterspeller_name is not None else None,
                "original_caster_name": clean(data.original_caster_name) if data.original_caster_name is not None else None,
                "spell_name": clean(data.spell_name) if data.spell_name is not None else None,
                "counterspeller_uuid": identity(data.counterspeller_uuid),
                "original_caster_uuid": identity(data.original_caster_uuid),
            })
        case SkillCheckLogData():
            return data.model_copy(update={
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "entity_uuid": identity(data.entity_uuid),
                "advantage_breakdown": _breakdowns(data.advantage_breakdown, clean),
                "bonus_breakdown": _breakdowns(data.bonus_breakdown, clean),
            })
        case EntitySpottedLogData():
            return data.model_copy(update={
                "observer_name": clean(data.observer_name) if data.observer_name is not None else None,
                "target_name": clean(data.target_name) if data.target_name is not None else None,
                "observer_uuid": identity(data.observer_uuid),
                "target_uuid": identity(data.target_uuid),
                "target_position": position(data.target_position),
            })
        case HazardDetectedLogData():
            return data.model_copy(update={
                "hazard_name": clean(data.hazard_name) if data.hazard_name is not None else None,
                "observer_name": clean(data.observer_name) if data.observer_name is not None else None,
                "observer_uuid": identity(data.observer_uuid),
                "position": position(data.position),
            })
        case DamageTakenLogData():
            return data.model_copy(update={
                "source_name": clean(data.source_name) if source_known else "Unknown",
                "target_name": clean(data.target_name) if data.target_name is not None else None,
                "effect_id": data.effect_id if data.effect_id in content_ids else None,
                "blocked_reason": clean(data.blocked_reason) if data.blocked_reason else None,
            })
        case HealLogData():
            return data.model_copy(update={
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "source_description": clean(data.source_description) if data.source_description is not None else None,
                "entity_uuid": identity(data.entity_uuid),
            })
        case ActionLogData():
            return data.model_copy(update={
                "action_name": clean(data.action_name) if data.action_name is not None else None,
                "effect_description": clean(data.effect_description) if data.effect_description is not None else None,
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "target_name": clean(data.target_name) if data.target_name is not None else None,
                "entity_uuid": identity(data.entity_uuid),
                "target_uuid": identity(data.target_uuid),
            })
        case TurnLogData():
            return data.model_copy(update={
                "turn_index": None,
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "entity_uuid": identity(data.entity_uuid),
            })
        case MultiEntityLogData():
            return data.model_copy(update={
                "action_name": clean(data.action_name) if data.action_name is not None else None,
                "caster_name": clean(data.caster_name) if data.caster_name is not None else None,
                "aoe_center": position(data.aoe_center),
            })
        case ConditionRemovedLogData():
            return data.model_copy(update={
                "condition_name": clean(data.condition_name) if data.condition_name is not None else None,
            })
        case DeathLogData():
            return data.model_copy(update={
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
            })
        case SpellDamageLogData():
            return data.model_copy(update={
                "spell_name": clean(data.spell_name) if data.spell_name is not None else None,
                "target_name": clean(data.target_name) if data.target_name is not None else None,
            })
        case DeathSaveLogData():
            return data.model_copy(update={
                "entity_name": clean(data.entity_name) if data.entity_name is not None else None,
                "entity_uuid": identity(data.entity_uuid),
            })
        case ShoveLogData():
            return data.model_copy(update={
                "end_position": position(data.end_position),
                "blocked_by": clean(data.blocked_by) if data.blocked_by else None,
            })
        case SpatialChangeLogData():
            return data.model_copy(update={
                "affected_positions": tuple(p for p in data.affected_positions if p in admitted),
            })
        case SpatialInteractionLogData():
            return data.model_copy(update={
                "affected_positions": tuple(p for p in data.affected_positions if p in admitted),
                "source_item_id": data.source_item_id if data.source_item_id in content_ids else None,
            })
        case RollModificationLogData():
            return data.model_copy(update={"modifications": [value.model_copy(update={
                "handler_name": clean(value.handler_name), "reason": clean(value.reason)})
                for value in data.modifications]})
        case MovementLogData() | JumpMovementLogData() | ConnectorMovementLogData():
            return data.model_copy(update={"entity_name": clean(data.entity_name), "entity_uuid": identity(data.entity_uuid)})
        case ForcedMovementLogData():
            return data.model_copy(update={"cause": clean(data.cause),
                "blocked_by": clean(data.blocked_by) if data.blocked_by else None})
        case StepMovementLogData() | EmptyLogData() | UnlocatedMovementLogData() | UnknownMovementLogData() | ObservedMovementLogData():
            return data


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
