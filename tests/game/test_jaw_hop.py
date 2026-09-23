"""A real saved retreat owns exactly one hop to its authoritative landing."""

from dataclasses import replace
from math import hypot
from uuid import uuid4

import pygame
import pytest

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.core.events import EventQueue, MovementTrajectory
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.jaws import materialize_jaw_trap
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.world import OccupancyLayer
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.body_hop import sample_body_hop
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import ForcedMovementFact, MechanismActivationFact, MovementFact, SavingThrowFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera, TILE_WIDTH
from game.replay import ObserverCapture, capture_history
from tests.game.trap_expansion_scenarios import trap_expansion_history
from tests.game.mechanism_scenarios import mechanism_history


def empty_jaw_history():
    """A real pressure-plate entry closes remote, unoccupied jaws."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    try:
        actors = []
        for name, position in (("Traveler", (2, 2)), ("Witness", (5, 3))):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes"))
            setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors.append(actor)
        jaw = materialize_jaw_trap((4, 2))
        materialize_pressure_plate({(3, 2)}, ActivationLink(target_condition_uuid=jaw.uuid))
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        interval = capture_interval(name="Empty jaw", start_cursor=0, end_cursor=cursor,
            observer_uuid=actors[0].uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, interval)
        event = Move(source_entity_uuid=actors[0].uuid, end_position=(3, 2),
            path=[(2, 2), (3, 2)], prefer_safe=False).apply()
        assert event is not None and not event.canceled
        assert not jaw.linked_conditions
        return capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, cursor)
            for role, actor in zip(("traveler", "witness"), actors)))
    finally:
        game.close()
        reset_engine_runtime()


@pytest.fixture(scope="module")
def histories():
    return {"success": trap_expansion_history(program="jaw", save=True),
            "failure": trap_expansion_history(program="jaw", save=False),
            "empty": empty_jaw_history()}


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def groups(bound):
    yield bound
    for motion in bound.movements:
        for reaction in motion.timeline.reactions:
            yield from groups(reaction.choreography)


def replay_groups(recorded, data):
    payload = encode_player_sequence(project_sequence(recorded))
    state, roots = decode_player_sequence(payload)
    bound_groups = []
    for root in roots:
        bound = bind_choreography(state, root, data)
        assert not bound.gaps
        bound_groups.extend(groups(bound))
        state = reduce_lineage(state, root)
    return payload, state, roots, bound_groups


@pytest.mark.parametrize("outcome", ("success", "failure", "empty"))
@pytest.mark.parametrize("role", ("traveler", "witness"))
def test_real_save_and_retreat_are_required_and_replay_does_not_duplicate_movement(histories, data, outcome, role):
    recorded = histories[outcome].views[role]
    native_before = recorded.model_dump_json()
    payload, state, roots, bound_groups = replay_groups(recorded, data)
    nodes = [node for root in roots for node in root.events]
    activations = [node for node in nodes if isinstance(node.fact, MechanismActivationFact)
                   and node.fact.mechanism_content_id == "spatial_effect.environment.jaw_trap"]
    saves = [node for node in nodes if isinstance(node.fact, SavingThrowFact)]
    hops = [hop for group in bound_groups for hop in group.body_hops]
    retreats = [node for node in nodes if isinstance(node.fact, ForcedMovementFact)]
    assert len(activations) == (1 if outcome == "empty" else 2)
    assert len(saves) == (0 if outcome == "empty" else 2)
    assert len(hops) == (2 if outcome == "success" else 0)
    assert len(retreats) == len(hops)
    for save in saves:
        assert isinstance(save.fact, SavingThrowFact)
        assert save.fact.succeeded is (outcome == "success")
        assert save.parent_lineage in {node.lineage_uuid for node in activations}
    for hop in hops:
        assert hop.event_uuid in {node.uuid for node in saves}
        assert hop.movement_event_uuid in {node.uuid for node in retreats}
        assert hop.landing.grid == (2, 2)
        assert not any(cue.event_uuid == hop.movement_event_uuid
                       for group in bound_groups for cue in group.forced_movement)
    traveler = next(actor for actor in state.actors.values() if actor.name == "Traveler")
    initial, _ = decode_player_sequence(payload)
    assert traveler.normal_hp == initial.actors[traveler.uuid].normal_hp - (8 if outcome == "failure" else 0)
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    assert all(node.fact.trajectory is MovementTrajectory.PATH for node in nodes
               if isinstance(node.fact, MovementFact))
    assert recorded.model_dump_json() == native_before
    assert encode_player_sequence(project_sequence(recorded)) == payload
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def first_hop(histories, data):
    _, _, _, bound_groups = replay_groups(histories["success"].views["traveler"], data)
    group = next(group for group in bound_groups if group.body_hops)
    return group, group.body_hops[0]


def hop_at(hop, time):
    sample = sample_body_hop(hop, time)
    assert sample is not None
    return sample


def test_hop_is_one_seekable_cycle_and_lands_at_recorded_previous_cell(histories, data):
    group, hop = first_hop(histories, data)
    apex = (hop.start_ms + hop.end_ms) / 2
    transition, = [row for row in group.world_transitions if row.field == "activation"]
    assert apex == pytest.approx(transition.start_ms + 5 * 1000 / 12)
    before_grid = hop.contact.grid
    samples = [hop_at(hop, hop.start_ms + (hop.end_ms-hop.start_ms)*i/100) for i in range(100)]
    assert [sample[0].frame for sample in samples] == sorted(sample[0].frame for sample in samples)
    assert {sample[0].frame for sample in samples} == set(range(hop.frames))
    body, contact = hop_at(hop, apex)
    assert contact.body_lift_px - hop.contact.body_lift_px == pytest.approx(10)
    assert hypot(contact.grid[0]-before_grid[0], contact.grid[1]-before_grid[1]) == pytest.approx(.5)
    # The actual entry was east from(2,2) to(3,2); the save returns west.
    assert contact.grid == (2.5, 2) and hop.landing.grid == (2, 2)
    assert contact.elevation_steps == hop.contact.elevation_steps
    assert contact.facing == hop.contact.facing
    assert hop_at(hop, hop.end_ms)[1] == hop.landing
    assert sample_body_hop(hop, hop.start_ms-1) is None
    assert sample_body_hop(hop, hop.end_ms+1) is None
    actual = sample_choreography(group, apex)
    assert body in actual.bodies and contact in actual.contacts
    sample_choreography(group, hop.end_ms+1)
    sample_choreography(group, hop.start_ms)
    assert sample_choreography(group, apex) == actual
    for time in (hop.end_ms, hop.end_ms+1, group.complete_ms):
        settled = sample_choreography(group, time)
        contact = next(contact for contact in settled.contacts if contact.actor_uuid == hop.contact.actor_uuid)
        assert contact.grid == hop.landing.grid and contact.body_lift_px == 0


@pytest.mark.parametrize("program", ("blade", "crusher"))
def test_other_authored_reflex_traps_reuse_the_actual_retreat_hop(data, program):
    history = mechanism_history(program=program, save=True)
    for role, recorded in history.views.items():
        _, state, roots, bound_groups = replay_groups(recorded, data)
        hops = [hop for group in bound_groups for hop in group.body_hops]
        assert [hop.contact.grid for hop in hops] == [(3, 2), (3, 2)], role
        assert [hop.landing.grid for hop in hops] == [(2, 2), (4, 2)], role
        forced = [node for root in roots for node in root.events if isinstance(node.fact, ForcedMovementFact)]
        assert {hop.movement_event_uuid for hop in hops} == {node.uuid for node in forced}
        assert not any(group.forced_movement for group in bound_groups)
        reactions = [group for group in bound_groups if group.body_hops]
        edges = [change.current for group in reactions for change in group.world_transitions
                 if change.field == "pressed"]
        assert edges == ["true", "false", "true", "false"], "Real landing vacates and releases the pressure plate."
        assert state.senses is not None
        assert all(effect.pressed is False for effect in state.senses.spatial_effects.values()
                   if effect.pressed is not None)
        traveler = next(actor for actor in state.actors.values() if actor.name == "Traveler")
        assert traveler.last_visual_position == (4, 2) and traveler.normal_hp == 80
        assert traveler.occupancy_layer is OccupancyLayer.GROUND
        for group in bound_groups:
            for hop in group.body_hops:
                sample = sample_choreography(group, group.complete_ms)
                contact = next(contact for contact in sample.contacts if contact.actor_uuid == hop.contact.actor_uuid)
                assert contact.grid == hop.landing.grid and contact.body_lift_px == 0


def test_actual_draw_lifts_body_above_ground_in_all_four_cameras(histories, data, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        group, hop = first_hop(histories, data)
        actor = next(actor for actor in group.before.actors.values() if str(actor.uuid) == hop.contact.actor_uuid)
        layers = resolve_player_layers(data, actor, rig_id=hop.contact.rig_id)
        rows = load_actor_media(data, ((hop.contact, layers, (hop.body_clip, "Idle")),), all_facings=True)
        body, peak = hop_at(hop, (hop.start_ms+hop.end_ms)/2)
        grounded = replace(peak, body_lift_px=hop.contact.body_lift_px)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=.5).with_focus(hop.contact.grid)
            lifted = actor_draw_commands(data, body, peak, layers, rows, camera)
            level = actor_draw_commands(data, body, grounded, layers, rows, camera)
            assert lifted and len(lifted) == len(level)
            for above, below in zip(lifted, level):
                assert above.destination[0] == below.destination[0]
                expected = 0 if above.evidence[6] == "actor_shadow" else 10*TILE_WIDTH/data.rig.TILE_W*camera.zoom
                assert below.destination[1]-above.destination[1] == pytest.approx(expected, abs=1)
                assert pygame.image.tobytes(above.surface, "RGBA") == pygame.image.tobytes(below.surface, "RGBA")
    finally:
        pygame.quit()
