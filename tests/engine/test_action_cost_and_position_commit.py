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
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import StaticValue
from dnd.entity import Entity
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


def test_position_staging_failure_restores_all_four_position_owners(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_core_action_state()
    entity = strong_entity("Mover", (1, 1), "heroes")
    grid = get_map()
    original = grid.recompute_tile_directional_blocking

    def fail_at_destination(position: tuple[int, int]):
        if position == (2, 1):
            raise RuntimeError("injected staging failure")
        return original(position)

    monkeypatch.setattr(grid, "recompute_tile_directional_blocking", fail_at_destination)
    before_events = EventQueue.event_cursor()

    with pytest.raises(PositionCommitError) as error:
        Entity.update_entity_position(entity, (2, 1))

    assert error.value.position_committed is False
    assert entity.position == (1, 1)
    assert entity.senses.position == (1, 1)
    assert Entity.get_all_entities_at_position((1, 1)) == [entity]
    assert Entity.get_all_entities_at_position((2, 1)) == []
    assert grid.get_entity_position(entity.uuid) == (1, 1)
    assert grid.get_entities_at((1, 1)) == {entity.uuid}
    assert grid.get_entities_at((2, 1)) == set()
    assert EventQueue.event_cursor() == before_events


def test_spatial_publication_failure_keeps_committed_position_and_raises_typed_error() -> None:
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
    assert entity.senses.position == (2, 1)
    assert Entity.get_all_entities_at_position((2, 1)) == [entity]
    assert grid.get_entity_position(entity.uuid) == (2, 1)
    assert grid.get_entities_at((2, 1)) == {entity.uuid}
