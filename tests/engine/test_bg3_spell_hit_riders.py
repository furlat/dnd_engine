"""Paid mark/favor casts, real weapon/spell attacks, and retained quarry state."""
from dnd.spells.transmutation import SlowedEffect, Shillelagh
from dnd.spells.abjuration import AntimagicField, GlobeOfInvulnerability
from dnd.spells.evocation import FlameBlade
from dnd.entity import Entity
import pytest
from uuid import uuid4
from dnd.classes.paladin import register_divine_smite, unregister_divine_smite, create_learned_divine_smite_handler, DivineSmiteHandler
from dnd.spells.reaction_spell_content import LEARNED_REACTION_SPELL_SPECS

from dnd.actions import Attack, AllyHelp
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import AdvantageStatus
from dnd.spells.divination import HuntersMark, ReapplyHuntersMark
from dnd.spells.enchantment import Hex, ReapplyHex
from dnd.spells.evocation import SearingSmite, BrandingSmite, DivineFavor, FireBolt, EldritchBlast, MagicMissile
from tests.engine.test_bg3_rank_one_two_spells import combatant, game
from dnd.spells.conjuration import EnsnaringStrike
from dnd.spells.transmutation import MagicWeapon
from tests.manual.spell_regression_support import force_save_result


def cast(spell,caster,target=None,**kwargs):
    caster.action_economy.reset_all_costs()
    result=spell(source_entity_uuid=caster.uuid,target_entity_uuid=(target or caster).uuid,**kwargs).apply()
    assert result is not None
    assert not result.canceled,result.status_message
    return result


def equip(caster,item_id='weapon.longsword',slot=WeaponSlot.MELEE_MAIN):
    item=build_authored_item(item_id,caster.uuid)
    assert caster.loot_item(item)
    assert caster.equip_item(item.uuid,slot)
    return item


@pytest.mark.parametrize('spell,die',[(DivineFavor,4),(HuntersMark,6),(Hex,6)])
@pytest.mark.parametrize('critical',[False,True])
def test_weapon_hit_appends_one_critical_aware_spell_component(game,spell,die,critical):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    equip(caster)
    cast(spell,caster,enemy if spell!=DivineFavor else None)
    with fixed_dice_faces(20 if critical else 15,*([2]*10)):
        result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.MELEE_MAIN)
    assert len(result.damages)==2
    assert result.damage_rolls[1].total==(4 if critical else 2)
    assert result.damages[1].damage_dice==die
    assert result.damages[1].effect_origin is not None
    caster.remove_condition('Concentrating')
    with fixed_dice_faces(15,2): result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.MELEE_MAIN)
    assert len(result.damages)==1


@pytest.mark.parametrize('spell',[HuntersMark,DivineFavor,Hex])
def test_hex_alone_adds_to_spell_attacks_not_automatic_damage(game,spell):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(5,2),'foes')
    cast(spell,caster,enemy if spell!=DivineFavor else None)
    with fixed_dice_faces(15,3,2):result=cast(FireBolt,caster,enemy)
    assert len(result.damages)==(2 if spell==Hex else 1)
    hp=enemy.get_hp()
    with fixed_dice_faces(2,2,2):cast(MagicMissile,caster,enemy)
    assert enemy.get_hp()==hp-9


def test_hex_changes_checks_and_linked_skills_without_changing_saves(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(5,2),'foes')
    save=enemy.saving_throws.get_saving_throw('strength').bonus.advantage
    cast(Hex,caster,enemy,ability='strength')
    assert enemy.ability_check_bonus(None,'strength').advantage==AdvantageStatus.DISADVANTAGE
    assert enemy.skill_bonus(None,'athletics').advantage==AdvantageStatus.DISADVANTAGE
    assert enemy.skill_bonus(None,'stealth').advantage==AdvantageStatus.NONE
    assert enemy.saving_throws.get_saving_throw('strength').bonus.advantage==save


@pytest.mark.parametrize('spell,reapply',[(HuntersMark,ReapplyHuntersMark),(Hex,ReapplyHex)])
def test_defeated_quarry_reapply_preserves_concentration_and_spends_no_slot(game,spell,reapply):
    caster=combatant(game)
    enemy=combatant(game,'First',(4,2),'foes')
    next_enemy=combatant(game,'Second',(6,2),'foes')
    cast(spell,caster,enemy)
    granted=next(action for action in caster.registered_actions if isinstance(action,reapply))
    assert not granted.instantiate(target_entity_uuid=next_enemy.uuid).pre_validate()
    enemy.receive_damage(enemy.get_hp(),DamageType.FORCE,caster.uuid)
    assert 'Concentrating' in set(caster.active_conditions)
    caster.action_economy.reset_all_costs()
    slots=caster.action_economy.spell_slot_1.normalized_score
    result=granted.instantiate(target_entity_uuid=next_enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert caster.action_economy.spell_slot_1.normalized_score==slots
    assert caster.action_economy.bonus_actions.normalized_score==0
    assert 'Concentrating' in set(caster.active_conditions)
    caster.remove_condition('Concentrating')
    assert not any(isinstance(action,reapply) for action in caster.registered_actions)



@pytest.mark.parametrize('spell',[SearingSmite,BrandingSmite,EnsnaringStrike])
@pytest.mark.parametrize('hit',[False,True])
def test_attack_backed_spell_pays_slot_and_bonus_only_on_hit(game,spell,hit):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    equip(caster)
    caster.action_economy.reset_all_costs()
    rank=spell.model_fields['spell_level'].default
    slots=caster.action_economy.spell_slot_1 if rank==1 else caster.action_economy.spell_slot_2
    before=slots.normalized_score
    force_save_result(enemy,'strength',succeeds=False)
    with fixed_dice_faces(15 if hit else 1,*([2]*12)):
        result=spell(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None
    assert not result.canceled,result.status_message
    assert caster.action_economy.actions.normalized_score==0
    assert caster.action_economy.bonus_actions.normalized_score==(0 if hit else 1)
    assert slots.normalized_score==before-(1 if hit else 0)
    if hit and spell in (SearingSmite,BrandingSmite):
        assert len(result.damages)==2


def test_ensnaring_ticks_and_ally_help_restores_movement(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    helper=combatant(game,'Helper',(4,2),'foes')
    equip(caster)
    force_save_result(enemy,'strength',succeeds=False)
    with fixed_dice_faces(15,*([2]*8)):cast(EnsnaringStrike,caster,enemy)
    assert enemy.action_economy.current_speed()==0
    hp=enemy.get_hp()
    with fixed_dice_faces(3):enemy.on_turn_start()
    assert enemy.get_hp()==hp-3
    cast(AllyHelp,helper,enemy)
    assert enemy.action_economy.current_speed()>0
    assert 'Ensnaring Strike' not in set(enemy.active_conditions)


def test_magic_weapon_bonus_and_exact_concentration_cleanup(game):
    caster=combatant(game)
    ally=combatant(game,'Ally',(3,2))
    enemy=combatant(game,'Enemy',(4,2),'foes')
    weapon=equip(ally)
    baseline=ally.attack_bonus(WeaponSlot.MELEE_MAIN,enemy.uuid).normalized_score
    cast(MagicWeapon,caster,ally)
    assert ally.attack_bonus(WeaponSlot.MELEE_MAIN,enemy.uuid).normalized_score==baseline+1
    assert weapon.attack_is_magical(ally.uuid)
    caster.remove_condition('Concentrating')
    assert ally.attack_bonus(WeaponSlot.MELEE_MAIN,enemy.uuid).normalized_score==baseline
    assert not weapon.attack_is_magical(ally.uuid)


def test_learned_divine_smite_and_feature_share_five_toggles_and_one_hit(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    equip(caster)
    spec=next(spec for spec in LEARNED_REACTION_SPELL_SPECS if spec.declaration.ref.content_id=='spell.divine_smite')
    learned=spec.handler_factory(caster.uuid)
    caster.add_event_handler(learned)
    identities=dict(caster.spellcasting.divine_smite_handler_uuids)
    assert len(identities)==5
    register_divine_smite(caster)
    assert caster.spellcasting.divine_smite_handler_uuids==identities
    slot=caster.action_economy.spell_slot_3
    before=slot.normalized_score
    with fixed_dice_faces(15,*([2]*12)):result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.MELEE_MAIN)
    assert len(result.damages)==2
    assert result.damages[1].dice_numbers==4
    assert slot.normalized_score==before-1
    caster.remove_event_handler(learned)
    assert caster.spellcasting.divine_smite_handler_uuids==identities
    unregister_divine_smite(caster,caster.uuid)
    assert not caster.spellcasting.divine_smite_handler_uuids
    assert not any(isinstance(handler,DivineSmiteHandler) for handler in caster.event_handlers.values())


def test_learned_smite_last_owner_cleanup_and_no_spell_attack_smite(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(4,2),'foes')
    learned=create_learned_divine_smite_handler(caster.uuid)
    caster.add_event_handler(learned)
    before=caster.action_economy.spell_slot_3.normalized_score
    with fixed_dice_faces(15,3):result=cast(FireBolt,caster,enemy)
    assert len(result.damages)==1
    assert caster.action_economy.spell_slot_3.normalized_score==before
    learned.remove()
    assert not caster.spellcasting.divine_smite_handler_uuids
    assert not caster.spellcasting.divine_smite_entitlements


@pytest.mark.parametrize('spell',[SearingSmite,BrandingSmite,EnsnaringStrike])
def test_slow_rejects_required_action_and_conditional_bonus_before_payment(game,spell):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    equip(caster)
    caster.add_condition(SlowedEffect(source_entity_uuid=enemy.uuid,target_entity_uuid=caster.uuid,spell_dc=100))
    slots=caster.action_economy.spell_slot_1.normalized_score
    action=spell(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid)
    assert not action.pre_validate()
    result=action.apply()
    assert result is None or result.canceled
    assert caster.action_economy.actions.normalized_score==1
    assert caster.action_economy.bonus_actions.normalized_score==1
    assert caster.action_economy.spell_slot_1.normalized_score==slots


@pytest.mark.parametrize('spell',[SearingSmite,BrandingSmite,EnsnaringStrike])
def test_attack_backed_spell_rejects_flame_blade_spell_attacks_before_payment(game,spell):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    cast(FlameBlade,caster)
    caster.action_economy.reset_all_costs()
    slots=(caster.action_economy.spell_slot_1.normalized_score,caster.action_economy.spell_slot_2.normalized_score)
    action=spell(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid)
    assert not action.pre_validate()
    result=action.apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score==1 and caster.action_economy.bonus_actions.normalized_score==1
    assert slots==(caster.action_economy.spell_slot_1.normalized_score,caster.action_economy.spell_slot_2.normalized_score)


def test_hex_multi_beam_hit_miss_critical_and_independent_casters(game):
    caster=combatant(game)
    other=combatant(game,'Other caster',(2,4))
    first=combatant(game,'Marked',(6,2),'foes')
    second=combatant(game,'Other quarry',(6,4),'foes')
    cast(Hex,caster,first)
    cast(Hex,other,second)
    hp=first.get_hp();other_hp=second.get_hp()
    with fixed_dice_faces(15,4,2,1,20,3,5,1,2):
        result=cast(EldritchBlast,caster,first,caster_level=11,extra_target_entity_uuids=[second.uuid,first.uuid])
    assert result is not None and not result.canceled
    assert first.get_hp()==hp-17 and second.get_hp()==other_hp
    with fixed_dice_faces(15,4):cast(EldritchBlast,other,first)
    assert first.get_hp()==hp-21
    with fixed_dice_faces(15,4,2):cast(EldritchBlast,other,second)
    assert second.get_hp()==other_hp-6


def test_magic_weapon_composes_with_shillelagh_and_follows_real_transfer(game):
    caster=combatant(game)
    holder=combatant(game,'Holder',(3,2))
    recipient=combatant(game,'Recipient',(4,2))
    enemy=combatant(game,'Enemy',(5,2),'foes')
    weapon=equip(holder,'weapon.quarterstaff')
    cast(Shillelagh,holder)
    baseline=holder.attack_bonus(WeaponSlot.MELEE_MAIN,enemy.uuid).normalized_score
    cast(MagicWeapon,caster,holder)
    assert weapon.attack_damage_die(holder.uuid)==8
    assert holder.attack_bonus(WeaponSlot.MELEE_MAIN,enemy.uuid).normalized_score==baseline+1
    assert holder.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert holder.drop_item(weapon.uuid) is weapon
    assert recipient.loot_item(weapon) and recipient.equip_item(weapon.uuid,WeaponSlot.MELEE_MAIN)
    assert 'Shillelagh' not in set(holder.active_conditions)
    assert weapon.attack_bonus.normalized_score==1 and weapon.attack_is_magical(recipient.uuid)
    caster.remove_condition('Concentrating')
    assert weapon.attack_bonus.normalized_score==0 and not weapon.attack_is_magical(recipient.uuid)


@pytest.mark.parametrize('contact',[False,True])
def test_magic_weapon_arrow_crossing_or_contacting_antimagic_keeps_physical_damage(game,contact):
    caster=combatant(game,position=(1,2))
    enemy=combatant(game,'Enemy',(10,2),'foes')
    field_caster=combatant(game,'Field',(5,3),slots={8:1})
    weapon=equip(caster,'weapon.longbow',WeaponSlot.RANGED_MAIN)
    cast(MagicWeapon,caster,weapon_slot=WeaponSlot.RANGED_MAIN)
    assert weapon.attack_bonus.normalized_score==1
    cast(AntimagicField,field_caster)
    if contact:Entity.update_entity_position(enemy,(6,2))
    Entity.update_all_entities_senses()
    hp=enemy.get_hp()
    with fixed_dice_faces(15,5):result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.RANGED_MAIN)
    assert enemy.get_hp()==hp-5
    assert result.item_magic_suppression_provider_uuids and not result.attack_is_magical
    assert weapon.attack_bonus.normalized_score==1


@pytest.mark.parametrize('protection',[GlobeOfInvulnerability,AntimagicField])
def test_attack_backed_smite_protection_stops_rider_and_preserves_physical_hit(game,protection):
    caster=combatant(game,position=(4,2))
    enemy=combatant(game,'Enemy',(5,2),'foes')
    field_caster=combatant(game,'Field',(7,2),'foes',slots={6:1,8:1})
    equip(caster)
    cast(protection,field_caster)
    hp=enemy.get_hp()
    with fixed_dice_faces(15,*([2]*12)):result=cast(BrandingSmite,caster,enemy)
    assert enemy.get_hp()==hp-2
    assert len(result.damages)==1
    assert not any(condition.get_display_name()=='Branding Smite' for condition in enemy.active_conditions_by_uuid.values())


def test_two_magic_weapon_casters_keep_strongest_bonus_then_fall_back(game):
    first=combatant(game)
    second=combatant(game,'Stronger caster',(2,3),slots={4:1})
    holder=combatant(game,'Holder',(3,2))
    weapon=equip(holder)
    cast(MagicWeapon,first,holder)
    cast(MagicWeapon,second,holder,cast_at_level=4)
    assert weapon.attack_bonus.normalized_score==2
    second.remove_condition('Concentrating')
    assert weapon.attack_bonus.normalized_score==1
    first.remove_condition('Concentrating')
    assert weapon.attack_bonus.normalized_score==0



def test_feature_first_then_learned_smite_keeps_toggle_and_uses_highest_slot(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(3,2),'foes')
    equip(caster)
    register_divine_smite(caster,max_slot_level=1)
    first_toggle=caster.spellcasting.divine_smite_handler_uuids[1]
    learned=create_learned_divine_smite_handler(caster.uuid)
    caster.add_event_handler(learned)
    assert caster.spellcasting.divine_smite_handler_uuids[1]==first_toggle
    slots=caster.action_economy.spell_slot_3.normalized_score
    with fixed_dice_faces(15,*([2]*12)):result=cast(Attack,caster,enemy,weapon_slot=WeaponSlot.MELEE_MAIN)
    assert len(result.damages)==2 and result.damages[1].dice_numbers==4
    assert caster.action_economy.spell_slot_3.normalized_score==slots-1
    caster.remove_event_handler(learned)
    assert caster.spellcasting.divine_smite_handler_uuids=={1:first_toggle}
