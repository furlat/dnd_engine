"""Typed external-assistance removal contracts for control conditions."""

from dnd.actions.operations import setup_standard_actions
from dnd.types.conditions import ConditionRemovalTrigger
from dnd.entities.entity import Entity
from dnd.spells.enchantment import SleepEffect
from dnd.spells.illusion import HypnoticPatternEffect
from dnd.spells.necromancy import EyebiteAsleepEffect
from tests.engine.test_combat_actions import (
    reset_core_action_state,
    strong_entity,
)


def test_shake_awake_uses_typed_removal_capability_for_every_supported_effect() -> None:
    """Shake Awake discovers Hypnotic Pattern without concrete-name coupling."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    helper = strong_entity("Helper", (2, 2), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    setup_standard_actions(helper)
    Entity.materialize_all_navigation(max_distance=80)

    supported_effects = (
        SleepEffect,
        HypnoticPatternEffect,
        EyebiteAsleepEffect,
    )
    for effect_type in supported_effects:
        effect = effect_type(
            source_entity_uuid=source.uuid,
            target_entity_uuid=target.uuid,
        )
        applied = target.add_condition(effect)

        assert applied is not None
        assert ConditionRemovalTrigger.SHAKE_AWAKE in effect.removal_triggers

        action_info = next(
            action
            for action in helper.get_available_actions().entity_actions
            if action.template_name == "Shake Awake"
        )
        assert [candidate.target_uuid for candidate in action_info.valid_targets] == [
            target.uuid
        ]

        template = helper.get_action_template("Shake Awake")
        assert template is not None
        completion = template.instantiate(target_entity_uuid=target.uuid).apply()

        assert completion is not None
        assert completion.canceled is False
        assert effect.uuid not in target.active_conditions_by_uuid
        helper.action_economy.reset_all_costs()
