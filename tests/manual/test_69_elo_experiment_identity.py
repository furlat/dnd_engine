"""Experimental-identity checks for side order and played-world manifests."""

import random

from ai.evaluation.arena_manifest import build_arena_manifest
from ai.external_selfplay import run_external_selfplay
from dnd.entity import Entity
from dnd.scenarios.ai_validation_arenas import create_ai_validation_arena


def test_side_order_forces_opening_faction_without_rerolling_initiative() -> None:
    previous_state = random.getstate()
    try:
        random.seed(17)
        hero_first = create_ai_validation_arena(
            "standard_skeleton_doors",
            opening_faction="heroes",
        )
        hero_rolls = _initiative_by_name(hero_first)
        hero_opener = Entity.get(hero_first.encounter.initiative_order[0])

        random.seed(17)
        monster_first = create_ai_validation_arena(
            "standard_skeleton_doors",
            opening_faction="monsters",
        )
        monster_rolls = _initiative_by_name(monster_first)
        monster_opener = Entity.get(monster_first.encounter.initiative_order[0])
    finally:
        random.setstate(previous_state)

    assert hero_rolls == monster_rolls
    assert hero_opener is not None and hero_opener.faction == "heroes"
    assert monster_opener is not None and monster_opener.faction == "monsters"


def test_selfplay_observer_captures_actual_external_controller_manifest() -> None:
    manifests = []

    result = run_external_selfplay(
        "standard_skeleton_doors",
        max_commands=1,
        hero_first=False,
        random_seed=23,
        arena_observer=lambda arena: manifests.append(build_arena_manifest(arena)),
    )

    assert result.command_count == 1
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest.opening_faction == "monsters"
    assert manifest.initiative_order[0]["faction"] == "monsters"
    assert {
        row.controller_type
        for roster in manifest.entity_rosters.values()
        for row in roster
    } == {"external_ai"}


def test_roster_hash_ignores_opening_order_and_arena_placement_state() -> None:
    previous_state = random.getstate()
    try:
        random.seed(31)
        hero_arena = create_ai_validation_arena(
            "standard_skeleton_doors",
            opening_faction="heroes",
        )
        hero_manifest = build_arena_manifest(hero_arena)
        random.seed(31)
        monster_arena = create_ai_validation_arena(
            "standard_skeleton_doors",
            opening_faction="monsters",
        )
        monster_manifest = build_arena_manifest(monster_arena)
    finally:
        random.setstate(previous_state)

    assert hero_manifest.opening_faction == "heroes"
    assert monster_manifest.opening_faction == "monsters"
    assert hero_manifest.roster_hash_by_side == monster_manifest.roster_hash_by_side


def _initiative_by_name(arena) -> dict[str, tuple[int, int]]:
    rows: dict[str, tuple[int, int]] = {}
    for combatant in arena.encounter.combatants.values():
        entity = combatant.entity
        assert entity is not None
        rows[entity.name] = (combatant.initiative_roll, combatant.initiative_total)
    return rows
