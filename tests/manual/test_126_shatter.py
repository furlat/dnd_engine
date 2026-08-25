"""Active parity coverage for the eight archived Shatter behavior groups.

This is the maintained replacement for ``to_archive/examples/test_shatter.py``.
"""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.entities.entity import Entity
from dnd.spells.evocation import Shatter
from dnd.types.materials import Material, TileSurface
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _cast_shatter(
    *,
    save_succeeds: bool,
    damage_face: int,
) -> tuple[SpellEvent, int]:
    """Cast one base-level Shatter with a deterministic save and damage roll."""
    reset_spell_regression_arena(16, 9)
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    target = create_spell_regression_actor(
        "Shatter Target",
        (7, 4),
        "monsters",
    )
    force_save_result(target, "constitution", succeeds=save_succeeds)
    Entity.materialize_all_navigation(max_distance=100)

    hp_before = target.get_hp()
    with fixed_dice_faces(10, damage_face, damage_face, damage_face):
        result = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result, hp_before - target.get_hp()


def test_shatter_full_damage_on_failed_save() -> None:
    """Archived group 1: a failed Constitution save takes the full 3d8."""
    event, damage = _cast_shatter(save_succeeds=False, damage_face=4)

    assert event.total_damage == 12
    assert damage == 12


def test_shatter_half_damage_on_passed_save() -> None:
    """Archived group 2: a successful Constitution save halves, rounding down."""
    event, damage = _cast_shatter(save_succeeds=True, damage_face=5)

    assert event.total_damage == 7
    assert damage == 7


@pytest.mark.parametrize(
    ("slot_level", "expected_dice"),
    [(2, 3), (3, 4), (4, 5), (5, 6), (9, 10)],
)
def test_shatter_upcast(slot_level: int, expected_dice: int) -> None:
    """Archived group 3: Shatter gains one d8 per slot above second."""
    spell = Shatter(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_damage_dice_count() == expected_dice


def test_shatter_smaller_radius() -> None:
    """Archived group 4: the ten-foot sphere includes two tiles, not three."""
    reset_spell_regression_arena(16, 9)
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    center = create_spell_regression_actor("Center", (7, 4), "monsters")
    near = create_spell_regression_actor("Near", (8, 4), "monsters")
    far = create_spell_regression_actor("Far", (10, 4), "monsters")
    force_save_result(center, "constitution", succeeds=False)
    force_save_result(near, "constitution", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)
    hp_before = {actor.uuid: actor.get_hp() for actor in (center, near, far)}

    with fixed_dice_faces(*([10, 4, 4, 4] * 2)):
        result = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=center.position,
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert center.get_hp() == hp_before[center.uuid] - 12
    assert near.get_hp() == hp_before[near.uuid] - 12
    assert far.get_hp() == hp_before[far.uuid]


def test_shatter_range_validation() -> None:
    """Archived group 5: sixty feet succeeds and sixty-five feet is rejected."""
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    in_range = create_spell_regression_actor("At 60 feet", (14, 4), "monsters")
    Entity.materialize_all_navigation(max_distance=100)

    out_of_range = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(15, 4),
        cast_at_level=2,
    ).apply()
    assert isinstance(out_of_range, SpellEvent)
    assert out_of_range.canceled
    assert out_of_range.status_message is not None
    assert "out of range" in out_of_range.status_message.lower()

    force_save_result(in_range, "constitution", succeeds=False)
    with fixed_dice_faces(10, 3, 3, 3):
        at_limit = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=in_range.position,
            cast_at_level=2,
        ).apply()
    assert isinstance(at_limit, SpellEvent)
    assert not at_limit.canceled


def test_shatter_wall_blocks() -> None:
    """Archived group 6: sphere propagation cannot damage through a wall."""
    reset_spell_regression_arena(14, 9)
    get_map().set_tile(
        8,
        4,
        surface=TileSurface(base_material=Material.STONE),
        walkable=False,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    visible = create_spell_regression_actor("Visible", (7, 4), "monsters")
    blocked = create_spell_regression_actor("Blocked", (9, 4), "monsters")
    force_save_result(visible, "constitution", succeeds=False)
    force_save_result(blocked, "constitution", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)
    visible_hp = visible.get_hp()
    blocked_hp = blocked.get_hp()

    with fixed_dice_faces(10, 4, 4, 4):
        result = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=visible.position,
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert visible.get_hp() == visible_hp - 12
    assert blocked.get_hp() == blocked_hp


def test_shatter_los_to_center() -> None:
    """Archived group 7: the caster must see the sphere's origin."""
    reset_spell_regression_arena(14, 9)
    get_map().set_tile(
        5,
        4,
        surface=TileSurface(base_material=Material.STONE),
        walkable=False,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    create_spell_regression_actor("Hidden Target", (7, 4), "monsters")
    Entity.materialize_all_navigation(max_distance=100)

    result = Shatter(
        source_entity_uuid=caster.uuid,
        end_position=(7, 4),
        cast_at_level=2,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    assert result.status_message == "Position (7, 4) not visible"


def test_shatter_both_save_outcomes_are_reported() -> None:
    """Archived group 8: one cast records both save branches without randomness."""
    reset_spell_regression_arena(14, 9)
    caster = create_spell_regression_actor(
        "Shatter Caster",
        (2, 4),
        "heroes",
        spell_slots={2: 1},
    )
    failing = create_spell_regression_actor("Failing", (7, 4), "monsters")
    passing = create_spell_regression_actor("Passing", (8, 4), "monsters")
    force_save_result(failing, "constitution", succeeds=False)
    force_save_result(passing, "constitution", succeeds=True)
    Entity.materialize_all_navigation(max_distance=100)

    with fixed_dice_faces(*([10, 4, 4, 4] * 2)):
        result = Shatter(
            source_entity_uuid=caster.uuid,
            end_position=failing.position,
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert result.combat_log is not None
    save_results = {
        entry.data["save_success"]
        for entry in result.combat_log.sub_entries
    }
    assert save_results == {False, True}
