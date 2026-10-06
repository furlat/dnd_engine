"""Exact scene identities resolve to already discovered native actions."""

from uuid import UUID

from dnd.core.base_actions import AvailableActionsResult, AvailableTarget, AvailableWorldInteraction, prefers_safe_movement_path
from dnd.types.world import MovementMode
from game.controls import ActionSelection
from game.interaction_types import WorldHit


def world_options(actions: AvailableActionsResult, hit: WorldHit) -> tuple[AvailableWorldInteraction, ...]:
    return tuple(sorted((option for option in actions.world_interactions
        if str(option.subject_uuid) == hit.identity), key=lambda option: option.default_priority))


def admitted_world_actions(actions: AvailableActionsResult, option: AvailableWorldInteraction) -> tuple[ActionSelection, ...]:
    selections = []
    for index, row in enumerate(actions.all_actions):
        if (row.interaction_affordance.surface != 'world' or row.behavior_id != option.behavior_id
                or option.template_name is not None and row.template_name != option.template_name
                or row.configured_action_ref != option.configured_action_ref or row.variant_facets != option.variant_facets):
            continue
        if option.connector_uuid is not None:
            if row.connector_traversal is None or row.connector_traversal.command.connector_uuid != option.connector_uuid:
                continue
            selections.extend(ActionSelection(index, (target.index,)) for target in row.valid_targets)
        elif row.interaction_affordance.binding == 'source_item':
            if row.source_item_uuid == option.subject_uuid:
                selections.extend(ActionSelection(index, (target.index,)) for target in row.valid_targets)
        else:
            selections.extend(ActionSelection(index, (target.index,)) for target in row.valid_targets
                if target.target_uuid == option.subject_uuid)
    return tuple(selections)


def approach_action(actions: AvailableActionsResult, option: AvailableWorldInteraction,
                    movement_mode: MovementMode = MovementMode.WALKING) -> tuple[ActionSelection, AvailableTarget] | None:
    admitted = [(ActionSelection(index, (target.index,)), target)
        for index, row in enumerate(actions.all_actions) if row.behavior_id == 'action.move'
        and any(facet.key=='movement' and facet.value==movement_mode.value for facet in row.variant_facets)
        for target in row.valid_targets if target.position in option.contact_positions]
    safe = [(selection, target) for selection, target in admitted
            if prefers_safe_movement_path(target, actions.remaining_movement) or not target.is_path_hazardous]
    # UI never silently selects a hazardous approach, Dashes or spends a bonus.
    return min(safe, key=lambda pair: (pair[1].safe_path_cost if prefers_safe_movement_path(pair[1], actions.remaining_movement)
                                    else pair[1].path_cost) or 0) if safe else None


def main_attack(actions: AvailableActionsResult, subject_uuid: UUID,
                preference: str = 'MELEE_MAIN') -> ActionSelection | None:
    rows = [(index, row) for index, row in enumerate(actions.all_actions)
        if row.is_attack and row.weapon_slot in ('MELEE_MAIN','RANGED_MAIN')
        and not any(cost.cost_type in ('bonus_actions','reactions') for cost in row.costs)]
    rows.sort(key=lambda pair: pair[1].weapon_slot != preference)
    for index, row in rows:
        target = next((target for target in row.valid_targets if target.target_uuid == subject_uuid), None)
        if target is not None:
            return ActionSelection(index, (target.index,))
    return None


def move_to(actions: AvailableActionsResult, position: tuple[int, int],
            movement_mode: MovementMode = MovementMode.WALKING) -> ActionSelection | None:
    return next((ActionSelection(index, (target.index,))
        for index, row in enumerate(actions.all_actions) if row.behavior_id == 'action.move'
        and any(facet.key=='movement' and facet.value==movement_mode.value for facet in row.variant_facets)
        for target in row.valid_targets if target.position == position), None)


def target_at(options: tuple[AvailableTarget, ...], hit: WorldHit) -> AvailableTarget | None:
    if hit.kind in ('actor','object'):
        exact = next((target for target in options if target.target_uuid is not None and str(target.target_uuid) == hit.identity), None)
        if exact is not None:
            return exact
    return next((target for target in options if target.target_uuid is None and target.position == hit.position), None)
