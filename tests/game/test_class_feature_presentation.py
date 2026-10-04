"""Real class progression crosses native replay and the existing presentation boundary."""
from pathlib import Path
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventType
from game.attack import BoundAttack,bind_attack
from game.weapon_trail_media import weapon_trail_draw_commands
from game.projection import Camera
from tests.game.scenarios import attack_history

import pygame
import pytest

from game.animation_data import load_animation_data
from dnd.types.class_features import IndomitableReroll,RelentlessRageIntervention
from game.choreography import bind_choreography
from game.player_reduction import reduce_lineage
from game.player_facts import SavingThrowFact,DamageRequestFact,ActionFact,ConditionChangeFact
from tests.game.player_helpers import player_history
from tests.game.class_feature_scenarios import class_feature_history

PROGRAMS=('rage','frenzy','reckless','intimidate','relentless','mindless','native_martial',
 'second_wind','action_surge','protection','indomitable','survivor','font_gather','font_shape',
 'quickened','twinned','distant','affinity','wings','awe','draconic_fear')

@pytest.fixture(scope='module')
def data():
    pygame.init();pygame.display.set_mode((1,1))
    yield load_animation_data(rig_files=(Path('game/data/rigs/goblin01.json'),))
    pygame.quit()

@pytest.mark.parametrize('program',PROGRAMS)
def test_native_class_actions_keep_real_owner_and_bind_without_presentation_gaps(data,program):
    history=class_feature_history(program=program)
    for role in ('owner','observer'):
        state,roots=player_history(history,role=role)
        if role=='owner':assert roots
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            state=reduce_lineage(state,root)

@pytest.mark.parametrize('program',['indomitable','relentless'])
@pytest.mark.parametrize('succeeded',[True,False])
def test_intervention_flash_follows_recorded_result_without_fake_action(data,program,succeeded):
    history=class_feature_history(program=program,succeeded=succeeded)
    state,roots=player_history(history,role='owner');tracks=[];facts=[]
    for root in roots:
        group=bind_choreography(state,root,data);tracks.extend(group.stationary_media)
        facts.extend(node.fact for node in root.events);state=reduce_lineage(state,root)
    assert not any(isinstance(fact,ActionFact) for fact in facts)
    records:list[IndomitableReroll|RelentlessRageIntervention]=[fact.indomitable_reroll for fact in facts if isinstance(fact,SavingThrowFact) and fact.indomitable_reroll]
    records.extend(fact.relentless_rage for fact in facts if isinstance(fact,DamageRequestFact) and fact.relentless_rage)
    assert records and all(row.succeeded is succeeded and row.condition_uuid is None for row in records)
    assert bool(tracks) is succeeded


@pytest.mark.parametrize('program,recipe_id',[
    ('indomitable','class_feature.fighter.indomitable'),
    ('relentless','class_feature.barbarian.relentless_rage'),
    ('survivor','class_feature.fighter.survivor'),
    ('protection','reaction.class_feature.fighter.protection'),
])
def test_selected_handler_response_uses_one_actual_intervention_owner(data,program,recipe_id):
    state,roots=player_history(class_feature_history(program=program),role='owner')
    responses=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        responses.extend(cue for cue in group.body_actions if cue.recipe_id==recipe_id)
        state=reduce_lineage(state,root)
    assert len(responses)==1
    assert responses[0].contact.actor_uuid==str(state.observer_uuid)




@pytest.mark.parametrize('weapon,slot',[
    ('weapon.dagger',WeaponSlot.MELEE_MAIN),('weapon.greatsword',WeaponSlot.MELEE_MAIN),
    ('weapon.mace',WeaponSlot.MELEE_MAIN),('weapon.dagger',WeaponSlot.MELEE_OFF)])
def test_critical_trail_uses_actual_weapon_pose_and_draws_four_views(data,weapon,slot):
    history=attack_history(weapon,5,weapon_slot=slot);state,(root,)=player_history(history)
    bound=bind_attack(state,root,data);assert bound is not None
    timeline=bound.timeline;assert timeline.weapon_pose is not None and timeline.show_contact
    selected=next(layer.category for layer in bound.appearances[timeline.source.actor_uuid]
        if layer.slot==('offhand' if slot==WeaponSlot.MELEE_OFF else 'weapon'))
    assert timeline.weapon_pose.category==selected and timeline.weapon_pose.clip==timeline.clip
    for quadrant in range(4):
        camera=Camera(quadrant=quadrant,zoom=1,viewport=(800,600)).with_focus(timeline.source.grid)
        swing=weapon_trail_draw_commands(timeline,timeline.contact_ms*.7,camera)
        assert any(row.volume is not None for row in swing),(weapon,quadrant)
        impact=weapon_trail_draw_commands(timeline,timeline.contact_ms+125,camera)
        assert any('weapon_contact' in row.evidence for row in impact)


@pytest.mark.parametrize('seed',[1,17])
def test_ordinary_noncritical_attack_keeps_existing_recipe(data,seed):
    history=attack_history('weapon.longsword',seed);state,(root,)=player_history(history)
    bound=bind_attack(state,root,data);assert bound is not None
    assert bound.timeline.weapon_trail is None
    assert any(layer.slot=='slash' for layer in bound.timeline.layers)


def test_fixed_sheet_offhand_keeps_existing_pose_without_modular_trail():
    fixed=load_animation_data(rig_files=(Path('game/data/rigs/goblin01.json'),))
    history=attack_history('weapon.dagger',5,goblin_source=True,weapon_slot=WeaponSlot.MELEE_OFF,goblin_offhand='weapon.dagger')
    state,(root,)=player_history(history);bound=bind_attack(state,root,fixed)
    assert bound is not None and bound.timeline.source.rig_id!='modular'
    assert bound.timeline.weapon_pose is None
    assert bound.timeline.clip in fixed.rigs[bound.timeline.source.rig_id].clips


@pytest.mark.parametrize('route',['frenzied','retaliation','extra'])
def test_class_martial_follows_actual_attack_lineage(data,route):
    history=class_feature_history(program='native_martial',martial_route=route)
    state,roots=player_history(history,role='owner');attacks=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        attacks.extend(clip.bound.timeline for clip in group.nodes if isinstance(clip.bound,BoundAttack))
        state=reduce_lineage(state,root)
    assert attacks and any(attack.weapon_pose is not None for attack in attacks)
    if route=='retaliation':assert len(attacks)==1

@pytest.mark.parametrize('program',['rage','frenzy','wings','quickened','twinned','distant','awe','draconic_fear'])
def test_class_status_retires_from_real_native_removal(data,program):
    history=class_feature_history(program=program,retire=True)
    state,roots=player_history(history,role='owner');applications=set();removals=set()
    for root in roots:
        group=bind_choreography(state,root,data);assert not group.gaps,group.gaps
        for node in root.events:
            if isinstance(node.fact,ConditionChangeFact):
                target=applications if node.fact.event_type is EventType.CONDITION_APPLICATION else removals
                target.add(node.fact.condition.condition_uuid)
        state=reduce_lineage(state,root)
    assert applications & removals
