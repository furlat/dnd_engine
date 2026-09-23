"""Portal crossings remain usable after reset, with independent endpoint grants."""

import json
from uuid import uuid4

import pytest

from dnd.actions import Jump, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, PortalTransferEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.portals import PORTAL_HATCH_CONTENT_REF, materialize_portal
from dnd.types.traps import TrapState
from game.player_facts import MovementFact, PortalTransferFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage, reduce_nodes
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history


@pytest.fixture(scope="module", params=("walk", "jump"))
def recorded(request):
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    for y in range(built.definition.height):
        get_map().set_tile(10, y, name="Wall", walking_cost=0, blocks_optics=True)
    game = Game()
    try:
        actors = {}
        for role, position in (("traveler", (2, 2)), ("departure", (2, 3)), ("arrival", (17, 3))):
            actor = Entity.create(uuid4(), role, config=EntityConfig(position=position,
                ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18))))
            setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        encounter = Encounter(name="Portal experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        encounter.start_encounter()
        portal = materialize_portal({(3, 2)}, (17, 2), trap_state=TrapState.READY,
            content_ref=PORTAL_HATCH_CONTENT_REF, stealth_dc=40)
        Entity.update_all_entities_senses()
        assert all(portal.uuid not in actor.senses.spatial_effects for actor in actors.values())
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Portal room", start_cursor=0, end_cursor=cursor,
            observer_uuid=actors["traveler"].uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        action = (Jump(source_entity_uuid=actors["traveler"].uuid, end_position=(3, 2))
            if request.param == "jump" else Move(source_entity_uuid=actors["traveler"].uuid,
                end_position=(4, 2), path=[(2, 2), (3, 2), (4, 2)], prefer_safe=False))
        result = action.apply()
        assert result is not None and not result.canceled
        assert actors["traveler"].position == (17, 2)
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, cursor) for role, actor in actors.items()))
        return history, portal.uuid, actors["traveler"].uuid, result.lineage_uuid
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("role,departure,arrival", (
    ("traveler", (3, 2), (17, 2)),
    ("departure", (3, 2), None),
    ("arrival", None, (17, 2)),
))
def test_record_once_replay_discloses_only_observed_portal_endpoints(recorded, role, departure, arrival):
    history, portal_uuid, traveler_uuid, root_uuid = recorded
    native = RecordedSequence.model_validate_json(history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    events = [event for root in native.lineages for event in root.events if isinstance(event, PortalTransferEvent)]
    assert len(events) == 1 and events[0].committed
    assert events[0].portal_content_ref == PORTAL_HATCH_CONTENT_REF
    sequence = project_sequence(native)
    state, roots = decode_player_sequence(encode_player_sequence(sequence))
    crossings = [node.fact for root in roots for node in root.events if isinstance(node.fact, PortalTransferFact)]
    assert len(crossings) == 1
    crossing, = crossings
    assert crossing.target_entity_uuid == traveler_uuid and crossing.committed
    assert crossing.portal_content_id == PORTAL_HATCH_CONTENT_REF.content_id
    assert (crossing.start_position, crossing.end_position) == (departure, arrival)
    if role == "arrival":
        assert crossing.portal_uuid is None
    else:
        assert crossing.portal_uuid == portal_uuid
    for root in roots:
        if root.root.lineage_uuid == root_uuid and role == "departure":
            fact = root.root.fact
            assert isinstance(fact, MovementFact)
            assert fact.end_position != (17, 2), "A visible jump must not disclose an unseen portal exit"
        state = reduce_lineage(state, root)
    assert state.senses is not None
    if role == "traveler":
        assert state.senses.position == (17, 2)
    elif role == "arrival":
        assert state.senses.entities[traveler_uuid].position == (17, 2)
    else:
        assert traveler_uuid not in state.senses.entities
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_incremental_player_replay_keeps_later_spatial_commit_across_timed_groups(recorded):
    history, _, _, _ = recorded
    sequence = project_sequence(RecordedSequence.model_validate_json(
        history.views["traveler"].model_dump_json(), context=PASSIVE_EVENT_REPLAY))
    initial, roots = decode_player_sequence(encode_player_sequence(sequence))
    whole = incremental = initial
    for root in roots:
        whole = reduce_lineage(whole, root)
        for node in root.events:
            incremental = reduce_nodes(incremental, (node,), root.version_rows,
                tuple(row for row in root.observations if row.event_uuid == node.uuid),
                tuple(row for row in root.world_updates if row.event_uuid == node.uuid))
    assert whole.senses is not None and incremental.senses is not None
    assert whole.senses.position == incremental.senses.position == (17, 2)
    assert initial.senses is not None and initial.senses.position == (2, 2)


def test_existing_saved_portal_inputs_remain_readable_without_new_content_identity(recorded):
    history, _, _, _ = recorded
    original = project_sequence(history.views["arrival"])
    payload = json.loads(encode_player_sequence(original))
    for lineage in payload["lineages"]:
        for node in (lineage["root"], *lineage["events"]):
            if node["fact"] and node["fact"]["kind"] == "portal_transfer":
                node["fact"].pop("portal_content_id")
    _, roots = decode_player_sequence(json.dumps(payload).encode())
    crossing, = [node.fact for root in roots for node in root.events if isinstance(node.fact, PortalTransferFact)]
    assert crossing.portal_content_id is None and crossing.portal_uuid is None
    assert crossing.start_position is None and crossing.end_position == (17, 2)
