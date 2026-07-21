import random

from dnd.entity import Entity
from dnd.scenarios.evaluation.assembler import (
    assemble_composed_arena,
    assemble_generic_side_duel,
)


SIDE_A_SLOTS = ((2, 4), (2, 7), (2, 10))
SIDE_B_SLOTS = ((12, 4), (12, 7), (12, 10))


def test_generic_duel_assembles_two_multi_actor_monster_parties() -> None:
    random.seed(20260718)
    arena = assemble_generic_side_duel(
        "monsters.skeleton_trio",
        "monsters.goblin_water_cell",
        "battlefield.open_floor_bright",
        side_a_slots=SIDE_A_SLOTS,
        side_b_slots=SIDE_B_SLOTS,
        opening_faction="side_b",
    )

    assert len(arena.side_a) == 3
    assert len(arena.side_b) == 3
    assert tuple(actor.position for actor in arena.side_a) == SIDE_A_SLOTS
    assert tuple(actor.position for actor in arena.side_b) == SIDE_B_SLOTS
    assert {actor.faction for actor in arena.side_a} == {"side_a"}
    assert {actor.faction for actor in arena.side_b} == {"side_b"}
    assert set(arena.encounter.combatants) == {
        actor.uuid for actor in (*arena.side_a, *arena.side_b)
    }
    assert set(arena.controllers) == set(arena.encounter.combatants)
    assert arena.encounter.get_current_entity().faction == "side_b"
    assert all(actor.senses.visible for actor in (*arena.side_a, *arena.side_b))

    assert arena.hero is arena.side_a[0]
    assert arena.monsters == arena.side_b


def test_mirrored_configuration_keeps_roles_and_names_isolated_by_side() -> None:
    arena = assemble_generic_side_duel(
        "monsters.skeleton_trio",
        "monsters.skeleton_trio",
        "battlefield.open_floor_bright",
        side_a_slots=SIDE_A_SLOTS,
        side_b_slots=SIDE_B_SLOTS,
        actor_names={
            "side_a:monster_1": "A Vanguard",
            "side_b:monster_1": "B Vanguard",
        },
    )

    assert arena.side_a[0].name == "A Vanguard"
    assert arena.side_b[0].name == "B Vanguard"
    assert arena.side_a[0].position == SIDE_A_SLOTS[0]
    assert arena.side_b[0].position == SIDE_B_SLOTS[0]
    assert arena.side_a[0].uuid != arena.side_b[0].uuid


def test_existing_hero_monster_assembly_populates_neutral_side_views() -> None:
    arena = assemble_composed_arena(
        "hero.sorcerer_l5_standard_torch",
        "monsters.skeleton_trio",
        "battlefield.open_floor_bright",
        "neutral.battlefield.open_floor_bright",
    )

    assert arena.side_a == (arena.hero,)
    assert arena.side_b == arena.monsters
    assert all(Entity.get(actor.uuid) is actor for actor in (*arena.side_a, *arena.side_b))
