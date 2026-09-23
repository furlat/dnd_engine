"""A received object's observation contact is distinct from its physical anchor."""

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.player_facts import ObjectDestroyedFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history
from tests.game.door_destruction_scenarios import attack_object, review_actor, take_turn


def furniture_history(*, remove=False, late=False):
    reset_engine_runtime()
    battlefield = "battlefield.visibility_open_range"
    build_battlefield(battlefield)
    game = Game()
    try:
        bed = build_world_prop("environment.furniture.bed", hit_points=4)
        bed.place_on_grid((3, 3))
        actors = {role: review_actor(game, role.title(), position)
                  for role, position in (("attacker", (4, 2)), ("observer", (14, 3)))}
        encounter = Encounter(name="Furniture at the edge of sight", source_entity_uuid=bed.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, actors["attacker"])
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Furniture observation", start_cursor=0, end_cursor=baseline,
            observer_uuid=actors["attacker"].uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        if remove:
            # Actual native disposal tests absence without inventing a player
            # salvage/clear action that the game does not currently offer.
            bed.retire()
        else:
            attack_object(actors["attacker"], bed, 4)
        if late:
            baseline = EventQueue.event_cursor()
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        return bed.uuid, captured.views
    finally:
        game.close()
        reset_engine_runtime()


def saved_views(views):
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    for role, original in views.items():
        restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        yield role, decode_player_sequence(encode_player_sequence(project_sequence(restored)))
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


def test_nonanchor_observation_replays_same_identity_destruction_for_both_views():
    identity, views = furniture_history()
    for role, (state, roots) in saved_views(views):
        initial = state.objects[identity]
        assert initial.placement.position == (3, 3)
        assert set(initial.placement.positions) == {(3, 3), (4, 3)}
        assert state.senses is not None and identity in state.senses.objects
        if role == "observer":
            assert (3, 3) not in state.senses.visible and (4, 3) in state.senses.visible
        breaks = []
        for root in roots:
            breaks.extend(node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact))
            state = reduce_lineage(state, root)
        destruction, = breaks
        assert destruction.object_uuid == identity and destruction.replacement_uuid is None
        assert destruction.placement.position == (3, 3)
        assert state.objects[identity].item.integrity is ItemIntegrity.DESTROYED
        assert state.objects[identity].placement.positions == initial.placement.positions


def test_native_removal_is_observed_at_nonanchor_end():
    identity, views = furniture_history(remove=True)
    for role, (state, roots) in saved_views(views):
        assert identity in state.objects
        if role == "observer":
            assert state.senses is not None and (3, 3) not in state.senses.visible
        for root in roots:
            assert not any(isinstance(node.fact, ObjectDestroyedFact) for node in root.events)
            state = reduce_lineage(state, root)
        assert identity not in state.objects


def test_late_nonanchor_observer_receives_settled_wreck_without_past_break():
    identity, views = furniture_history(late=True)
    for _, (state, roots) in saved_views(views):
        assert state.objects[identity].item.integrity is ItemIntegrity.DESTROYED
        assert state.objects[identity].placement.position == (3, 3)
        assert not any(isinstance(node.fact, ObjectDestroyedFact) for root in roots for node in root.events)
