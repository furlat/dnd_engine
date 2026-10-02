"""Native rules, costs and possession lifecycle for the approved roster batch."""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_by_index
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig
from dnd.classes.fighter import ExtraAttack, ExtraAttackFeature, ActionSurgeFeature
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.action_types import HasteActionPolicy
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier, AdvantageStatus
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.actions_functional import execute_use_action
from dnd.monsters.roster_abilities import InnateFlight, InnateInvisibility, MagicResistance, WightLifeDrain, wight_melee_multiattack
from dnd.monsters.traits import MultiattackAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.roster_support import Longstrider
from dnd.spells.transmutation import HasteEffect, SlowedEffect
from dnd.types.world import MovementMode


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(16,9))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(16,9))


def actor(game, name='Owner', position=(3,3), strength=10):
    entity = Entity.create(uuid4(),name,config=EntityConfig(faction=name,
        health=HealthConfig(max_hit_points_bonus=100),
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=strength))))
    entity.compose_entity()
    game.deploy_entity(entity,position)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()
    return entity


def equip(owner, item_id, slot):
    item=build_authored_item(item_id,owner.uuid)
    assert owner.loot_item(item) and owner.equip_item(item.uuid,slot)
    return item


def arrows(owner, suffix='ember', count=3):
    item=build_authored_item('consumable.arrow.'+suffix,owner.uuid,quantity=count)
    assert owner.loot_item(item)
    return item


def shoot(owner,target,item):
    Entity.update_all_entities_senses()
    return Attack(source_entity_uuid=owner.uuid,target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,selected_ammunition_uuid=item.uuid).apply()


@pytest.mark.parametrize('suffix,damage_type',[('ember',DamageType.FIRE),('frost',DamageType.COLD),('storm',DamageType.LIGHTNING),('venom',DamageType.POISON)])
def test_selected_arrow_uses_normal_attack_and_one_stack_copy(game,suffix,damage_type):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN)
    item=arrows(owner,suffix)
    before=target.get_hp()
    action=Attack(source_entity_uuid=owner.uuid,target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,selected_ammunition_uuid=item.uuid)
    packet=action.get_outcome_profile(owner).damage_rolls[-1]
    assert packet.damage_type == damage_type.value
    assert packet.save_dc == (10 if suffix=='venom' else None)
    with fixed_dice_faces(15,2,3,1):
        result=action.apply()
    assert result and not result.canceled and target.get_hp()<before
    assert item.stack_count==2 and owner.action_economy.actions.normalized_score==0
    assert 'Poisoned' not in target.active_conditions


@pytest.mark.parametrize('cancel_at',[EventType.ITEM_CHARGE_CONSUMPTION,EventType.ATTACK])
def test_arrow_canceled_before_release_keeps_the_stack(game,cancel_at):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN); item=arrows(owner)
    owner.add_event_handler(EventHandler(name='Cancel before release',source_entity_uuid=owner.uuid,
        trigger_conditions=[Trigger(event_type=cancel_at,event_phase=EventPhase.EFFECT if cancel_at is EventType.ITEM_CHARGE_CONSUMPTION else EventPhase.EXECUTION)],
        event_processor=lambda event,source:event.cancel(status_message='Release denied')))
    result=shoot(owner,target,item)
    assert result and result.canceled and item.stack_count==3
    assert owner.action_economy.actions.normalized_score==(1 if cancel_at is EventType.ITEM_CHARGE_CONSUMPTION else 0)


def test_arrow_miss_consumes_one_and_musket_cannot_fire_it(game):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN); item=arrows(owner)
    hp=target.get_hp()
    with fixed_dice_faces(1): result=shoot(owner,target,item)
    assert result and not result.canceled and target.get_hp()==hp and item.stack_count==2
    owner.action_economy.reset_all_costs()
    equip(owner,'weapon.musket',WeaponSlot.RANGED_MAIN)
    result=shoot(owner,target,item)
    assert result is None or result.canceled
    assert item.stack_count==2 and owner.action_economy.actions.normalized_score==1


def test_extra_attack_and_ranged_multiattack_discover_and_spend_selected_arrows(game):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN); item=arrows(owner,count=6)
    owner.add_condition(ExtraAttackFeature(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid))
    with fixed_dice_faces(15,2,3): result=shoot(owner,target,item)
    assert result and not result.canceled
    template=next(action for action in owner.registered_actions if isinstance(action,ExtraAttack) and action.weapon_slot is WeaponSlot.RANGED_MAIN)
    selected=next(action for action in template.get_discovery_variants(owner) if action.selected_ammunition_uuid==item.uuid)
    with fixed_dice_faces(15,2,3): result=selected.instantiate(target_entity_uuid=target.uuid).apply()
    assert result and not result.canceled and item.stack_count==4
    owner.action_economy.reset_all_costs()
    multi=MultiattackAction(source_entity_uuid=owner.uuid,target_entity_uuid=target.uuid,
        attack_sequence=((WeaponSlot.RANGED_MAIN,2),),selected_ammunition_uuid=item.uuid)
    with fixed_dice_faces(15,2,3,15,2,3): result=multi.apply()
    assert result and not result.canceled and item.stack_count==2
    assert owner.action_economy.actions.normalized_score==0


def test_pack_activation_requires_current_equipment_and_rest_recharges_exact_item(game):
    owner=actor(game); receiver=actor(game,'Receiver',(3,4))
    pack=equip(owner,'gear.wayfarer_pack',BodyPart.BACKPACK)
    stale=pack.get_use_actions(owner.uuid)[0].instantiate(target_entity_uuid=owner.uuid)
    assert owner.unequip_item(BodyPart.BACKPACK) is pack
    result=stale.apply()
    assert result is None or result.canceled
    assert pack.charges==1 and owner.action_economy.actions.normalized_score==1
    assert owner.equip_item(pack.uuid,BodyPart.BACKPACK)
    result=execute_use_action(owner,pack.uuid,pack.get_use_actions(owner.uuid)[0].get_discovery_template_name())
    assert result and not result.canceled and pack.charges==0
    assert owner.action_economy.current_speed()==40
    assert owner.unequip_item(BodyPart.BACKPACK) is pack and owner.drop_item(pack.uuid)
    assert receiver.loot_item(pack) and receiver.equip_item(pack.uuid,BodyPart.BACKPACK)
    assert pack.charges==0 and not pack.get_use_actions(receiver.uuid)
    receiver.on_long_rest()
    assert pack.charges==1 and pack.get_use_actions(receiver.uuid)
    recharges=[event for event in EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
        if event.phase is EventPhase.COMPLETION and event.resource_change=='recharge']
    assert len(recharges)==1


def test_magic_resistance_only_applies_to_explicit_magical_saves(game):
    owner=actor(game)
    owner.add_condition(MagicResistance(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid))
    for magical,expected in ((False,False),(True,True)):
        request=owner.create_saving_throw_request(owner.uuid,'constitution',12,
            saving_throw_context=SavingThrowContext(cause_id='test.save',effect_id='test.save.effect',is_magical=magical))
        with fixed_dice_faces(1,18): _,_,saved=owner.saving_throw(request)
        assert saved is expected


def test_innate_invisibility_is_not_a_spell_and_survives_nonconcentration_cast(game):
    owner=actor(game)
    cursor=EventQueue.event_cursor()
    result=InnateInvisibility(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid).apply()
    assert result and not result.canceled and 'Invisible' in owner.active_conditions
    assert not any(event.event_type is EventType.CAST_SPELL for _,event in EventQueue.iter_events_since(cursor))
    owner.action_economy.reset_all_costs()
    result=Longstrider(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,alt_skip_slot=True).apply()
    assert result and not result.canceled and 'Invisible' in owner.active_conditions
    owner.remove_condition('Concentrating')
    assert 'Invisible' not in owner.active_conditions


def test_innate_flight_keeps_authored_speed_and_nonmagical_provenance(game):
    owner=actor(game)
    effect=InnateFlight(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,flying_speed=45)
    owner.add_condition(effect)
    assert owner.action_economy.current_speed()==30
    assert owner.action_economy.current_speed(MovementMode.FLYING)==45
    assert ConditionTag.MAGICAL not in effect.tags and 'Concentrating' not in owner.active_conditions


def test_fixed_life_drain_baseline_keeps_independent_buffs_and_reductions_accumulate(game):
    owner=actor(game,strength=20); target=actor(game,'Target',(4,3))
    owner.equipment.attack_bonus.self_static.add_value_modifier(NumericalModifier(value=3,name='Attack buff',source_entity_uuid=owner.uuid))
    owner.equipment.damage_bonus.self_static.add_value_modifier(NumericalModifier(value=2,name='Damage buff',source_entity_uuid=owner.uuid))
    action=WightLifeDrain(source_entity_uuid=owner.uuid,target_entity_uuid=target.uuid)
    profile=action.get_outcome_profile(owner)
    assert profile.attack_bonus==7 and profile.damage_rolls[0].flat_bonus==4
    before=target.get_max_hp()
    for _ in range(2):
        owner.action_economy.reset_all_costs()
        with fixed_dice_faces(15,4,1): result=action.apply()
        assert result and not result.canceled
    assert target.get_max_hp()==before-16 and target.get_hp()>0
    owner.receive_instant_death(target.uuid,'Test source retirement')
    assert target.get_max_hp()==before-16
    target.on_long_rest()
    assert target.get_max_hp()==before


def test_wight_multiattack_replaces_one_longsword_and_has_no_bow_replacement(game):
    owner=actor(game); target=actor(game,'Target',(4,3))
    equip(owner,'weapon.longsword',WeaponSlot.MELEE_MAIN)
    action=wight_melee_multiattack(owner.uuid)
    action.template=True
    choice=next(variant for variant in action.get_discovery_variants(owner) if variant.use_attack_substitution)
    with fixed_dice_faces(15,4,1,15,2): result=choice.instantiate(target_entity_uuid=target.uuid).apply()
    assert result and not result.canceled
    roots=[event for event in EventQueue.get_events_by_type(EventType.ATTACK) if event.phase is EventPhase.DECLARATION]
    assert len(roots)==2 and sum(event.natural_weapon is not None for event in roots)==1
    assert owner.action_economy.actions.normalized_score==0
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN)
    ranged=MultiattackAction(source_entity_uuid=owner.uuid,attack_sequence=((WeaponSlot.RANGED_MAIN,2),),
        attack_substitution=action.attack_substitution,substitution_slot=action.substitution_slot,substitution_item_id=action.substitution_item_id)
    assert not any(variant.use_attack_substitution for variant in ranged.get_discovery_variants(owner))


def test_odd_speed_haste_and_slow_do_not_depend_on_application_order(game):
    owner=actor(game)
    owner.action_economy.movement.self_static.add_value_modifier(NumericalModifier(name='Odd speed',value=5,source_entity_uuid=owner.uuid))
    for types in ((HasteEffect,SlowedEffect),(SlowedEffect,HasteEffect)):
        for condition in types:
            owner.add_condition(condition(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid, **({"apply_lethargy":False} if condition is HasteEffect else {})))
        assert owner.action_economy.current_speed()==35
        owner.remove_condition('Haste'); owner.remove_condition('Slowed')


def test_arrow_discovery_and_charge_events_expose_the_selected_possession(game):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN); item=arrows(owner)
    available=get_available_actions(owner,legal_only=True)
    row=next(row for row in available.entity_actions if row.selected_ammunition_uuid==item.uuid)
    assert row.ammunition_payload and row.ammunition_payload.item_id==item.item_id
    with fixed_dice_faces(15,2,3):
        result=execute_by_index(owner,row.template_name,
            next(option.index for option in row.valid_targets if option.target_uuid==target.uuid),available=available)
    assert result and not result.canceled
    charges=EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
    assert charges
    for event in charges:
        parent=event.get_parent_event()
        assert parent is not None and parent.event_type is EventType.ATTACK


@pytest.mark.parametrize('slow',[False,True])
@pytest.mark.parametrize('haste_policy',[None,HasteActionPolicy.SRD_5_1,HasteActionPolicy.BG3_HONOUR])
@pytest.mark.parametrize('attacks_per_action',[1,2,3,4])
@pytest.mark.parametrize('surge',[False,True])
def test_special_arrow_haste_extra_attack_surge_slow_budget_grid(game,slow,haste_policy,attacks_per_action,surge):
    owner=actor(game); target=actor(game,'Target',(7,3))
    equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN); item=arrows(owner,count=20)
    if attacks_per_action>1:
        owner.add_condition(ExtraAttackFeature(source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,extra_attacks=attacks_per_action-1))
        owner.action_economy.resources['extra_attacks'].current=0
    if surge:
        owner.add_condition(ActionSurgeFeature(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,num_uses=1))
    if haste_policy is not None:
        owner.action_economy.haste_action_policy=haste_policy
        owner.add_condition(HasteEffect(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,
            caster_uuid=owner.uuid,apply_lethargy=False))
    if slow:
        owner.add_condition(SlowedEffect(source_entity_uuid=target.uuid,target_entity_uuid=owner.uuid,
            caster_uuid=target.uuid,spell_dc=0))

    def execute(route):
        available=get_available_actions(owner,legal_only=True)
        if route=='surge':
            row=next(row for row in available.self_actions if row.template_name=='Action Surge')
            option=row.valid_targets[0]
        else:
            rows=[row for row in available.entity_actions if row.selected_ammunition_uuid==item.uuid
                and row.weapon_slot==WeaponSlot.RANGED_MAIN.value]
            resource={'haste':'haste_action','extra':'extra_attacks'}.get(route)
            row=next(row for row in rows if
                (any(cost.resource_name==resource for cost in row.costs) if resource else
                    row.cost_amount==1 and all(cost.resource_name is None for cost in row.costs)))
            option=next(option for option in row.valid_targets if option.target_uuid==target.uuid)
        with fixed_dice_faces(10,1,1):
            result=execute_by_index(owner,row.template_name,option.index,available=available)
        assert result and not result.canceled

    shots=0
    if haste_policy is not None:
        execute('haste'); shots+=1
        assert owner.action_economy.actions.normalized_score==1
    execute('normal'); shots+=1
    credits=0 if slow else attacks_per_action-1
    if credits>1:
        execute('extra'); shots+=1; credits-=1
    if surge:
        execute('surge')
        execute('normal'); shots+=1
        credits+=0 if slow else attacks_per_action-1
    while credits:
        execute('extra'); shots+=1; credits-=1
    expected=(1 if slow else attacks_per_action)*(1+int(surge))+int(haste_policy is not None)
    assert shots==expected and item.stack_count==20-expected
    assert owner.action_economy.actions.normalized_score==0
    assert owner.action_economy.bonus_actions.normalized_score==(0 if slow else 1)
    assert owner.action_economy.reactions.normalized_score==(0 if slow else 1)
    assert not any(row.selected_ammunition_uuid==item.uuid
        for row in get_available_actions(owner,legal_only=True).entity_actions)


@pytest.mark.parametrize('item_id', ['gear.ember_quiver','gear.wayfarer_pack','gear.warden_pack'])
def test_powered_backpacks_construct_equip_and_activate_through_normal_item_use(game,item_id):
    owner=actor(game)
    bow=equip(owner,'weapon.longbow',WeaponSlot.RANGED_MAIN)
    pack=equip(owner,item_id,BodyPart.BACKPACK)
    result=execute_use_action(owner,pack.uuid,pack.get_use_actions(owner.uuid)[0].get_discovery_template_name())
    assert result and not result.canceled and pack.charges==0
    if item_id=='gear.ember_quiver':
        assert any(condition.target_entity_uuid==bow.uuid for condition in bow.active_conditions.values())
    elif item_id=='gear.wayfarer_pack':
        assert owner.action_economy.current_speed()==40
    else:
        assert 'Resistance' in owner.active_conditions and 'Concentrating' in owner.active_conditions
