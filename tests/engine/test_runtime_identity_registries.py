"""Engine semantic tests for object identity and registries."""

from uuid import uuid4

import pytest

from dnd.core.base_block import BaseBlock
from dnd.core.base_block import LightLevel
from dnd.core.base_object import BaseObject
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.values import BaseValue, ContextualValue, ModifiableValue, StaticValue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from tests.engine.support import create_test_entity, reset_combat_state


class RegistryProbe(BaseObject):
    """Small concrete object used to isolate BaseObject registry behavior."""


class OtherRegistryProbe(BaseObject):
    """Second concrete object used to verify typed registry lookup."""


def reset_identity_state() -> None:
    """Clear the global state touched by these registry examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()


def test_eb_01_001_base_object_registration_lifecycle() -> None:
    """EB-01-001: BaseObject registers by default and can opt out."""
    reset_identity_state()
    source_uuid = uuid4()

    registered = RegistryProbe(source_entity_uuid=source_uuid)
    assert RegistryProbe.get(registered.uuid) is registered
    assert registered.use_register is True

    transient = RegistryProbe(source_entity_uuid=source_uuid, use_register=False)
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False

    transient.add_to_register()
    assert RegistryProbe.get(transient.uuid) is transient
    assert transient.use_register is True

    transient.remove_from_register()
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False


def test_eb_01_002_base_object_lookup_is_typed() -> None:
    """EB-01-002: subclass lookup rejects another registered object type."""
    reset_identity_state()
    source_uuid = uuid4()

    other = OtherRegistryProbe(source_entity_uuid=source_uuid)

    try:
        RegistryProbe.get(other.uuid)
    except ValueError as error:
        assert "is not a RegistryProbe" in str(error)
    else:
        raise AssertionError("RegistryProbe.get() should reject OtherRegistryProbe")


def test_eb_01_003_value_and_block_registries_are_separate() -> None:
    """EB-01-003: values and blocks use registries separate from BaseObject."""
    reset_identity_state()
    source_uuid = uuid4()

    value = BaseValue(source_entity_uuid=source_uuid)
    block = BaseBlock(source_entity_uuid=source_uuid)

    assert BaseValue.get(value.uuid) is value
    assert BaseObject.get(value.uuid) is None

    assert BaseBlock.get(block.uuid) is block
    assert BaseValue.get(block.uuid) is None


def test_eb_01_004_entity_registers_as_block_and_entity() -> None:
    """EB-01-004: Entity creation populates block and entity registries."""
    reset_identity_state()
    get_map().create_rectangle(0, 0, 6, 6)
    entity_uuid = uuid4()
    config = EntityConfig(position=(2, 3))

    entity = create_test_entity(
        source_id=entity_uuid,
        name="Registry Hero",
        config=config,
    )

    assert Entity.get(entity_uuid) is entity
    assert BaseBlock.get(entity_uuid) is entity
    assert entity.uuid in get_map().get_entities_at((2, 3))

    Entity.update_entity_position(entity, (4, 5))

    assert entity.position == (4, 5)
    assert entity.senses.position == (4, 5)
    assert entity.uuid not in get_map().get_entities_at((2, 3))
    assert entity.uuid in get_map().get_entities_at((4, 5))


def test_tile_owns_defensive_entity_membership_without_public_map_mutators() -> None:
    """Co-location is Tile state and callers cannot mutate its snapshot."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 5)
    first = create_test_entity(
        name="First",
        config=EntityConfig(position=(2, 2)),
    )
    second = create_test_entity(
        name="Second",
        config=EntityConfig(position=(2, 2)),
    )

    expected = {first.uuid, second.uuid}
    assert grid.get_entities_at((2, 2)) == expected
    snapshot = grid.get_tile(2, 2).get_entity_uuids()
    snapshot.clear()
    assert grid.get_entities_at((2, 2)) == expected
    assert not hasattr(grid, "register_entity")
    assert not hasattr(grid, "move_entity")

    revision = grid.occupancy_revision
    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(first, first.position)
    assert grid.occupancy_revision == revision
    assert EventQueue.event_cursor() == cursor


def test_missing_destination_rejects_without_position_membership_or_events() -> None:
    """A failed move leaves every public occupancy fact unchanged."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 4)
    entity = create_test_entity(
        name="Atomic mover",
        config=EntityConfig(position=(1, 1)),
    )
    grid.remove_tile(2, 1)
    before_cursor = EventQueue.event_cursor()
    before_revision = grid.occupancy_revision
    before_senses_position = entity.senses.position

    with pytest.raises(PositionCommitError):
        Entity.update_entity_position(entity, (2, 1))

    assert entity.position == (1, 1)
    assert entity.senses.position == before_senses_position
    assert grid.get_entities_at((1, 1)) == {entity.uuid}
    assert grid.get_entity_position(entity.uuid) == (1, 1)
    assert grid.occupancy_revision == before_revision
    assert EventQueue.event_cursor() == before_cursor


def test_disabled_spatial_events_reject_membership_without_partial_commit() -> None:
    """World presence cannot change while its required facts are disabled."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 4)
    entity = create_test_entity(
        name="Batch-protected mover",
        config=EntityConfig(position=(1, 1)),
    )
    before_revision = grid.occupancy_revision
    before_cursor = EventQueue.event_cursor()

    grid.disable_events()
    try:
        with pytest.raises(PositionCommitError):
            Entity.update_entity_position(entity, (2, 1))
    finally:
        grid.enable_events()

    assert entity.position == (1, 1)
    assert entity.senses.position == (1, 1)
    assert grid.get_entity_position(entity.uuid) == (1, 1)
    assert grid.get_entities_at((1, 1)) == {entity.uuid}
    assert grid.get_entities_at((2, 1)) == set()
    assert grid.occupancy_revision == before_revision
    assert EventQueue.event_cursor() == before_cursor


def test_public_world_presence_revision_deltas_are_exact() -> None:
    """Each real membership transition invalidates occupancy exactly once."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 5)
    game = Game()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Lifecycle actor",
        config=EntityConfig(position=(1, 1)),
    )
    entity.compose_entity()

    revision = grid.occupancy_revision
    game.deploy_entity(entity, (1, 1))
    assert grid.occupancy_revision == revision + 1

    revision = grid.occupancy_revision
    Entity.update_entity_position(entity, (2, 1))
    assert grid.occupancy_revision == revision + 1

    revision = grid.occupancy_revision
    entity.suspend_spatial_presence()
    assert grid.occupancy_revision == revision + 1

    revision = grid.occupancy_revision
    entity.restore_spatial_presence((2, 1))
    assert grid.occupancy_revision == revision + 1

    revision = grid.occupancy_revision
    assert game.remove_entity(entity.uuid) is entity
    assert grid.occupancy_revision == revision + 1


def test_live_entity_membership_protects_its_tile_and_map() -> None:
    """Live support cannot be replaced, removed, or cleared around occupancy."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 4)
    entity = create_test_entity(
        name="Protected actor",
        config=EntityConfig(position=(1, 1)),
    )

    with pytest.raises(ValueError, match="entity occupancy"):
        grid.set_tile(1, 1, name="Replacement")
    with pytest.raises(ValueError, match="entity occupancy"):
        grid.remove_tile(1, 1)
    with pytest.raises(ValueError, match="entities are deployed"):
        grid.clear()

    assert grid.get_entity_position(entity.uuid) == (1, 1)
    assert grid.get_entities_at((1, 1)) == {entity.uuid}


def test_detached_carried_light_activates_only_at_committed_deployment() -> None:
    """A pre-deployment carried light appears only at the entered coordinate."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        5,
        3,
        default_light=LightLevel.DARKNESS,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Detached light bearer",
        config=EntityConfig(position=(0, 1)),
    )
    light_uuid = grid.add_light_source(
        (0, 1),
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=entity.uuid,
    )
    entity.compose_entity()

    assert grid.get_tile(0, 1).resolved_light_level is LightLevel.DARKNESS
    cursor = EventQueue.event_cursor()
    Game().deploy_entity(entity, (3, 1))
    events = [event for _, event in EventQueue.iter_events_since(cursor)]

    assert grid.get_light_source_position(light_uuid) == (3, 1)
    assert grid.get_tile(0, 1).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(3, 1).resolved_light_level is LightLevel.BRIGHT_LIGHT
    enter_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.EFFECT
    )
    light_events = [
        event
        for event in events
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED
    ]
    assert light_events
    assert all(event.parent_event == enter_effect.uuid for event in light_events)


def test_publication_failure_keeps_objective_membership_committed() -> None:
    """A handler failure after commit cannot roll objective position backward."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 3)
    entity = create_test_entity(
        name="Committed mover",
        config=EntityConfig(position=(1, 1)),
    )

    def fail_left(_event, _source_uuid):
        raise RuntimeError("injected spatial publication failure")

    handler = EventHandler(
        name="Fail committed LEFT",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            )
        ],
        event_processor=fail_left,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(PositionPublicationError) as error:
            Entity.update_entity_position(entity, (2, 1))
    finally:
        EventQueue.remove_event_handler(handler)

    assert error.value.position_committed is True
    assert entity.position == (2, 1)
    assert entity.senses.position == (1, 1)
    assert grid.get_entity_position(entity.uuid) == (2, 1)
    assert grid.get_entities_at((1, 1)) == set()
    assert grid.get_entities_at((2, 1)) == {entity.uuid}


def test_game_ownership_follows_committed_deploy_and_detach_failures() -> None:
    """Game ownership follows committed presence, even if fact publishing fails."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 3)
    game = Game()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Ownership actor",
        config=EntityConfig(position=(1, 1)),
    )
    entity.compose_entity()

    def fail_publication(_event, _source_uuid):
        raise RuntimeError("injected ownership publication failure")

    enter_handler = EventHandler(
        name="Fail committed deployment",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            )
        ],
        event_processor=fail_publication,
    )
    EventQueue.add_event_handler(enter_handler)
    try:
        with pytest.raises(PositionPublicationError):
            game.deploy_entity(entity, (1, 1))
    finally:
        EventQueue.remove_event_handler(enter_handler)

    assert game.get_entity(entity.uuid) is entity
    assert entity.is_deployed
    assert grid.get_entity_position(entity.uuid) == (1, 1)

    left_handler = EventHandler(
        name="Fail committed detachment",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            )
        ],
        event_processor=fail_publication,
    )
    EventQueue.add_event_handler(left_handler)
    try:
        with pytest.raises(PositionPublicationError):
            game.remove_entity(entity.uuid)
    finally:
        EventQueue.remove_event_handler(left_handler)

    assert game.get_entity(entity.uuid) is None
    assert not entity.is_deployed
    assert grid.get_entity_position(entity.uuid) is None
    assert grid.get_entities_at((1, 1)) == set()


def test_committed_membership_facts_do_not_run_declaration_vetoes() -> None:
    """LEFT and ENTERED describe committed state and remain non-vetoable."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 4, 3)
    entity = create_test_entity(
        name="Non-vetoable mover",
        config=EntityConfig(position=(1, 1)),
    )
    observed_effects: list[EventType] = []

    def veto_declaration(event, _source_uuid):
        if event.phase is EventPhase.DECLARATION:
            return event.cancel(status_message="must not run")
        observed_effects.append(event.event_type)
        return None

    handler = EventHandler(
        name="Probe committed spatial facts",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=event_type,
                event_phase=phase,
                event_source_entity_uuid=entity.uuid,
            )
            for event_type in (
                EventType.SPATIAL_ENTITY_LEFT,
                EventType.SPATIAL_ENTITY_ENTERED,
            )
            for phase in (EventPhase.DECLARATION, EventPhase.EFFECT)
        ],
        event_processor=veto_declaration,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    try:
        Entity.update_entity_position(entity, (2, 1))
    finally:
        EventQueue.remove_event_handler(handler)

    spatial_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ]
    assert entity.position == entity.senses.position == (2, 1)
    assert grid.get_entities_at((2, 1)) == {entity.uuid}
    expected_phases = [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [event.phase for event in spatial_events[:4]] == expected_phases
    assert [event.phase for event in spatial_events[4:]] == expected_phases
    assert observed_effects == [
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_ENTERED,
    ]


def test_world_presence_and_carried_light_settle_before_spatial_completion() -> None:
    """Move/suspend/restore use one membership path and causal light children."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        6,
        4,
        default_light=LightLevel.DARKNESS,
    )
    game = Game()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Light bearer",
        config=EntityConfig(position=(1, 1)),
    )
    entity.compose_entity()
    game.deploy_entity(entity, (1, 1))
    light_uuid = grid.add_light_source(
        entity.position,
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=entity.uuid,
    )

    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(entity, (2, 1))
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    enter_effect = next(
        event
        for event in events
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.EFFECT
    )
    enter_completion_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
    )
    light_indices = [
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED
    ]
    assert light_indices
    assert max(light_indices) < enter_completion_index
    assert all(events[index].parent_event == enter_effect.uuid for index in light_indices)
    assert grid.get_light_source_position(light_uuid) == (2, 1)
    assert entity.senses.position == (2, 1)

    retained_position = entity.position
    entity.suspend_spatial_presence()
    assert entity.position == retained_position
    assert not entity.is_deployed
    assert entity.is_spatially_suspended
    assert grid.get_entity_position(entity.uuid) is None
    assert grid.get_entity_subscriptions(entity.uuid) == set()

    entity.restore_spatial_presence(retained_position)
    assert entity.is_deployed
    assert not entity.is_spatially_suspended
    assert grid.get_entity_position(entity.uuid) == retained_position
    assert grid.get_light_source_position(light_uuid) == retained_position

    entity.suspend_spatial_presence()
    cursor = EventQueue.event_cursor()
    assert game.remove_entity(entity.uuid) is entity
    assert EventQueue.event_cursor() == cursor


def test_eb_01_005_value_subclass_lookup_contracts() -> None:
    """EB-01-005: value subclasses share one registry but differ on misses."""
    reset_identity_state()
    source_uuid = uuid4()

    static_value = StaticValue(source_entity_uuid=source_uuid)
    contextual_value = ContextualValue(source_entity_uuid=source_uuid)
    modifiable_value = ModifiableValue.create(source_entity_uuid=source_uuid)

    assert BaseValue.get(static_value.uuid) is static_value
    assert BaseValue.get(contextual_value.uuid) is contextual_value
    assert BaseValue.get(modifiable_value.uuid) is modifiable_value

    assert StaticValue.get(static_value.uuid) is static_value
    assert ContextualValue.get(contextual_value.uuid) is contextual_value
    assert ModifiableValue.get(modifiable_value.uuid) is modifiable_value

    try:
        StaticValue.get(contextual_value.uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
    else:
        raise AssertionError("StaticValue.get() should reject ContextualValue")

    try:
        ContextualValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ContextualValue" in str(error)
    else:
        raise AssertionError("ContextualValue.get() should reject StaticValue")

    try:
        ModifiableValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ModifiableValue" in str(error)
    else:
        raise AssertionError("ModifiableValue.get() should reject StaticValue")

    missing_uuid = uuid4()
    assert BaseValue.get(missing_uuid) is None
    assert ContextualValue.get(missing_uuid) is None
    assert ModifiableValue.get(missing_uuid) is None

    try:
        StaticValue.get(missing_uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
        assert "NoneType" in str(error)
    else:
        raise AssertionError("StaticValue.get() should raise on missing UUID")


if __name__ == "__main__":
    test_eb_01_001_base_object_registration_lifecycle()
    test_eb_01_002_base_object_lookup_is_typed()
    test_eb_01_003_value_and_block_registries_are_separate()
    test_eb_01_004_entity_registers_as_block_and_entity()
    test_eb_01_005_value_subclass_lookup_contracts()
    print("PASS: engine book registry tests")
