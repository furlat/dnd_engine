"""Maintained direct-item behavior proof for Neurodragon consumables."""

from uuid import uuid4

from dnd.actions_functional import execute_use_action
from dnd.core.creature_types import DamageType
from dnd.entity import Entity
from dnd.items.consumables import (
    HEALING_POTION_DRINK_SEMANTIC_KEY,
    build_healing_potion,
)
from dnd.runtime_reset import reset_engine_runtime


def test_healing_potion_keeps_healing_cost_and_consumption_behavior() -> None:
    """The direct item heals, spends a bonus action, and is consumed."""
    reset_engine_runtime(grid_size=(4, 3))
    actor = Entity.create(source_entity_uuid=uuid4(), name="Potion tester")
    potion = build_healing_potion(actor.uuid, heal_amount=4)
    assert actor.loot_item(potion)
    assert actor.receive_damage(
        4,
        DamageType.SLASHING,
        actor.uuid,
    ) == 4
    before_bonus_actions = actor.action_economy.bonus_actions.normalized_score

    action = potion.get_use_actions(actor.uuid)[0]
    assert action.get_semantic_key() == HEALING_POTION_DRINK_SEMANTIC_KEY
    assert action.get_fixed_healing(actor) == 4
    assert tuple(
        (cost.cost_type, cost.cost)
        for cost in action.costs
    ) == (("bonus_actions", 1),)

    completion = execute_use_action(actor, potion.uuid, "Drink Potion")

    assert completion is not None and not completion.canceled
    assert actor.get_hp() == actor.get_max_hp()
    assert (
        actor.action_economy.bonus_actions.normalized_score
        == before_bonus_actions - 1
    )
    assert potion.uuid not in actor.inventory.items
