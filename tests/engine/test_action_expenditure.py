"""Expenditure describes the resource actually used by a discovered action."""

from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.core.base_actions import ActionEvent
from dnd.core.events import EventPhase
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import Haste
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


def test_haste_named_action_expenditure_is_recorded_after_ordinary_action_is_spent() -> None:
    reset_spell_regression_arena(8, 8)
    try:
        actor = create_spell_regression_actor("Hasted runner", (3, 3), "heroes")
        caster = create_spell_regression_actor("Ally", (2, 3), "heroes", spell_slots={3: 1})
        setup_standard_actions(actor)
        Entity.update_all_entities_senses()
        cast = Haste(source_entity_uuid=caster.uuid, target_entity_uuid=actor.uuid).apply()
        assert cast is not None and cast.phase is EventPhase.COMPLETION, cast.status_message if cast else None
        ordinary = next(row for row in get_available_actions(actor, legal_only=True).all_actions
                        if row.template_name == "Dodge")
        dodge = execute_available_action(actor, ordinary, ordinary.valid_targets[0])
        assert dodge is not None and dodge.phase is EventPhase.COMPLETION
        assert actor.action_economy.actions.normalized_score == 0
        assert actor.action_economy.resources["haste_action"].current == 1
        action = next(row for row in get_available_actions(actor, legal_only=True).all_actions
                      if row.template_name == "Dash__grant_haste")
        movement = actor.action_economy.movement.normalized_score
        result = execute_available_action(actor, action, action.valid_targets[0])
        assert isinstance(result, ActionEvent) and result.phase is EventPhase.COMPLETION
        assert result.action_economy_spent
        assert all(cost.cost == 0 for cost in result.costs)
        assert any(cost.resource_name == "haste_action" and cost.resource_cost == 1 for cost in result.costs)
        assert actor.action_economy.actions.normalized_score == 0
        assert actor.action_economy.resources["haste_action"].current == 0
        assert actor.action_economy.movement.normalized_score > movement
    finally:
        reset_engine_runtime()
