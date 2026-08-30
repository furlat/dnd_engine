"""Public action-economy proofs for exact, atomic fixed-cost commitment."""

from uuid import UUID, uuid4

import pytest

from dnd.blocks.action_economy import (
    ActionEconomyChannelCost,
    ActionEconomyDebitReceipt,
    FixedCostCommitError,
    NamedResourceCost,
    RechargeType,
    Resource,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import StaticValue
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


def test_aggregate_debit_combines_channels_and_undoes_only_exact_handles() -> None:
    """Repeated channels form one exact debit that can be undone once."""
    reset_core_action_state()
    economy = strong_entity("Debtor", (1, 1), "heroes").action_economy

    receipt = economy.consume_aggregate_with_receipt((
        ActionEconomyChannelCost(cost_type="movement", amount=5, name="first"),
        ActionEconomyChannelCost(cost_type="movement", amount=10, name="second"),
        ActionEconomyChannelCost(cost_type="bonus_actions", amount=1, name="jump"),
    ))

    assert economy.movement.normalized_score == 15
    assert economy.bonus_actions.normalized_score == 0
    assert len(receipt.handles) == 2
    economy.undo_prevalidated_debit(receipt)
    assert economy.movement.normalized_score == 30
    assert economy.bonus_actions.normalized_score == 1
    with pytest.raises(ValueError, match="no longer names exact installed state"):
        economy.undo_prevalidated_debit(receipt)


def test_aggregate_affordability_fails_before_any_channel_is_debited() -> None:
    """The complete aggregate is admitted before its first mutation."""
    reset_core_action_state()
    economy = strong_entity("Poor", (1, 1), "heroes").action_economy
    before = tuple(economy.actions.self_static.value_modifiers)

    with pytest.raises(ValueError, match="Not enough actions"):
        economy.consume_aggregate_with_receipt((
            ActionEconomyChannelCost(cost_type="actions", amount=1),
            ActionEconomyChannelCost(cost_type="actions", amount=1),
        ))

    assert tuple(economy.actions.self_static.value_modifiers) == before


@pytest.mark.parametrize("raise_after_insert", (False, True))
def test_aggregate_install_failure_removes_all_owned_modifier_state(
    monkeypatch: pytest.MonkeyPatch,
    raise_after_insert: bool,
) -> None:
    """Failure before or after insertion cannot leave a partial channel debit."""
    reset_core_action_state()
    economy = strong_entity("Atomic Debtor", (1, 1), "heroes").action_economy
    before_registry = set(NumericalModifier._registry)
    original_add = StaticValue.add_value_modifier
    calls = 0

    def fail_second(value: StaticValue, modifier: NumericalModifier) -> UUID:
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


def test_fixed_resource_failure_restores_resources_and_channel_debits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A compound fixed-cost failure restores every state owned by the call."""
    reset_core_action_state()
    economy = strong_entity("Atomic Resources", (1, 1), "heroes").action_economy
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
    with pytest.raises(FixedCostCommitError, match="fixed resource costs"):
        economy.commit_fixed_costs_without_dispatch(
            channel_costs=(
                ActionEconomyChannelCost(cost_type="bonus_actions", amount=1),
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
    """Undo validates the entire typed receipt before touching live state."""
    reset_core_action_state()
    economy = strong_entity("Receipt Owner", (1, 1), "heroes").action_economy
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
    forged_receipt = ActionEconomyDebitReceipt.model_construct(
        owner_uuid=receipt.owner_uuid,
        handles=(forged_handle,),
    )

    with pytest.raises(TypeError, match="malformed typed evidence"):
        economy.undo_prevalidated_debit(forged_receipt)

    assert economy.bonus_actions.normalized_score == 0
    assert unrelated.uuid in economy.movement.self_static.value_modifiers
