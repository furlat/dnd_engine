"""Native cone direction and saves govern the accepted eight-heading Fear art."""

from dataclasses import replace
from math import hypot
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.core.condition_types import ConditionCategory
from dnd.player.actor_facts import ConditionFact
from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.cast_media import cast_media_draw_commands, cast_media_placement
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, project_screen
from tests.game.fear_scenarios import fear_history

DIRECTIONS = ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_native_mixed_saves_and_real_eight_heading_pixels(data, direction):
    history = fear_history(direction=direction)
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    witnessed = False
    for root in roots:
        group = bind_choreography(before, root, data)
        assert not group.gaps
        for node in group.nodes:
            if not isinstance(node.bound, BoundCast):
                continue
            timeline = node.bound.timeline
            actual_direction = timeline.source.area_direction
            assert actual_direction is not None
            assert actual_direction[0]*direction[1] == actual_direction[1]*direction[0]
            assert sum(a*b for a,b in zip(actual_direction,direction,strict=True)) > 0
            assert len(timeline.source.applications) == 2
            saves = tuple(a.save_succeeded for a in timeline.source.applications)
            assert saves.count(False) == saves.count(True) == 1
            assert all(t.attachment == 'area_ground' and not t.scaleWithActor for t in timeline.recipe.media)
            centroids = []
            for q in range(4):
                camera = Camera(quadrant=q, zoom=1)
                track = timeline.recipe.media[0]
                placement = cast_media_placement(timeline, track, timeline.source.caster, camera)
                assert placement.anchor == project_screen(timeline.source.caster.grid, camera)
                assert placement.rotation == 0
                assert placement.scale == pytest.approx(48/(896/24))
                commands = cast_media_draw_commands(timeline,
                    sample_cast(timeline, timeline.release_ms + 49*1000/32), camera, None, {})
                assert commands  # Empty rear/front banks individually are intentional.
                weighted = np.zeros(2)
                weight = 0.
                origin = np.array(project_screen(timeline.source.caster.grid, camera))
                for command in commands:
                    alpha = pygame.surfarray.array_alpha(command.surface).astype(float)
                    x,y = np.indices(alpha.shape)
                    mass = float(alpha.sum())
                    weighted += np.array([(alpha*(x+command.destination[0])).sum(),
                                          (alpha*(y+command.destination[1])).sum()])
                    weight += mass
                centroids.append(weighted/weight-origin)
            # Remove the same baked vertical elevation in every view, then compare
            # actual alpha geometry with authoritative cone projection, not row labels.
            height_offset = float(np.mean([p[1] for p in centroids]))
            for q,actual in enumerate(centroids):
                origin = project_screen((0,0),Camera(quadrant=q,zoom=1))
                end = project_screen(direction,Camera(quadrant=q,zoom=1))
                expected = np.array(end)-origin
                actual = actual-np.array([0,height_offset])
                cosine = np.dot(actual,expected)/(hypot(*actual)*hypot(*expected))
                assert cosine > .999, (direction,q,actual,expected)
        before = reduce_lineage(before,root)
        actors = {a.name:a for a in before.actors.values()}
        if any(c.behavior_id == 'condition.spell.fear' for c in actors['Recipient'].conditions):
            witnessed = True
            appearance = resolve_condition_appearance(actors['Recipient'].conditions,
                data.condition_recipes,data.condition_media)
            assert not appearance.unsupported
            assert len([layer for layer in appearance.layers if not layer.layer.markerGroup]) == 2
            assert [layer.layer.markerGroup for layer in appearance.layers if layer.layer.markerGroup] == ['frightened']
            assert all(c.behavior_id not in ('condition.frightened','condition.spell.fear')
                for c in actors['Second'].conditions)
    assert witnessed
    assert before.senses is not None
    assert not before.senses.spatial_effects
    assert all(a.normal_hp == 120 for a in before.actors.values())
    assert not any(c.behavior_id in ('condition.frightened','condition.spell.fear')
        for a in before.actors.values() for c in a.conditions)


def test_frightened_maintain_overlap_clear_and_unknown_application(data):
    actor,owner = uuid4(),uuid4()
    fact = ConditionFact(condition_uuid=owner,category=ConditionCategory.CONDITION,
        behavior_id='condition.frightened',event_uuid=uuid4(),name='Frightened',
        resulting_max_hp=None,resulting_ac=None)
    appearance = resolve_condition_appearance((fact,),data.condition_recipes,data.condition_media)
    record = ConditionMediaLifetime(actor,owner,'condition.frightened',applied_ms=0)
    def samples(age, lifetime=record):
        layers = sample_condition_lifetimes({str(actor):appearance},{owner:lifetime},data,age)[str(actor)].layers
        return [sample for sample in sample_condition_media(data,layers[0])]
    assert all('.apply.' in s.asset_id for s in samples(500))
    assert [s.frame for s in samples(2999)] == [63,15]
    assert samples(3000)[0].frame == 16  # Continue the incoming overlapping phase.
    quiet = samples(500,replace(record,applied_ms=None))
    assert all('.hold.' in s.asset_id for s in quiet)
    removed = replace(record,removed_ms=3000,
        removed_layers=tuple(l.layer.assetId for l in appearance.layers))
    empty = resolve_condition_appearance((),data.condition_recipes,data.condition_media)
    tail = sample_condition_lifetimes({str(actor):empty},{owner:removed},data,3225)[str(actor)]
    assert len(tail.layers)==2
    assert all(s.alpha == pytest.approx(.5) for l in tail.layers for s in sample_condition_media(data,l))
    assert not sample_condition_lifetimes({str(actor):empty},{owner:removed},data,3450)[str(actor)].layers
