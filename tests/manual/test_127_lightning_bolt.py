"""Active parity coverage for the ten archived Lightning Bolt behavior groups.

This replaces ``to_archive/examples/test_lightning_bolt.py`` with deterministic
rolls and hard assertions for every geometry case the archived test only
printed.
"""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.evocation import LightningBolt
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _cast_lightning_bolt(
    *,
    save_succeeds: bool,
    damage_face: int,
) -> tuple[SpellEvent, int]:
    """Cast one base Lightning Bolt with deterministic save and damage dice."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor(
        "Lightning Target",
        (7, 4),
        "monsters",
    )
    force_save_result(target, "dexterity", succeeds=save_succeeds)
    Entity.update_all_entities_senses(max_distance=150)
    hp_before = target.get_hp()

    with fixed_dice_faces(10, *([damage_face] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result, hp_before - target.get_hp()


def test_lightning_bolt_full_damage_on_failed_save() -> None:
    """Archived group 1: a failed Dexterity save takes the full 8d6."""
    event, damage = _cast_lightning_bolt(
        save_succeeds=False,
        damage_face=4,
    )

    assert event.total_damage == 32
    assert damage == 32


def test_lightning_bolt_half_damage_on_passed_save() -> None:
    """Archived group 2: a successful Dexterity save halves, rounding down."""
    event, damage = _cast_lightning_bolt(
        save_succeeds=True,
        damage_face=5,
    )

    assert event.total_damage == 20
    assert damage == 20


@pytest.mark.parametrize(
    ("slot_level", "expected_dice"),
    [(3, 8), (4, 9), (5, 10), (6, 11), (9, 14)],
)
def test_lightning_bolt_upcast(
    slot_level: int,
    expected_dice: int,
) -> None:
    """Archived group 3: Lightning Bolt gains one d6 per slot above third."""
    spell = LightningBolt(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_damage_dice_count() == expected_dice


def test_lightning_bolt_hits_line_targets() -> None:
    """Archived group 4: every creature on the eastbound line is damaged."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    targets = [
        create_spell_regression_actor(f"Line {x}", (x, 4), "monsters")
        for x in (6, 10, 14)
    ]
    for target in targets:
        force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    hp_before = {target.uuid: target.get_hp() for target in targets}

    with fixed_dice_faces(*([10, *([4] * 8)] * len(targets))):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert result.total_targets == 3
    assert all(
        target.get_hp() == hp_before[target.uuid] - 32
        for target in targets
    )


def test_lightning_bolt_misses_off_line() -> None:
    """Archived group 5: an adjacent off-line creature is excluded."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    on_line = create_spell_regression_actor("On line", (8, 4), "monsters")
    off_line = create_spell_regression_actor("Off line", (8, 6), "monsters")
    force_save_result(on_line, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    on_line_hp = on_line.get_hp()
    off_line_hp = off_line.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert on_line.get_hp() == on_line_hp - 32
    assert off_line.get_hp() == off_line_hp


def test_lightning_bolt_wall_stops_line() -> None:
    """Archived group 6: a wall clips the line before creatures behind it."""
    reset_spell_regression_arena(28, 9)
    get_map().set_tile(10, 4, walkable=False, visible=False, name="Wall")
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    before = create_spell_regression_actor("Before wall", (8, 4), "monsters")
    after = create_spell_regression_actor("After wall", (12, 4), "monsters")
    force_save_result(before, "dexterity", succeeds=False)
    force_save_result(after, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    before_hp = before.get_hp()
    after_hp = after.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert before.get_hp() == before_hp - 32
    assert after.get_hp() == after_hp


def test_lightning_bolt_caster_excluded() -> None:
    """Archived group 7: the line's origin never damages its caster."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("Line target", (8, 4), "monsters")
    force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    caster_hp = caster.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert caster.get_hp() == caster_hp


def test_lightning_bolt_long_range() -> None:
    """Archived group 8: a target ninety-five feet down the line is hit."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("At 95 feet", (21, 4), "monsters")
    force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    hp_before = target.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert target.get_hp() == hp_before - 32


def test_lightning_bolt_diagonal_direction() -> None:
    """Archived group 9: diagonal geometry hits only the selected ray."""
    reset_spell_regression_arena(20, 20)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 2),
        "heroes",
        spell_slots={3: 1},
    )
    diagonal = create_spell_regression_actor("Diagonal", (8, 8), "monsters")
    off_diagonal = create_spell_regression_actor("Off diagonal", (8, 2), "monsters")
    force_save_result(diagonal, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    diagonal_hp = diagonal.get_hp()
    off_diagonal_hp = off_diagonal.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(15, 15),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert diagonal.get_hp() == diagonal_hp - 32
    assert off_diagonal.get_hp() == off_diagonal_hp


def test_lightning_bolt_both_save_outcomes_are_reported() -> None:
    """Archived group 10: one line records both save branches deterministically."""
    reset_spell_regression_arena(28, 9)
    caster = create_spell_regression_actor(
        "Lightning Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    failing = create_spell_regression_actor("Failing", (7, 4), "monsters")
    passing = create_spell_regression_actor("Passing", (9, 4), "monsters")
    force_save_result(failing, "dexterity", succeeds=False)
    force_save_result(passing, "dexterity", succeeds=True)
    Entity.update_all_entities_senses(max_distance=150)

    with fixed_dice_faces(*([10, *([4] * 8)] * 2)):
        result = LightningBolt(
            source_entity_uuid=caster.uuid,
            end_position=(24, 4),
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert result.combat_log is not None
    save_results = {
        entry.data["save_success"]
        for entry in result.combat_log.sub_entries
    }
    assert save_results == {False, True}
