"""Paid item/repeat/revival casts and their native lifecycle interactions."""
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.events import EventQueue, SavingThrowEvent
from dnd.core.modifiers import NumericalModifier
import pytest
from dnd.actions import Attack
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.core.modifiers import NumericalModifier, ResistanceModifier, ResistanceStatus
from dnd.items.created_items import GoodberryItem, FlameBladeItem
from dnd.spells.evocation import FlameBlade
from dnd.spells.abjuration import AntimagicField
from dnd.core.gridmap import get_map
from dnd.spells.transmutation import Goodberry, DragonsBreath, ExhaleDragonsBreath
from dnd.spells.necromancy import VampiricTouch, VampiricTouchStrike, Revivify
from dnd.spells.enchantment import Hex
from tests.engine.test_bg3_rank_one_two_spells import game, combatant
from tests.engine.test_bg3_spell_hit_riders import cast, equip
from tests.manual.spell_regression_support import force_save_result


def test_goodberry_real_bonus_action_consumption_and_source_long_rest(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(3,2))
    cast(Goodberry,caster,ally)
    berries=[item for item in ally.inventory.items.values() if isinstance(item,GoodberryItem)]
    assert len(berries)==4
    ally.receive_damage(20,DamageType.FORCE,caster.uuid)
    hp=ally.get_hp()
    action=berries[0].get_use_actions(ally.uuid)[0]
    with fixed_dice_faces(3):result=action.instantiate().apply()
    assert result is not None and not result.canceled
    assert ally.get_hp()==hp+3
    assert ally.action_economy.bonus_actions.normalized_score==0
    assert BaseBlock.get(berries[0].uuid) is None
    ally.drop_item(berries[1].uuid)
    cast(Goodberry,caster,caster)
    caster.on_long_rest()
    assert all(BaseBlock.get(item.uuid) is None for item in berries)
    assert not any(isinstance(item,GoodberryItem) for item in caster.inventory.items.values())


def test_goodberry_capacity_failure_spends_nothing_and_creates_nothing(game):
    caster=combatant(game)
    caster.inventory.max_slots=3
    slots=caster.action_economy.spell_slot_1.normalized_score
    result=Goodberry(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score==1
    assert caster.action_economy.spell_slot_1.normalized_score==slots
    assert not caster.inventory.items


def test_dragons_breath_recipient_pays_repeat_with_original_dc(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(3,2),intelligence=8)
    enemy=combatant(game,'Enemy',(5,2),'foes')
    force_save_result(enemy,'dexterity',succeeds=False)
    cast(DragonsBreath,caster,ally,element='cold',cast_at_level=3)
    assert caster.action_economy.bonus_actions.normalized_score==0
    exhale=next(action for action in ally.registered_actions if isinstance(action,ExhaleDragonsBreath))
    hp=enemy.get_hp()
    with fixed_dice_faces(*([2]*20)):result=exhale.instantiate(end_position=enemy.position).apply()
    assert result is not None and not result.canceled
    assert enemy.get_hp()==hp-8
    assert ally.action_economy.actions.normalized_score==0
    assert caster.action_economy.actions.normalized_score==1
    assert exhale.spell_dc==caster.spell_save_dc()
    caster.remove_condition('Concentrating')
    assert not any(isinstance(action,ExhaleDragonsBreath) for action in ally.registered_actions)
    ally.action_economy.reset_all_costs()
    stale=exhale.instantiate(end_position=enemy.position).apply()
    assert stale is not None and stale.canceled
    assert ally.action_economy.actions.normalized_score==1


@pytest.mark.parametrize('resistance',[False,True])
def test_vampiric_own_damage_healing_excludes_same_type_hex_and_repeat_slot(game,resistance):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    caster.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name="Native second concentration slot",value=1,source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
    caster.receive_damage(50,DamageType.FORCE,enemy.uuid)
    cast(Hex,caster,enemy)
    if resistance:
        enemy.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=enemy.uuid,damage_type=DamageType.NECROTIC,value=ResistanceStatus.RESISTANCE))
    hp=caster.get_hp()
    with fixed_dice_faces(15,4,4,4,6):result=cast(VampiricTouch,caster,enemy)
    assert len(result.damages)==2
    assert all(damage.damage_type is DamageType.NECROTIC for damage in result.damages)
    assert caster.get_hp()==hp+(3 if resistance else 6)
    strike=next(action for action in caster.registered_actions if isinstance(action,VampiricTouchStrike))
    caster.action_economy.reset_all_costs()
    slots=caster.action_economy.spell_slot_3.normalized_score
    with fixed_dice_faces(15,2,2,2,2):result=strike.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert caster.action_economy.spell_slot_3.normalized_score==slots
    caster.remove_condition('Concentrating')
    assert not any(isinstance(action,VampiricTouchStrike) for action in caster.registered_actions)


def test_flame_blade_real_item_spell_accuracy_damage_and_drop_retirement(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    old=equip(caster)
    cast(FlameBlade,caster)
    blade=caster.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert isinstance(blade,FlameBladeItem)
    assert old.uuid in caster.inventory.items
    hp=enemy.get_hp()
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(15,3,3,3):result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.MELEE_MAIN)
    assert enemy.get_hp()==hp-9
    assert result.attack_bonus.normalized_score==caster.spell_attack_bonus().normalized_score
    caster.unequip_item(WeaponSlot.MELEE_MAIN)
    assert blade.uuid in caster.inventory.items
    assert caster.drop_item(blade.uuid) is not None
    assert BaseBlock.get(blade.uuid) is None
    assert BaseBlock.get(old.uuid) is old


@pytest.mark.parametrize('state',['dead','dying','stable'])
def test_revivify_companion_one_hp_and_optional_relocation(game,state):
    caster=combatant(game)
    ally=combatant(game,'Ally',(4,2))
    ally.is_player_companion=True
    ally.uses_death_saves=state!='dead'
    ally.receive_damage(ally.get_hp(),DamageType.FORCE,caster.uuid)
    if state=='stable':ally.stabilize()
    assert ally.health.life_state=={'dead':LifeState.DEAD,'dying':LifeState.DYING,'stable':LifeState.STABLE}[state]
    cast(Revivify,caster,ally,relocate=True,end_position=(4,3))
    assert ally.health.life_state is LifeState.ALIVE
    assert ally.get_normal_hp()==1
    assert ally.position==(4,3)


def test_revivify_rejects_noncompanion_and_disintegrated_remains_before_cost(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(4,2))
    ally.receive_damage(ally.get_hp(),DamageType.FORCE,caster.uuid)
    assert not Revivify(source_entity_uuid=caster.uuid,target_entity_uuid=ally.uuid).pre_validate()
    ally.is_player_companion=True
    ally.health.remains_disposition=RemainsDisposition.DISINTEGRATED
    assert not Revivify(source_entity_uuid=caster.uuid,target_entity_uuid=ally.uuid).pre_validate()
    assert caster.action_economy.actions.normalized_score==1


@pytest.mark.parametrize("flat_reduction,temp_hp,target_hp",[(4,0,200),(0,20,200),(0,0,1)])
def test_vampiric_post_mitigation_includes_temporary_hp_and_overkill_but_not_hex(game,flat_reduction,temp_hp,target_hp):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    caster.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name="Native second concentration slot",value=1,source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
    caster.receive_damage(50,DamageType.FORCE,enemy.uuid)
    cast(Hex,caster,enemy)
    if flat_reduction:
        enemy.health.damage_reduction.self_static.add_value_modifier(NumericalModifier(
            name="Packet defense",value=flat_reduction,source_entity_uuid=enemy.uuid,target_entity_uuid=enemy.uuid))
    if temp_hp:enemy.health.add_temporary_hit_points(temp_hp,enemy.uuid)
    enemy.health.damage_taken=enemy.get_max_hp()-target_hp
    hp=caster.get_hp()
    with fixed_dice_faces(15,4,4,4,6):result=cast(VampiricTouch,caster,enemy)
    assert len(result.damages)==2
    assert caster.get_hp()==hp+(12-flat_reduction)//2


def test_flame_blade_no_inventory_capacity_spends_nothing(game):
    caster=combatant(game)
    caster.inventory.max_slots=0
    slots=caster.action_economy.spell_slot_2.normalized_score
    result=FlameBlade(source_entity_uuid=caster.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.bonus_actions.normalized_score==1
    assert caster.action_economy.spell_slot_2.normalized_score==slots


def test_flame_blade_transfer_retires_exact_blade_and_preserves_other_weapon(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(3,2))
    old=equip(caster)
    cast(FlameBlade,caster)
    blade=caster.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    caster.unequip_item(WeaponSlot.MELEE_MAIN)
    assert caster.inventory.transfer_to(blade.uuid,ally.inventory)
    assert BaseBlock.get(blade.uuid) is None
    assert blade.uuid not in ally.inventory.items
    assert caster.inventory.items[old.uuid] is old


def test_all_goodberries_return_after_antimagic_blocker_leaves(game):
    caster=combatant(game)
    holder=combatant(game,'Holder',(3,2))
    field_caster=combatant(game,'Field caster',(7,2),'foes',slots={8:2})
    cast(Goodberry,caster,holder)
    berries=[item for item in holder.inventory.items.values() if isinstance(item,GoodberryItem)]
    holder.move((6,2))
    for berry in berries:holder.drop_item(berry.uuid)
    cast(AntimagicField,field_caster)
    assert all(get_map().get_object_placement(berry.uuid) is None for berry in berries)
    field_caster.remove_condition('Concentrating')
    assert all(berry.antimagic_suspended_placement is not None for berry in berries)
    holder.move((10,2))
    assert all(get_map().get_object_placement(berry.uuid) is not None for berry in berries)
    caster.on_long_rest()
    assert all(BaseBlock.get(berry.uuid) is None for berry in berries)


@pytest.mark.parametrize('blocked_event',[EventType.REVIVE,EventType.PORTAL_TRANSFER])
def test_revivify_native_admission_veto_preserves_death_position_and_payment(game,blocked_event):
    caster=combatant(game)
    ally=combatant(game,'Ally',(4,2))
    ally.is_player_companion=True
    ally.receive_damage(ally.get_hp(),DamageType.FORCE,caster.uuid)
    def veto(event,_):return event.cancel(status_message='Native admission veto')
    EventQueue.add_event_handler(EventHandler(source_entity_uuid=caster.uuid,name='Revival veto',
        trigger_conditions=[Trigger(event_type=blocked_event,event_phase=EventPhase.DECLARATION)],event_processor=veto))
    slots=caster.action_economy.spell_slot_3.normalized_score
    result=Revivify(source_entity_uuid=caster.uuid,target_entity_uuid=ally.uuid,relocate=True,end_position=(4,3)).apply()
    assert result is not None and result.canceled
    assert ally.health.life_state is LifeState.DEAD and ally.position==(4,2)
    assert caster.action_economy.actions.normalized_score==1
    assert caster.action_economy.spell_slot_3.normalized_score==slots


def test_ally_breath_uses_original_caster_dc_and_no_recipient_damage_bonus(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(3,2),intelligence=8)
    enemy=combatant(game,'Enemy',(5,2),'foes')
    ally.spellcasting.spell_damage_bonus.self_static.add_value_modifier(NumericalModifier(
        name='Recipient extra damage',value=25,source_entity_uuid=ally.uuid))
    cast(DragonsBreath,caster,ally,element='acid')
    exhale=next(action for action in ally.registered_actions if isinstance(action,ExhaleDragonsBreath))
    assert ally.spell_save_dc()<caster.spell_save_dc()
    hp=enemy.get_hp()
    cursor=EventQueue.event_cursor()
    with fixed_dice_faces(10,2,2,2):result=exhale.instantiate(end_position=enemy.position).apply()
    assert result is not None and not result.canceled
    saves=[event for _,event in EventQueue.iter_events_since(cursor) if isinstance(event,SavingThrowEvent)
        and event.target_entity_uuid==enemy.uuid and event.phase is EventPhase.COMPLETION]
    assert saves and saves[0].dc==caster.spell_save_dc()
    assert enemy.get_hp()==hp-6

