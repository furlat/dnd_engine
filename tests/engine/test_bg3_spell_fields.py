"""Persistent spell fields and their actual exposure, movement and cleanup."""
from dnd.actions import Shove
from dnd.spells.evocation import RayOfFrost, LightningBolt, FireBolt
from dnd.spatial.environmental_conditions import IceSurface, ElectrifiedWater, SteamCloud
from dnd.spells.abjuration import GlyphSleepEffect
import pytest
from uuid import uuid4
from dnd.core.base_block import LightLevel
from dnd.core.events import Event, EventQueue, EventPhase, EventType, EventHandler, Trigger
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.equipment_types import WeaponSlot
from dnd.types.world import MovementMode
from dnd.spells.transmutation import CreateOrDestroyWater, PlantGrowth
from dnd.spells.evocation import Moonbeam, MoveMoonbeam, ChromaticOrb, AcidArrow
from dnd.spells.abjuration import GlyphOfWarding
from dnd.spells.enchantment import Hex
from dnd.spells.surfaces import SpellAcidSurface, SimpleToxinSurface
from dnd.spatial.environmental_conditions import WetSurface, Wet, FireSurface
from dnd.spatial.ignition import ignite_surface_contacts
from dnd.core.creature_types import CreatureType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.spells.evocation import DancingLights, MoveDancingLights
from dnd.spells.illusion import PhantasmalForce
from tests.engine.test_bg3_rank_one_two_spells import combatant, game
from tests.engine.test_bg3_spell_hit_riders import cast
from tests.manual.spell_regression_support import force_save_result


def test_dancing_lights_moves_owned_light_and_concentration_removes_repeat(game):
    caster=combatant(game)
    grid=get_map()
    grid.set_tile_base_light((16,2),LightLevel.DARKNESS)
    result=DancingLights(source_entity_uuid=caster.uuid,end_position=(5,2)).apply()
    assert result is not None and not result.canceled
    grid.set_tile_base_light((5,2),LightLevel.DARKNESS)
    assert grid.get_tile(5,2).resolved_light_level==LightLevel.BRIGHT_LIGHT
    action=next(action for action in caster.registered_actions if isinstance(action,MoveDancingLights))
    caster.action_economy.reset_all_costs()
    result=action.instantiate(end_position=(11,2)).apply()
    assert result is not None and not result.canceled
    assert caster.action_economy.bonus_actions.normalized_score==0
    assert grid.get_tile(16,2).resolved_light_level==LightLevel.BRIGHT_LIGHT
    caster.remove_condition('Concentrating')
    assert not any(isinstance(action,MoveDancingLights) for action in caster.registered_actions)
    assert grid.get_tile(16,2).resolved_light_level==LightLevel.DARKNESS


def test_phantasmal_force_tracks_external_positive_damage_and_ends_on_repeat_save(game):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    force_save_result(target,'intelligence',succeeds=False)
    cast(PhantasmalForce,caster,target)
    hp=target.get_hp()
    with fixed_dice_faces(3):target.on_turn_start()
    assert target.get_hp()==hp-3
    target.receive_damage(4,DamageType.FIRE,caster.uuid)
    effect=next(condition for condition in target.active_conditions_by_uuid.values() if condition.get_display_name()=='Phantasmal Force')
    assert effect.damage_type==DamageType.FIRE
    hp=target.get_hp()
    with fixed_dice_faces(3):target.on_turn_start()
    assert target.get_hp()==hp-3
    assert effect.damage_type==DamageType.FIRE
    force_save_result(target,'intelligence',succeeds=True)
    force_save_result(target,'intelligence',succeeds=True)
    target.on_turn_end()
    assert not any(condition.get_display_name()=='Phantasmal Force' for condition in target.active_conditions_by_uuid.values())


def position_cast(spell,caster,position,**kwargs):
    caster.action_economy.reset_all_costs()
    result=spell(source_entity_uuid=caster.uuid,end_position=position,**kwargs).apply()
    assert result is not None
    assert not result.canceled,result.status_message
    return result


def test_create_destroy_water_preserves_direct_rain_lease(game):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    position_cast(CreateOrDestroyWater,caster,(5,2))
    assert 'Wet' in set(target.active_conditions)
    assert any(isinstance(field,WetSurface) for field in get_map().get_spatial_conditions())
    position_cast(CreateOrDestroyWater,caster,(5,2),mode='destroy')
    assert not any(isinstance(field,WetSurface) for field in get_map().get_spatial_conditions())
    assert 'Wet' in set(target.active_conditions)
    for _ in range(3):target.on_turn_start()
    assert 'Wet' not in set(target.active_conditions)


@pytest.mark.parametrize('element,field_type',[('acid',SpellAcidSurface),('poison',SimpleToxinSurface),('fire',FireSurface)])
def test_orb_ground_cast_creates_patch_without_initial_hit_damage(game,element,field_type):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    force_save_result(target,'constitution',succeeds=False)
    hp=target.get_hp()
    position_cast(ChromaticOrb,caster,(5,2),element=element,target_mode='ground')
    assert target.get_hp()==hp
    assert any(isinstance(field,field_type) for field in get_map().get_spatial_conditions())
    if element=='poison':
        with fixed_dice_faces(3):target.on_turn_end()
        assert target.get_hp()==hp-3


def test_acid_patch_penalty_nonstacking_and_movement_restores_ac(game):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    baseline=target.ac_bonus().normalized_score
    position_cast(ChromaticOrb,caster,(5,2),element='acid',target_mode='ground')
    position_cast(ChromaticOrb,caster,(5,2),element='acid',target_mode='ground')
    assert target.ac_bonus().normalized_score==baseline-2
    target.move((10,2))
    assert target.ac_bonus().normalized_score==baseline


@pytest.mark.parametrize('hit',[False,True])
def test_acid_arrow_miss_half_has_no_hex_or_delayed_tick(game,hit):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    cast(Hex,caster,target)
    hp=target.get_hp()
    with fixed_dice_faces(15 if hit else 1,*([2]*10)):
        result=cast(AcidArrow,caster,target)
    assert target.get_hp()==hp-(10 if hit else 4)
    assert result.attack_outcome in ((AttackOutcome.HIT,AttackOutcome.CRIT) if hit else (AttackOutcome.MISS,AttackOutcome.CRIT_MISS))
    hp=target.get_hp()
    with fixed_dice_faces(3,3):target.on_turn_end()
    assert target.get_hp()==hp-(6 if hit else 0)
    hp=target.get_hp()
    target.on_turn_end()
    assert target.get_hp()==hp


def test_moonbeam_initial_and_entry_share_one_turn_allowance_and_move(game):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    other=combatant(game,'Other',(7,2),'foes')
    for actor in (target,other):force_save_result(actor,'constitution',succeeds=False)
    turn=EventQueue.begin_turn_execution()
    hp=target.get_hp()
    with fixed_dice_faces(5,3,3):position_cast(Moonbeam,caster,(5,2))
    assert target.get_hp()==hp-6
    target.move((6,2));target.move((5,2))
    assert target.get_hp()==hp-6
    EventQueue.end_turn_execution(turn)
    turn=EventQueue.begin_turn_execution()
    hp=target.get_hp()
    with fixed_dice_faces(5,3,3):target.on_turn_start()
    assert target.get_hp()==hp-6
    move=next(action for action in caster.registered_actions if isinstance(action,MoveMoonbeam))
    caster.action_economy.reset_all_costs()
    hp=other.get_hp()
    with fixed_dice_faces(5,3,3):result=move.instantiate(end_position=other.position).apply()
    assert result is not None and not result.canceled
    assert other.get_hp()==hp-6
    caster.remove_condition('Concentrating')
    assert not any(field.get_display_name()=='Moonbeam' for field in get_map().get_spatial_conditions())
    EventQueue.end_turn_execution(turn)


def test_rejected_moonbeam_concentration_has_no_initial_damage_or_field(game):
    caster=combatant(game)
    target=combatant(game,'Enemy',(5,2),'foes')
    hp=target.get_hp()
    def veto(event,source):
        if isinstance(event,ConditionApplicationEvent) and event.condition.name=='Concentrating':
            return event.cancel(status_message='Concentration rejected')
        return None
    handler=EventHandler(name='Reject concentration',source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,event_phase=EventPhase.DECLARATION)],event_processor=veto)
    caster.add_event_handler(handler)
    result=Moonbeam(source_entity_uuid=caster.uuid,end_position=target.position).apply()
    assert result is not None and result.canceled
    assert target.get_hp()==hp
    assert not any(field.get_display_name()=='Moonbeam' for field in get_map().get_spatial_conditions())


def test_plant_growth_strongest_cost_partial_fire_and_flight_bypass(game):
    caster=combatant(game)
    position_cast(PlantGrowth,caster,(5,2))
    position_cast(PlantGrowth,caster,(5,2))
    grid=get_map()
    assert grid.get_tile(5,2).get_movement_cost(MovementMode.WALKING)==4
    assert grid.get_tile(5,2).get_movement_cost(MovementMode.FLYING)==1
    assert grid.movement_edge_cost_units((4,2),(5,2),MovementMode.WALKING,ignore_difficult_terrain=True)==1
    parent=Event(source_entity_uuid=caster.uuid,event_type=EventType.BASE_ACTION)
    ignite_surface_contacts(parent,{(5,2)})
    assert grid.get_tile(5,2).get_movement_cost(MovementMode.WALKING)==1
    assert grid.get_tile(6,2).get_movement_cost(MovementMode.WALKING)==4


@pytest.mark.parametrize('payload',['acid','cold','fire','lightning','thunder','sleep','detonation'])
def test_glyph_hostile_occupancy_triggers_once_and_affects_all_factions(game,payload):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(7,2),'foes')
    ally=combatant(game,'Ally',(7,3))
    for target in (enemy,ally):force_save_result(target,'dexterity',succeeds=False)
    hp=[enemy.get_hp(),ally.get_hp()]
    with fixed_dice_faces(*([3]*30)):position_cast(GlyphOfWarding,caster,(7,2),payload=payload)
    assert not any(field.get_display_name()=='Glyph of Warding' for field in get_map().get_spatial_conditions())
    assert 'Glyph of Warding Sustain' not in set(caster.active_conditions)
    if payload=='sleep':
        assert 'Glyph Sleep' in set(enemy.active_conditions)
        assert 'Glyph Sleep' in set(ally.active_conditions)
    elif payload=='detonation':
        assert enemy.position!=(7,2) and ally.position!=(7,3)
    else:
        assert [enemy.get_hp(),ally.get_hp()]==[value-15 for value in hp]


@pytest.mark.parametrize('spell,field_type',[(RayOfFrost,IceSurface),(LightningBolt,ElectrifiedWater),(FireBolt,SteamCloud)])
def test_native_elemental_spells_transform_created_water(game,spell,field_type):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(6,2),'foes')
    position_cast(CreateOrDestroyWater,caster,enemy.position)
    force_save_result(enemy,'dexterity',succeeds=False)
    with fixed_dice_faces(15,*([2]*40)):
        if spell is LightningBolt:position_cast(spell,caster,enemy.position)
        else:cast(spell,caster,enemy)
    assert any(isinstance(field,field_type) and enemy.position in field.affected_positions
        for field in get_map().get_spatial_conditions())


def test_successful_ally_shove_wakes_glyph_sleep_without_damage(game):
    caster=combatant(game)
    ally=combatant(game,'Sleeping ally',(3,2))
    ally.add_condition(GlyphSleepEffect(source_entity_uuid=caster.uuid,target_entity_uuid=ally.uuid))
    hp=ally.get_hp()
    assert 'Glyph Sleep' in set(ally.active_conditions)
    result=Shove(source_entity_uuid=caster.uuid,target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled and result.contest_success
    assert 'Glyph Sleep' not in set(ally.active_conditions)
    assert ally.get_hp()==hp

