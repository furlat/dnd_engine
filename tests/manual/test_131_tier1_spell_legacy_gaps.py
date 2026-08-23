"""Restore only the tier-1 behaviors not covered after the d80 test rework.

Old cases already protected by maintained selectors are intentionally not
duplicated:

* creature factory defaults:
  ``test_95_creature_presentation_contract::
  test_preset_goblin_and_skeleton_keep_layered_presentation``
* ``EntityConfig.creature_type`` propagation:
  ``test_130_tier2_spells::test_blight_rejects_construct``
* Hold Person humanoid acceptance, paralysis, and concentration:
  ``test_chapter_15_spell_families::
  test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup``
* Hold Monster undead rejection, living-target acceptance, and paralysis:
  ``test_chapter_15_spell_families::
  test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup``

The selectors below cover the remaining thirteen logical groups from
``to_archive/examples/test_tier1_spells.py``.
"""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.conditions import Concentrating
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.check_events import (
    SavingThrowEvent,
)
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus
from dnd.entities.entity import Entity
from dnd.spells.conjuration import PoisonSpray
from dnd.spells.enchantment import HoldMonster, HoldPerson
from dnd.spells.evocation import Sunburst
from tests.engine.support import has_condition
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def test_creature_type_enum_completeness() -> None:
    """Old group 1: all fourteen canonical creature types remain available."""
    assert set(CreatureType) == {
        CreatureType.ABERRATION,
        CreatureType.BEAST,
        CreatureType.CELESTIAL,
        CreatureType.CONSTRUCT,
        CreatureType.DRAGON,
        CreatureType.ELEMENTAL,
        CreatureType.FEY,
        CreatureType.FIEND,
        CreatureType.GIANT,
        CreatureType.HUMANOID,
        CreatureType.MONSTROSITY,
        CreatureType.OOZE,
        CreatureType.PLANT,
        CreatureType.UNDEAD,
    }


def test_hold_person_rejects_non_humanoid() -> None:
    """Old group 4: Hold Person rejects a visible non-humanoid explicitly."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Hold Person Caster",
        (2, 3),
        "heroes",
        spell_slots={2: 1},
    )
    undead = create_spell_regression_actor(
        "Undead Target",
        (4, 3),
        "monsters",
        creature_type=CreatureType.UNDEAD,
    )
    Entity.materialize_all_navigation(max_distance=100)

    result = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=undead.uuid,
        cast_at_level=2,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.status_message is not None
    assert "humanoid" in result.status_message.lower()
    assert caster.action_economy.spell_slot_2.normalized_score == 1


@pytest.mark.parametrize(
    ("slot_level", "expected_targets"),
    [(5, 1), (6, 2), (7, 3), (8, 4), (9, 5)],
)
def test_hold_monster_multi_target_calculation(
    slot_level: int,
    expected_targets: int,
) -> None:
    """Old group 10: each slot above fifth adds one Hold Monster target."""
    spell = HoldMonster(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_max_targets_for_level() == expected_targets
    assert spell.get_multi_target_count() == expected_targets


def test_hold_monster_concentration_cleanup() -> None:
    """Old group 12: breaking concentration removes the full hold transform."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Hold Monster Caster",
        (2, 3),
        "heroes",
        spell_slots={5: 1},
    )
    target = create_spell_regression_actor(
        "Living Monster",
        (4, 3),
        "monsters",
        creature_type=CreatureType.MONSTROSITY,
    )
    force_save_result(target, "wisdom", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)

    with fixed_dice_faces(10):
        result = HoldMonster(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert has_condition(target, "Hold Monster")
    assert has_condition(target, "Paralyzed")
    concentration = caster.active_conditions.get("Concentrating")
    assert isinstance(concentration, Concentrating)

    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    assert not has_condition(target, "Hold Monster")
    assert not has_condition(target, "Paralyzed")
    assert not has_condition(target, "Incapacitated")
    assert target.action_economy.action_permission.normalized_score == 1


def _sunburst_cast(
    *,
    save_succeeds: bool,
    creature_type: CreatureType = CreatureType.HUMANOID,
) -> tuple[SpellEvent, Entity, int]:
    """Cast Sunburst outside its own sphere with deterministic save/damage."""
    reset_spell_regression_arena(30, 7)
    caster = create_spell_regression_actor(
        "Sunburst Caster",
        (1, 3),
        "heroes",
        spell_slots={8: 1},
    )
    target = create_spell_regression_actor(
        "Sunburst Target",
        (15, 3),
        "monsters",
        creature_type=creature_type,
    )
    force_save_result(target, "constitution", succeeds=save_succeeds)
    Entity.materialize_all_navigation(max_distance=200)
    hp_before = target.get_hp()
    save_faces = (18, 3) if creature_type is CreatureType.UNDEAD else (10,)

    with fixed_dice_faces(*save_faces, *([4] * 12)):
        result = Sunburst(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=8,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result, target, hp_before - target.get_hp()


def test_sunburst_full_damage_and_blind_on_fail() -> None:
    """Old group 13: failed save takes 12d6 and creates blindness."""
    result, target, damage = _sunburst_cast(save_succeeds=False)

    assert result.total_damage == 48
    assert result.damage_types == [DamageType.RADIANT]
    assert damage == 48
    assert has_condition(target, "Sunburst Blindness")
    assert has_condition(target, "Blinded")


def test_sunburst_half_damage_no_blind_on_success() -> None:
    """Old group 14: successful save takes half and creates no blindness."""
    result, target, damage = _sunburst_cast(save_succeeds=True)

    assert result.total_damage == 24
    assert damage == 24
    assert not has_condition(target, "Sunburst Blindness")
    assert not has_condition(target, "Blinded")


def test_sunburst_undead_gets_disadvantage() -> None:
    """Old group 15: undead save with disadvantage and use the lower d20."""
    _result, target, _damage = _sunburst_cast(
        save_succeeds=False,
        creature_type=CreatureType.UNDEAD,
    )

    saving_throws = [
        event
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if (
            isinstance(event, SavingThrowEvent)
            and event.target_entity_uuid == target.uuid
            and event.dice_roll is not None
        )
    ]
    assert saving_throws
    save_roll = saving_throws[-1].dice_roll
    assert save_roll is not None
    assert save_roll.advantage_status is AdvantageStatus.DISADVANTAGE
    assert save_roll.results == [18, 3]


def test_sunburst_sub_condition_cleanup() -> None:
    """Old group 16: removing the wrapper removes its Blinded child."""
    _result, target, _damage = _sunburst_cast(save_succeeds=False)
    assert has_condition(target, "Sunburst Blindness")
    assert has_condition(target, "Blinded")

    target.remove_condition("Sunburst Blindness")

    assert not has_condition(target, "Sunburst Blindness")
    assert not has_condition(target, "Blinded")


def _poison_spray_scene(
    *,
    distance_tiles: int,
    caster_level: int = 5,
) -> tuple[Entity, Entity, PoisonSpray]:
    """Create one visible Poison Spray target at an exact grid distance."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor("Poison Caster", (2, 3), "heroes")
    target = create_spell_regression_actor(
        "Poison Target",
        (2 + distance_tiles, 3),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=100)
    return caster, target, PoisonSpray(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=caster_level,
    )


def test_poison_spray_works_at_10ft() -> None:
    """Old group 17: exactly ten feet is a valid range."""
    caster, target, spell = _poison_spray_scene(distance_tiles=2)
    force_save_result(target, "constitution", succeeds=True)

    with fixed_dice_faces(10):
        result = spell.apply()

    assert caster.senses.get_feet_distance(target.position) == 10
    assert isinstance(result, SpellEvent)
    assert not result.canceled


def test_poison_spray_fails_at_15ft_with_range_error() -> None:
    """Old group 18: visible target at fifteen feet fails specifically on range."""
    caster, target, spell = _poison_spray_scene(distance_tiles=3)
    assert target.uuid in caster.senses.entities

    result = spell.apply()

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.status_message is not None
    assert "range" in result.status_message.lower()


def test_poison_spray_no_damage_on_save() -> None:
    """Old group 19: a successful Constitution save takes zero damage."""
    _caster, target, spell = _poison_spray_scene(distance_tiles=1)
    force_save_result(target, "constitution", succeeds=True)
    hp_before = target.get_hp()

    with fixed_dice_faces(10):
        result = spell.apply()

    assert isinstance(result, SpellEvent)
    assert result.save_success is True
    assert result.total_damage == 0
    assert target.get_hp() == hp_before


def test_poison_spray_deals_damage_on_failed_save() -> None:
    """Old group 20: failed level-5 save takes the full 2d12 poison."""
    _caster, target, spell = _poison_spray_scene(distance_tiles=1)
    force_save_result(target, "constitution", succeeds=False)
    hp_before = target.get_hp()

    with fixed_dice_faces(10, 6, 7):
        result = spell.apply()

    assert isinstance(result, SpellEvent)
    assert result.save_success is False
    assert result.total_damage == 13
    assert result.damage_types == [DamageType.POISON]
    assert target.get_hp() == hp_before - 13


@pytest.mark.parametrize(
    ("caster_level", "expected_dice"),
    [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)],
)
def test_poison_spray_cantrip_scaling(
    caster_level: int,
    expected_dice: int,
) -> None:
    """Old group 21: cantrip dice step at levels five, eleven, and seventeen."""
    spell = PoisonSpray(
        source_entity_uuid=uuid4(),
        caster_level=caster_level,
    )

    assert spell._get_cantrip_dice_count(caster_level) == expected_dice
