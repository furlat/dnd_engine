"""Accepted fire phases follow native material owners and real dousing causes."""

from dataclasses import replace

import pygame
import pytest

from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectInteractionOperation
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.player_facts import SpatialEffectStateFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from tests.game.surface_ignition_scenarios import surface_ignition_history


@pytest.fixture(scope='module')
def captured():
    pygame.init();pygame.display.set_mode((1,1))
    data=load_animation_data();history=surface_ignition_history()
    yield data,history
    pygame.quit()


def test_native_ignition_partial_douse_and_expiry_keep_exact_owners(captured):
    data,history=captured
    for observer in ('operator','witness'):
        before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        records={};now=0.;doused=set();expired=False;independent=False
        for root in roots:
            group=bind_choreography(before,root,data)
            assert not group.gaps
            records=register_spatial_lifetimes(records,before,data,absolute_start_ms=now,lineage=root,choreography=group)
            after=reduce_lineage(before,root)
            assert after.senses is not None
            active={owner:row for owner,row in after.senses.spatial_effects.items() if row.content_ref.content_id in
                ('spatial_effect.material.fire','spatial_effect.spell.web.burning')}
            independent |= sum(row.content_ref.content_id=='spatial_effect.material.fire' for row in active.values())==2
            facts=[row.fact for row in root.events if not row.canceled and isinstance(row.fact,SpatialEffectStateFact)]
            quenched={cell for fact in facts if fact.interaction_operation is SpatialEffectInteractionOperation.DOUSE
                for cell in fact.removed_positions}
            assert {cue.position for cue in group.contact_media if cue.track.id.startswith('quench:')}==quenched
            for fact in facts:
                if fact.interaction_operation is SpatialEffectInteractionOperation.DOUSE:
                    doused.update(fact.removed_positions)
                    record=records[fact.spatial_effect_uuid]
                    for cell in fact.removed_positions:
                        removed=dict(record.retired_cells).get(cell,record.removed_ms)
                        assert removed is not None
                        for q in range(4):
                            early=spatial_media_draw_commands(after,data,removed+100,Camera(quadrant=q),lifetimes=records)
                            later=spatial_media_draw_commands(after,data,removed+650,Camera(quadrant=q),lifetimes=records)
                            assert any(c.evidence[0]==str(fact.spatial_effect_uuid) and c.evidence[1]==cell for c in early)
                            assert not any(c.evidence[0]==str(fact.spatial_effect_uuid) and c.evidence[1]==cell for c in later)
                            assert any(c.evidence[1]==(7,5) for c in later)
                        hidden=replace(after,senses=replace(after.senses,visible=tuple(p for p in after.senses.visible if p!=cell)))
                        assert not any(c.evidence[1]==cell for c in spatial_media_draw_commands(hidden,data,removed+100,
                            Camera(),lifetimes=records))
                elif fact.operation is SpatialEffectChangeOperation.REMOVED and fact.spatial_effect_uuid in records:
                    expired=True
            before=after;now+=group.complete_ms+250
        assert doused=={(6,5),(8,5)} and expired and independent


def test_source_loop_overlap_and_late_acquisition_do_not_restart_ignition(captured):
    data,history=captured
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['operator'])))
    first=roots[0];group=bind_choreography(before,first,data)
    records=register_spatial_lifetimes({},before,data,absolute_start_ms=0,lineage=first,choreography=group)
    active=reduce_lineage(before,first)
    assert active.senses is not None
    live_cells={cell for effect in active.senses.spatial_effects.values() for cell in effect.positions}
    cold=register_spatial_lifetimes({},active,data,absolute_start_ms=200)
    for q in range(4):
        camera=Camera(quadrant=q)
        acquired=spatial_media_draw_commands(active,data,200,camera,lifetimes=cold)
        assert acquired and all('.hold.' in str(c.evidence[2]) for c in acquired)
        overlap=spatial_media_draw_commands(active,data,3125,camera,lifetimes=records)
        assert overlap and {c.evidence[9] for c in overlap}=={4,52}
        assert {c.surface.get_alpha() for c in overlap}=={64,191}
        assert {c.evidence[1] for c in overlap}<=live_cells
