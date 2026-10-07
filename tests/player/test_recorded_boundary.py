"""Subjective public packets retain native timing without exposing private history."""

from uuid import uuid4

import pytest

from dnd.conditions import Blinded
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.events import AreaReachEvent, EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.actor_facts import PresentationTarget
from dnd.player.facts import ConditionChangeFact, PlayerHUDSnapshot, PlayerState, PlayerWorld
from dnd.player.projection import ProjectionState, begin_projection, project_after_values, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield


@pytest.mark.parametrize("native_order, expected", [
    ((), (0, 0, 0, 0, 0, 0)),
    ((2, 5, 8), (0, 0, 1, 1, 2, 3)),
    # An older event may become public after later native events. Its public
    # occurrence must still be consumed before an after-value covering it.
    ((5, 8, 2), (0, 0, 3, 3, 3, 3)),
])
def test_after_values_wait_for_all_disclosed_occurrences(native_order, expected):
    generation, observer = uuid4(), uuid4()
    world = PlayerWorld(battlefield_id="test", battlefield_name="Test",
        bounds=(0, 0, 1, 1), width=2, height=2)
    projection = ProjectionState(
        world=PresentationTarget(generation=generation, observer_uuid=observer), actors={},
        remembered=PlayerState(generation=generation, observer_uuid=observer, world=world),
        public_cursors={native: local for local, native in enumerate(native_order)})
    revisions = []
    for native_cursor in (0, 2, 3, 5, 8, 9):
        hud, logs = project_after_values(projection, PlayerHUDSnapshot(
            generation=generation, observer_uuid=observer, revision=native_cursor,
            initiative=(), sheets=()), ())
        assert hud is not None and logs == ()
        revisions.append(hud.revision)
    assert tuple(revisions) == expected


@pytest.fixture
def world():
    reset_engine_runtime()
    built = build_battlefield('battlefield.open_floor_bright')
    game = Game()
    actors = []
    for name, position in [('Owner', (5, 5)), ('Witness', (6, 5))]:
        actor = Entity.create(uuid4(), name, config=EntityConfig(position=position))
        actor.compose_entity()
        game.deploy_entity(actor, position)
        actors.append(actor)
    try:
        yield game, built, actors
    finally:
        game.close()
        reset_engine_runtime()


def start_view(built, actor):
    return begin_projection(capture_interval(name='recorded boundary', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=actor.uuid,
        battlefield_id=built.definition.battlefield_id))


def test_condition_remaining_duration_is_recorded_under_turn_and_private_to_owner(world):
    _, built, (owner, witness) = world
    projections = {actor.uuid: start_view(built, actor) for actor in (owner, witness)}
    condition = Blinded(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid,
        duration=Duration(duration=3, duration_type=DurationType.ROUNDS))
    applied = owner.add_condition(condition, check_save_throw=False)
    assert applied is not None
    applied.identified_entity_observer_uuids[str(owner.uuid)] = {str(witness.uuid)}
    roots = (applied, owner.on_turn_start(round_number=1))
    assert condition.duration.duration == 2
    for actor in (owner, witness):
        projection, initial = projections[actor.uuid]
        state = reduce_initialization(initial)
        delivered = []
        for native in capture_lineages(roots, observer_uuid=actor.uuid, known_actor_uuids=frozenset(state.actors)):
            public = project_lineage(projection, native)
            if public is None:
                assert actor is witness
                continue
            delivered.append(public)
            state = reduce_lineage(state, public)
        member = next(row for row in state.actors[owner.uuid].conditions if row.condition_uuid == condition.uuid)
        assert member.state is not None
        if actor is owner:
            assert member.state.duration.remaining_rounds == 2
            changed = [node for node in delivered[-1].events if isinstance(node.fact, ConditionChangeFact)]
            assert len(changed) == 1 and changed[0].parent_lineage == roots[-1].lineage_uuid
            application = next(node for node in delivered[0].events if isinstance(node.fact, ConditionChangeFact))
            origin = next(row.source_index for row in delivered[0].version_rows if row.event_uuid == application.uuid)
            assert member.state.applied_source_event_cursor == origin + 1
        else:
            assert member.state.duration is None


def test_wholly_unseen_area_expansion_has_no_public_operation(world):
    _, built, (owner, _) = world
    projection, initial = start_view(built, owner)
    hidden = AreaReachEvent(source_entity_uuid=uuid4(), phase=EventPhase.COMPLETION,
        newly_reached_positions=((99, 99),), stage_index=7)
    native, = capture_lineages((hidden,), observer_uuid=owner.uuid)
    assert project_lineage(projection, native) is None
    assert projection.next_occurrence == initial.end_cursor
