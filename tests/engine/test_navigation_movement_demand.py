"""Exhausted movement keeps discovery and sensory facts without unused routes."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import Dash, Move
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_actions import BaseAction, PositionDiscoveryContract, TargetType
from dnd.core.base_block import MovementMode
from dnd.core.base_tiles import floor_factory, wall_factory
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.player.event_record import decode_event, encode_event
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import FlyEffect
from dnd.types.senses import reduce_senses_snapshot
from tests.engine.test_sensory_initial_replay import sensory_since


class ReachableVariant(BaseAction):
    """A visible template whose actual discovery form consumes known paths."""

    target_type: TargetType = TargetType.POSITION
    position_discovery: PositionDiscoveryContract = PositionDiscoveryContract()

    def get_discovery_variants(self, entity):
        return [self.model_copy(update={"position_discovery": PositionDiscoveryContract(
            candidate_source="reachable")})]


def make_actor():
    reset_engine_runtime()
    get_map().create_rectangle(0, 0, 16, 1)
    entity = Entity.create(uuid4(), "Walker", config=EntityConfig(position=(0, 0)))
    entity.compose_entity()
    Game().deploy_entity(entity, (0, 0))
    entity.register_action(Move(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dash(source_entity_uuid=entity.uuid, template=True))
    entity.update_entity_senses(max_distance=20)
    return entity


@pytest.fixture
def actor():
    entity = make_actor()
    yield entity
    reset_engine_runtime()


def move_to(actor, destination, **kwargs):
    event = Move(source_entity_uuid=actor.uuid, end_position=destination, **kwargs).apply()
    assert event is not None and not event.canceled
    assert actor.position == destination


def targets(actor, name):
    result = actor.get_available_actions()
    row = next(row for row in result.position_actions if row.template_name == name)
    return {target.position for target in row.valid_targets}


def path_consumer(actor, kind):
    binding = BehaviorBinding(behavior_id="test.navigation.path_consumer",
        provided_by_id="test.navigation.path_consumer", runtime_owner_uuid=actor.uuid)
    if kind == "variant":
        return ReachableVariant(name="Path consumer", source_entity_uuid=actor.uuid,
            template=True, behavior_binding=binding)
    return BaseAction(name="Path consumer", source_entity_uuid=actor.uuid, template=True,
        behavior_binding=binding,
        target_type=(TargetType.POSITION_PATH if kind == "path" else
                     TargetType.POSITION_LOS if kind == "los_reachable" else TargetType.POSITION),
        position_discovery=(PositionDiscoveryContract(candidate_source="reachable")
                            if kind in ("reachable", "los_reachable") else None))


def test_exhausted_move_keeps_walkable_discovery_and_serialized_perception(actor):
    move_to(actor, (6, 0))
    assert actor.action_economy.movement_remaining() == 0
    assert targets(actor, "Move") == set()
    assert actor.senses.paths == {(6, 0): [(6, 0)]}
    assert actor.senses.walkable == {position: True for position in capture_senses_snapshot(actor.senses).visible}
    replayed = None
    for event in sensory_since(actor.uuid):
        replayed = reduce_senses_snapshot(actor.uuid, replayed, decode_event(encode_event(event)))
    before = capture_senses_snapshot(actor.senses)
    assert replace(replayed, paths_dirty=False) == replace(before, paths_dirty=False)
    actor.materialize_navigation(max_distance=20)
    assert capture_senses_snapshot(actor.senses) == before


def test_dash_reestablishes_affordable_paths_after_exhaustion(actor):
    move_to(actor, (6, 0))
    result = Dash(source_entity_uuid=actor.uuid).apply()
    assert result is not None and not result.canceled
    assert actor.action_economy.movement_remaining() == 30
    assert (12, 0) in targets(actor, "Move")
    move_to(actor, (12, 0))


# A position action without a discovery contract is a free-aim region, not a path consumer (plan §14.4).
@pytest.mark.parametrize("kind", ["reachable", "los_reachable", "path", "variant"])
@pytest.mark.parametrize("register_after_move", [False, True])
def test_custom_path_consumers_keep_the_legacy_domain(actor, kind, register_after_move):
    if not register_after_move:
        actor.register_action(path_consumer(actor, kind))
    move_to(actor, (6, 0))
    if register_after_move:
        actor.register_action(path_consumer(actor, kind))
    assert (15, 0) in targets(actor, "Path consumer")
    assert actor.senses.paths[(15, 0)][0] == (6, 0)


def test_positive_budget_and_explicit_navigation_domains_remain_unchanged(actor):
    actor.register_action(path_consumer(actor, "reachable"))
    move_to(actor, (5, 0))
    assert actor.action_economy.movement_remaining() == 5
    assert targets(actor, "Path consumer") == {(4, 0), (6, 0)}
    actor.materialize_navigation(max_distance=4, path_max_distance=0)
    assert (9, 0) in actor.senses.paths
    assert (10, 0) not in actor.senses.paths
    actor.materialize_navigation(max_distance=20, path_max_distance=2)
    assert (7, 0) in actor.senses.paths
    assert (8, 0) not in actor.senses.paths


def test_exhausted_flight_keeps_walking_navigation(actor):
    actor.add_condition(FlyEffect(source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid, flying_speed=10))
    actor.register_action(Move(name="Flying Movement", source_entity_uuid=actor.uuid,
        template=True, movement_mode=MovementMode.FLYING))
    move_to(actor, (2, 0), name="Flying Movement", movement_mode=MovementMode.FLYING)
    assert actor.action_economy.movement_remaining(MovementMode.FLYING) == 0
    assert actor.action_economy.movement_remaining(MovementMode.WALKING) == 20
    assert (15, 0) in actor.senses.paths
    assert (6, 0) in targets(actor, "Move")


def test_restored_paths_use_current_terrain_in_remembered_cells(actor):
    actor.update_entity_senses(max_distance=1, path_max_distance=20)
    move_to(actor, (6, 0))
    assert (10, 0) in capture_senses_snapshot(actor.senses).seen and (10, 0) not in capture_senses_snapshot(actor.senses).visible
    grid = get_map()
    grid.set_tile(10, 0, tile=wall_factory((10, 0)))
    actor.register_action(path_consumer(actor, "reachable"))
    assert (9, 0) in targets(actor, "Path consumer")
    assert (11, 0) not in targets(actor, "Path consumer")
    grid.set_tile(10, 0, tile=floor_factory((10, 0)))
    actor.materialize_navigation(max_distance=20)
    assert (11, 0) in targets(actor, "Path consumer")


def test_hidden_mutation_sensory_prefix_matches_full_navigation_reference():
    def transcript(restore_full_domain):
        actor = make_actor()
        actor.update_entity_senses(max_distance=1, path_max_distance=20)
        move_to(actor, (6, 0))
        if restore_full_domain:
            actor.materialize_navigation(max_distance=20)
        assert (10, 0) in capture_senses_snapshot(actor.senses).seen and (10, 0) not in capture_senses_snapshot(actor.senses).visible
        cursor = EventQueue.event_cursor()
        get_map().set_tile(10, 0, tile=wall_factory((10, 0)))
        first = capture_senses_snapshot(actor.senses)
        get_map().set_tile(10, 0, tile=floor_factory((10, 0)))
        second = capture_senses_snapshot(actor.senses)
        return first, second, tuple(encode_event(event) for event in sensory_since(actor.uuid, cursor))

    try:
        trimmed = transcript(False)
        reference = transcript(True)
        # These unchanged hidden inputs publish no sensory delta in the native
        # full-domain reference either. Keep paths_dirty in both snapshots.
        assert reference[2] == ()
        assert trimmed == reference
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize("start", [(0, 0), (1, 0), (-1, 0)])
def test_zero_distance_path_query_retains_origin_for_supported_and_absent_start(actor, start):
    grid = get_map()
    grid.set_tile(1, 0, tile=wall_factory((1, 0)))
    assert grid.compute_paths(start, 0) == ({start: 0}, {start: [start]})
