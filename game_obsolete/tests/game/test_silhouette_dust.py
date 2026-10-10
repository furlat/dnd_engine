"""Committed remains cross player bytes; source-alpha dust never invents anatomy."""
import numpy as np
import pygame
import pytest

from dnd.core.life_types import RemainsDisposition
from game.animation_data import load_animation_data
from game.body_effects import silhouette_dust
from game.animation_draw import actor_draw_commands, load_actor_media
from game.projection import Camera
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography
from game.condition_animation import condition_body_pose
from dnd.player.facts import LifeFact
from dnd.player.reduction import reduce_lineage
from game.scene_actors import scene_actors
from tests.game.directed_spell_scenarios import disintegrate_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('saved,lethal', [(True,True), (False,False), (False,True)])
def test_actual_disintegrate_remains_are_retained_in_subjective_history(data, saved, lethal):
    history = disintegrate_history(saved=saved, lethal=lethal, magical_weapon=True)
    for role in ('caster','recipient'):
        state, roots = player_history(history, role=role)
        recipient = next(actor for actor in state.actors.values() if actor.name=='Recipient')
        magic = {row.item_uuid for row in recipient.visual_loadout.layers if row.item_id=='weapon.circus.longsword_plus_one'}
        for root in roots:
            life = [row.fact for row in root.events if isinstance(row.fact,LifeFact) and row.fact.entity_uuid==recipient.uuid]
            if lethal and not saved and life:
                assert life[-1].remains_disposition is RemainsDisposition.DISINTEGRATED
                assert set(life[-1].preserved_equipped_item_uuids)==magic
            state = reduce_lineage(state, root)
        expected = RemainsDisposition.DISINTEGRATED if lethal and not saved else RemainsDisposition.INTACT
        assert state.actors[recipient.uuid].remains_disposition is expected
        assert (str(recipient.uuid) in {actor.contact.actor_uuid for actor in scene_actors(state,data,{})}) is (expected is RemainsDisposition.INTACT)


@pytest.mark.parametrize('shape', ['standing','prone'])
def test_original_dust_pixels_preserve_source_and_clear_after_finite_lifetime(data, shape):
    recipe = data.death_context.silhouetteDust
    assert recipe is not None
    source = pygame.Surface((64,64),pygame.SRCALPHA)
    pygame.draw.ellipse(source,(140,95,75,230),(23,5,18,55) if shape=='standing' else (4,43,55,18))
    before = pygame.image.tobytes(source,'RGBA')
    frames = []
    for elapsed in (0,450,1100,1800,2501):
        image,offset = silhouette_dust(source,recipe,elapsed,71)
        frames.append(pygame.surfarray.array_alpha(image))
        assert offset[0]<0 and offset[1]<0
    assert np.count_nonzero(frames[0])==np.count_nonzero(pygame.surfarray.array_alpha(source))
    assert np.count_nonzero(frames[2])<np.count_nonzero(frames[0])
    assert np.count_nonzero(frames[-1])==0
    assert pygame.image.tobytes(source,'RGBA')==before


@pytest.mark.parametrize('prone', [False,True])
def test_lethal_transition_keeps_actual_precontact_body_and_owned_gear(data, prone):
    history = disintegrate_history(prone=prone, magical_weapon=True)
    state, roots = player_history(history,role='caster')
    recipient = next(actor for actor in state.actors.values() if actor.name=='Recipient')
    assert any(member.behavior_id=='condition.prone' for member in recipient.conditions) is prone
    for root in roots:
        group = bind_choreography(state,root,data)
        witnessed = 0
        for cue in group.lifecycle:
            if not isinstance(cue.event.fact,LifeFact) or cue.event.fact.remains_disposition is not RemainsDisposition.DISINTEGRATED:
                continue
            witnessed += 1
            pre_time = max(0.,cue.start_ms-.001)
            pre = sample_body_presentation(state,group.after if cue.start_ms > 0 else None,data,pre_time,pre_time,{},
                choreography=group if cue.start_ms > 0 else None)
            at = sample_body_presentation(state,group.after,data,cue.start_ms+450,cue.start_ms+450,{},choreography=group)
            identity = str(cue.event.fact.entity_uuid)
            original = next(pose for pose in pre.poses if pose.body.actor_uuid==identity)
            dissolving = next(pose for pose in at.poses if pose.body.actor_uuid==identity)
            assert dissolving.body==original.body
            assert dissolving.dust_elapsed_ms==pytest.approx(450)
            assert all(layer.item_uuid not in cue.event.fact.preserved_equipped_item_uuids for layer in dissolving.actor.layers)
            retained = dissolving.appearance_override or dissolving.actor.condition
            visible_pose = condition_body_pose(data,dissolving.body,dissolving.actor.contact,retained)
            original_pose = condition_body_pose(data,original.body,original.actor.contact,original.appearance_override or original.actor.condition)
            assert visible_pose==original_pose
            if prone:
                assert visible_pose.clip==data.death_context.bodyClip
                assert visible_pose.frame>0
            media = load_actor_media(data, ((dissolving.actor.contact,dissolving.actor.layers,(visible_pose.clip,)),),all_facings=True)
            for quarter in range(4):
                camera = Camera(quadrant=quarter,viewport=(900,700),pan=(450,350))
                commands = actor_draw_commands(data,dissolving.body,dissolving.actor.contact,dissolving.actor.layers,
                    media,camera,condition=dissolving.appearance_override,dust_elapsed_ms=450,dust_seed=dissolving.dust_seed)
                assert any(command.surface.get_bounding_rect() for command in commands)
            assert group.complete_ms>=cue.start_ms+2500
            final = sample_body_presentation(state,group.after,data,group.complete_ms+1,group.complete_ms+1,{},choreography=group)
            assert identity not in {pose.body.actor_uuid for pose in final.poses}
        assert witnessed == 1
        state = reduce_lineage(state,root)
