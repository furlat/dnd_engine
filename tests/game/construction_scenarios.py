"""Discovered panel casts and ordinary attacks preserve independent section owners."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import walk


class ConstructionAttackUnavailable(AssertionError):
    """Native discovery must admit an adjacent owned wall section."""


def construction_history(*, material: Literal['ice', 'stone', 'force']='ice', break_section: bool = True, disintegrate: bool = False, fracture_after_cut: bool = False, dome_radius: int | None = None, antimagic: bool = False) -> CapturedHistory:
    previous_random=random.getstate();reset_engine_runtime()
    battlefield='battlefield.open_floor_bright';build_battlefield(battlefield);game=Game()
    try:
        actors={}
        spell_name='Wall of '+material.title()
        behavior='spell.wall_of_'+material
        for role,position in (('caster',(7,6)),('recipient',(11,10))):
            actor=Entity.create(uuid4(),role.title(),config=EntityConfig(position=position,faction='heroes',
                ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=30),intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2:1,5:2,6:2,8:1}),
                spellcasting=SpellcastingConfig(spellcasting_ability='intelligence'),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12,hit_dice_count=20,mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody',head_category='Head10',has_beard=False)))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET),
                (build_authored_item('weapon.greataxe',actor.uuid),WeaponSlot.MELEE_MAIN)))
            setup_standard_actions(actor)
            if role=='caster':
                register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME[spell_name].spell_type,caster_level=17)
                if material=='force':register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME['See Invisibility'].spell_type,caster_level=17)
                if disintegrate:register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME['Disintegrate'].spell_type,caster_level=17)
            elif antimagic:
                register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME['Antimagic Field'].spell_type,caster_level=17)
            actor.compose_entity();game.deploy_entity(actor,position);actors[role]=actor
        caster=actors['caster'];encounter=Encounter(name='Independent physical spell sections',source_entity_uuid=caster.uuid)
        for actor in actors.values():encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(18,4):encounter.start_encounter()
        encounter.start_turn()
        if material=='force':
            choices=[(a,t) for a in get_available_actions(caster).all_actions if a.behavior_id=='spell.see_invisibility' for t in a.valid_targets]
            assert choices
            result=execute_available_action(caster,*choices[0]);assert result is not None and not result.canceled
            encounter.next_turn()
            while encounter.get_current_entity() is not caster:encounter.next_turn()
        baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Construction initialization',start_cursor=0,end_cursor=baseline,
            observer_uuid=caster.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)
        def perform(identity,target=None,extra=()):
            while encounter.get_current_entity() is not caster:encounter.next_turn()
            caster.update_entity_senses()
            choices=[(a,t) for a in get_available_actions(caster).all_actions if a.behavior_id==identity
                and (identity!=behavior or (a.position_selection is not None and a.position_selection.kind=='path' if dome_radius is None else f'__dome_outside_{dome_radius}_' in a.template_name))
                and (not disintegrate or material!='stone' or identity!=behavior or a.template_name.endswith('_20'))
                and (identity!='action.attack' or a.weapon_slot==WeaponSlot.MELEE_MAIN.value)
                for t in a.valid_targets if target is None or t.position==target or t.target_uuid==target]
            if not choices and identity=='action.attack':
                raise ConstructionAttackUnavailable(f'{material}: no ordinary attack target for adjacent section {target}')
            assert choices,(identity,target)
            with fixed_dice_faces(*([20,12,12]*40)):
                result=execute_available_action(caster,*choices[0],extra_target_positions=list(extra))
            assert result is not None and not result.canceled,result
            return result
        perform(behavior,(9,8) if dome_radius is not None else (7,7),() if dome_radius is not None else ((11 if disintegrate and material=='stone' else 13,7),))
        caster.update_entity_senses()
        objects={identity:obj for identity in caster.senses.objects
            if isinstance((obj:=BaseBlock.get(identity)),BaseItem) and obj.item_id==f'spell_construction.{material}.section'}
        assert len(objects)==(1 if dome_radius is not None or disintegrate and material=='stone' else 3)
        if antimagic:
            recipient=actors['recipient']
            while encounter.get_current_entity() is not recipient:encounter.next_turn()
            template=recipient.get_action_template('Antimagic Field');assert template is not None
            result=template.instantiate().apply();assert result is not None and not result.canceled
            walk(recipient,(11,9));walk(recipient,(11,8))
            walk(recipient,(11,9));walk(recipient,(11,10))
            while encounter.get_current_entity() is not caster:encounter.next_turn()
        if material=='force' and break_section:
            target=min(objects.values(),key=lambda o:o.get_position() or (0,0))
            encounter.next_turn();perform('action.attack',target.uuid)
            assert target.health is None and target.is_active
        if disintegrate:
            target=min(objects.values(),key=lambda o:o.get_position() or (0,0))
            encounter.next_turn();perform('spell.disintegrate',target.uuid)
            if fracture_after_cut:
                walk(caster,(8,6))
                walk(caster,(9,6))
        if (break_section and not disintegrate and material!='force') or fracture_after_cut:
            target=min(objects.values(),key=lambda o:o.get_position() or (0,0))
            for _ in range(8):
                encounter.next_turn()
                perform('action.attack',target.uuid)
                if target.get_hp()<=0:break
            assert target.get_hp()<=0
            caster.update_entity_senses()
            remaining=[o for identity in caster.senses.objects
                if isinstance((o:=BaseBlock.get(identity)),BaseItem) and o.item_id==target.item_id]
            assert len(remaining)==(0 if fracture_after_cut or dome_radius is not None else 2) and all(o.get_hp()==(30 if material=='ice' else 180) for o in remaining)
        if material=='force' and disintegrate:
            assert 'Concentrating' not in caster.active_conditions
            assert not any(a.behavior_id=='action.drop_concentration' and a.valid_targets for a in get_available_actions(caster).all_actions)
            assert all(BaseBlock.get(identity) is None for identity in objects)
        else:
            encounter.next_turn();perform('action.drop_concentration')
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,a.uuid,baseline) for role,a in actors.items()))
        primary=captured.views['caster'];return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close();reset_engine_runtime();random.setstate(previous_random)
