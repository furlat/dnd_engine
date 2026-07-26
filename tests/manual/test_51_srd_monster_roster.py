"""SRD-derived monster roster and arena coverage tests."""

from uuid import uuid4

from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.scenarios.ai_validation_arenas import create_ai_validation_arena, reset_ai_validation_arena_state


def _materialize_roster_fixture(
    creature_id: str,
    *,
    name: str | None = None,
    position: tuple[int, int] = (1, 1),
    faction: str = "monsters",
):
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=name or declaration.descriptor.display_name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.srd_roster.{creature_id}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def test_srd_roster_has_at_least_twenty_structured_monsters() -> None:
    """The validation roster should stay broad enough to fight overfitting."""
    ids = tuple(SRD_CREATURE_DECLARATIONS_BY_ID)
    challenge_tags = {
        tag
        for declaration in SRD_CREATURE_DECLARATIONS_BY_ID.values()
        for tag in declaration.descriptor.tags
        if tag.startswith("cr_")
    }

    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    assert set(ids) == set(SRD_CREATURE_RECIPES_BY_ID)
    assert challenge_tags >= {
        "cr_0",
        "cr_1_8",
        "cr_1_4",
        "cr_1_2",
        "cr_1",
        "cr_2",
        "cr_3",
        "cr_6",
    }


def test_each_srd_monster_builds_with_legal_actions() -> None:
    """Every SRD roster row should create a live entity with action rows."""
    for monster_id in SRD_CREATURE_RECIPES_BY_ID:
        reset_ai_validation_arena_state()
        monster = _materialize_roster_fixture(
            monster_id,
            name=f"Roster {monster_id}",
        )
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
