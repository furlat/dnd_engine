"""Incremental derivation of typed policy facts from subjective state."""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ai.knowledge.models import (
    ActorFacts,
    AffordanceAffectedSetGroup,
    AffordanceIndex,
    AgentFacts,
    CapabilityIndex,
    CombatMemoryFacts,
    ContactFacts,
    NavigationHistoryFacts,
    ObjectFacts,
    TargetEffectBlockHypothesis,
    ThreatFacts,
    TopologyFacts,
    target_effect_hypothesis_key,
)
from server.agent_protocol.observation import KnowledgeState, SubjectiveWorldState
from ai.knowledge.replay import entity_fact_replay_token
from server.agent_protocol.control import ActionAffordance
from server.agent_protocol.immutable import FrozenDict
from server.agent_protocol.semantics import ActionSemantics, ActionTag


SectionT = TypeVar("SectionT")
_COMBAT_MEMORY_LOG_WINDOW = 32
_COMBAT_MEMORY_EPISODES_PER_HYPOTHESIS = 4
_COMBAT_MEMORY_HYPOTHESIS_LIMIT = 32
_AFFECTED_SET_GROUP_TAGS = frozenset({
    ActionTag.DAMAGE_SINGLE_TARGET,
    ActionTag.DAMAGE_MULTI_TARGET,
    ActionTag.DAMAGE_AREA,
    ActionTag.CONTROL_HARD,
    ActionTag.CONTROL_SOFT,
})


class FactDerivationMetric(BaseModel):
    """Timing and reuse result for one typed fact section."""

    model_config = ConfigDict(frozen=True)

    section: str = Field(description="Derived fact section.")
    elapsed_ms: float = Field(ge=0.0, description="Section derivation time in milliseconds.")
    reused: bool = Field(description="Whether the previous immutable section was reused.")


class FactDerivation(BaseModel):
    """One derivation result with explicit invalidation evidence."""

    model_config = ConfigDict(frozen=True)

    facts: AgentFacts = Field(description="Typed facts for the current subjective cursor.")
    invalidated_sections: tuple[str, ...] = Field(description="Sections rebuilt for this revision.")
    metrics: tuple[FactDerivationMetric, ...] = Field(description="Per-section derivation timings.")


def derive_agent_facts(
    world: SubjectiveWorldState,
    *,
    previous_world: Optional[SubjectiveWorldState] = None,
    previous_facts: Optional[AgentFacts] = None,
) -> FactDerivation:
    """Derive typed policy facts and reuse unchanged immutable sections.

    Args:
        world: Current canonical session-subjective world.
        previous_world: Previous world revision when available.
        previous_facts: Facts derived from the previous world revision.

    Returns:
        Facts, invalidated section names, and per-section timings.
    """
    metrics: list[FactDerivationMetric] = []
    invalidated: list[str] = []

    actor = _derive_or_reuse(
        "actor",
        previous_facts.actor if previous_facts is not None else None,
        _actor_inputs_unchanged(world, previous_world),
        lambda: _derive_actor(world),
        metrics,
        invalidated,
    )
    contacts = _derive_or_reuse(
        "contacts",
        previous_facts.contacts if previous_facts is not None else None,
        _mapping_items_identical(world.known_entities, previous_world.known_entities if previous_world else None)
        and _same_object(world.session, previous_world.session if previous_world else None),
        lambda: _derive_contacts(world),
        metrics,
        invalidated,
    )
    threat = _derive_or_reuse(
        "threat",
        previous_facts.threat if previous_facts is not None else None,
        _threat_inputs_unchanged(world, previous_world),
        lambda: _derive_threat(world, contacts),
        metrics,
        invalidated,
    )
    objects = _derive_or_reuse(
        "objects",
        previous_facts.objects if previous_facts is not None else None,
        _mapping_items_identical(world.known_objects, previous_world.known_objects if previous_world else None),
        lambda: _derive_objects(world),
        metrics,
        invalidated,
    )
    topology = _derive_or_reuse(
        "topology",
        previous_facts.topology if previous_facts is not None else None,
        _mapping_items_identical(
            world.known_tiles,
            previous_world.known_tiles if previous_world else None,
        )
        and _mapping_items_identical(
            world.known_objects,
            previous_world.known_objects if previous_world else None,
        ),
        lambda: _derive_topology(world),
        metrics,
        invalidated,
    )
    navigation = _derive_or_reuse(
        "navigation",
        previous_facts.navigation if previous_facts is not None else None,
        _navigation_inputs_unchanged(world, previous_world),
        lambda: _derive_navigation_history(world),
        metrics,
        invalidated,
    )
    combat_memory = _derive_or_reuse(
        "combat_memory",
        previous_facts.combat_memory if previous_facts is not None else None,
        _combat_logs_unchanged(world, previous_world),
        lambda: _derive_combat_memory(world),
        metrics,
        invalidated,
    )
    affordances = _derive_or_reuse(
        "affordances",
        previous_facts.affordances if previous_facts is not None else None,
        _same_object(world.current_epoch, previous_world.current_epoch if previous_world else None),
        lambda: _derive_affordances(world),
        metrics,
        invalidated,
    )
    capabilities = _derive_or_reuse(
        "capabilities",
        previous_facts.capabilities if previous_facts is not None else None,
        _same_object(world.current_epoch, previous_world.current_epoch if previous_world else None),
        lambda: _derive_capabilities(world),
        metrics,
        invalidated,
    )
    facts = AgentFacts.model_construct(
        observation_cursor=world.observation_cursor,
        epoch_id=world.current_epoch.epoch_id if world.current_epoch is not None else None,
        actor=actor,
        contacts=contacts,
        threat=threat,
        objects=objects,
        topology=topology,
        navigation=navigation,
        combat_memory=combat_memory,
        affordances=affordances,
        capabilities=capabilities,
    )
    return FactDerivation.model_construct(
        facts=facts,
        invalidated_sections=tuple(invalidated),
        metrics=tuple(metrics),
    )


def _derive_or_reuse(
    section: str,
    previous: Optional[SectionT],
    inputs_unchanged: bool,
    builder: Callable[[], SectionT],
    metrics: list[FactDerivationMetric],
    invalidated: list[str],
) -> SectionT:
    """Reuse an immutable section or rebuild it with timing evidence."""
    started = time.perf_counter()
    reused = previous is not None and inputs_unchanged
    if reused:
        assert previous is not None
        value = previous
    else:
        value = builder()
    if not reused:
        invalidated.append(section)
    metrics.append(
        FactDerivationMetric.model_construct(
            section=section,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            reused=reused,
        )
    )
    return value


def _actor_inputs_unchanged(
    world: SubjectiveWorldState,
    previous: Optional[SubjectiveWorldState],
) -> bool:
    """Return whether every source used by ActorFacts retained identity."""
    if previous is None or world.session is not previous.session or world.current_epoch is not previous.current_epoch:
        return False
    actor_uuid = world.current_epoch.actor_uuid if world.current_epoch is not None else None
    if actor_uuid is None:
        return True
    return world.known_entities.get(actor_uuid) is previous.known_entities.get(actor_uuid)


def _threat_inputs_unchanged(
    world: SubjectiveWorldState,
    previous: Optional[SubjectiveWorldState],
) -> bool:
    """Return whether every source used by ThreatFacts retained identity."""
    if previous is None or world.session is not previous.session or world.current_epoch is not previous.current_epoch:
        return False
    return _threat_input_signature(world) == _threat_input_signature(previous)


def _threat_input_signature(
    world: SubjectiveWorldState,
) -> tuple[
    Optional[str],
    Optional[tuple[int, int]],
    tuple[str, ...],
    tuple[tuple[str, Optional[tuple[int, int]], Optional[str], Optional[bool]], ...],
]:
    """Return the exact subjective entity fields used by ThreatFacts.

    Threat derivation only depends on the active actor's known position and the
    visible hostile set with their known positions. Damage, AC, conditions, and
    other contact details are intentionally excluded so damage-only patches do
    not invalidate immediate-pressure facts.
    """
    epoch = world.current_epoch
    actor_uuid = epoch.actor_uuid if epoch is not None and world.session.is_my_turn else None
    actor = world.known_entities.get(actor_uuid) if actor_uuid is not None else None
    controlled_factions = tuple(sorted(
        entity.faction
        for entity in world.known_entities.values()
        if entity.controlled and entity.faction is not None
    ))
    visible_hostiles = tuple(sorted(
        (
            entity.uuid,
            entity.position,
            entity.faction,
            entity.is_dead,
        )
        for entity in world.known_entities.values()
        if not entity.controlled
        and entity.is_dead is not True
        and entity.knowledge_state is KnowledgeState.VISIBLE
        and entity.faction is not None
        and controlled_factions
        and entity.faction not in controlled_factions
    ))
    return (
        actor_uuid,
        actor.position if actor is not None else None,
        controlled_factions,
        visible_hostiles,
    )


def _derive_actor(world: SubjectiveWorldState) -> ActorFacts:
    """Derive current actor facts without inventing an actor while inactive."""
    epoch = world.current_epoch
    actor_uuid = epoch.actor_uuid if epoch is not None and world.session.is_my_turn else None
    actor = world.known_entities.get(actor_uuid) if actor_uuid is not None else None
    return ActorFacts.model_construct(
        session_id=world.session.session_id,
        controlled_entity_uuids=tuple(world.session.controlled_entity_uuids),
        active_entity_uuid=world.session.active_entity_uuid,
        actor_uuid=actor_uuid,
        is_my_turn=actor_uuid is not None,
        position=actor.position if actor is not None else None,
        hp=actor.hp if actor is not None else None,
        normal_hp=actor.normal_hp if actor is not None else None,
        temporary_hp=actor.temporary_hp if actor is not None else None,
        max_hp=actor.max_hp if actor is not None else None,
        healing_blocked=actor.healing_blocked if actor is not None else None,
        conditions=tuple(actor.conditions) if actor is not None else tuple(),
        condition_semantic_keys=(
            tuple(actor.condition_semantic_keys)
            if actor is not None and actor.condition_semantic_keys is not None
            else None
        ),
        is_concentrating=actor.is_concentrating if actor is not None else False,
        faction=actor.faction if actor is not None else None,
        economy=epoch.economy if actor_uuid is not None and epoch is not None else None,
    )


def _derive_threat(world: SubjectiveWorldState, contacts: ContactFacts) -> ThreatFacts:
    """Derive immediate pressure from disclosed hostile positions only."""
    epoch = world.current_epoch
    actor_uuid = epoch.actor_uuid if epoch is not None and world.session.is_my_turn else None
    actor = world.known_entities.get(actor_uuid) if actor_uuid is not None else None
    if actor_uuid is None or actor is None or actor.position is None:
        return ThreatFacts.model_construct(actor_uuid=actor_uuid)

    adjacent: list[str] = []
    nearest_uuid: Optional[str] = None
    nearest_distance: Optional[int] = None
    nearest_token: Optional[str] = None
    for hostile_uuid in contacts.visible_hostile_uuids:
        hostile = world.known_entities.get(hostile_uuid)
        if hostile is None or hostile.position is None:
            continue
        distance = _grid_distance_cells(actor.position, hostile.position)
        replay_token = entity_fact_replay_token(hostile)
        if distance <= 1:
            adjacent.append(hostile_uuid)
        if (
            nearest_distance is None
            or distance < nearest_distance
            or (distance == nearest_distance and nearest_token is not None and replay_token < nearest_token)
        ):
            nearest_uuid = hostile_uuid
            nearest_distance = distance
            nearest_token = replay_token
    return ThreatFacts.model_construct(
        actor_uuid=actor_uuid,
        adjacent_hostile_uuids=tuple(sorted(adjacent)),
        nearest_visible_hostile_uuid=nearest_uuid,
        nearest_visible_hostile_distance_cells=nearest_distance,
    )


def _derive_contacts(world: SubjectiveWorldState) -> ContactFacts:
    """Partition known entities using only explicit subjective knowledge."""
    controlled: list[str] = []
    visible: list[str] = []
    remembered: list[str] = []
    visible_allies: list[str] = []
    remembered_allies: list[str] = []
    visible_unknown_relationship: list[str] = []
    remembered_unknown_relationship: list[str] = []
    dead: list[str] = []
    unknown: list[str] = []
    entity_replay_tokens: dict[str, str] = {}
    known_hp_sort_keys: dict[str, tuple[bool, int]] = {}
    wounded_fractions: dict[str, float] = {}
    healthy_fractions: dict[str, float] = {}
    controlled_factions = {
        entity.faction
        for entity in world.known_entities.values()
        if entity.controlled and entity.faction is not None
    }
    for entity in world.known_entities.values():
        entity_replay_tokens[entity.uuid] = entity_fact_replay_token(entity)
        if entity.hp is None:
            known_hp_sort_keys[entity.uuid] = (True, 0)
            wounded_fractions[entity.uuid] = 0.0
            healthy_fractions[entity.uuid] = 0.0
        else:
            known_hp_sort_keys[entity.uuid] = (False, entity.hp)
            if entity.max_hp is None or entity.max_hp <= 0:
                wounded_fractions[entity.uuid] = 0.0
                healthy_fractions[entity.uuid] = 0.0
            else:
                wounded_fractions[entity.uuid] = max(
                    0.0,
                    min(1.0, (entity.max_hp - entity.hp) / entity.max_hp),
                )
                healthy_fractions[entity.uuid] = max(
                    0.0,
                    min(1.0, entity.hp / entity.max_hp),
                )
        if entity.controlled:
            controlled.append(entity.uuid)
        elif entity.is_dead is True:
            dead.append(entity.uuid)
        elif entity.knowledge_state is KnowledgeState.VISIBLE and entity.is_dead is not True:
            if entity.faction is None or not controlled_factions:
                visible_unknown_relationship.append(entity.uuid)
            elif entity.faction in controlled_factions:
                visible_allies.append(entity.uuid)
            else:
                visible.append(entity.uuid)
        elif entity.knowledge_state in {KnowledgeState.SEEN, KnowledgeState.REMEMBERED} and entity.is_dead is not True:
            if entity.faction is None or not controlled_factions:
                remembered_unknown_relationship.append(entity.uuid)
            elif entity.faction in controlled_factions:
                remembered_allies.append(entity.uuid)
            else:
                remembered.append(entity.uuid)
        else:
            unknown.append(entity.uuid)
    return ContactFacts.model_construct(
        controlled_entity_uuids=tuple(sorted(controlled)),
        visible_hostile_uuids=tuple(sorted(visible)),
        remembered_hostile_uuids=tuple(sorted(remembered)),
        visible_ally_uuids=tuple(sorted(visible_allies)),
        remembered_ally_uuids=tuple(sorted(remembered_allies)),
        visible_unknown_relationship_uuids=tuple(sorted(visible_unknown_relationship)),
        remembered_unknown_relationship_uuids=tuple(sorted(remembered_unknown_relationship)),
        known_dead_entity_uuids=tuple(sorted(dead)),
        unknown_contact_uuids=tuple(sorted(unknown)),
        entity_replay_tokens=FrozenDict(entity_replay_tokens),
        known_hp_sort_keys=FrozenDict(known_hp_sort_keys),
        wounded_fractions=FrozenDict(wounded_fractions),
        healthy_fractions=FrozenDict(healthy_fractions),
    )


def _derive_objects(world: SubjectiveWorldState) -> ObjectFacts:
    """Derive typed object state and door indexes."""
    known: list[str] = []
    closed: list[str] = []
    opened: list[str] = []
    for obj in world.known_objects.values():
        known.append(obj.uuid)
        is_open = _optional_bool(obj.state, "is_open")
        if is_open is False:
            closed.append(obj.uuid)
        elif is_open is True:
            opened.append(obj.uuid)
    return ObjectFacts.model_construct(
        known_object_uuids=tuple(sorted(known)),
        closed_door_uuids=tuple(sorted(closed)),
        open_door_uuids=tuple(sorted(opened)),
    )


def _derive_topology(world: SubjectiveWorldState) -> TopologyFacts:
    """Derive typed topology without treating unknown walkability as true."""
    known: list[str] = []
    hazards: set[tuple[int, int]] = set()
    slow: set[tuple[int, int]] = set()
    blocked: set[tuple[int, int]] = set()
    vision_blockers = {
        obj.position
        for obj in world.known_objects.values()
        if obj.knowledge_state is KnowledgeState.VISIBLE
        and obj.position is not None
        and (
            obj.state.get("blocks_vision") is True
            or obj.state.get("blocks_vision_field") is True
        )
    }
    for tile in world.known_tiles.values():
        known.append(tile.key)
        if tile.is_hazardous is True:
            hazards.add(tile.position)
        if tile.walking_cost is not None and tile.walking_cost > 5:
            slow.add(tile.position)
        if tile.walkable is False:
            blocked.add(tile.position)
    return TopologyFacts.model_construct(
        known_tile_keys=tuple(sorted(known)),
        hazardous_positions=frozenset(hazards),
        slow_positions=frozenset(slow),
        blocked_positions=frozenset(blocked),
        vision_blocker_positions=frozenset(vision_blockers),
    )


def _derive_navigation_history(
    world: SubjectiveWorldState,
) -> NavigationHistoryFacts:
    """Reduce the active actor's voluntary path from subjective typed logs."""
    epoch = world.current_epoch
    if epoch is None or not world.session.is_my_turn:
        return NavigationHistoryFacts.model_construct(
            actor_uuid=None,
            round_number=None,
            turn_index=None,
            same_turn_path=tuple(),
            visited_positions=frozenset(),
        )

    turn_start_index: Optional[int] = None
    for log_index in range(len(world.combat_logs) - 1, -1, -1):
        entry = world.combat_logs[log_index]
        if not isinstance(entry, Mapping) or entry.get("entry_type") != "turn_start":
            continue
        data = entry.get("data")
        if not isinstance(data, Mapping):
            continue
        if (
            entry.get("source_uuid") == epoch.actor_uuid
            and data.get("entity_uuid") == epoch.actor_uuid
            and data.get("round_number") == epoch.round_number
            and data.get("turn_index") == epoch.turn_index
        ):
            turn_start_index = log_index
            break

    same_turn_path: list[tuple[int, int]] = []
    if turn_start_index is not None:
        for entry in world.combat_logs[turn_start_index + 1:]:
            if (
                not isinstance(entry, Mapping)
                or entry.get("entry_type") != "movement"
                or entry.get("source_uuid") != epoch.actor_uuid
                or entry.get("success") is not True
            ):
                continue
            data = entry.get("data")
            if (
                not isinstance(data, Mapping)
                or data.get("entity_uuid") != epoch.actor_uuid
                or data.get("type") == "forced_movement"
            ):
                continue
            path = data.get("path")
            if not isinstance(path, list):
                continue
            for raw_position in path:
                if (
                    not isinstance(raw_position, (list, tuple))
                    or len(raw_position) != 2
                    or type(raw_position[0]) is not int
                    or type(raw_position[1]) is not int
                ):
                    continue
                position = (raw_position[0], raw_position[1])
                if not same_turn_path or same_turn_path[-1] != position:
                    same_turn_path.append(position)

    return NavigationHistoryFacts.model_construct(
        actor_uuid=epoch.actor_uuid,
        round_number=epoch.round_number,
        turn_index=epoch.turn_index,
        same_turn_path=tuple(same_turn_path),
        visited_positions=frozenset(same_turn_path),
    )


def _derive_affordances(world: SubjectiveWorldState) -> AffordanceIndex:
    """Index legal epoch rows while retaining the authoritative row objects."""
    epoch = world.current_epoch
    if epoch is None:
        return AffordanceIndex.model_construct(
            epoch_id=None,
            rows=tuple(),
            by_id={},
            row_ids_by_bucket={},
            row_ids_by_semantic_id={},
            row_ids_by_tag={},
            semantics_by_row_id={},
            target_effect_row_ids=tuple(),
            affected_entity_uuids_by_row_id={},
            primary_target_uuid_by_row_id={},
            target_geometry_key_by_row_id={},
            affected_set_groups=tuple(),
            affected_set_group_indices_by_tag={},
        )
    affordances = epoch.affordances
    rows = affordances.all_rows
    by_bucket = {
        bucket: tuple(row.row_id for row in bucket_rows)
        for bucket, bucket_rows in (
            ("entity_actions", affordances.entity_actions),
            ("position_actions", affordances.position_actions),
            ("self_actions", affordances.self_actions),
            ("object_actions", affordances.object_actions),
            ("special_commands", affordances.special_commands),
        )
        if bucket_rows
    }
    by_semantic_id: dict[str, list[str]] = {}
    by_tag: dict[ActionTag, list[str]] = {}
    semantics_by_row: dict[str, ActionSemantics] = {}
    target_effect_row_ids: list[str] = []
    rows_by_affected_set: dict[
        tuple[str, str, frozenset[str]],
        list[ActionAffordance],
    ] = {}
    affected_by_row: dict[str, frozenset[str]] = {}
    primary_by_row: dict[str, Optional[str]] = {}
    geometry_by_row: dict[str, tuple[tuple[int, int, int], ...]] = {}
    semantics_by_ref: dict[str, ActionSemantics] = {}
    for row in rows:
        semantics = semantics_by_ref.get(row.semantics_ref)
        if semantics is None:
            semantics = affordances.semantics_for(row)
            semantics_by_ref[row.semantics_ref] = semantics
        semantics_by_row[row.row_id] = semantics
        by_semantic_id.setdefault(semantics.semantic_id, []).append(row.row_id)
        if semantics.target_effects:
            target_effect_row_ids.append(row.row_id)
        for tag in semantics.tags:
            by_tag.setdefault(tag, []).append(row.row_id)

        affected: set[str] = set()
        primary_uuid: Optional[str] = None
        for target in row.targets:
            if target.target_uuid is not None:
                affected.add(target.target_uuid)
                if primary_uuid is None:
                    primary_uuid = target.target_uuid
            affected.update(target.affected_entity_uuids)
        affected_by_row[row.row_id] = frozenset(affected)
        primary_by_row[row.row_id] = primary_uuid
        if not semantics.tags & _AFFECTED_SET_GROUP_TAGS:
            continue
        geometry = tuple(
            (0, target.position[0], target.position[1])
            if target.position is not None
            else (1, 0, 0)
            for target in row.targets
        )
        geometry_by_row[row.row_id] = geometry
        source_scope = row.source_action_id or row.row_id
        rows_by_affected_set.setdefault(
            (source_scope, row.semantics_ref, affected_by_row[row.row_id]),
            [],
        ).append(row)
    affected_set_groups: list[AffordanceAffectedSetGroup] = []
    affected_group_indices_by_tag: dict[ActionTag, list[int]] = {}
    for (
        source_action_id,
        semantics_ref,
        affected_entity_uuids,
    ), grouped_rows in rows_by_affected_set.items():
        ordered_rows = sorted(
            grouped_rows,
            key=lambda row: (geometry_by_row[row.row_id], row.row_id),
        )
        group = AffordanceAffectedSetGroup.model_construct(
            source_action_id=source_action_id,
            semantics_ref=semantics_ref,
            canonical_row_id=ordered_rows[0].row_id,
            row_ids=tuple(row.row_id for row in ordered_rows),
            affected_entity_uuids=affected_entity_uuids,
        )
        group_index = len(affected_set_groups)
        affected_set_groups.append(group)
        semantics = semantics_by_row.get(group.canonical_row_id)
        if semantics is not None:
            for tag in semantics.tags:
                affected_group_indices_by_tag.setdefault(tag, []).append(group_index)
    return AffordanceIndex.model_construct(
        epoch_id=epoch.epoch_id,
        rows=rows,
        by_id=FrozenDict({row.row_id: row for row in rows}),
        row_ids_by_bucket=FrozenDict(by_bucket),
        row_ids_by_semantic_id=FrozenDict({key: tuple(value) for key, value in by_semantic_id.items()}),
        row_ids_by_tag=FrozenDict({key: tuple(value) for key, value in by_tag.items()}),
        semantics_by_row_id=FrozenDict(semantics_by_row),
        target_effect_row_ids=tuple(target_effect_row_ids),
        affected_entity_uuids_by_row_id=FrozenDict(affected_by_row),
        primary_target_uuid_by_row_id=FrozenDict(primary_by_row),
        target_geometry_key_by_row_id=FrozenDict(geometry_by_row),
        affected_set_groups=tuple(affected_set_groups),
        affected_set_group_indices_by_tag=FrozenDict({
            tag: tuple(indices)
            for tag, indices in affected_group_indices_by_tag.items()
        }),
    )


def _derive_capabilities(world: SubjectiveWorldState) -> CapabilityIndex:
    """Index actor-owned possibilities without promoting them to legal rows."""
    epoch = world.current_epoch
    if epoch is None:
        return CapabilityIndex.model_construct(
            rows=tuple(),
            by_id={},
            capability_ids_by_tag={},
            semantics_by_capability_id={},
        )
    rows = epoch.affordances.capabilities
    by_tag: dict[ActionTag, list[str]] = {}
    semantics_by_capability: dict[str, ActionSemantics] = {}
    for capability in rows:
        semantics = epoch.affordances.semantic_catalog.get(capability.semantics_ref)
        if semantics is None:
            continue
        semantics_by_capability[capability.capability_id] = semantics
        for tag in semantics.tags:
            by_tag.setdefault(tag, []).append(capability.capability_id)
    return CapabilityIndex.model_construct(
        rows=rows,
        by_id=FrozenDict({capability.capability_id: capability for capability in rows}),
        capability_ids_by_tag=FrozenDict({key: tuple(value) for key, value in by_tag.items()}),
        semantics_by_capability_id=FrozenDict(semantics_by_capability),
    )


def _derive_combat_memory(world: SubjectiveWorldState) -> CombatMemoryFacts:
    """Reduce bounded typed blocker episodes from visible subjective logs."""
    controlled = set(world.session.controlled_entity_uuids)
    source_log_count = len(world.combat_logs)
    window_start = max(0, source_log_count - _COMBAT_MEMORY_LOG_WINDOW)
    episodes_by_pair: dict[
        tuple[str, str],
        list[tuple[int, int, int, bool]],
    ] = {}
    for log_index, top_level in enumerate(
        world.combat_logs[window_start:],
        start=window_start,
    ):
        if not isinstance(top_level, Mapping):
            continue
        if top_level.get("source_uuid") not in controlled:
            continue
        applications: dict[tuple[str, str], list[bool]] = {}
        for target_uuid, effect_id, blocked in _typed_damage_applications(top_level):
            target = world.known_entities.get(target_uuid)
            if target is not None and target.is_dead is True:
                continue
            applications.setdefault((target_uuid, effect_id), []).append(blocked)
        for pair, blocked_rows in applications.items():
            blocked_count = sum(blocked_rows)
            episodes_by_pair.setdefault(pair, []).append(
                (
                    log_index,
                    blocked_count,
                    len(blocked_rows),
                    blocked_count == len(blocked_rows),
                )
            )

    hypotheses: list[TargetEffectBlockHypothesis] = []
    for (target_uuid, effect_id), episodes in episodes_by_pair.items():
        retained = episodes[-_COMBAT_MEMORY_EPISODES_PER_HYPOTHESIS:]
        blocked_episodes = sum(episode[3] for episode in retained)
        if blocked_episodes == 0:
            continue
        total_episodes = len(retained)
        hypotheses.append(TargetEffectBlockHypothesis.model_construct(
            target_uuid=target_uuid,
            effect_id=effect_id,
            blocked_episodes=blocked_episodes,
            total_episodes=total_episodes,
            blocked_applications=sum(episode[1] for episode in retained),
            total_applications=sum(episode[2] for episode in retained),
            episode_log_indices=tuple(episode[0] for episode in retained),
            latest_log_index=retained[-1][0],
            block_probability=(blocked_episodes + 1) / (total_episodes + 2),
        ))
    hypotheses.sort(
        key=lambda hypothesis: (
            -hypothesis.latest_log_index,
            target_effect_hypothesis_key(
                hypothesis.target_uuid,
                hypothesis.effect_id,
            ),
        )
    )
    retained_hypotheses = tuple(hypotheses[:_COMBAT_MEMORY_HYPOTHESIS_LIMIT])
    return CombatMemoryFacts.model_construct(
        source_log_count=source_log_count,
        hypotheses=retained_hypotheses,
        by_target_effect=FrozenDict({
            target_effect_hypothesis_key(hypothesis.target_uuid, hypothesis.effect_id): hypothesis
            for hypothesis in retained_hypotheses
        }),
    )


def _typed_damage_applications(
    top_level: Mapping[str, Any],
) -> tuple[tuple[str, str, bool], ...]:
    """Return structured damage applications without interpreting display text."""
    applications: list[tuple[str, str, bool]] = []
    pending: list[Mapping[str, Any]] = [top_level]
    while pending:
        entry = pending.pop()
        children = entry.get("sub_entries")
        if isinstance(children, list):
            pending.extend(
                child
                for child in reversed(children)
                if isinstance(child, Mapping)
            )
        if entry.get("entry_type") != "damage_taken":
            continue
        data = entry.get("data")
        target_uuid = entry.get("target_uuid")
        if not isinstance(data, Mapping) or not isinstance(target_uuid, str) or not target_uuid:
            continue
        effect_id = data.get("effect_id")
        if not isinstance(effect_id, str) or not effect_id:
            continue
        applications.append((target_uuid, effect_id, data.get("blocked") is True))
    return tuple(applications)


def _combat_logs_unchanged(
    world: SubjectiveWorldState,
    previous_world: Optional[SubjectiveWorldState],
) -> bool:
    """Return whether append-only visible log history retained its last row."""
    if previous_world is None or len(world.combat_logs) != len(previous_world.combat_logs):
        return False
    if not world.combat_logs:
        return True
    return world.combat_logs[-1] is previous_world.combat_logs[-1]


def _navigation_inputs_unchanged(
    world: SubjectiveWorldState,
    previous_world: Optional[SubjectiveWorldState],
) -> bool:
    """Return whether the actor turn identity and subjective logs are unchanged."""
    if previous_world is None or not _combat_logs_unchanged(world, previous_world):
        return False
    epoch = world.current_epoch
    previous_epoch = previous_world.current_epoch
    if epoch is None or previous_epoch is None:
        return epoch is previous_epoch and world.session.is_my_turn == previous_world.session.is_my_turn
    return (
        world.session.is_my_turn == previous_world.session.is_my_turn
        and epoch.actor_uuid == previous_epoch.actor_uuid
        and epoch.round_number == previous_epoch.round_number
        and epoch.turn_index == previous_epoch.turn_index
    )


def _mapping_items_identical(
    current: Mapping[str, object],
    previous: Optional[Mapping[str, object]],
) -> bool:
    """Return whether two keyed fact sets contain the same object instances."""
    if previous is None or current.keys() != previous.keys():
        return False
    return all(value is previous[key] for key, value in current.items())


def _same_object(current: object, previous: object) -> bool:
    """Return identity equality, including the shared None singleton."""
    return current is previous


def _optional_bool(values: Mapping[str, object], key: str) -> Optional[bool]:
    """Return a known boolean without coercing arbitrary object state."""
    value = values.get(key)
    return value if type(value) is bool else None


def _grid_distance_cells(origin: tuple[int, int], target: tuple[int, int]) -> int:
    """Return the engine-style floored Euclidean distance in cells."""
    return int(((origin[0] - target[0]) ** 2 + (origin[1] - target[1]) ** 2) ** 0.5)
