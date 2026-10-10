"""Native three-ray allocations, hit/miss outcomes and paired saved replay."""

import random
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
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def scorching_history(*, direction: tuple[int,int]=(1,0), split: bool=False, miss: bool=False) -> CapturedHistory:
    random_state=random.getstate(); reset_engine_runtime()
    battlefield='battlefield.open_floor_bright'; build_battlefield(battlefield)
    game=Game()
    dx,dy=direction
    try:
        actors={}
        for role,position in (('caster',(7,7)),('recipient',(7+3*dx,7+3*dy)),
                              ('second',(7+3*dx-dy,7+3*dy+dx)),('bystander',(7-2*dy,7+2*dx))):
            actor=Entity.create(uuid4(),role.title(),config=EntityConfig(position=position,
                faction='heroes' if role=='caster' else 'monsters',
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2:3}),
                spellcasting=SpellcastingConfig(spellcasting_ability='intelligence'),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,hit_dice_count=12,mode='maximums')]),
                appearance=AppearanceConfig(body_category='NakedBody',has_beard=False,
                    head_category='Head10' if role=='caster' else 'Head22')))
            actor.install_initial_items(((build_authored_item('apparel.robes.red_mage',actor.uuid),BodyPart.BODY),
                (build_authored_item('apparel.cloth_shoes.red',actor.uuid),BodyPart.FEET)))
            setup_standard_actions(actor)
            if role=='caster': register_spell(actor,SPELL_CONTENT_IDENTITY_BY_NAME['Scorching Ray'].spell_type,caster_level=17)
            actor.compose_entity(); game.deploy_entity(actor,position); actors[role]=actor
        caster,recipient=actors['caster'],actors['recipient']
        encounter=Encounter(name='Scorching native volley',source_entity_uuid=caster.uuid)
        for actor in actors.values(): encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10]*4)): encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            with fixed_dice_faces(*([4]*40)): encounter.next_turn()
        baseline=EventQueue.event_cursor()
        initial=capture_interval(name='Scorching initialization',start_cursor=0,end_cursor=baseline,
            observer_uuid=caster.uuid,battlefield_id=battlefield)
        before,_=reduce_interval(None,initial)
        action,selection=next((a,t) for a in get_available_actions(caster).all_actions
            if a.behavior_id=='spell.scorching_ray' for t in a.valid_targets if t.target_uuid==recipient.uuid)
        additional=[str(actors['second'].uuid),str(recipient.uuid)] if split else []
        with fixed_dice_faces(*([1]*40 if miss else [10,4,4]*12)):
            result=execute_available_action(caster,action,selection,extra_target_uuids=additional)
        assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
        assert recipient.get_normal_hp()==(120 if miss else 104 if split else 96), recipient.get_normal_hp()
        assert actors['second'].get_normal_hp()==(112 if split and not miss else 120)
        assert actors['bystander'].get_normal_hp()==caster.get_normal_hp()==120
        captured=capture_history(before,(),observers=tuple(ObserverCapture(role,actors[role].uuid,baseline)
            for role in ('caster','recipient')))
        primary=captured.views['caster']
        return CapturedHistory(primary.initialization,before,primary.lineages,captured.views)
    finally:
        game.close(); reset_engine_runtime(); random.setstate(random_state)
