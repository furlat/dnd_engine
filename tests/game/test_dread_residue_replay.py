"""Saved arrivals retain contact, fear and the separately paid reverse step."""

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, EventType, SpatialChangeType
from dnd.entity import Entity
from dnd.types.world import OccupancyLayer
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.player_facts import ConditionChangeFact, DamageFact, MovementFact, SpatialFact, SpellFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import reduce_interval, reduce_lineage as reduce_native_lineage
from game.replay import RecordedSequence
from tests.game.dread_residue_scenarios import dread_residue_history


@pytest.fixture(scope="module", params=("walk", "jump", "misty-step"))
def history(request):
    return dread_residue_history(entry=request.param), request.param


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def saved_public(native):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


def entry_action(history, role):
    state, roots = saved_public(history.views[role])
    traveler = history.views["traveler"].initialization.observer_uuid
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, (MovementFact, SpellFact)) and fact.source_entity_uuid == traveler:
            return state, root, traveler
        state = reduce_lineage(state, root)
    raise AssertionError("No traveler entry was disclosed")


@pytest.mark.parametrize("role", ("traveler", "witness"))
def test_native_dread_arrival_and_paid_reverse_step_survive_saved_player_replay(history, role):
    captured, entry = history
    native = captured.views[role]
    initial, roots = saved_public(native)
    traveler = captured.views["traveler"].initialization.observer_uuid
    donor = next(actor for actor in initial.actors.values()
                 if actor.creature_content_ref == "content.neurodragon:creature:creature.dread_demon@1")
    assert not initial.tiles[(7, 3)].residues
    before, root, _ = entry_action(captured, role)
    residue, = before.tiles[(7, 3)].residues
    assert residue.residue_id == "residue.dread_blood"
    assert before.actors[donor.uuid].last_visual_position == (8, 3)
    release, = [node.fact.body_release for lineage in roots for node in lineage.events
        if isinstance(node.fact, DamageFact) and node.fact.body_release is not None]
    assert release.release_id == "body.dread_blood" and release.deposited_position == (7, 3)

    steps = [node for node in root.events if isinstance(node.fact, StepFact) and node.fact.committed]
    expected_incoming = {"walk": [((6, 3), (7, 3))],
        "jump": [((5, 3), (6, 3)), ((6, 3), (7, 3))], "misty-step": []}[entry]
    assert [(node.fact.from_position, node.fact.to_position) for node in steps
            if isinstance(node.fact, StepFact)] == (
        expected_incoming + [((7, 3), (6, 3))])
    movements = [node for node in root.events if isinstance(node.fact, MovementFact)
                 and node.lineage_uuid != root.root.lineage_uuid]
    retreat, = movements
    assert retreat.parent_lineage == root.root.lineage_uuid
    entered = next(node for node in root.events if isinstance(node.fact, SpatialFact)
        and node.fact.change_type is SpatialChangeType.ENTITY_ENTERED
        and node.fact.position == (7, 3) and node.fact.occupancy_layer is OccupancyLayer.GROUND)
    assert root.events.index(entered) < root.events.index(steps[-1])
    assert steps[-1].parent_lineage == retreat.lineage_uuid
    transitions = [node.fact for node in root.events if isinstance(node.fact, ConditionChangeFact)
                   and node.fact.condition.name == "Frightened"]
    assert [fact.event_type for fact in transitions] == [
        EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL]
    assert transitions[0].condition.condition_uuid == transitions[1].condition.condition_uuid
    final = reduce_lineage(before, root)
    assert final.actors[traveler].last_visual_position == (6, 3)
    assert final.actors[traveler].occupancy_layer is OccupancyLayer.GROUND
    assert not any(condition.name == "Frightened" for condition in final.actors[traveler].conditions)
    assert final.tiles[(7, 3)].residues == (residue,)
    reference, _ = reduce_interval(None, native.initialization)
    for lineage in native.lineages:
        reference = reduce_native_lineage(reference, lineage)
    assert reference.actors[traveler].last_visual_position == final.actors[traveler].last_visual_position
    assert reference.tiles[(7, 3)] == final.tiles[(7, 3)]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("role", ("traveler", "witness"))
def test_playback_reaches_the_pool_then_walks_back_without_collapsing_the_arrival(history, role, data):
    captured, entry = history
    before, root, traveler = entry_action(captured, role)
    if entry == "misty-step":
        group = bind_choreography(before, root, data)
        cast, = group.body_actions
        arrival_ms = cast.effect_ms
        complete_ms = group.complete_ms

        def sample(at):
            frame = sample_choreography(group, at)
            contact = next((row for row in frame.contacts if row.actor_uuid == str(traveler)), None)
            body = next((row for row in frame.bodies if row.actor_uuid == str(traveler)), None)
            return contact, body, frame.displayed

        pending_contact, _, pending_state = sample(arrival_ms - .001)
        assert pending_contact is not None and pending_contact.grid == (3, 3)
        assert pending_state.actors[traveler].last_visual_position == (3, 3)
    else:
        timeline = bind_motion(before, root, data)
        assert timeline is not None and timeline.legs
        arrival_ms = timeline.legs[0].end_ms
        complete_ms = timeline.complete_ms

        def sample(at):
            frame = sample_motion(timeline, data, at)
            assert frame.displayed is not None
            return frame.contact, frame.body, frame.displayed

        if entry == "jump":
            airborne = sample_motion(timeline, data, (timeline.legs[0].start_ms + arrival_ms) / 2)
            assert airborne.lift_px > 0 and airborne.displayed is not None
            assert airborne.displayed.actors[traveler].occupancy_layer is OccupancyLayer.AIR

    arrival_sample = sample(arrival_ms)
    arrived, _, arrived_state = arrival_sample
    assert arrived is not None and arrived.grid == (7, 3), "incoming contact must precede paid retreat"
    assert arrived_state.actors[traveler].last_visual_position == (7, 3)
    assert arrived_state.actors[traveler].occupancy_layer is OccupancyLayer.GROUND
    retreat_samples = [sample(arrival_ms + (complete_ms - arrival_ms) * fraction / 100)
                       for fraction in range(1, 100)]
    walking = [(contact, body) for contact, body, _ in retreat_samples
               if contact is not None and 6 < contact.grid[0] < 7 and contact.grid[1] == 3]
    assert walking, "retreat must traverse the paid reverse edge"
    assert all(body is not None and body.clip == data.movement_context.walkClip for _, body in walking)
    final_contact, _, final = sample(complete_ms)
    assert final_contact is not None and final_contact.grid == (6, 3)
    assert final.actors == reduce_lineage(before, root).actors
    assert not any(condition.name == "Frightened" for condition in final.actors[traveler].conditions)
    assert sample(arrival_ms) == arrival_sample
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
