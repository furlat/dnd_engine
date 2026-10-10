"""Accepted class presentation driven by real direct progression and native commands."""
import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig,HitDiceConfig
from dnd.content.characters.fighter_grants import apply_fighter_level
from dnd.content.characters.barbarian_grants import apply_barbarian_level
from dnd.content.characters.sorcerer_grants import apply_sorcerer_level
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart,WeaponSlot
from dnd.core.events import EventQueue
from dnd.conditions import Frightened,Charmed,Blinded,Deafened
from dnd.entity import Entity,EntityConfig
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.player.capture import capture_interval,reduce_interval
from dnd.player.recorded import CapturedHistory,ObserverCapture,capture_history
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import force_save_result
from tests.progression.test_direct_fighter_progression import _fighter_level
from tests.progression.test_direct_barbarian_progression import _barbarian_level
from tests.progression.test_direct_sorcerer_progression import _level

ClassProgram=Literal['rage','frenzy','reckless','intimidate','relentless','mindless','native_martial',
 'second_wind','action_surge','protection','indomitable','survivor','font_gather','font_shape',
 'quickened','twinned','distant','affinity','wings','awe','draconic_fear']


def class_feature_history(*,program:ClassProgram,succeeded:bool=True,hidden_owner:bool=False, retire:bool=False, martial_route:Literal['frenzied','retaliation','extra']='frenzied') -> CapturedHistory:
    random_state=random.getstate();reset_engine_runtime();battlefield='battlefield.open_floor_bright'
    build_battlefield(battlefield);game=Game()
    try:
        actors={}
        fighter=program in ('second_wind','action_surge','protection','indomitable','survivor')
        barbarian=program in ('rage','frenzy','reckless','intimidate','relentless','mindless','native_martial')
        for role,pos in [('owner',(4,6)),('recipient',(5,6)),('observer',(4,7) if program=='protection' else (3,8))]:
            actor=Entity.create(uuid4(),role.title(),config=EntityConfig(position=pos,
                faction='foes' if role=='recipient' else 'heroes',
                appearance=AppearanceConfig(body_category='NakedBody',has_beard=False),
                health=HealthConfig(hit_dices=[] if role=='owner' else [HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=20,mode='maximums')],max_hit_points_bonus=200)))
            actor.install_initial_items(((build_authored_item('weapon.longsword',actor.uuid),WeaponSlot.MELEE_MAIN),))
            if role=='owner' and program=='protection':
                actor.install_initial_items(((build_authored_item('shield.shield',actor.uuid),WeaponSlot.MELEE_OFF),))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET)))
            actor.compose_entity();setup_standard_actions(actor)
            if role=='owner':
                for level in range(1,(18 if fighter else 2 if program=='rage' else 11 if program=='relentless' else 14 if barbarian else 18)+1):
                    if fighter:apply_fighter_level(actor,_fighter_level(level,first_style='class_feature.fighter.fighting_style.protection'))
                    elif barbarian:apply_barbarian_level(actor,_barbarian_level(level))
                    else:apply_sorcerer_level(actor,_level(level))
            game.deploy_entity(actor,pos);actors[role]=actor
        owner,target=actors['owner'],actors['recipient']
        encounter=Encounter(name='Native class presentation',source_entity_uuid=owner.uuid)
        for actor in actors.values():encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*30)):encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not owner:encounter.next_turn()
        def action(identity,**kw):
            template=next((a for a in owner.registered_actions if a.behavior_binding is not None
                and a.behavior_binding.behavior_id==identity),None)
            assert template is not None,identity
            owner.action_economy.reset_all_costs()
            result=template.instantiate(**kw).apply()
            assert result is not None and not result.canceled,(identity,result.status_message if result else None)
            return result
        if program in ('relentless','native_martial'):action('action.class.barbarian.frenzy')
        if program=='mindless':
            owner.add_condition(Frightened(source_entity_uuid=target.uuid,target_entity_uuid=owner.uuid))
            owner.add_condition(Charmed(source_entity_uuid=target.uuid,target_entity_uuid=owner.uuid))
        if program in ('second_wind','survivor'):set_hp(owner,25)
        if program=='relentless':set_hp(owner,10)
        if program=='font_gather':owner.action_economy.resources['sorcery_points'].current=2
        if program=='font_shape':owner.action_economy.consume('spell_slot_2',1)
        if hidden_owner:
            observer=actors['observer']
            observer.add_condition(Blinded(source_entity_uuid=observer.uuid,target_entity_uuid=observer.uuid))
            observer.add_condition(Deafened(source_entity_uuid=observer.uuid,target_entity_uuid=observer.uuid))
        Entity.update_all_entities_senses();baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Class feature initialization',start_cursor=0,end_cursor=baseline,
            observer_uuid=owner.uuid,battlefield_id=battlefield);before,_=reduce_interval(None,initial)
        if program=='indomitable':
            with fixed_dice_faces(1,20 if succeeded else 1):owner.saving_throw(target.create_saving_throw_request(owner.uuid,'wisdom',20))
        elif program=='relentless':
            with fixed_dice_faces(20 if succeeded else 1):owner.receive_damage(20,DamageType.FORCE,target.uuid)
        elif program=='survivor':owner.on_turn_start(round_number=1)
        elif program=='protection':
            ally=actors['observer']
            attack=next(a for a in target.registered_actions if a.behavior_binding is not None and a.behavior_binding.behavior_id=='action.attack');assert attack is not None
            with fixed_dice_faces(18 if succeeded else 2,*([3]*60)):
                result=attack.instantiate(target_entity_uuid=ally.uuid,attack_source_kind='equipped',weapon_slot=WeaponSlot.MELEE_MAIN).apply()
                assert result is not None and not result.canceled
        elif program=='native_martial':
            with fixed_dice_faces((10 if martial_route=='retaliation' else 20) if succeeded else 2,*([3]*60)):
                if martial_route=='retaliation':
                    owner.receive_damage(1,DamageType.FORCE,target.uuid)
                else:
                    if martial_route=='extra':
                        action('action.attack',target_entity_uuid=target.uuid,weapon_slot=WeaponSlot.MELEE_MAIN)
                    action('action.feature.extra_attack' if martial_route=='extra' else 'action.class.barbarian.frenzied_strike',
                        target_entity_uuid=target.uuid,weapon_slot=WeaponSlot.MELEE_MAIN)
        elif program in ('font_gather','font_shape'):
            identity='action.class.sorcerer.'+('convert_slot_to_sorcery_points' if program=='font_gather' else 'convert_sorcery_points_to_slot')
            template=next(a for a in owner.registered_actions if a.behavior_binding is not None
                and a.behavior_binding.behavior_id==identity and a.slot_level==2)
            result=template.instantiate().apply();assert result is not None and not result.canceled
        else:
            identities={'rage':'action.class.barbarian.rage','frenzy':'action.class.barbarian.frenzy',
                'mindless':'action.class.barbarian.frenzy','reckless':'action.class.barbarian.reckless_attack',
                'intimidate':'action.class.barbarian.intimidating_presence','second_wind':'action.class.fighter.second_wind',
                'action_surge':'action.class.fighter.action_surge','quickened':'action.class.sorcerer.quickened_spell',
                'twinned':'action.class.sorcerer.twinned_spell','distant':'action.class.sorcerer.distant_spell',
                'affinity':'action.class.sorcerer.elemental_affinity.resistance','wings':'action.class.sorcerer.dragon_wings.toggle',
                'awe':'action.class.sorcerer.draconic_presence','draconic_fear':'action.class.sorcerer.draconic_presence'}
            kw={}
            if program=='intimidate':
                force_save_result(target,'wisdom',succeeds=not succeeded);kw['target_entity_uuid']=target.uuid
            if program in ('awe','draconic_fear'):kw['mode']='awe' if program=='awe' else 'fear'
            with fixed_dice_faces(*([3]*120)):action(identities[program],**kw)
        if retire:
            if program in ('rage','frenzy'):action('action.class.barbarian.end_rage')
            elif program=='wings':action('action.class.sorcerer.dragon_wings.toggle')
            elif program in ('awe','draconic_fear'):action('action.drop_concentration')
            elif program in ('quickened','twinned','distant'):
                with fixed_dice_faces(18,*([3]*60)):
                    action('spell.fire_bolt',target_entity_uuid=target.uuid)
            else:raise ValueError('No requested native retirement route for '+program)
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,actor.uuid,baseline) for role,actor in actors.items()))
        primary=captured.views['owner']
        return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:game.close();reset_engine_runtime();random.setstate(random_state)
