"""Subjective combat-log projection: hidden steps, identities and damage evidence."""

from uuid import uuid4
import json

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    ConditionRemovedLogData,
    DamageTakenLogData,
    MovementLogData,
    MultiEntityLogData,
    SpellDamageLogData,
    StepMovementLogData,
    summarize_target_entries,
)
from dnd.core.events import TakeDamageEvent
from dnd.subjective_combat_log import project_combat_log
from dnd.types.event_facts import MovementTrajectory
from dnd.types.world import MovementProvocationPolicy


def test_known_enemy_movement_log_stops_at_last_perceived_step() -> None:
    """A known mover's parent log cannot reveal steps hidden after contact is lost."""
    hero_id, monster_id = uuid4(), uuid4()
    monster_name = "Observation Skeleton"

    visible_step = CombatLogEntry(
        entry_type=CombatLogEntryType.MOVEMENT,
        source_name=monster_name,
        source_uuid=str(monster_id),
        compact=f"{monster_name} steps to (3, 1)",
        verbose=f"{monster_name} (2, 1) -> (3, 1)",
        detailed=f"{monster_name} (2, 1) -> (3, 1) (step 1/3, 5ft)",
        data=StepMovementLogData(from_position=(2, 1), to_position=(3, 1),
            path_index=1, movement_cost=5.0, trajectory=MovementTrajectory.PATH,
            disclosed_path=((2, 1), (3, 1)), from_elevation_feet=0, to_elevation_feet=0,
            provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT, committed=True),
        perceiver_uuids={str(hero_id)},
        identified_entity_observer_uuids={str(monster_id): {str(hero_id)}},
        located_entity_observer_uuids={str(monster_id): {str(hero_id)}},
    )
    hidden_steps = [
        CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=monster_name,
            source_uuid=str(monster_id),
            compact=f"{monster_name} steps to {destination}",
            verbose=f"{monster_name} {origin} -> {destination}",
            detailed=f"{monster_name} {origin} -> {destination}",
            data=StepMovementLogData(from_position=origin, to_position=destination,
                path_index=index, movement_cost=5.0, trajectory=MovementTrajectory.PATH,
                disclosed_path=(origin, destination), from_elevation_feet=0, to_elevation_feet=0,
                provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT, committed=True),
            perceiver_uuids={str(monster_id)},
        )
        for index, origin, destination in (
            (2, (3, 1), (4, 1)),
            (3, (4, 1), (5, 1)),
        )
    ]
    parent_log = CombatLogEntry(
        entry_type=CombatLogEntryType.MOVEMENT,
        source_name=monster_name,
        source_uuid=str(monster_id),
        compact=f"{monster_name} moves 15ft to (5, 1)",
        verbose=f"{monster_name} moves (2, 1) -> (5, 1) (15ft)",
        detailed=f"{monster_name} moves (2, 1) -> (5, 1)\nPath: (2, 1) -> (3, 1) -> (4, 1) -> (5, 1)",
        data=MovementLogData(entity_name=monster_name, entity_uuid=str(monster_id),
            start_position=(2, 1), end_position=(5, 1), path=[(2, 1), (3, 1), (4, 1), (5, 1)],
            distance_feet=15, movement_cost=15),
        sub_entries=[visible_step, *hidden_steps],
        perceiver_uuids={str(hero_id), str(monster_id)},
        identified_entity_observer_uuids={str(monster_id): {str(hero_id)}},
    )
    projected = project_combat_log(parent_log,
        controlled_entity_uuids=frozenset({str(hero_id)}),
        observer_entity_uuids=frozenset({str(hero_id)}))
    assert projected is not None
    movement = CombatLogEntry.model_validate_json(projected.model_dump_json()).model_dump(mode="json")
    movement_text = json.dumps(movement)

    assert len(movement["sub_entries"]) == 1
    assert movement["data"]["observation_complete"] is False
    assert movement["data"]["observed_path_segments"] == []
    assert movement["data"]["start_position"] is None
    assert movement["data"]["end_position"] is None
    assert movement["data"]["path"] == []
    safe_step = movement["sub_entries"][0]
    assert safe_step["entry_type"] == CombatLogEntryType.MOVEMENT.value
    assert safe_step["source_uuid"] == str(monster_id)
    assert safe_step["data"] == {
        "kind": "unlocated_movement",
        "type": "movement",
        "observation_complete": False,
    }
    for hidden_position in ("(2, 1)", "(3, 1)", "(4, 1)", "(5, 1)"):
        assert hidden_position not in movement_text
    for hidden_position in ("[2, 1]", "[3, 1]", "[4, 1]", "[5, 1]"):
        assert hidden_position not in movement_text


def test_subjective_combat_logs_scrub_nested_hidden_identity_payloads() -> None:
    """Nested combat-log data cannot smuggle unknown entity identities."""
    hero_id, monster_id = uuid4(), uuid4()
    monster_name = "Observation Skeleton"
    child_log = CombatLogEntry(
        entry_type=CombatLogEntryType.SPELL_DAMAGE,
        source_name=monster_name,
        source_uuid=str(monster_id),
        target_name=monster_name,
        target_uuid=str(monster_id),
        compact=f"{monster_name} nested child",
        verbose=f"{monster_name} nested child verbose",
        detailed=f"{monster_name} nested child detailed",
        data=SpellDamageLogData(spell_name="Nested Leakage", target_name=monster_name,
            damage=7, damage_type="force"),
        sub_entries=[CombatLogEntry(entry_type=CombatLogEntryType.DAMAGE_TAKEN,
            source_name=monster_name, source_uuid=str(monster_id),
            target_name=monster_name, target_uuid=str(monster_id),
            compact=f"{monster_name} takes 7 force damage", verbose=monster_name, detailed=monster_name,
            data=DamageTakenLogData(target_name=monster_name, damage=7, damage_type="force",
                source_name=monster_name, effect_id=str(monster_id)),
            perceiver_uuids={str(hero_id)})],
        perceiver_uuids={str(hero_id)},
    )
    parent_log = CombatLogEntry(
        entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name=monster_name,
        source_uuid=str(monster_id),
        target_name=None,
        target_uuid=None,
        compact=f"{monster_name} uses nested leakage",
        verbose=f"{monster_name} uses nested leakage verbose",
        detailed=f"{monster_name} uses nested leakage detailed",
        data=MultiEntityLogData(action_name="Nested Leakage", caster_name=monster_name,
            total_targets=1, target_names=[monster_name], target_entry_indices=(0,)),
        sub_entries=[child_log],
        perceiver_uuids={str(hero_id)},
    )
    raw_log_text = parent_log.model_dump_json()
    assert str(monster_id) in raw_log_text
    assert monster_name in raw_log_text
    projected = project_combat_log(parent_log,
        controlled_entity_uuids=frozenset({str(hero_id)}),
        observer_entity_uuids=frozenset({str(hero_id)}))
    assert projected is not None
    logs_text = CombatLogEntry.model_validate_json(projected.model_dump_json()).model_dump_json()
    assert str(monster_id) not in logs_text
    assert monster_name not in logs_text
    assert "Unknown" in logs_text
    assert '"effect_id":null' in logs_text
    assert parent_log.model_dump_json() == raw_log_text


def test_multi_projectile_summary_ignores_non_target_causal_descendants() -> None:
    """Repeated direct targets are not replaced by targets of nested consequences."""
    def log(
        entry_type: CombatLogEntryType,
        target_name: str,
        target_uuid: str,
        *,
        damage: int | None = None,
        children: list[CombatLogEntry] | None = None,
    ) -> CombatLogEntry:
        data = (SpellDamageLogData(spell_name="Scorching Ray", target_name=target_name,
            damage=damage, damage_type="fire") if damage is not None else
            ConditionRemovedLogData(condition_name="Cleanup", reveals_target=False))
        return CombatLogEntry(
            entry_type=entry_type,
            source_name="Sorcerer",
            source_uuid="sorcerer",
            target_name=target_name,
            target_uuid=target_uuid,
            compact=f"{entry_type.value} -> {target_name}",
            verbose=f"{entry_type.value} -> {target_name}",
            detailed=f"{entry_type.value} -> {target_name}",
            data=data,
            sub_entries=list(children or []),
            identified_entity_observer_uuids={target_uuid: {"sorcerer"}},
        )

    hero_cleanup = log(CombatLogEntryType.CONDITION_REMOVED, "Hero", "hero")
    warrior_cleanup = log(
        CombatLogEntryType.CONDITION_REMOVED,
        "Skeleton Warrior",
        "warrior",
    )
    direct_children = [
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Warlock",
            "warlock",
            damage=12,
            children=[hero_cleanup],
        ),
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Archer",
            "archer",
            damage=4,
        ),
        log(
            CombatLogEntryType.SPELL_DAMAGE,
            "Skeleton Warlock",
            "warlock",
            damage=5,
            children=[warrior_cleanup],
        ),
    ]
    parent = CombatLogEntry(
        entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name="Sorcerer",
        source_uuid="sorcerer",
        compact="Sorcerer uses Scorching Ray",
        verbose="Sorcerer uses Scorching Ray",
        detailed="Sorcerer uses Scorching Ray",
        data=summarize_target_entries(MultiEntityLogData(action_name="Scorching Ray",
            caster_name="Sorcerer"), direct_children, (0, 1, 2)),
        sub_entries=direct_children,
    )

    original = parent.model_copy(deep=True)
    projected = project_combat_log(parent, controlled_entity_uuids=frozenset({"sorcerer"}),
        observer_entity_uuids=frozenset({"sorcerer"}))
    assert projected is not None and isinstance(projected.data, MultiEntityLogData)
    projected = CombatLogEntry.model_validate_json(projected.model_dump_json())
    assert parent == original
    assert parent.data.target_names == ["Skeleton Warlock", "Skeleton Archer", "Skeleton Warlock"]
    assert parent.data.per_target_damage == [12, 4, 5]
    assert projected.data.target_names == parent.data.target_names
    assert projected.data.per_target_damage == [12, 4, 5]
    assert projected.data.total_damage == 21 and projected.data.total_targets == 3
    assert projected.data.target_entry_indices == (0, 1, 2)
    assert len(parent.sub_entries) == 3
    assert parent.sub_entries[0].sub_entries == [hero_cleanup]
    assert parent.sub_entries[2].sub_entries == [warrior_cleanup]


def test_subjective_damage_evidence_respects_sanitization_and_perception() -> None:
    """Typed effect evidence cannot reveal hidden identities or unseen events."""
    hero_id, monster_id = uuid4(), uuid4()
    hero_name, monster_name = "Observation Hero", "Observation Skeleton"

    hidden_identity_log = TakeDamageEvent(
        source_entity_uuid=monster_id,
        target_entity_uuid=hero_id,
        source_entity_name=monster_name,
        target_entity_name=hero_name,
        total_damage=1,
        damages=[],
        effect_id=str(monster_id),
        use_register=False,
    ).generate_combat_log().model_copy(update={
        "perceiver_uuids": {str(hero_id)},
    })
    unperceived_effect_id = "tests.subjective_observation.unperceived_damage"
    unperceived_log = TakeDamageEvent(
        source_entity_uuid=monster_id,
        target_entity_uuid=monster_id,
        source_entity_name=monster_name,
        target_entity_name=monster_name,
        total_damage=1,
        damages=[],
        effect_id=unperceived_effect_id,
        use_register=False,
    ).generate_combat_log().model_copy(update={
        "perceiver_uuids": {str(monster_id)},
    })

    assert hidden_identity_log.data.effect_id == str(monster_id)
    assert unperceived_log.data.effect_id == unperceived_effect_id
    authority = dict(controlled_entity_uuids=frozenset({str(hero_id)}),
        observer_entity_uuids=frozenset({str(hero_id)}))
    perceived_damage = project_combat_log(hidden_identity_log, **authority)
    assert perceived_damage is not None
    assert project_combat_log(unperceived_log, **authority) is None
    perceived_damage = CombatLogEntry.model_validate_json(perceived_damage.model_dump_json())
    logs_json = perceived_damage.model_dump_json()
    assert perceived_damage.source_uuid == ""
    assert perceived_damage.source_name == "Unknown"
    assert isinstance(perceived_damage.data, DamageTakenLogData)
    assert perceived_damage.data.effect_id is None
    assert str(monster_id) not in logs_json
    assert monster_name not in logs_json
    assert unperceived_effect_id not in logs_json


