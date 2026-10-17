"""Fixed faces control native spell riders, selection pools and weapon rerolls."""

import random
from uuid import UUID

import pytest

from dnd.core.values import ValueRead, read_value
from dnd.actions import Attack
from dnd.blocks.health import HealthConfig
from dnd.classes.fighter import GreatWeaponFighting
from dnd.conditions import Blinded, Unconscious
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.aoe import objective_footprint
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, Dice, RollType, fixed_dice_faces, roll_die_face
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.spells.abjuration import Resistance
from dnd.spells.divination import Guidance
from dnd.spells.enchantment import Bane, Bless, Sleep
from dnd.spells.evocation import PrismaticSpray
from dnd.spells.illusion import ColorSpray
from tests.engine.test_roster_support_spells import actor
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - fixture export
from tests.manual.spell_regression_support import force_save_result


def reading(value, target_uuid=None):
    """The value read by its owner against an optional target."""
    return read_value(value, ValueRead(value.source_entity_uuid, target_uuid))


@pytest.fixture(autouse=True, params=[0, 1], ids=["seed0", "seed1"])
def seeded_rng(request):
    previous = random.getstate()
    random.seed(request.param)
    yield
    random.setstate(previous)


def bonus(owner):
    return ModifiableValue.create(
        source_entity_uuid=owner.uuid, value_name="Dice coverage", base_value=0,
    )


def ordinary_roll(owner, *, sides=20, count=1, roll_type=RollType.HEAL, **kwargs):
    return Dice(count=count, value=sides, bonus=reading(bonus(owner)), roll_type=roll_type, **kwargs).roll


def d20(owner, category):
    roll, event = owner.roll_d20_event(
        reading(bonus(owner)), category,
        **({"ability_name": "wisdom"} if category is RollType.SAVE else
           {"skill_name": "perception"} if category is RollType.CHECK else {}),
    )
    event.phase_to(EventPhase.COMPLETION)
    return roll, event


def cast(spell_type, caster, target=None, **kwargs):
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell_type(source_entity_uuid=caster.uuid,
                        target_entity_uuid=target.uuid if target else None,
                        alt_skip_slot=True, **kwargs).apply()
    assert result is not None
    assert not result.canceled, result.status_message
    return result


@pytest.mark.parametrize("spell_type,sign,categories", [
    (Bless, 1, (RollType.ATTACK, RollType.SAVE)),
    (Bane, -1, (RollType.ATTACK, RollType.SAVE)),
    (Guidance, 1, (RollType.CHECK,)),
    (Resistance, 1, (RollType.SAVE,)),
])
@pytest.mark.parametrize("category", [RollType.ATTACK, RollType.SAVE, RollType.CHECK])
def test_d4_riders_use_fixed_faces_only_for_their_roll_categories(game, spell_type, sign, categories, category):
    caster = actor(game)
    recipient = actor(game, "Recipient", (3, 2), "foes" if spell_type is Bane else "heroes")
    force_save_result(recipient, "charisma", succeeds=False)
    cast(spell_type, caster, recipient)
    eligible = category in categories
    with fixed_dice_faces(10, *((3,) if eligible else ()), 7):
        rolled, event = d20(recipient, category)
        following = ordinary_roll(recipient)
    assert event.original_roll.results == [10]
    assert rolled.total == 10 + (sign * 3 if eligible else 0)
    assert [row.handler_name for row in event.roll_modifications] == ([spell_type.__name__] if eligible else [])
    assert following.results == [7]
    one_use = spell_type in (Guidance, Resistance)
    assert (spell_type.__name__ in recipient.active_conditions) is (not one_use or not eligible)
    if one_use and eligible:
        assert "Concentrating" not in caster.active_conditions
        with fixed_dice_faces(11):
            second, second_event = d20(recipient, category)
        assert second.total == 11
        assert not second_event.roll_modifications


def test_bless_bane_and_resistance_compose_through_native_handlers(game):
    caster = actor(game)
    baner = actor(game, "Baner", (2, 3), "foes")
    protector = actor(game, "Protector", (3, 3))
    recipient = actor(game, "Recipient", (3, 2))
    force_save_result(recipient, "charisma", succeeds=False)
    cast(Bless, caster, recipient)
    cast(Bane, baner, recipient)
    cast(Resistance, protector, recipient)
    with fixed_dice_faces(10, 2, 3, 4, 7):
        rolled, event = d20(recipient, RollType.SAVE)
        following = ordinary_roll(recipient)
    assert [row.handler_name for row in event.roll_modifications] == ["Bless", "Bane", "Resistance"]
    assert rolled.total == 10 + 2 - 3 + 4
    assert following.results == [7]
    assert {"Bless", "Bane"} <= recipient.active_conditions.keys()
    assert "Resistance" not in recipient.active_conditions
    assert "Concentrating" not in protector.active_conditions


def pool_recipient(game, identity, name, position, hp):
    recipient = Entity.create(UUID(int=identity), name, config=EntityConfig(
        health=HealthConfig(max_hit_points_bonus=200), faction="foes",
    ))
    recipient.compose_entity()
    game.deploy_entity(recipient, position)
    recipient.receive_damage(recipient.get_hp() - hp, DamageType.FORCE, recipient.uuid)
    return recipient


@pytest.mark.parametrize("spell_type,base_count,sides", [(Sleep, 5, 8), (ColorSpray, 6, 10)])
@pytest.mark.parametrize("level", [1, 3])
def test_hp_pools_use_fixed_base_and_upcast_faces_and_cache_selection(game, spell_type, base_count, sides, level):
    caster = actor(game)
    count = base_count + 2 * (level - 1)
    total = count * 2
    first = pool_recipient(game, 1, "Exact fit", (3, 3), total)
    later = pool_recipient(game, 2, "Too expensive", (4, 4), total + 1)
    immune = pool_recipient(game, 3, "Immune", (4, 3), 1)
    immune.add_condition_immunity("Charmed" if spell_type is Sleep else "Blinded", immunity_name="Pool filter")
    sightless = pool_recipient(game, 4, "Excluded state", (3, 4), 1)
    exclusion = Unconscious if spell_type is Sleep else Blinded
    sightless.add_condition(exclusion(source_entity_uuid=sightless.uuid, target_entity_uuid=sightless.uuid))
    Entity.update_all_entities_senses()
    spell = spell_type(source_entity_uuid=caster.uuid, end_position=(5, 5), cast_at_level=level, alt_skip_slot=True)
    assert spell.get_hp_pool_dice() == (count, sides)
    with fixed_dice_faces(*([2] * count), 7):
        selected = spell.get_all_targets()
        repeated = spell.get_all_targets()
        following = ordinary_roll(caster)
    assert selected == repeated == [first.uuid]
    assert spell.aoe_shape is not None
    area = objective_footprint(spell.aoe_shape, (5, 5), caster.position)
    assert {first.position, later.position, immune.position, sightless.position} <= area
    assert later.uuid not in selected and immune.uuid not in selected and sightless.uuid not in selected
    assert spell.hp_pool_rolled == total and spell.hp_pool_remaining == 0
    assert following.results == [7]
    with fixed_dice_faces():
        result = spell.apply()
    assert result is not None and not result.canceled
    assert spell_type.__name__.replace("ColorSpray", "Color Spray") in first.active_conditions


@pytest.mark.parametrize("spell_type,count", [(Sleep, 5), (ColorSpray, 6)])
def test_hp_pool_equal_hp_order_is_preserved_with_explicit_identities(game, spell_type, count):
    caster = actor(game)
    lower = pool_recipient(game, 11, "Lower UUID", (3, 2), count)
    higher = pool_recipient(game, 12, "Higher UUID", (4, 2), count)
    Entity.update_all_entities_senses()
    spell = spell_type(source_entity_uuid=caster.uuid, end_position=(5, 2), alt_skip_slot=True)
    with fixed_dice_faces(*([1] * count)):
        selected = spell.get_all_targets()
    assert selected == [lower.uuid]
    assert higher.uuid not in selected


def prismatic_target(game):
    caster = actor(game)
    target = actor(game, "Target", (4, 2), "foes")
    for ability in ("dexterity", "constitution", "wisdom"):
        force_save_result(target, ability, succeeds=False)
    return caster, target


def committed_damage_types(target):
    return [event.damage_type for event in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED)
            if event.target_entity_uuid == target.uuid and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("color", [1, 2, 3, 4, 5, 6, 7])
def test_prismatic_fixed_colors_produce_their_native_damage_or_conditions(game, color):
    caster, target = prismatic_target(game)
    before = target.get_hp()
    with fixed_dice_faces(color, 10, *(([2] * 10) if color <= 5 else []), 7):
        cast(PrismaticSpray, caster, end_position=target.position)
        following = ordinary_roll(caster)
    assert following.results == [7]
    types = {1: DamageType.FIRE, 2: DamageType.ACID, 3: DamageType.LIGHTNING,
             4: DamageType.POISON, 5: DamageType.COLD}
    assert committed_damage_types(target) == ([types[color]] if color <= 5 else [])
    assert before - target.get_hp() == (20 if color <= 5 else 0)
    assert ("Prismatic Restrained" in target.active_conditions) is (color == 6)
    assert ("Blinded" in target.active_conditions) is (color == 7)


@pytest.mark.parametrize("choices", [(1, 2), (1, 1, 2)])
def test_prismatic_two_colors_preserves_distinct_d7_choices(game, choices):
    caster, target = prismatic_target(game)
    before = target.get_hp()
    with fixed_dice_faces(8, *choices, 10, *([2] * 10), 10, *([3] * 10), 7):
        cast(PrismaticSpray, caster, end_position=target.position)
        following = ordinary_roll(caster)
    assert committed_damage_types(target) == [DamageType.FIRE, DamageType.ACID]
    assert before - target.get_hp() == 50
    assert following.results == [7]


def test_prismatic_exhausted_color_choice_does_not_fall_back_to_randomness(game):
    caster, target = prismatic_target(game)
    with fixed_dice_faces(8, 1, 1), pytest.raises(RuntimeError, match="No fixed dice face"):
        cast(PrismaticSpray, caster, end_position=target.position)


@pytest.mark.parametrize("weapon_id,offhand,slot,faces,expected", [
    ("weapon.greatsword", None, WeaponSlot.MELEE_MAIN, (1, 2, 5, 1), [5, 1]),
    ("weapon.greatsword", None, WeaponSlot.MELEE_MAIN, (3, 4), [3, 4]),
    ("weapon.longsword", None, WeaponSlot.MELEE_MAIN, (2, 7), [7]),
    ("weapon.longsword", "shield.wooden", WeaponSlot.MELEE_MAIN, (2,), [2]),
    ("weapon.longsword", "weapon.shortsword", WeaponSlot.MELEE_OFF, (2,), [2]),
])
def test_great_weapon_fighting_fixed_faces_control_actual_attack_damage(game, weapon_id, offhand, slot, faces, expected):
    attacker = actor(game)
    target = actor(game, "Target", (3, 2), "foes")
    assert attacker.equipment.equip(build_authored_item(weapon_id, attacker.uuid), WeaponSlot.MELEE_MAIN)
    if offhand is not None:
        assert attacker.equipment.equip(build_authored_item(offhand, attacker.uuid), WeaponSlot.MELEE_OFF)
    attacker.add_condition(GreatWeaponFighting(source_entity_uuid=attacker.uuid, target_entity_uuid=attacker.uuid))
    before = target.get_hp()
    with fixed_dice_faces(15, *faces, 7):
        result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid, weapon_slot=slot).apply()
        following = ordinary_roll(attacker)
    assert result is not None and not result.canceled and result.attack_outcome is AttackOutcome.HIT
    assert result.damage_rolls[0].results == expected
    assert before - target.get_hp() == sum(roll.total for roll in result.damage_rolls)
    assert following.results == [7]
    completed = [event for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
                 if event.phase is EventPhase.COMPLETION]
    changes = completed[-1].roll_modifications
    assert bool(changes) is (list(faces) != expected)
    assert all(row.handler_name == "Great Weapon Fighting" for row in changes)


def test_great_weapon_fighting_leaves_extra_damage_packet_faces_unchanged(game):
    attacker = actor(game)
    target = actor(game, "Target", (3, 2), "foes")
    assert attacker.equipment.equip(build_authored_item("weapon.greatsword", attacker.uuid), WeaponSlot.MELEE_MAIN)
    attacker.equipment.extra_attack_damage_dices.append(4)
    attacker.equipment.extra_attack_damage_dices_numbers.append(1)
    attacker.equipment.extra_attack_damage_bonus.append(bonus(attacker))
    attacker.equipment.extra_attack_damage_type.append(DamageType.RADIANT)
    attacker.add_condition(GreatWeaponFighting(source_entity_uuid=attacker.uuid, target_entity_uuid=attacker.uuid))
    before = target.get_hp()
    with fixed_dice_faces(15, 1, 2, 1, 6, 5, 7):
        result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()
        following = ordinary_roll(attacker)
    assert result is not None and not result.canceled
    assert [roll.results for roll in result.damage_rolls] == [[6, 5], [1]]
    assert before - target.get_hp() == 12
    assert following.results == [7]


@pytest.mark.parametrize("advantage,expected", [(AdvantageStatus.ADVANTAGE, 18), (AdvantageStatus.DISADVANTAGE, 2)])
def test_ordinary_dice_advantage_stays_on_the_same_face_queue(game, advantage, expected):
    owner = actor(game)
    modifier = bonus(owner)
    modifier.self_static.add_advantage_modifier(AdvantageModifier(source_entity_uuid=owner.uuid, value=advantage))
    with fixed_dice_faces(2, 18):
        result = Dice(count=1, value=20, bonus=reading(modifier), roll_type=RollType.SAVE).roll
    assert result.results == [2, 18] and result.total == expected


def test_ordinary_critical_damage_still_consumes_exact_doubled_faces(game):
    owner = actor(game)
    with fixed_dice_faces(1, 2, 3, 4):
        result = ordinary_roll(owner, sides=6, count=2, roll_type=RollType.DAMAGE, attack_outcome=AttackOutcome.CRIT)
    assert result.results == [1, 2, 3, 4] and result.total == 10


def test_fixed_face_contexts_restore_outer_queue_on_error_and_normal_exit(game):
    owner = actor(game)
    before = random.getstate()
    with fixed_dice_faces(3, 4):
        assert ordinary_roll(owner).results == [3]
        with fixed_dice_faces(6):
            assert ordinary_roll(owner).results == [6]
        with pytest.raises(ValueError, match="outside the requested range"), fixed_dice_faces(21):
            ordinary_roll(owner)
        with pytest.raises(RuntimeError, match="No fixed dice face"), fixed_dice_faces():
            ordinary_roll(owner)
        assert ordinary_roll(owner).results == [4]
    assert random.getstate() == before
    assert 1 <= ordinary_roll(owner).total <= 20
    assert random.getstate() != before


@pytest.mark.parametrize("sides,face", [(1, 1), (7, 7), (20, 20)])
def test_supplementary_rule_faces_share_the_ordinary_dice_queue(game, sides, face):
    owner = actor(game)
    with fixed_dice_faces(face, 3):
        assert roll_die_face(sides) == face
        assert ordinary_roll(owner).results == [3]


@pytest.mark.parametrize("sides", [0, -1])
def test_nonpositive_die_rejection_leaves_fixed_faces_available(game, sides):
    owner = actor(game)
    with fixed_dice_faces(3):
        with pytest.raises(ValueError, match="Die sides must be positive"):
            roll_die_face(sides)
        assert ordinary_roll(owner).results == [3]


def test_supplementary_d7_rejects_an_out_of_range_fixed_face():
    with fixed_dice_faces(8), pytest.raises(ValueError, match="outside the requested range 1-7"):
        roll_die_face(7)
