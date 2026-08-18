"""Typed projection for the human-client available-actions API."""

from dnd.core.base_actions import AvailableActionsResult
from dnd.entities.entity import Entity
from server.api_models import (
    APIAvailableActions,
    APIResourcePool,
    ActionExecutionAuthorization,
)


def serialize_available_actions(
    entity: Entity,
    actions: AvailableActionsResult,
    *,
    execution_authorization: ActionExecutionAuthorization,
) -> APIAvailableActions:
    """Attach current resources to the engine's typed action-discovery result.

    Args:
        entity: Entity whose resources are summarized.
        actions: Canonical engine-discovered legal actions.
        execution_authorization: Independent session/turn command authority.

    Returns:
        Typed action response preserving every engine action and target field.
    """
    action_economy = entity.action_economy
    spell_slots: dict[str, APIResourcePool] = {}
    if entity.is_spellcaster:
        for level in range(1, 10):
            slot = action_economy.spell_slot_value(level)
            base_modifier = slot.get_base_modifier()
            maximum = base_modifier.value if base_modifier else 0
            if maximum > 0:
                spell_slots[str(level)] = APIResourcePool(
                    current=slot.normalized_score,
                    max=maximum,
                )

    resources = {
        name: APIResourcePool(current=resource.current, max=resource.maximum)
        for name, resource in action_economy.resources.items()
        if name != "extra_attacks"
    }
    action_fields = {
        name: getattr(actions, name)
        for name in AvailableActionsResult.model_fields
    }
    return APIAvailableActions.model_construct(
        **action_fields,
        execution_authorization=execution_authorization,
        actions_remaining=action_economy.actions.normalized_score,
        bonus_actions_remaining=action_economy.bonus_actions.normalized_score,
        reactions_remaining=action_economy.reactions.normalized_score,
        extra_attacks_remaining=action_economy.get_resource_current("extra_attacks"),
        spell_slots=spell_slots,
        resources=resources,
    )
