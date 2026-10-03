"""Observable rule/ownership contracts for the approved SRD5.1 batch."""
from uuid import uuid4

import pytest

from dnd.conditions import Restrained
from dnd.monsters.traits import InnateFlight
from dnd.types.materials import Material
from dnd.actions import Attack, SpellEvent
from dnd.classes.fighter import FightingStyleTwoWeaponFighting
from dnd.spells.evocation import ShockingGrasp
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot, BodyPart
from dnd.core.effect_types import EventResolutionRef
from dnd.core.events import DamageAppliedEvent, TakeDamageEvent, EventQueue, EventType, EventHandler, EventPhase, Trigger
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier, ResistanceStatus
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import Barkskin, Fly, Longstrider, Shillelagh
from dnd.spells.evocation import FireShield
from dnd.spells.conjuration import ProduceFlame
from dnd.spells.transmutation import HasteEffect, SlowedEffect
from dnd.types.world import MovementMode


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(18, 8))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(18, 8))


def actor(game, name="Caster", position=(2, 2), faction="heroes"):
    entity = Entity.create(uuid4(), name, config=EntityConfig(faction=faction,
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=18)), health=HealthConfig(max_hit_points_bonus=200)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()
    return entity


def cast(spell_type, caster, target=None, **kwargs):
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell_type(source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid if target else caster.uuid, alt_skip_slot=True, **kwargs).apply()
    assert result is not None and not result.canceled, result
    return result


def test_longstrider_reapplication_and_removal_preserve_spent_movement(game):
    caster = actor(game)
    caster.action_economy.consume("movement", 15)
    result = Longstrider(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
    assert result is not None and not result.canceled
    assert caster.action_economy.current_speed() == 40
    assert caster.action_economy.movement_remaining() == 25
    caster.action_economy.reset_all_costs()
    cast(Longstrider, caster)
    assert caster.action_economy.current_speed() == 40
    assert caster.active_conditions["Longstrider"].duration.duration == 600
    caster.remove_condition("Longstrider")
    assert caster.action_economy.current_speed() == 30


@pytest.mark.parametrize("base_ac", [10, 18, 23])
def test_barkskin_is_whole_ac_floor_and_concentration_removes_it(game, base_ac):
    caster = actor(game)
    caster.equipment.ac_bonus.self_static.add_value_modifier(NumericalModifier(name="Armor test", value=base_ac-10,
        source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    before = caster.ac_bonus().normalized_score
    cast(Barkskin, caster)
    assert caster.ac_bonus().normalized_score == max(16, before)
    assert caster.active_conditions["Barkskin"].duration.duration == 600
    caster.remove_condition("Concentrating")
    assert "Barkskin" not in caster.active_conditions
    assert caster.ac_bonus().normalized_score == before


@pytest.mark.parametrize("haste,slow,expected", [(False,False,60),(True,False,120),(False,True,30),(True,True,60)])
def test_fly_has_own_speed_and_one_spent_ledger(game, haste, slow, expected):
    caster = actor(game)
    cast(Fly, caster)
    if haste:
        caster.add_condition(HasteEffect(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid, apply_lethargy=False))
    if slow:
        caster.add_condition(SlowedEffect(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
    walking = (60 if haste else 30) // (2 if slow else 1)
    assert caster.action_economy.current_speed() == walking
    assert caster.action_economy.current_speed(MovementMode.FLYING) == expected
    caster.action_economy.consume("movement", 20, movement_mode=MovementMode.FLYING)
    assert caster.action_economy.movement_remaining(MovementMode.FLYING) == expected-20
    assert caster.action_economy.movement_remaining() == max(0,walking-20)
    caster.remove_condition("Concentrating")
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 0
    assert caster.action_economy.movement_spent() == 20


def test_shillelagh_exact_item_release_and_strength_choice(game):
    caster = actor(game)
    caster.spellcasting.spellcasting_ability = "wisdom"
    staff = build_authored_item("weapon.quarterstaff",caster.uuid)
    assert caster.loot_item(staff) and caster.equip_item(staff.uuid,WeaponSlot.MELEE_MAIN)
    original_die = staff.damage_dice
    cast(Shillelagh,caster)
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert staff.damage_dice == original_die
    assert staff.attack_damage_die(caster.uuid) == 8
    assert staff.attack_is_magical(caster.uuid)
    assert caster.attack_bonus().normalized_score > caster.attack_bonus(override_ability="strength").normalized_score
    assert caster.equipment.unequip(WeaponSlot.MELEE_MAIN) is not None
    assert "Shillelagh" not in caster.active_conditions
    assert staff.attack_damage_die(caster.uuid) == original_die
    assert not staff.attack_is_magical(caster.uuid)


def test_produce_flame_retains_then_consumes_light_and_hurl_action_on_miss(game):
    caster = actor(game)
    enemy = actor(game,"Enemy",(5,2),"foes")
    cast(ProduceFlame,caster)
    flame = caster.active_conditions["Produce Flame"]
    light_uuid = flame.light_source_uuid
    assert light_uuid is not None
    hurl = next(action for action in caster.registered_actions if action.name == "Hurl Produce Flame")
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(1):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert "Produce Flame" not in caster.active_conditions
    assert not any(action.name == "Hurl Produce Flame" for action in caster.registered_actions)
    assert flame.light_source_uuid is None
    assert not EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)


@pytest.mark.parametrize("kind,resisted,retaliation",[("warm",DamageType.COLD,DamageType.FIRE),("chill",DamageType.FIRE,DamageType.COLD)])
def test_fire_shield_melee_hit_retaliates_without_reaction_cost(game,kind,resisted,retaliation):
    caster = actor(game)
    enemy = actor(game,"Enemy",(3,2),"foes")
    shield_cast = cast(FireShield,caster,shield_kind=kind)
    assert caster.health.get_resistance(resisted) is ResistanceStatus.RESISTANCE
    before = enemy.get_hp()
    with fixed_dice_faces(15, 2, 3, 4):
        result = Attack(source_entity_uuid=enemy.uuid,target_entity_uuid=caster.uuid,weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    assert enemy.get_hp() == before-5
    assert caster.action_economy.reactions.normalized_score == 1
    retaliation_request = next(event for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION and event.target_entity_uuid == enemy.uuid)
    assert retaliation_request.resolution_ref == EventResolutionRef(lineage_uuid=retaliation_request.lineage_uuid)
    assert retaliation_request.resolution_ref != result.resolution_ref
    assert retaliation_request.effect_origin is not None
    assert retaliation_request.effect_origin.source_event_lineage_uuid == str(shield_cast.lineage_uuid)
    committed = [event for event in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED)
                 if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION and event.target_entity_uuid == enemy.uuid]
    assert committed and all(event.resolution_ref == retaliation_request.resolution_ref for event in committed)
    caster.remove_condition("Fire Shield")
    assert caster.health.get_resistance(resisted) is ResistanceStatus.NONE


def test_swimming_retains_normal_fallback_speed(game):
    caster = actor(game)
    assert caster.action_economy.current_speed(MovementMode.SWIMMING) == 30
    caster.action_economy.consume("movement", 10, movement_mode=MovementMode.SWIMMING)
    assert caster.action_economy.movement_remaining() == 20


def test_fire_shield_retaliates_against_melee_spell_hit(game):
    caster = actor(game)
    enemy = actor(game,"Enemy",(3,2),"foes")
    cast(FireShield,caster)
    before = enemy.get_hp()
    with fixed_dice_faces(20,2,3,4,4):
        result = cast(ShockingGrasp,enemy,caster)
    assert result.attack_outcome is not None
    assert enemy.get_hp() < before


def test_shillelagh_offhand_style_uses_selected_casting_ability(game):
    caster = actor(game)
    caster.spellcasting.spellcasting_ability = "wisdom"
    club = build_authored_item("weapon.club",caster.uuid)
    assert caster.loot_item(club) and caster.equip_item(club.uuid,WeaponSlot.MELEE_OFF)
    cast(Shillelagh,caster,weapon_slot=WeaponSlot.MELEE_OFF)
    without_style = caster.get_damages(WeaponSlot.MELEE_OFF)[0]
    assert without_style.damage_bonus.normalized_score == 0
    caster.add_condition(FightingStyleTwoWeaponFighting(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
    with_style = caster.get_damages(WeaponSlot.MELEE_OFF)[0]
    assert with_style.damage_bonus.normalized_score == 4


def test_flight_lost_during_step_stops_without_spending_or_teleport(game):
    caster = actor(game)
    cast(Fly,caster)
    start = caster.position
    def remove_flight(event,owner_uuid):
        caster.remove_condition("Concentrating",parent_event=event)
        return None
    caster.add_event_handler(EventHandler(name="Reaction ending flight",source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.STEP_MOVEMENT,event_phase=EventPhase.EFFECT)],
        event_processor=remove_flight))
    template = next(action for action in caster.registered_actions if action.name == "Flying Movement")
    result = template.instantiate(end_position=(4,2)).apply()
    assert result is not None
    assert caster.position == start
    assert caster.action_economy.movement_spent() == 0
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 0


def test_flight_added_after_speed_effects_uses_same_budget_and_queries_are_pure(game):
    caster = actor(game)
    cast(Longstrider, caster)
    caster.action_economy.reset_all_costs()
    caster.add_condition(HasteEffect(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
        apply_lethargy=False))
    caster.action_economy.consume('movement', 20)
    result = Fly(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
    assert result and not result.canceled
    economy = caster.action_economy
    before = economy.model_dump(mode='json')
    for _ in range(3):
        assert economy.current_speed() == 80
        assert economy.current_speed(MovementMode.FLYING) == 140
        assert economy.movement_remaining() == 60
        assert economy.movement_remaining(MovementMode.FLYING) == 120
    assert economy.model_dump(mode='json') == before
    caster.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    assert economy.current_speed() == economy.current_speed(MovementMode.FLYING) == 0
    caster.remove_condition('Restrained')
    assert economy.movement_remaining(MovementMode.FLYING) == 120


def test_independent_flight_grants_and_vetoed_removal_preserve_permission(game):
    caster = actor(game)
    innate = InnateFlight(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, flying_speed=40)
    caster.add_condition(innate)
    cast(Fly, caster)
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 60
    caster.remove_condition('Concentrating')
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 40
    caster.add_event_handler(EventHandler(name='Keep innate flight', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.cancel(status_message='Retain flight')))
    assert not caster.remove_condition(innate.name)
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 40


def test_shillelagh_uses_wood_and_weapon_kind_for_named_items(game):
    caster = actor(game)
    staff = build_authored_item('weapon.arcane_staff', caster.uuid)
    assert caster.loot_item(staff) and caster.equip_item(staff.uuid, WeaponSlot.MELEE_MAIN)
    cast(Shillelagh, caster)
    assert staff.attack_damage_die(caster.uuid) == 8
    caster.remove_condition('Shillelagh')
    staff.material = Material.METAL
    caster.action_economy.reset_all_costs()
    result = Shillelagh(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
    assert result is None or result.canceled
    assert 'Shillelagh' not in caster.active_conditions


@pytest.mark.parametrize('spell_type,name', [(Longstrider,'Longstrider'), (Barkskin,'Barkskin'),
    (Fly,'Fly'), (Shillelagh,'Shillelagh'), (ProduceFlame,'Produce Flame'), (FireShield,'Fire Shield')])
@pytest.mark.parametrize('event_type,phase', [(EventType.CONDITION_APPLICATION, EventPhase.DECLARATION),
    (EventType.CONDITION_APPLICATION, EventPhase.EXECUTION), (EventType.CONDITION_APPLICATION, EventPhase.EFFECT),
    (EventType.CAST_SPELL, EventPhase.EFFECT)])
def test_rejected_spell_condition_releases_only_its_provisional_state(game, spell_type, name, event_type, phase):
    caster = actor(game)
    staff = build_authored_item('weapon.quarterstaff', caster.uuid)
    assert caster.loot_item(staff) and caster.equip_item(staff.uuid, WeaponSlot.MELEE_MAIN)
    before_actions = {row.uuid for row in caster.registered_actions}
    before_light = set(caster.get_attached_light_sources())
    before_ac = caster.ac_bonus().normalized_score
    caster.add_event_handler(EventHandler(name='Veto incoming condition', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=event_type, event_phase=phase)],
        event_processor=lambda event, _: event.cancel('Condition veto')))
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
    assert result is not None
    assert any(isinstance(row, SpellEvent) and row.canceled and row.target_entity_uuid == caster.uuid
        for row in EventQueue.get_events_by_type(EventType.CAST_SPELL))
    assert name not in caster.active_conditions and 'Concentrating' not in caster.active_conditions
    assert caster.action_economy.current_speed() == 30
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 0
    assert caster.ac_bonus().normalized_score == before_ac
    assert not staff.attack_overrides
    assert caster.health.get_resistance(DamageType.COLD) is ResistanceStatus.NONE
    assert {row.uuid for row in caster.registered_actions} == before_actions
    assert set(caster.get_attached_light_sources()) == before_light


@pytest.mark.parametrize('veto', ['owner', 'child', 'old-removal'])
def test_failed_concentration_replacement_keeps_previous_owner_and_children(game, veto):
    caster = actor(game)
    cast(Barkskin, caster)
    previous = dict(caster.active_conditions)
    def refuse(event, _):
        if ((veto == 'owner' and isinstance(event, ConditionApplicationEvent) and event.condition.name == 'Concentrating')
                or (veto == 'child' and isinstance(event, ConditionApplicationEvent) and event.condition.name == 'Fly') or veto == 'old-removal'):
            return event.cancel('Keep accepted graph')
        return None
    caster.add_event_handler(EventHandler(name='Veto replacement', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL if veto == 'old-removal'
            else EventType.CONDITION_APPLICATION, event_phase=EventPhase.EFFECT)], event_processor=refuse))
    caster.action_economy.reset_all_costs()
    result = Fly(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
    assert result is not None
    assert any(isinstance(row, SpellEvent) and row.canceled and row.target_entity_uuid == caster.uuid
        for row in EventQueue.get_events_by_type(EventType.CAST_SPELL))
    assert caster.active_conditions == previous
    assert all(condition.applied for condition in previous.values())
    assert caster.action_economy.current_speed(MovementMode.FLYING) == 0
    assert caster.ac_bonus().normalized_score == 16


def test_contextual_speed_queries_preserve_serialized_economy_and_recompute_after_equipment(game):
    caster = actor(game)
    plate = build_authored_item('armor.plate', caster.uuid)
    assert caster.loot_item(plate) and caster.equip_item(plate.uuid, BodyPart.BODY)
    before = caster.action_economy.model_dump(mode='json')
    for _ in range(3):
        assert caster.action_economy.current_speed() == 20
        assert caster.action_economy.model_dump(mode='json') == before
    assert caster.unequip_item(BodyPart.BODY)
    assert caster.action_economy.current_speed() == 30
