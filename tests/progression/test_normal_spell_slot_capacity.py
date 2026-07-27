"""Focused regressions for the one shared normal spell-slot capacity."""

from typing import cast
from uuid import uuid4

import pytest

from dnd.blocks.action_economy import ActionEconomy, ActionEconomyConfig


def test_normal_slot_capacity_sets_all_ranks_without_touching_turn_resources() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    economy.consume("actions", 1, "before_slot_rebuild")
    source_id = uuid4()

    receipt = economy.set_normal_spell_slot_capacity(
        source_id,
        {1: 4, 2: 3, 3: 2},
    )

    assert receipt.source_id == source_id
    assert receipt.capacities == ((1, 4), (2, 3), (3, 2))
    assert len(receipt.capacity_modifier_uuids) == 9
    assert economy.get_normal_spell_slot_capacity_source() == source_id
    assert economy.get_normal_spell_slot_capacities() == {1: 4, 2: 3, 3: 2}
    assert [
        economy._get_spell_slot_value(rank).normalized_score
        for rank in range(1, 10)
    ] == [4, 3, 2, 0, 0, 0, 0, 0, 0]
    assert economy.actions.normalized_score == 0


def test_replacing_capacity_preserves_spend_across_raise_and_lower() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    first = economy.set_normal_spell_slot_capacity(uuid4(), {1: 4, 2: 2})
    economy.consume("spell_slot_1", 2, "two_casts")
    economy.consume("spell_slot_2", 1, "one_cast")

    second = economy.set_normal_spell_slot_capacity(uuid4(), {1: 1, 2: 1})

    assert second.source_id != first.source_id
    assert economy.spell_slot_1.normalized_score == 0
    assert economy.spell_slot_2.normalized_score == 0
    for rank, modifier_uuid in first.capacity_modifier_uuids:
        assert (
            modifier_uuid
            not in economy._get_spell_slot_value(rank).self_static.value_modifiers
        )

    economy.set_normal_spell_slot_capacity(uuid4(), {1: 5, 2: 3})

    assert economy.spell_slot_1.normalized_score == 3
    assert economy.spell_slot_2.normalized_score == 2


def test_remove_restores_legacy_capacity_and_clamps_availability_at_zero() -> None:
    economy = ActionEconomy.create(
        source_entity_uuid=uuid4(),
        config=ActionEconomyConfig(spell_slots={1: 1}),
    )
    source_id = uuid4()
    economy.set_normal_spell_slot_capacity(source_id, {1: 4})
    economy.consume("spell_slot_1", 2, "casts_above_legacy_capacity")

    assert not economy.remove_normal_spell_slot_capacity(uuid4())
    assert economy.get_normal_spell_slot_capacity_source() == source_id
    assert economy.remove_normal_spell_slot_capacity(source_id)

    assert economy.get_normal_spell_slot_capacity_source() is None
    assert economy.spell_slot_1.normalized_score == 0
    assert not economy.remove_normal_spell_slot_capacity(source_id)


def test_same_source_is_idempotent_but_cannot_be_reused_for_another_contract() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    source_id = uuid4()
    first = economy.set_normal_spell_slot_capacity(source_id, {2: 2, 1: 4})

    second = economy.set_normal_spell_slot_capacity(source_id, {1: 4, 2: 2})

    assert second is first
    with pytest.raises(
        ValueError,
        match="already owns a different normal spell-slot capacity",
    ):
        economy.set_normal_spell_slot_capacity(source_id, {1: 3, 2: 2})


@pytest.mark.parametrize(
    "capacities",
    [
        {0: 1},
        {10: 1},
        {True: 1},
        {"1": 1},
        {1: -1},
        {1: True},
        {1: 1.5},
    ],
)
def test_normal_slot_capacity_rejects_invalid_ranks_and_counts(
    capacities: dict[object, object],
) -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())

    with pytest.raises(ValueError, match="normal spell-slot"):
        economy.set_normal_spell_slot_capacity(
            uuid4(),
            cast(dict[int, int], capacities),
        )


def test_long_rest_cost_reset_restores_current_structural_capacity() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    economy.set_normal_spell_slot_capacity(uuid4(), {1: 4, 2: 2})
    economy.consume("spell_slot_1", 3, "casts")
    economy.consume("spell_slot_2", 2, "casts")

    economy.reset_spell_slot_costs()

    assert economy.spell_slot_1.normalized_score == 4
    assert economy.spell_slot_2.normalized_score == 2
