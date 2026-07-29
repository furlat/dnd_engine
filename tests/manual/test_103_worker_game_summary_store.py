"""Focused tests for the worker-local terminal game summary store."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

import server.game_summary_store as game_summary_store_module
from dnd.analytics import GameOutcomeResolution, summary_digest_is_valid
from dnd.blocks.action_economy import RechargeType
from dnd.content_system.creature_materialization import materialize_creature
from dnd.controller import Controller, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from server.game_summary_store import WorkerGameSummaryStore


@pytest.fixture(autouse=True)
def isolated_engine_state():
    """Reset global engine registries around every focused store test."""
    _reset_engine_state()
    yield
    _reset_engine_state()


def _reset_engine_state() -> None:
    """Clear global runtime state used by real encounter boundaries."""
    EventQueue.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 30, 12)


def _start_encounter(
    *,
    hero: Entity,
    monster: Entity,
    name: str,
) -> Encounter:
    """Start a deterministic two-side encounter using passive controllers."""
    encounter = Encounter(name=name, source_entity_uuid=uuid4())
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.start_encounter()
    return encounter


def _materialize_bestiary_creature(
    creature_id: str,
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Materialize one exact authored creature for objective replay projection."""
    runtime_entity_uuid = uuid4()
    return materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=runtime_entity_uuid,
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=(
                "tests.worker_summary."
                f"creature_{runtime_entity_uuid.hex}"
            ),
        ),
        possession_mode=(
            CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )


def _run_empty_encounter(name: str, offset: int) -> Encounter:
    """Run one terminal encounter for bounded-capacity checks."""
    hero = _materialize_bestiary_creature(
        "goblin",
        name=f"{name} Hero",
        position=(1, offset),
        faction=f"{name}-heroes",
    )
    monster = _materialize_bestiary_creature(
        "skeleton",
        name=f"{name} Monster",
        position=(4, offset),
        faction=f"{name}-monsters",
    )
    encounter = _start_encounter(hero=hero, monster=monster, name=name)
    encounter.end_encounter("bounded store test")
    return encounter


def test_reset_reattaches_after_event_queue_reset() -> None:
    """Store reset restores the callback that EventQueue.reset removes."""
    store = WorkerGameSummaryStore(max_summaries=2)
    EventQueue.reset()
    store.reset()
    store.ensure_attached()

    hero = _materialize_bestiary_creature(
        "goblin",
        name="Reset Hero",
        position=(1, 1),
        faction="heroes",
    )
    monster = _materialize_bestiary_creature(
        "skeleton",
        name="Reset Skeleton",
        position=(4, 1),
        faction="monsters",
    )
    encounter = _start_encounter(hero=hero, monster=monster, name="Reset Encounter")
    encounter.end_encounter("attachment restored")

    summary = store.get(encounter.uuid)
    assert summary is not None
    assert summary.game_id == str(encounter.uuid)
    assert summary.outcome.terminal_event_observed is True
    assert summary_digest_is_valid(summary)


def test_terminal_encounter_captures_typed_boundaries_and_summary(
) -> None:
    """A real terminal match yields complete typed evidence and a valid digest."""
    hosted_game_id = uuid4()
    store = WorkerGameSummaryStore(max_summaries=2)

    hero = _materialize_bestiary_creature(
        "goblin",
        name="Summary Hero",
        position=(2, 3),
        faction="heroes",
    )
    hero.action_economy.add_resource(
        "heroic_focus",
        maximum=2,
        recharge_type=RechargeType.LONG_REST,
    )
    monster = _materialize_bestiary_creature(
        "skeleton_warlock",
        name="Summary Warlock",
        position=(7, 3),
        faction="monsters",
    )
    monster.health.add_temporary_hit_points(3, monster.uuid)
    encounter = _start_encounter(hero=hero, monster=monster, name="Terminal Summary")
    store.bind_directory_game_id(encounter.uuid, hosted_game_id)
    store.capture_active_encounter(encounter)

    initial_event_cursor = EventQueue.event_cursor()
    damage = monster.get_max_hp() + 6
    monster.receive_damage(damage, DamageType.FORCE, hero.uuid)
    encounter.end_encounter("one faction remains")

    summary = store.get(hosted_game_id)
    assert summary is not None
    replay_capture = store.get_replay_capture(hosted_game_id)
    assert replay_capture is not None
    assert store.get(encounter.uuid) == summary
    assert store.get_replay_capture(encounter.uuid) == replay_capture
    assert summary.game_id == str(hosted_game_id)
    assert summary.encounter_uuid == encounter.uuid
    assert summary.terminal_cursor.event_cursor > initial_event_cursor
    assert summary.terminal_cursor.combat_log_cursor == len(encounter.combat_log)
    assert summary.completeness.issues == ()
    assert summary.outcome.resolution == GameOutcomeResolution.VICTORY
    assert summary.outcome.winning_side_ids == ("heroes",)
    assert summary.outcome.losing_side_ids == ("monsters",)

    entities = {entity.entity_uuid: entity for entity in summary.entities}
    hero_summary = entities[hero.uuid]
    monster_summary = entities[monster.uuid]
    assert hero_summary.initial is not None
    assert hero_summary.final is not None
    assert hero_summary.initial.position == (2, 3)
    assert hero_summary.initial.resources["heroic_focus"] == 2
    assert hero_summary.initial.resources["spell_slot_1"] == 0
    assert monster_summary.initial is not None
    assert monster_summary.final is not None
    assert monster_summary.initial.temporary_hit_points == 3
    assert monster_summary.initial.resources["spell_slot_1"] == 2
    assert monster_summary.initial.resources["spell_slot_2"] == 1
    assert monster_summary.final.temporary_hit_points == 0
    assert monster_summary.final.is_defeated is True
    assert monster_summary.final.life_state is LifeState.DEAD
    assert "dnd.conditions.Dead" not in monster_summary.final.condition_semantic_keys
    assert hero_summary.statistics.damage_dealt.applied > 0
    assert monster_summary.statistics.damage_taken.applied == (
        hero_summary.statistics.damage_dealt.applied
    )
    assert hero_summary.statistics.kills == 1
    assert monster_summary.statistics.deaths == 1
    assert summary_digest_is_valid(summary)
    assert replay_capture.encounter_uuid == str(encounter.uuid)
    assert replay_capture.generation_id == str(EventQueue.generation_id())
    assert replay_capture.seed.event_cursor == initial_event_cursor
    assert replay_capture.seed.world.equipment_by_entity
    assert replay_capture.terminal_event_cursor == summary.terminal_cursor.event_cursor
    assert (
        replay_capture.terminal_combat_log_cursor
        == summary.terminal_cursor.combat_log_cursor
    )

    caller_view_final = summary.entities[0].final
    assert caller_view_final is not None
    caller_view_final.resources["caller_mutation"] = 999
    retained = store.get(hosted_game_id)
    assert retained is not None
    assert all(
        "caller_mutation" not in entity.final.resources
        for entity in retained.entities
        if entity.final is not None
    )
    assert summary_digest_is_valid(retained)


def test_store_is_bounded_and_has_no_database_imports() -> None:
    """Old summaries are evicted and the worker store has no DB dependency."""
    store = WorkerGameSummaryStore(max_summaries=2)
    first = _run_empty_encounter("First", 1)
    second = _run_empty_encounter("Second", 4)
    third = _run_empty_encounter("Third", 7)

    assert store.get(first.uuid) is None
    assert store.get_replay_capture(first.uuid) is None
    assert store.get(second.uuid) is not None
    assert store.get_replay_capture(second.uuid) is not None
    assert store.get(third.uuid) is not None
    latest = store.get()
    assert latest is not None
    assert latest.encounter_uuid == third.uuid

    source_path = Path(game_summary_store_module.__file__)
    syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden_imports = {
        module_name
        for module_name in imported_modules
        if module_name in {"sqlite3", "aiosqlite", "game_directory"}
        or module_name.endswith(".game_directory")
    }
    assert forbidden_imports == set()
