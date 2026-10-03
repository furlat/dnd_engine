"""Native section identities control formation, local fracture and intact retirement."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from tests.game.construction_scenarios import ConstructionAttackUnavailable, construction_history


@pytest.fixture(scope='module')
def data():
    pygame.init();pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('material',('ice','stone'))
def test_real_cast_attack_and_removal_keep_sections_independent(data,material):
    history=construction_history(material=material)
    observed=broken=retired=False
    for observer in ('caster','recipient'):
        before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        records={};now=0.
        for root in roots:
            group=bind_choreography(before,root,data)
            assert not group.gaps
            records=register_construction_lifetimes(records,before,data,absolute_start_ms=now,choreography=group)
            after=reduce_lineage(before,root)
            for identity,record in records.items():
                if record.applied_ms is not None and record.destroyed_ms is None and record.removed_ms is None:
                    observed=True
                    # Losing contact does not invent a fracture or restart its clock.
                    assert after.senses is not None
                    unknown=replace(after,senses=replace(after.senses,objects={}))
                    retained=register_construction_lifetimes(records,unknown,data,absolute_start_ms=now)
                    assert retained[identity].applied_ms==record.applied_ms and retained[identity].destroyed_ms is None
                    assert not construction_media_draw_commands(unknown,data,now+10000,Camera(zoom=1),retained)
                if record.destroyed_ms is not None:
                    broken=True
                    for q in range(4):
                        commands=construction_media_draw_commands(after,data,record.destroyed_ms+500,Camera(quadrant=q,zoom=1),records)
                        own=[c for c in commands if c.owner==str(identity)]
                        assert own and all('.destruction.' in str(c.evidence[2]) for c in own)
                        other=[c for c in commands if c.owner!=str(identity)]
                        assert other and all('.hold.' in str(c.evidence[2]) for c in other)
                        assert all(c.owner!=str(identity) for c in construction_media_draw_commands(after,data,
                            record.destroyed_ms+5000,Camera(quadrant=q,zoom=1),records))
                if record.removed_ms is not None:
                    retired=True
                    assert record.destroyed_ms is None
                    assert all(c.owner!=str(identity) for c in construction_media_draw_commands(after,data,
                        record.removed_ms+50,Camera(zoom=1),records))
            before=after;now+=group.complete_ms+250
    assert observed and broken and retired


@pytest.mark.parametrize('material',('ice','stone'))
def test_real_formation_and_concentration_removal_do_not_fracture(data,material):
    history=construction_history(material=material,break_section=False)
    observed=retired=False
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    records={};now=0.
    for root in roots:
        group=bind_choreography(before,root,data);assert not group.gaps
        records=register_construction_lifetimes(records,before,data,absolute_start_ms=now,choreography=group)
        after=reduce_lineage(before,root)
        for identity,record in records.items():
            assert record.destroyed_ms is None
            if record.applied_ms is not None and record.removed_ms is None:
                observed=True
                for q in range(4):
                    commands=construction_media_draw_commands(after,data,record.applied_ms+750,Camera(quadrant=q,zoom=1),records)
                    assert any(c.owner==str(identity) and '.application.' in str(c.evidence[2]) for c in commands)
                    commands=construction_media_draw_commands(after,data,record.applied_ms+2000,Camera(quadrant=q,zoom=1),records)
                    assert any(c.owner==str(identity) and '.hold.' in str(c.evidence[2]) for c in commands)
            if record.removed_ms is not None:
                retired=True
                assert all(c.owner!=str(identity) for c in construction_media_draw_commands(after,data,record.removed_ms,Camera(zoom=1),records))
        before=after;now+=group.complete_ms+250
    assert observed and retired
