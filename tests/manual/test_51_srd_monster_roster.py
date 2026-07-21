"""SRD-derived monster roster and arena coverage tests."""

from dnd.monsters.srd_roster import (
    SRD_MONSTER_FACTORIES,
    create_srd_monster,
    list_srd_monster_specs,
)
from dnd.scenarios.ai_validation_arenas import create_ai_validation_arena, reset_ai_validation_arena_state


def test_srd_roster_has_at_least_twenty_structured_monsters() -> None:
    """The validation roster should stay broad enough to fight overfitting."""
    specs = list_srd_monster_specs()
    ids = [spec.monster_id for spec in specs]

    assert len(specs) >= 20
    assert len(ids) == len(set(ids))
    assert set(ids) == set(SRD_MONSTER_FACTORIES)
    assert {spec.challenge_rating for spec in specs} >= {"0", "1/8", "1/4", "1/2", "1", "2", "3", "6"}


def test_each_srd_monster_builds_with_legal_actions() -> None:
    """Every SRD roster row should create a live entity with action rows."""
    for monster_id in SRD_MONSTER_FACTORIES:
        reset_ai_validation_arena_state()
        monster = create_srd_monster(monster_id, name=f"Roster {monster_id}", position=(1, 1), faction="monsters")
        actions = monster.get_available_actions()
        total_rows = (
            len(actions.entity_actions)
            + len(actions.position_actions)
            + len(actions.self_actions)
            + len(actions.object_actions)
        )
        assert monster.get_hp() > 0
        assert monster.ac_bonus().normalized_score >= 8
        assert total_rows > 0


def test_new_srd_validation_arenas_build() -> None:
    """The new SRD validation arenas should be discoverable and constructible."""
    arena_ids = [
        "srd_low_cr_patrol",
        "srd_undead_crypt",
        "srd_goblinoid_warband",
        "srd_divine_cult_cell",
        "srd_elite_mercenary_contract",
    ]
    for arena_id in arena_ids:
        arena = create_ai_validation_arena(arena_id)
        assert arena.spec.arena_id == arena_id
        assert arena.hero.faction == "heroes"
        assert len(arena.monsters) >= 4
        assert all(monster.faction == "monsters" for monster in arena.monsters)
