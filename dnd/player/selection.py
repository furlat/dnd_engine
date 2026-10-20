"""Ordered target selection over native discovery values."""

from dnd.core.base_actions import AvailableActionInfo, AvailableTarget
from dnd.actions_functional import secondary_candidates
from dnd.entity import Entity


def selection_target_pool(actor: Entity, action: AvailableActionInfo,
                          selected: tuple[int, ...]) -> list[AvailableTarget]:
    if selected:
        primary = next((target for target in action.valid_targets if target.index == selected[0]), None)
        if primary is not None and primary.secondary_targets is not None:
            return [primary, *primary.secondary_targets]
        if primary is not None and len(selected) > 1:
            return secondary_candidates(actor, action, actor.action_scan(subjective=True))
    return action.valid_targets

