"""Unit 4 debit receipts and exception-safe position commit seams."""

from uuid import UUID, uuid4

import pytest

from dnd.blocks.action_economy import (
    ActionEconomyChannelCost,
    FixedCostCommitError,
    NamedResourceCost,
    RechargeType,
    Resource,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import StaticValue
from dnd.content.monsters.monster_builders import create_monster
from dnd.entities.entity import Entity
from dnd.game import Game
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


def test_aggregate_debit_combines_channels_and_undoes_only_exact_handles() -> None:
    reset_core_action_state()
    entity = strong_entity("Debtor", (1, 1), "heroes")
    economy = entity.action_economy

    receipt = economy.consume_aggregate_with_receipt(
        (
            ActionEconomyChannelCost(cost_type="movement", amount=5, name="first"),
            ActionEconomyChannelCost(cost_type="movement", amount=10, name="second"),
            ActionEconomyChannelCost(cost_type="bonus_actions", amount=1, name="jump"),
        )
    )

    assert economy.movement.normalized_score == 15
    assert economy.bonus_actions.normalized_score == 0
    assert len(receipt.handles) == 2
    economy.undo_prevalidated_debit(receipt)
    assert economy.movement.normalized_score == 30
    assert economy.bonus_actions.normalized_score == 1
    with pytest.raises(ValueError):
        economy.undo_prevalidated_debit(receipt)


def test_prevalidated_install_does_not_recheck_post_admission_affordability() -> None:
    reset_core_action_state()
    entity = strong_entity("Accepted", (1, 1), "heroes")
    economy = entity.action_economy
    permission_modifier = economy.action_permission.get_base_modifier()
    assert permission_modifier is not None
    economy.movement.self_static.add_max_constraint(
        permission_modifier.model_copy(
            update={"uuid": uuid4(), "name": "Post-admission stop", "value": 0}
        )
    )

    receipt = economy.install_prevalidated_aggregate_with_receipt(
        (ActionEconomyChannelCost(cost_type="movement", amount=5, name="accepted"),)
    )

    assert len(receipt.handles) == 1
    assert economy.movement.normalized_score == 0


def test_current_aggregate_affordability_fails_before_any_install() -> None:
    reset_core_action_state()
    entity = strong_entity("Poor", (1, 1), "heroes")
    economy = entity.action_economy
    before = tuple(economy.actions.self_static.value_modifiers)

    with pytest.raises(ValueError):
        economy.consume_aggregate_with_receipt(
            (
                ActionEconomyChannelCost(cost_type="actions", amount=1),
                ActionEconomyChannelCost(cost_type="actions", amount=1),
            )
        )

    assert tuple(economy.actions.self_static.value_modifiers) == before


def test_fixed_cost_commit_restores_its_partial_channels_and_resources() -> None:
    reset_core_action_state()
    entity = strong_entity("Jumper", (1, 1), "heroes")
    economy = entity.action_economy
    economy.add_resource_contribution(
        "Ki",
        uuid4(),
        maximum=1,
        recharge_type=RechargeType.SHORT_REST,
    )

    with pytest.raises(FixedCostCommitError):
        economy.commit_fixed_costs_without_dispatch(
            channel_costs=(
                ActionEconomyChannelCost(cost_type="bonus_actions", amount=1),
            ),
            resource_costs=(NamedResourceCost(name="Ki", amount=2),),
        )

    assert economy.bonus_actions.normalized_score == 1
    assert economy.get_resource_current("Ki") == 1


@pytest.mark.parametrize("raise_after_insert", (False, True))
def test_aggregate_debit_failure_removes_current_and_prior_modifier_state(
    monkeypatch: pytest.MonkeyPatch,
    raise_after_insert: bool,
) -> None:
    reset_core_action_state()
    entity = strong_entity("Atomic Debtor", (1, 1), "heroes")
    economy = entity.action_economy
    before_registry = set(NumericalModifier._registry)
    original_add = StaticValue.add_value_modifier
    calls = 0

    def fail_second(
        value: StaticValue,
        modifier: NumericalModifier,
    ) -> UUID:
        nonlocal calls
        calls += 1
        if calls == 2 and not raise_after_insert:
            raise RuntimeError("injected add failure")
        result = original_add(value, modifier)
        if calls == 2:
            raise RuntimeError("injected post-insert failure")
        return result

    monkeypatch.setattr(StaticValue, "add_value_modifier", fail_second)
    with pytest.raises(RuntimeError, match="injected"):
        economy.consume_aggregate_with_receipt((
            ActionEconomyChannelCost(cost_type="actions", amount=1),
            ActionEconomyChannelCost(cost_type="bonus_actions", amount=1),
        ))

    assert economy.actions.normalized_score == 1
    assert economy.bonus_actions.normalized_score == 1
    assert set(NumericalModifier._registry) == before_registry


def test_fixed_cost_resource_decrement_then_raise_restores_every_owned_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_core_action_state()
    entity = strong_entity("Atomic Resources", (1, 1), "heroes")
    economy = entity.action_economy
    for name in ("A", "B"):
        economy.add_resource_contribution(
            name,
            uuid4(),
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
        )
    original_consume = Resource.consume

    def consume_then_fail(resource: Resource, amount: int = 1) -> bool:
        result = original_consume(resource, amount)
        if resource.name == "B":
            raise RuntimeError("injected resource failure")
        return result

    monkeypatch.setattr(Resource, "consume", consume_then_fail)
    with pytest.raises(FixedCostCommitError):
        economy.commit_fixed_costs_without_dispatch(
            channel_costs=(
                ActionEconomyChannelCost(
                    cost_type="bonus_actions",
                    amount=1,
                ),
            ),
            resource_costs=(
                NamedResourceCost(name="A", amount=1),
                NamedResourceCost(name="B", amount=1),
            ),
        )

    assert economy.bonus_actions.normalized_score == 1
    assert economy.get_resource_current("A") == 1
    assert economy.get_resource_current("B") == 1


def test_debit_undo_rejects_forged_handle_before_removing_any_modifier() -> None:
    reset_core_action_state()
    entity = strong_entity("Receipt Owner", (1, 1), "heroes")
    economy = entity.action_economy
    receipt = economy.consume_aggregate_with_receipt((
        ActionEconomyChannelCost(cost_type="bonus_actions", amount=1),
    ))
    unrelated = NumericalModifier.create(
        source_entity_uuid=economy.source_entity_uuid,
        name="Unrelated",
        value=5,
    )
    economy.movement.self_static.add_value_modifier(unrelated)
    forged_handle = receipt.handles[0].model_copy(update={
        "cost_type": "movement",
        "modifier_uuid": unrelated.uuid,
        "amount": -5,
        "modifier_name": "Unrelated",
    })
    forged_receipt = receipt.model_copy(update={"handles": (forged_handle,)})

    with pytest.raises(TypeError, match="malformed typed evidence"):
        economy.undo_prevalidated_debit(forged_receipt)

    assert economy.bonus_actions.normalized_score == 0
    assert unrelated.uuid in economy.movement.self_static.value_modifiers


def test_spatial_publication_failure_keeps_committed_objective_position_and_raises() -> None:
    reset_core_action_state()
    entity = strong_entity("Mover", (1, 1), "heroes")
    grid = get_map()
    handler = EventHandler(
        name="Injected left failure",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="Raise on left",
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            )
        ],
        event_processor=lambda _event, _source: (_ for _ in ()).throw(
            RuntimeError("injected publication failure")
        ),
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
    assert get_map().get_entities_at((2, 1)) == {entity.uuid}
    assert grid.get_entity_position(entity.uuid) == (2, 1)
    assert grid.get_entities_at((2, 1)) == {entity.uuid}


def test_committed_entity_membership_facts_ignore_declaration_veto() -> None:
    reset_core_action_state()
    entity = strong_entity("Committed mover", (1, 1), "heroes")
    grid = get_map()
    observed_effects = []

    def veto_declaration_and_observe_effect(event, _source_uuid):
        if event.phase is EventPhase.DECLARATION:
            return event.cancel(status_message="declaration veto")
        observed_effects.append((event.event_type, event.uuid))
        return None

    handler = EventHandler(
        name="Veto committed spatial declarations",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="Veto Entity LEFT declaration",
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.DECLARATION,
                event_source_entity_uuid=entity.uuid,
            ),
            Trigger(
                name="Veto Entity ENTERED declaration",
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.DECLARATION,
                event_source_entity_uuid=entity.uuid,
            ),
            Trigger(
                name="Observe Entity LEFT effect",
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            ),
            Trigger(
                name="Observe Entity ENTERED effect",
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            ),
        ],
        event_processor=veto_declaration_and_observe_effect,
    )
    EventQueue.add_event_handler(handler)
    cursor = EventQueue.event_cursor()
    root = EventQueue.publish_declaration(Event(
        source_entity_uuid=entity.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    root = root.phase_to(EventPhase.EXECUTION)
    root = root.phase_to(EventPhase.EFFECT)
    parent_uuid = root.uuid
    try:
        Entity.update_entity_position(entity, (2, 1), parent_event=parent_uuid)
    finally:
        EventQueue.remove_event_handler(handler)
    root.phase_to(EventPhase.COMPLETION)

    assert entity.position == (2, 1)
    assert entity.senses.position == (2, 1)
    assert grid.get_entity_position(entity.uuid) == (2, 1)
    assert grid.get_entities_at((1, 1)) == set()
    assert grid.get_entities_at((2, 1)) == {entity.uuid}
    spatial_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ]
    assert [event.event_type for event in spatial_events] == [
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
    ]
    assert [event.phase for event in spatial_events[:4]] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [event.phase for event in spatial_events[4:]] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert len({event.lineage_uuid for event in spatial_events[:4]}) == 1
    assert len({event.lineage_uuid for event in spatial_events[4:]}) == 1
    assert all(event.parent_event == parent_uuid for event in spatial_events)
    assert observed_effects == [
        (EventType.SPATIAL_ENTITY_LEFT, spatial_events[2].uuid),
        (EventType.SPATIAL_ENTITY_ENTERED, spatial_events[6].uuid),
    ]


def test_disabled_entity_occupancy_attempts_are_atomic_and_publish_nothing() -> None:
    reset_core_action_state()
    grid = get_map()
    game = Game()
    entity = create_monster("creature.commoner", uuid4(), faction="heroes")
    game.deploy_entity(entity, (1, 1))
    unpublished = create_monster("creature.commoner", uuid4(), faction="heroes")
    unpublished_position = unpublished.position

    tracked_positions = ((1, 1), (2, 1), (3, 1), (4, 1))

    def snapshot() -> tuple[object, ...]:
        return (
            entity.position,
            entity.is_deployed,
            entity.is_spatially_suspended,
            game.get_entity(entity.uuid) is entity,
            grid.get_entity_position(entity.uuid),
            tuple(
                frozenset(grid.get_entities_at(position))
                for position in tracked_positions
            ),
            grid.occupancy_revision,
            EventQueue.event_cursor(),
            entity.senses.position,
            tuple(
                grid.get_tile(*position).resolved_light_level
                for position in tracked_positions
            ),
        )

    cursor = EventQueue.event_cursor()
    before_disabled = snapshot()

    grid.disable_events()

    with pytest.raises(PositionCommitError):
        Entity.update_entity_position(entity, (2, 1))
    assert snapshot() == before_disabled

    with pytest.raises(PositionCommitError):
        Entity.update_entity_position(entity, (3, 1))
    assert snapshot() == before_disabled

    with pytest.raises(PositionCommitError):
        game.deploy_entity(unpublished, (4, 1))
    assert unpublished.position == unpublished_position
    assert not unpublished.is_deployed
    assert not unpublished.is_spatially_suspended
    assert game.get_entity(unpublished.uuid) is None
    assert grid.get_entity_position(unpublished.uuid) is None
    assert snapshot() == before_disabled

    with pytest.raises(PositionCommitError):
        game.remove_entity(entity.uuid)
    assert snapshot() == before_disabled

    with pytest.raises(PositionCommitError):
        entity.suspend_spatial_presence()
    assert snapshot() == before_disabled

    grid.enable_events(flush_pending=True)
    assert EventQueue.event_cursor() == cursor
    assert [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type
        in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ] == []

    root = EventQueue.publish_declaration(Event(
        source_entity_uuid=entity.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    root = root.phase_to(EventPhase.EXECUTION)
    root = root.phase_to(EventPhase.EFFECT)
    parent_uuid = root.uuid
    Entity.update_entity_position(entity, (2, 1), parent_event=parent_uuid)
    root.phase_to(EventPhase.COMPLETION)
    assert entity.position == (2, 1)
    assert entity.senses.position == (2, 1)
    assert grid.get_entity_position(entity.uuid) == (2, 1)
    assert grid.get_entities_at((1, 1)) == set()
    assert grid.get_entities_at((2, 1)) == {entity.uuid}

    move_cursor = cursor

    spatial_events = [
        event
        for _, event in EventQueue.iter_events_since(move_cursor)
        if event.event_type in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ]
    assert [event.event_type for event in spatial_events] == [
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
    ]
    assert [event.phase for event in spatial_events[:4]] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [event.phase for event in spatial_events[4:]] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert all(event.parent_event == parent_uuid for event in spatial_events)

    entity.suspend_spatial_presence()
    suspended_cursor = EventQueue.event_cursor()
    suspended_before_disabled = snapshot()
    grid.disable_events()

    with pytest.raises(PositionCommitError):
        entity.restore_spatial_presence((4, 1))
    assert snapshot() == suspended_before_disabled

    grid.enable_events(flush_pending=True)
    assert EventQueue.event_cursor() == suspended_cursor
    assert [
        event
        for _, event in EventQueue.iter_events_since(suspended_cursor)
        if event.event_type
        in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ] == []

    entity.restore_spatial_presence((4, 1))
    assert entity.is_deployed
    assert not entity.is_spatially_suspended
    assert entity.position == (4, 1)
    assert entity.senses.position == (4, 1)
    assert grid.get_entity_position(entity.uuid) == (4, 1)
    assert grid.get_entities_at((4, 1)) == {entity.uuid}
