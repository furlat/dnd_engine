"""Native discovered Thorns/Wind path casts, movement and actual source removal."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def assembly_history(*, program: Literal['thorns','wind']='thorns', direction: tuple[int,int]=(1,0),
                     form: Literal['straight','corner','ring']='straight') -> CapturedHistory:
    assert form!='corner' or program=='wind'
    assert form!='ring' or program=='thorns'
    dx,dy=direction
    start=(7,7);end=(7+3*dx,7+3*dy)
    positions={'caster':(2,13),'recipient':(7+dx,7+dy),'second':(7+2*dx,7+2*dy),'bystander':(12,3)}
    if form=='ring':positions.update(recipient=(9,7),second=(7,9))
    random_state=random.getstate();reset_engine_runtime()
    battlefield='battlefield.open_floor_bright';build_battlefield(battlefield);game=Game()
    try:
        actors={}
        spell_name='Wall of Thorns' if program=='thorns' else 'Wind Wall'
        behavior='spell.wall_of_thorns' if program=='thorns' else 'spell.wind_wall'
        for role,position in positions.items():
            actor=Entity.create(uuid4(),role.title(),config=EntityConfig(position=position,
                faction='heroes' if role=='caster' else 'monsters',
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    dexterity=AbilityConfig(ability_score=1),strength=AbilityConfig(ability_score=1)),
                action_economy=ActionEconomyConfig(spell_slots={6:2,3:2}),
                spellcasting=SpellcastingConfig(spellcasting_ability='intelligence'),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12,hit_dice_count=30,mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody',has_beard=False,
                    head_category='Head10' if role=='caster' else 'Head22')))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET)))
            setup_standard_actions(actor)
            if role=='caster':register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME[spell_name].spell_type,caster_level=17)
            actor.compose_entity();game.deploy_entity(actor,position);actors[role]=actor
        caster=actors['caster'];encounter=Encounter(name='Native wall assembly',source_entity_uuid=caster.uuid)
        for actor in actors.values():encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(18,14,10,6):encounter.start_encounter()
        encounter.start_turn();baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Wall initialization',start_cursor=0,end_cursor=baseline,observer_uuid=caster.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)
        def perform(role,identity,position=None,extra=()):
            actor=actors[role]
            with fixed_dice_faces(*([4]*200)):
                while encounter.get_current_entity() is not actor:encounter.next_turn()
            options=[(a,t) for a in get_available_actions(actor).all_actions if a.behavior_id==identity
                and (identity!=behavior or program=='wind' or a.position_selection is not None and a.position_selection.kind==('single' if form=='ring' else 'path'))
                for t in a.valid_targets if position is None or t.position==position]
            assert options,(identity,position)
            with fixed_dice_faces(*([4]*200)):result=execute_available_action(actor,*options[0],extra_target_positions=list(extra))
            assert result is not None and not result.canceled,result
            return result
        hp={role:a.get_hp() for role,a in actors.items()}
        perform('caster',behavior,start,extra=() if form=='ring' else (end,(end[0],end[1]+2)) if form=='corner' else (end,))
        assert all(actors[r].get_hp()<hp[r] for r in ('recipient','second'))
        assert actors['bystander'].get_hp()==hp['bystander']
        after_cast_hp=actors['recipient'].get_hp()
        if program=='wind':
            # Actual ordinary passage while the field is still present parts
            # the received visual sheet and must not repeat formation damage.
            perform('recipient','action.move',(positions['recipient'][0]-dy,positions['recipient'][1]+dx))
            assert actors['recipient'].get_hp()==after_cast_hp
        else:
            perform('recipient','action.dodge')
        perform('second','action.dodge')
        # Next turn actually invokes Thorns end-turn damage; Wind stays harmless.
        perform('caster','action.move',(2,14))
        assert (actors['recipient'].get_hp()<after_cast_hp) is (program=='thorns')
        # Source removal is a native action, not a fixture timestamp.
        perform('caster','action.drop_concentration')
        perform('recipient','action.move',(positions['recipient'][0]-dy*(2 if program=='wind' else 1),
            positions['recipient'][1]+dx*(2 if program=='wind' else 1)))
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,actors[role].uuid,baseline) for role in ('caster','recipient')))
        primary=captured.views['caster'];return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close();reset_engine_runtime();random.setstate(random_state)
