"""Recorded electric links govern arrival, damage and finite material sampling."""
import pygame
import pytest

from game.animation import sample_cast
from game.animation_draw import load_animation_media
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.directed_media import directed_draw_commands
from dnd.player.reduction import reduce_lineage
from game.projection import Camera, project_screen
from tests.game.electric_spell_scenarios import electric_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("program,empty", [("chain_lightning",False),("lightning_bolt",False),("lightning_bolt",True)])
def test_native_discharge_arrives_before_damage_and_seeking_is_deterministic(data, program, empty):
    history = electric_spell_history(program=program,empty=empty)
    state,roots = player_history(history,role="caster")
    casts=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        for node in group.nodes:
            if isinstance(node.bound,BoundCast):
                load_animation_media(node.bound.timeline,node.bound.appearances)
                casts.append(node.bound.timeline)
        state=reduce_lineage(state,root)
    assert len(casts)==1
    timeline=casts[0]
    assert len(timeline.applications)==(0 if empty else 3)
    assert all(row.damage_start_ms is None or row.damage_start_ms>=row.travel_end_ms for row in timeline.applications)
    if program=="chain_lightning":
        primary,*branches=timeline.applications
        assert all(row.source.propagation.source==primary.source.propagation.target for row in branches)
        assert all(row.travel_start_ms==primary.travel_end_ms+85 for row in branches)
    else:
        assert timeline.source.area_geometry.length_feet==100
        assert timeline.ground_delivery.travel_end_ms>timeline.release_ms
    at=timeline.release_ms+200
    for quadrant in range(4):
        camera=Camera(quadrant=quadrant).with_focus((8,6))
        first=directed_draw_commands(timeline,sample_cast(timeline,at),camera,None)
        assert first
        assert not directed_draw_commands(timeline,sample_cast(timeline,timeline.complete_ms+1),camera,None)
        again=directed_draw_commands(timeline,sample_cast(timeline,at),camera,None)
        assert [(row.destination,pygame.image.tobytes(row.surface,"RGBA")) for row in first]==[(row.destination,pygame.image.tobytes(row.surface,"RGBA")) for row in again]


def test_invisible_branch_does_not_hide_other_recorded_links_from_an_observer(data):
    history=electric_spell_history(program='chain_lightning',hidden_branch=True)
    totals={}
    identities={}
    for role in ('caster','recipient'):
        state,roots=player_history(history,role=role)
        timelines=[]
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            timelines.extend(node.bound.timeline for node in group.nodes if isinstance(node.bound,BoundCast)
                and node.bound.timeline.recipe.definitionRef.content_id=='spell.chain_lightning')
            state=reduce_lineage(state,root)
        assert len(timelines)==1
        timeline=timelines[0]
        totals[role]=len(timeline.applications)
        identities[role]=[row.source.application_id for row in timeline.applications]
        assert all(row.source.propagation is not None for row in timeline.applications)
    assert totals=={'caster':3,'recipient':2}
    assert identities['recipient']==[identities['caster'][0],identities['caster'][2]]


def test_antimagic_rejected_branch_has_no_recipient_contact_flare(data):
    history = electric_spell_history(program='chain_lightning', blocked_branch=True)
    state, roots = player_history(history, role='caster')
    rejected = next(actor for actor in state.actors.values() if actor.name == 'Second')
    initial_hp = rejected.normal_hp
    casts = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        casts.extend(node.bound.timeline for node in group.nodes if isinstance(node.bound, BoundCast))
        state = reduce_lineage(state, root)
    assert state.actors[rejected.uuid].normal_hp == initial_hp
    timeline, = casts
    blocked, = (row for row in timeline.applications
                if row.source.target.actor_uuid == str(rejected.uuid))
    assert blocked.source.propagation is None and not blocked.source.damage_applied
    assert sum(row.source.propagation is not None for row in timeline.applications) == 2
    # Before the admitted primary contact, the rejected branch used to receive
    # fallback-time glow/star/streak particles despite no received link or hit.
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus((8, 6))
        at = timeline.release_ms + 40
        commands = directed_draw_commands(timeline, sample_cast(timeline, at), camera, None)
        x, y = project_screen(blocked.source.target.grid, camera,
            elevation_steps=blocked.source.target.elevation_steps)
        recipient = pygame.Rect(round(x)-24, round(y)-95, 48, 100)
        flares = [row for row in commands if row.evidence[-1] == 'flare']
        assert flares, 'the real caster preparation still appears'
        assert all(not recipient.colliderect(row.surface.get_bounding_rect().move(row.destination))
                   for row in flares)
