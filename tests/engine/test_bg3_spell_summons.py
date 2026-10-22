"""Spell summons use actual native birth, turns, attacks, fields and departure."""
import pytest
from dnd.actions import Attack, Move
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventType, EventHandler, EventPhase, Trigger
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.spell_summons import FlamingSphereRam, FlamingSphereZone
from dnd.spells.summoning import SpiritualWeapon, FlamingSphere
from dnd.spatial.environmental_conditions import FireSurface
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.summoning.actions import DismissSummon
from dnd.types.world import MovementMode
from tests.engine.test_summoning_lifecycle import battle
from tests.engine.test_summoning_autonomous_turns import autonomous_attack, autonomous_battle
from tests.manual.spell_regression_support import force_save_result


def summon(battle,spell,level=3):
    _,_,system,caster,_=battle
    caster.action_economy.reset_all_costs()
    result=spell(source_entity_uuid=caster.uuid,cast_at_level=level,end_position=(4,2)).apply()
    assert result is not None and not result.canceled,result.status_message if result else 'No result'
    return next(member for member in system.memberships.values() if member.entity.position==(4,2))


def test_spiritual_weapon_scaled_real_native_creature_and_autonomous_attack(autonomous_battle):
    battle = autonomous_battle
    game,encounter,system,caster,enemy=battle
    Entity.update_entity_position(enemy,(5,2));Entity.update_all_entities_senses()
    member=summon(battle,SpiritualWeapon,4)
    assert member.entity.get_max_hp()==28
    assert member.entity.ac_bonus().normalized_score==10
    assert member.entity.action_economy.reactions.normalized_score==0
    assert 'Concentrating' not in set(caster.active_conditions)
    assert caster.action_economy.bonus_actions.normalized_score==0
    hp=enemy.get_hp()
    encounter.next_turn()
    result=autonomous_attack(encounter,member.entity.uuid)
    assert result.target_entity_uuid==enemy.uuid
    assert result.damages[0].damage_type is DamageType.FORCE
    assert result.damages[0].dice_numbers==2
    assert result.attack_bonus.normalized_score==caster.proficiency_bonus.normalized_score
    assert enemy.get_hp()==hp-3
    assert member.entity.uuid in encounter.initiative_order
    caster.action_economy.reset_all_costs()
    result=DismissSummon(source_entity_uuid=caster.uuid,target_entity_uuid=member.entity.uuid).apply()
    assert result is not None and not result.canceled
    assert game.get_entity(member.entity.uuid) is None
    assert member.entity.uuid not in system.memberships


def test_spiritual_weapon_moves_on_its_turn_and_retires_with_caster(battle):
    game,encounter,system,caster,enemy=battle
    weapon=summon(battle,SpiritualWeapon).entity
    encounter.next_turn()
    assert encounter.get_current_entity().uuid==weapon.uuid
    assert weapon.action_economy.movement_remaining(MovementMode.FLYING)==20
    move=next(action for action in weapon.registered_actions if isinstance(action,Move))
    result=move.instantiate(end_position=(5,2)).apply()
    assert result is not None and not result.canceled
    assert weapon.position==(5,2)
    assert weapon.action_economy.movement_remaining(MovementMode.FLYING)==15
    for _ in range(3):
        encounter.next_turn()
    assert encounter.get_current_entity().uuid==weapon.uuid
    assert weapon.action_economy.movement_remaining(MovementMode.FLYING)==20
    caster.receive_damage(caster.get_hp(),DamageType.FORCE,enemy.uuid)
    assert game.get_entity(weapon.uuid) is None
    assert weapon.uuid not in system.memberships
    assert not weapon.has_runtime_agency()
    assert not weapon.action_economy.movement_speed_grants


def test_flaming_sphere_ram_aura_trail_and_concentration_cleanup(battle):
    game,encounter,system,caster,enemy=battle
    Entity.update_entity_position(enemy,(5,2));Entity.update_all_entities_senses()
    force_save_result(enemy,'dexterity',succeeds=False)
    member=summon(battle,FlamingSphere)
    sphere=member.entity
    assert sphere.get_max_hp()==20
    assert sphere.ac_bonus().normalized_score==16
    assert 'Concentrating' in set(caster.active_conditions)
    assert any(isinstance(zone,FlamingSphereZone) for zone in get_map().get_spatial_conditions())
    Entity.update_entity_position(caster,(3,2))
    hp=enemy.get_hp();caster_hp=caster.get_hp()
    with fixed_dice_faces(*([2]*20)):enemy.on_turn_end()
    assert enemy.get_hp()==hp-6
    caster.on_turn_end()
    assert caster.get_hp()==caster_hp
    hp=enemy.get_hp()
    ram=next(action for action in sphere.registered_actions if isinstance(action,FlamingSphereRam))
    with fixed_dice_faces(*([2]*20)):result=ram.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert enemy.get_hp()==hp-6
    assert sphere.action_economy.bonus_actions.normalized_score==0
    sphere.move((4,3))
    assert any(isinstance(zone,FireSurface) and (4,2) in zone.affected_positions for zone in get_map().get_spatial_conditions())
    parent=Event(source_entity_uuid=caster.uuid,event_type=EventType.BASE_ACTION)
    apply_elemental_surface_contacts(parent,{(4,2)},DamageType.COLD)
    assert sphere.uuid in system.memberships
    caster.remove_condition('Concentrating')
    assert game.get_entity(sphere.uuid) is None
    assert not any(isinstance(zone,FlamingSphereZone) for zone in get_map().get_spatial_conditions())


@pytest.mark.parametrize('spell',[SpiritualWeapon,FlamingSphere])
def test_spell_summon_defeat_retires_exact_body(battle,spell):
    game,_,system,caster,enemy=battle
    member=summon(battle,spell)
    member.entity.receive_damage(1000,DamageType.FORCE,enemy.uuid)
    assert game.get_entity(member.entity.uuid) is None
    assert member.entity.uuid not in system.memberships


def test_spiritual_weapon_recast_replaces_only_same_caster_family(battle):
    game,_,system,caster,_=battle
    first=summon(battle,SpiritualWeapon)
    caster.action_economy.reset_all_costs()
    result=SpiritualWeapon(source_entity_uuid=caster.uuid,cast_at_level=3,end_position=(4,3)).apply()
    assert result is not None and not result.canceled
    assert game.get_entity(first.entity.uuid) is None
    assert len(system.memberships)==1
    assert next(iter(system.memberships.values())).entity.position==(4,3)


def test_sphere_damages_breakable_objects_on_its_own_turn_end(battle):
    _,_,_,caster,_=battle
    member=summon(battle,FlamingSphere)
    item=build_storage_chest("Sphere contact chest",include_loot_all_action=False)
    item.place_on_grid((4,3))
    hp=item.get_hp()
    with fixed_dice_faces(*([2]*30)):member.entity.on_turn_end()
    assert item.get_hp()<hp


def test_spiritual_weapon_owner_veto_leaves_no_native_summon(battle):
    _,_,system,caster,_=battle
    def veto(event,_):
        if isinstance(event,ConditionApplicationEvent) and event.condition.name=='Spiritual Weapon Owner':
            return event.cancel(status_message='Owner admission veto')
        return None
    caster.add_event_handler(EventHandler(name='Spiritual owner veto',source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,event_phase=EventPhase.DECLARATION)],event_processor=veto))
    result=SpiritualWeapon(source_entity_uuid=caster.uuid,cast_at_level=3,end_position=(4,2)).apply()
    assert result is not None and result.canceled
    assert not system.memberships
    assert not any(isinstance(zone,FlamingSphereZone) for zone in get_map().get_spatial_conditions())
