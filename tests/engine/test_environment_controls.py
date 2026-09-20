"""Native environment commands preserve visible state and causal ownership."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.content.items.environment_item_builders import (
    build_control_lever,
    build_directional_door,
    build_standing_torch,
    build_storage_chest,
    build_trap_lever,
)
from dnd.core.base_actions import ActionEvent
from dnd.core.events import Event, EventPhase, EventQueue, SpatialEffectChangeEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemPresentationState
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment_interactables import LeverLink
from dnd.items.torches import WallTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.traps import TrapState
from dnd.types.world import CardinalDirection
from dnd.world_facts import WorldFacts, apply_world_fact


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(10, 6))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


@pytest.fixture
def operator(game: Game) -> Entity:
    actor = Entity.create(uuid4(), "Operator", config=EntityConfig(position=(1, 1)))
    actor.compose_entity()
    game.deploy_entity(actor, actor.position)
    return actor


def available_names(actor: Entity, item_uuid: UUID) -> set[str]:
    actor.update_entity_senses(max_distance=10)
    return {
        row.template_name.split("__item_")[0]
        for row in actor.get_available_actions().all_actions
        if row.source_item_uuid == item_uuid
    }


def use(actor: Entity, item_uuid: UUID, name: str) -> Event:
    assert name in available_names(actor, item_uuid)
    completion = execute_use_action(actor, item_uuid, name)
    assert completion is not None and not completion.canceled
    return completion


def item_facts_since(cursor: int) -> list[ItemLocationStateEvent]:
    return [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ItemLocationStateEvent)
        and event.phase is EventPhase.COMPLETION
    ]


def assert_descends_from(event: Event, root: Event) -> None:
    ancestor = event
    while ancestor.parent_event is not None:
        parent = EventQueue.get_event_by_uuid(ancestor.parent_event)
        assert parent is not None
        ancestor = parent
    assert ancestor.lineage_uuid == root.lineage_uuid


def test_chest_lid_controls_loot_and_stays_usable_when_empty(operator: Entity) -> None:
    chest = build_storage_chest("Chest", include_loot_all_action=True)
    chest.chest_inventory.source_entity_uuid = chest.uuid
    gem = BaseItem(source_entity_uuid=chest.uuid, item_id="test.item.gem", name="Gem")
    assert chest.chest_inventory.add_item(gem)
    chest.place_on_grid((2, 1))

    assert available_names(operator, chest.uuid) == {"Open Chest"}
    with pytest.raises(ValueError, match="not found"):
        execute_use_action(operator, chest.uuid, "Loot All")
    assert gem.uuid in chest.chest_inventory.items

    recorded = WorldFacts()
    for name, expected_open in (
        ("Open Chest", True), ("Close Chest", False), ("Open Chest", True),
    ):
        cursor = EventQueue.event_cursor()
        root = use(operator, chest.uuid, name)
        facts = item_facts_since(cursor)
        assert len(facts) == 1
        fact = facts[0]
        saved_state = ItemPresentationState.model_validate_json(fact.item_state.model_dump_json())
        assert saved_state.is_open is expected_open
        assert fact.item_state.item_uuid == chest.uuid
        assert fact.world_placement is not None
        assert fact.world_placement.position == (2, 1)
        assert_descends_from(fact, root)
        assert apply_world_fact(recorded, fact)
        assert recorded.objects[chest.uuid].item.is_open is expected_open
        assert gem.uuid in chest.chest_inventory.items

    assert available_names(operator, chest.uuid) == {"Close Chest", "Loot All"}
    stale_loot = next(action for action in chest.get_use_actions(operator.uuid) if action.name == "Loot All")
    use(operator, chest.uuid, "Close Chest")
    refused = stale_loot.instantiate().apply()
    assert refused is not None and refused.canceled
    assert gem.uuid in chest.chest_inventory.items
    use(operator, chest.uuid, "Open Chest")

    use(operator, chest.uuid, "Loot All")
    assert gem.uuid in operator.inventory.items
    assert not chest.chest_inventory.items
    assert available_names(operator, chest.uuid) == {"Close Chest"}
    use(operator, chest.uuid, "Close Chest")
    assert available_names(operator, chest.uuid) == {"Open Chest"}
    use(operator, chest.uuid, "Open Chest")
    assert available_names(operator, chest.uuid) == {"Close Chest"}


@pytest.mark.parametrize("target_kind", ("light", "door"))
def test_lever_repeats_remote_target_actions_under_one_causal_root(
    operator: Entity, target_kind: str,
) -> None:
    if target_kind == "light":
        target = build_standing_torch()
        target.place_on_grid((7, 1))
        link = LeverLink(target_item_uuid=target.uuid, target_kind="light")
    else:
        target = build_directional_door()
        target.place_on_grid((7, 1), boundary_direction=CardinalDirection.EAST)
        link = LeverLink(target_item_uuid=target.uuid, target_kind="door")
    lever = build_control_lever(link)
    lever.place_on_grid((2, 1))
    assert available_names(operator, target.uuid) == set()
    recorded = WorldFacts()

    for expected_value in (True, False, True):
        cursor = EventQueue.event_cursor()
        root = use(operator, lever.uuid, "Toggle Lever")
        assert lever.is_engaged is expected_value
        assert (target.is_lit if isinstance(target, WallTorch) else target.is_open) is expected_value
        facts = item_facts_since(cursor)
        handle_facts = [fact for fact in facts if fact.item_state.item_uuid == lever.uuid]
        assert len(handle_facts) == 1
        handle = handle_facts[0]
        saved_state = ItemPresentationState.model_validate_json(handle.item_state.model_dump_json())
        assert saved_state.is_engaged is expected_value
        assert str(target.uuid) not in saved_state.model_dump_json()
        assert_descends_from(handle, root)
        actions = [
            event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ActionEvent) and event.phase is EventPhase.COMPLETION
        ]
        assert len(actions) == 2
        nested = next(action for action in actions if action.source_item_uuid == target.uuid)
        assert nested.source_item_presentation is not None
        assert nested.source_item_presentation.item_uuid == target.uuid
        assert_descends_from(nested, root)
        assert isinstance(root, ActionEvent)
        assert root.source_item_uuid == lever.uuid
        assert root.source_item_presentation is not None
        assert root.source_item_presentation.is_engaged is not expected_value
        for _, event in EventQueue.iter_events_since(cursor):
            if event.phase is EventPhase.COMPLETION:
                apply_world_fact(recorded, event)
        assert recorded.objects[lever.uuid].item.is_engaged is expected_value
        recorded_target = recorded.objects[target.uuid].item
        assert (recorded_target.is_lit if isinstance(target, WallTorch) else recorded_target.is_open) is expected_value


def test_lever_handle_is_independent_when_light_already_matches_request(
    operator: Entity, game: Game,
) -> None:
    light = build_standing_torch()
    light.place_on_grid((7, 1))
    lever = build_control_lever(LeverLink(
        target_item_uuid=light.uuid, target_kind="light", engaged_value=False,
    ))
    lever.place_on_grid((2, 1))
    witness = Entity.create(uuid4(), "Witness", config=EntityConfig(position=(7, 2)))
    witness.compose_entity()
    game.deploy_entity(witness, witness.position)

    # Engaging an off-switch while the light is already off moves only the handle.
    cursor = EventQueue.event_cursor()
    use(operator, lever.uuid, "Toggle Lever")
    assert lever.is_engaged and not light.is_lit
    assert [fact.item_state.item_uuid for fact in item_facts_since(cursor)] == [lever.uuid]

    # A separate user's local action changes the target without moving the handle.
    use(witness, light.uuid, "Light Wall Torch")
    assert lever.is_engaged and light.is_lit
    cursor = EventQueue.event_cursor()
    use(operator, lever.uuid, "Toggle Lever")
    assert not lever.is_engaged and light.is_lit
    assert [fact.item_state.item_uuid for fact in item_facts_since(cursor)] == [lever.uuid]


def test_occupied_door_rejects_remote_close_without_moving_handle(
    operator: Entity, game: Game,
) -> None:
    door = build_directional_door(is_open=True)
    door.place_on_grid((7, 1), boundary_direction=CardinalDirection.EAST)
    lever = build_control_lever(LeverLink(
        target_item_uuid=door.uuid, target_kind="door",
    ), is_engaged=True)
    lever.place_on_grid((2, 1))
    assert available_names(operator, lever.uuid) == {"Toggle Lever"}
    occupant = Entity.create(uuid4(), "Occupant", config=EntityConfig(position=(7, 1)))
    occupant.compose_entity()
    game.deploy_entity(occupant, occupant.position)

    assert available_names(operator, lever.uuid) == set()
    cursor = EventQueue.event_cursor()
    refused = execute_use_action(operator, lever.uuid, "Toggle Lever")
    assert refused is not None and refused.canceled
    assert lever.is_engaged and door.is_open
    assert not item_facts_since(cursor)


def test_finite_trap_lever_preserves_disabled_fixture_and_spent_handle(operator: Entity) -> None:
    linked = materialize_spike_trap_condition({(7, 1)})
    other = materialize_spike_trap_condition({(9, 1)})
    lever = build_trap_lever(linked.uuid, charges=1)
    lever.place_on_grid((2, 1))
    cursor = EventQueue.event_cursor()

    root = use(operator, lever.uuid, "Pull Lever")

    assert linked.trap_state is TrapState.DEACTIVATED
    assert linked.applied and get_map().get_spatial_condition(linked.uuid) is linked
    assert linked.affected_positions == {(7, 1)}
    assert not get_map().is_position_hazardous_for(7, 1, operator.uuid)
    assert other.trap_state is TrapState.READY
    assert get_map().is_position_hazardous_for(9, 1, operator.uuid)
    assert lever.charges == 0 and lever.is_engaged
    assert get_map().get_object_placement(lever.uuid) is not None
    assert available_names(operator, lever.uuid) == set()
    handle_facts = item_facts_since(cursor)
    assert any(fact.item_state.item_uuid == lever.uuid and fact.item_state.is_engaged is True
               for fact in handle_facts)
    for fact in handle_facts:
        assert_descends_from(fact, root)


def test_reusable_trap_lever_discovery_and_recorded_state_follow_same_control(operator: Entity) -> None:
    trap = materialize_spike_trap_condition({(7, 1), (8, 1)})
    lever = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
    lever.place_on_grid((2, 1))
    recorded = WorldFacts()

    for name, expected, handle_engaged in (
        ("Deactivate Trap", TrapState.DEACTIVATED, True),
        ("Activate Trap", TrapState.ACTIVATED, False),
        ("Deactivate Trap", TrapState.DEACTIVATED, True),
    ):
        assert available_names(operator, lever.uuid) == {name}
        cursor = EventQueue.event_cursor()
        root = use(operator, lever.uuid, name)
        assert trap.trap_state is expected
        assert trap.applied and trap.affected_positions == {(7, 1), (8, 1)}
        assert get_map().get_spatial_condition(trap.uuid) is trap
        assert lever.charges == -1 and lever.is_engaged is handle_engaged
        changes = [event for _, event in EventQueue.iter_events_since(cursor)
                   if isinstance(event, SpatialEffectChangeEvent)
                   and event.operation is SpatialEffectChangeOperation.STATE_CHANGED
                   and event.phase is EventPhase.COMPLETION]
        assert len(changes) == 1
        change = changes[0]
        assert change.spatial_effect_uuid == trap.uuid and change.trap_state is expected
        assert change.previous_positions == change.affected_positions == ((7, 1), (8, 1))
        assert_descends_from(change, root)
        handles = item_facts_since(cursor)
        assert len(handles) == 1 and handles[0].item_state.is_engaged is handle_engaged
        assert_descends_from(handles[0], root)
        assert apply_world_fact(recorded, handles[0])
        assert recorded.objects[lever.uuid].item.is_engaged is handle_engaged


def test_remote_trap_change_does_not_move_local_handle_or_change_offered_command(operator: Entity) -> None:
    trap = materialize_spike_trap_condition({(7, 1)})
    local = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
    remote = build_trap_lever(trap.uuid, charges=-1, allow_activation=True)
    local.place_on_grid((2, 1))
    remote.place_on_grid((1, 2))

    assert available_names(operator, local.uuid) == {"Deactivate Trap"}
    use(operator, remote.uuid, "Deactivate Trap")
    assert trap.trap_state is TrapState.DEACTIVATED
    assert not local.is_engaged
    assert available_names(operator, local.uuid) == {"Deactivate Trap"}

    # The target already matches: using this handle still moves only this handle.
    cursor = EventQueue.event_cursor()
    root = use(operator, local.uuid, "Deactivate Trap")
    assert local.is_engaged and remote.is_engaged
    assert available_names(operator, local.uuid) == {"Activate Trap"}
    assert not [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, SpatialEffectChangeEvent)]
    handles = item_facts_since(cursor)
    assert len(handles) == 1 and handles[0].item_state.item_uuid == local.uuid
    assert_descends_from(handles[0], root)
