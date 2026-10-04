"""Native section identities control formation, local fracture and intact retirement."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from game.player_projection import project_sequence
from game.player_facts import ObjectDamageFact, ObjectDestroyedFact
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from tests.game.construction_scenarios import ConstructionAttackUnavailable, construction_history


@pytest.fixture(scope='module')
def data():
    pygame.init();pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('material', ('stone', 'force'))
def test_physical_sections_join_authored_formation_and_retirement_dates(data, material):
    history = construction_history(material=material, break_section=False)
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    authored = replace(data, construction_media={key: value.model_copy(update={
        'formationCommitMs': 500., 'removalCommitMs': 300.})
        for key, value in data.construction_media.items()})
    records, clock = {}, 0.
    formed = cleared = False
    for root in roots:
        group = bind_choreography(before, root, authored)
        records = register_construction_lifetimes(records, before, authored,
            absolute_start_ms=clock, choreography=group)
        after = reduce_lineage(before, root)
        for identity, record in records.items():
            if identity not in before.objects and identity in after.objects:
                assert record.applied_ms is not None and record.committed_ms is not None
                assert record.committed_ms >= record.applied_ms + 500.
                at = record.applied_ms + 250. - clock
                forming = sample_choreography(group, at).displayed
                assert identity not in forming.objects
                commands = construction_media_draw_commands(forming, authored, clock + at,
                    Camera(zoom=.5).with_focus(record.object.placement.position), records)
                assert any(row.owner == str(identity) for row in commands)
                assert identity in sample_choreography(group, record.committed_ms-clock).displayed.objects
                assert identity not in sample_choreography(group, at).displayed.objects
                formed = True
            if identity in before.objects and identity not in after.objects:
                assert record.removed_ms is not None and record.destroyed_ms is None
                at = record.removed_ms-clock
                assert identity in sample_choreography(group, at+150.).displayed.objects
                assert identity not in sample_choreography(group, at+300.).displayed.objects
                cleared = True
        before = after
        clock += group.complete_ms + 250.
    assert formed and cleared


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
            if (any(isinstance(node.fact, ObjectDestroyedFact) and not node.canceled for node in root.events)
                    and any(isinstance(node.fact, ObjectDamageFact) and node.fact.applied_damage > 0
                            and not node.canceled for node in root.events)):
                retirement = replace(data, construction_media={key: value.model_copy(update={
                    'removalCommitMs': 1500.}) for key, value in data.construction_media.items()})
                fracture = bind_choreography(before, root, retirement)
                assert fracture.states == group.states, 'Dismissal timing must not delay destruction'
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
                    own=[c for c in construction_media_draw_commands(after,data,
                        record.removed_ms+50,Camera(zoom=1),records) if c.owner==str(identity)]
                    assert own and all('.removal.' in str(c.evidence[2]) for c in own)
                    assert all(c.owner!=str(identity) for c in construction_media_draw_commands(after,data,
                        record.removed_ms+850,Camera(zoom=1),records))
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
                for q in range(4):
                    start=[c for c in construction_media_draw_commands(after,data,record.removed_ms,
                        Camera(quadrant=q,zoom=1),records) if c.owner==str(identity)]
                    mid=[c for c in construction_media_draw_commands(after,data,record.removed_ms+500,
                        Camera(quadrant=q,zoom=1),records) if c.owner==str(identity)]
                    assert start and mid and all('.removal.' in str(c.evidence[2]) for c in (*start,*mid))
                    assert sum(pygame.surfarray.array_alpha(c.surface).sum() for c in mid) < sum(
                        pygame.surfarray.array_alpha(c.surface).sum() for c in start)
                    assert all(c.owner!=str(identity) for c in construction_media_draw_commands(after,data,
                        record.removed_ms+850,Camera(quadrant=q,zoom=1),records))
                retained=register_construction_lifetimes(records,after,data,absolute_start_ms=record.removed_ms+500)
                assert identity in retained
                retired_records=register_construction_lifetimes(records,after,data,absolute_start_ms=record.removed_ms+850)
                assert identity not in retired_records
                assert after.senses is not None
                unseen=replace(after,senses=replace(after.senses,visible=()))
                assert all(c.owner!=str(identity) for c in construction_media_draw_commands(unseen,data,
                    record.removed_ms+100,Camera(zoom=1),records))
        before=after;now+=group.complete_ms+250
    assert observed and retired
