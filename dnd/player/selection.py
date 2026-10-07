"""Ordered target selection over native discovery values."""

from dnd.core.base_actions import AvailableActionInfo, AvailableTarget


def selection_target_pool(action: AvailableActionInfo, selected: tuple[int, ...]) -> list[AvailableTarget]:
    if selected:
        primary = next((target for target in action.valid_targets if target.index == selected[0]), None)
        if primary is not None and primary.secondary_targets is not None:
            return [primary, *primary.secondary_targets]
    return action.valid_targets

