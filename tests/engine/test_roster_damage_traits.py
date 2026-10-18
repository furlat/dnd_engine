"""Shared roster defenses consume the damage's actual source facts."""

import pytest
from uuid import uuid4

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import EvasionFeature, SpellDamageResistance, UndeadFortitudeFeature
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.core.events import Damage, TakeDamageEvent, EventHandler, EventPhase, Trigger
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import DamageRollProfile
from dnd.monsters.spell_summon_actions import DragonBreath
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.saving_throw_types import DamageSaveContext
from dnd.core.values import Channel, Kind, add_modifier
from dnd.spells.evocation import Fireball, BurningHands
from dnd.spatial.mechanisms import AreaGeometry, TrapSave, materialize_finite_trap
from dnd.types.traps import TrapDamage, TrapPayload
from tests.engine.test_trap_mechanisms import pulse
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def runtime():
    reset_engine_runtime(grid_size=(8, 6))
    yield
    reset_engine_runtime(grid_size=(8, 6))


@pytest.fixture
def game():
    game = Game()
    yield game
    game.close()


def actor(game, name, position, *, hp=10, temporary_hp=0, resistances=()):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=EntityConfig(
        faction=name,
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=6, hit_dice_count=1, mode="maximums")],
            max_hit_points_bonus=hp - 6,
            temporary_hit_points=temporary_hp,
            resistances=list(resistances),
        ),
    ))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def fortitude(entity):
    entity.add_condition(UndeadFortitudeFeature(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
    ))


@pytest.mark.parametrize("critical, damage_type", [
    (True, DamageType.SLASHING),
    (False, DamageType.RADIANT),
])
def test_fortitude_does_not_roll_against_critical_or_radiant_damage(game, critical, damage_type):
    source = actor(game, "Attacker", (2, 2))
    zombie = actor(game, "Zombie", (3, 2))
    fortitude(zombie)
    before = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
    with fixed_dice_faces(20):
        zombie.receive_damage(12, damage_type, source.uuid, critical_hit=critical)
    assert zombie.get_normal_hp() <= 0
    assert len(EventQueue.get_events_by_type(EventType.SAVING_THROW)) == before


def test_fortitude_uses_post_defense_damage_for_its_save_dc(game):
    source = actor(game, "Attacker", (2, 2))
    zombie = actor(game, "Zombie", (3, 2), hp=5, resistances=(DamageType.FIRE,))
    fortitude(zombie)
    with fixed_dice_faces(11):
        zombie.receive_damage(12, DamageType.FIRE, source.uuid)
    assert zombie.get_normal_hp() == 1


def test_fortitude_does_not_count_temporary_hp_twice(game):
    source = actor(game, "Attacker", (2, 2))
    zombie = actor(game, "Zombie", (3, 2), temporary_hp=5)
    fortitude(zombie)
    with fixed_dice_faces(20):
        zombie.receive_damage(15, DamageType.SLASHING, source.uuid)
    assert zombie.get_normal_hp() == 1
    assert zombie.health.temporary_hit_points.normalized_score == 0


def defense(entity, feature_type):
    feature = feature_type(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(feature)
    return feature


@pytest.mark.parametrize("ability, fraction, success, incoming, expected", [
    ("dexterity", 0.5, True, 5, 0),
    ("dexterity", 0.5, False, 11, 5),
    ("constitution", 0.5, True, 5, 5),
    ("constitution", 0.5, False, 11, 11),
    ("dexterity", 0, False, 11, 11),
    ("dexterity", 0, True, 0, 0),
])
def test_evasion_uses_exact_save_facts_only(game, ability, fraction, success, incoming, expected):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, EvasionFeature)
    target.receive_damage(incoming, DamageType.FIRE, source.uuid,
        damage_save=DamageSaveContext(ability=ability, success=success, success_fraction=fraction))
    assert target.get_normal_hp() == 100 - expected


def test_evasion_preserves_mixed_component_rounding_and_affinities(game):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100, resistances=(DamageType.FIRE,))
    defense(target, EvasionFeature)
    packets = [Damage(source_entity_uuid=source.uuid, damage_dice=6, dice_numbers=1, damage_type=kind)
               for kind in (DamageType.FIRE, DamageType.COLD)]
    target.receive_damage(14, DamageType.FIRE, source.uuid, damages=packets, component_amounts=(5, 9),
        damage_save=DamageSaveContext(ability="dexterity", success=False, success_fraction=0.5))
    # Evasion floors each component, then fire resistance applies once: 5//2//2 + 9//2.
    assert target.get_normal_hp() == 95


@pytest.mark.parametrize("kind, magical, expected", [
    (EffectOriginKind.SPELL, True, 5),
    (EffectOriginKind.ACTION, True, 11),
    (EffectOriginKind.ACTION, False, 11),
    (EffectOriginKind.ITEM, True, 11),
])
def test_spell_resistance_uses_explicit_source_kind(game, kind, magical, expected):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, SpellDamageResistance)
    target.receive_damage(11, DamageType.FIRE, source.uuid,
        effect_origin=EffectOrigin(kind=kind, magical=magical))
    assert target.get_normal_hp() == 100 - expected


def test_spell_and_type_resistance_do_not_stack_and_immunity_wins(game):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100, resistances=(DamageType.FIRE,))
    defense(target, SpellDamageResistance)
    origin = EffectOrigin(kind=EffectOriginKind.SPELL, magical=True)
    target.receive_damage(11, DamageType.FIRE, source.uuid, effect_origin=origin)
    assert target.get_normal_hp() == 95
    add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE,
        ResistanceModifier(source_entity_uuid=target.uuid, name="Cold immunity",
            damage_type=DamageType.COLD, value=ResistanceStatus.IMMUNITY))
    target.receive_damage(11, DamageType.COLD, source.uuid, effect_origin=origin)
    assert target.get_normal_hp() == 95


def test_component_origin_overrides_packet_origin(game):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, SpellDamageResistance)
    packets = [Damage(source_entity_uuid=source.uuid, damage_dice=6, dice_numbers=1,
                      damage_type=kind, effect_origin=EffectOrigin(kind=origin))
               for kind, origin in ((DamageType.FIRE, EffectOriginKind.SPELL),
                                    (DamageType.COLD, EffectOriginKind.ACTION))]
    target.receive_damage(18, DamageType.FIRE, source.uuid, damages=packets, component_amounts=(9, 9),
        effect_origin=EffectOrigin(kind=EffectOriginKind.SPELL))
    assert target.get_normal_hp() == 87


@pytest.mark.parametrize("feature_type", [EvasionFeature, SpellDamageResistance])
def test_defense_removal_releases_only_owned_grant_and_reads_publish_nothing(game, feature_type):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    feature = defense(target, feature_type)
    origin = EffectOrigin(kind=EffectOriginKind.SPELL)
    save = DamageSaveContext(ability="dexterity", success=False, success_fraction=0.5)
    packet = TakeDamageEvent(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
        total_damage=11, damages=[Damage(source_entity_uuid=source.uuid, damage_dice=6,
            dice_numbers=1, damage_type=DamageType.FIRE)], damage_save=save, effect_origin=origin)
    cursor = EventQueue.event_cursor()
    for _ in range(3):
        assert target.preview_take_damage(packet).normal_hit_point_damage == 5
    assert tuple(EventQueue.iter_events_since(cursor)) == ()
    target.remove_condition_by_uuid(feature.uuid)
    target.receive_damage(11, DamageType.FIRE, source.uuid, damage_save=save, effect_origin=origin)
    assert target.get_normal_hp() == 89


def test_fortitude_does_not_roll_again_after_death(game):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Zombie", (3, 2))
    fortitude(target)
    target.receive_damage(10, DamageType.RADIANT, source.uuid)
    before = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
    with fixed_dice_faces(20):
        target.receive_damage(1, DamageType.SLASHING, source.uuid)
    assert target.get_normal_hp() <= 0
    assert len(EventQueue.get_events_by_type(EventType.SAVING_THROW)) == before


@pytest.mark.parametrize("saved, feature_type, expected", [
    (False, EvasionFeature, 4), (True, EvasionFeature, 0),
    (False, SpellDamageResistance, 4), (True, SpellDamageResistance, 2),
])
def test_native_fireball_carries_save_and_spell_source(game, saved, feature_type, expected):
    caster = create_spell_regression_actor("Caster", (0, 0), "heroes", spell_slots={3: 1})
    target = actor(game, "Defender", (6, 4), hp=100)
    defense(target, feature_type)
    force_save_result(target, "dexterity", succeeds=saved)
    register_spell(caster, Fireball, caster_level=5)
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    action = next(row for row in available.all_actions if row.behavior_id == "spell.fireball")
    selection = next(row for row in action.valid_targets if row.position == target.position)
    with fixed_dice_faces(*([1] * 100)):
        result = execute_available_action(caster, action, selection)
    assert result is not None and not result.canceled
    assert target.get_normal_hp() == 100 - expected


@pytest.mark.parametrize("feature_type", [EvasionFeature, SpellDamageResistance])
def test_refused_defense_does_not_leave_health_grant(game, feature_type):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    handler = EventHandler(source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
            event_phase=EventPhase.EFFECT, event_target_entity_uuid=target.uuid)],
        event_processor=lambda event, _: event.cancel(status_message="Refused defense"))
    target.add_event_handler(handler)
    feature = defense(target, feature_type)
    assert not feature.applied
    target.receive_damage(11, DamageType.FIRE, source.uuid,
        effect_origin=EffectOrigin(kind=EffectOriginKind.SPELL),
        damage_save=DamageSaveContext(ability="dexterity", success=False, success_fraction=0.5))
    assert target.get_normal_hp() == 89


def test_overlapping_defense_sources_do_not_stack_and_remove_independently(game):
    source = actor(game, "Attacker", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    first = SpellDamageResistance(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)
    second = SpellDamageResistance(name="Second source", source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(first)
    target.add_condition(second)
    origin = EffectOrigin(kind=EffectOriginKind.SPELL)
    target.receive_damage(11, DamageType.FIRE, source.uuid, effect_origin=origin)
    target.remove_condition_by_uuid(first.uuid)
    target.receive_damage(11, DamageType.FIRE, source.uuid, effect_origin=origin)
    target.remove_condition_by_uuid(second.uuid)
    target.receive_damage(11, DamageType.FIRE, source.uuid, effect_origin=origin)
    assert target.get_normal_hp() == 79


@pytest.mark.parametrize("feature_type,saved,expected", [
    (EvasionFeature, False, 4), (EvasionFeature, True, 0),
    (SpellDamageResistance, False, 8),
])
def test_native_breath_damage_is_save_aware_and_is_not_spell_damage(game, feature_type, saved, expected):
    source = actor(game, "Dragon", (2, 2))
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, feature_type)
    force_save_result(target, "dexterity", succeeds=saved)
    action = DragonBreath(source_entity_uuid=source.uuid, template=True,
        packets=(DamageRollProfile(dice_count=2, die_size=6, damage_type="Fire"),))
    source.register_action(action)
    Entity.update_all_entities_senses()
    with fixed_dice_faces(10, 4, 4):
        result = source.perform(action, ActionSelection(template_uuid=action.uuid, positions=((4, 2),)))
    assert result is not None and not result.canceled
    assert target.get_normal_hp() == 100 - expected


@pytest.mark.parametrize("feature_type,saved,expected", [
    (EvasionFeature, False, 4), (EvasionFeature, True, 0),
    (SpellDamageResistance, False, 4),
])
def test_native_burning_hands_preserves_damage_cause(game, feature_type, saved, expected):
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={1: 1})
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, feature_type)
    force_save_result(target, "dexterity", succeeds=saved)
    register_spell(caster, BurningHands, caster_level=1)
    Entity.update_all_entities_senses()
    action = next(row for row in get_available_actions(caster).all_actions
                  if row.behavior_id == "spell.burning_hands")
    selection = next(row for row in action.valid_targets if row.position == target.position)
    with fixed_dice_faces(*([3] * 30)):
        result = execute_available_action(caster, action, selection)
    assert result is not None and not result.canceled
    assert target.get_normal_hp() == 100 - expected


@pytest.mark.parametrize("saved,expected", [(False, 4), (True, 0)])
def test_native_trap_half_save_supplies_evasion_facts(game, saved, expected):
    target = actor(game, "Defender", (3, 2), hp=100)
    defense(target, EvasionFeature)
    force_save_result(target, "dexterity", succeeds=saved)
    trap = materialize_finite_trap(target.position, geometry=AreaGeometry(),
        avoidance=TrapSave(half_damage_on_success=True), payload=TrapPayload(damages=(
            TrapDamage(dice_count=2, dice_sides=6, damage_type=DamageType.PIERCING),)))
    result = pulse(trap, 10, 4, 4)
    assert result.committed
    assert target.get_normal_hp() == 100 - expected
