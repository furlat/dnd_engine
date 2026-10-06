"""Pure selection intents consume complete native-prefix previews."""

from dataclasses import dataclass, replace

from dnd.core.base_actions import AvailableActionInfo, AvailableTarget, AvailableSelectionPreview


@dataclass(frozen=True, slots=True)
class MenuState:
    selected_action: int = 0
    active: bool = False
    selected_targets: tuple[int, ...] = ()
    selected_positions: tuple[tuple[int, int], ...] = ()
    status: str = ""
    target_cursor: int = 0


@dataclass(frozen=True, slots=True)
class ActionSelection:
    action_index: int
    target_indices: tuple[int, ...]
    extra_target_positions: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class EndTurn:
    pass


def selection_target_pool(action: AvailableActionInfo, selected: tuple[int, ...]) -> list[AvailableTarget]:
    if selected:
        primary = next((target for target in action.valid_targets if target.index == selected[0]), None)
        if primary is not None and primary.secondary_targets is not None:
            return [primary, *primary.secondary_targets]
    return action.valid_targets



def begin_targeting(index: int) -> MenuState:
    return MenuState(selected_action=index, active=True)


def targeting_values(state: MenuState, action: AvailableActionInfo) -> tuple[AvailableTarget,...]:
    pool=selection_target_pool(action,state.selected_targets)
    by_index={target.index:target for target in pool}
    return tuple(by_index[index] for index in state.selected_targets)


def append_target(state: MenuState, preview: AvailableSelectionPreview, index: int) -> MenuState:
    if not state.active or not any(target.index==index for target in preview.next_targets):
        return replace(state,status=preview.reason or 'This target is not admitted')
    return replace(state,selected_targets=(*state.selected_targets,index),status='')


def append_position(state: MenuState, preview: AvailableSelectionPreview, position: tuple[int,int]) -> MenuState:
    if not state.active or position not in preview.next_positions:
        return replace(state,status=preview.reason or 'This position is not admitted')
    return replace(state,selected_positions=(*state.selected_positions,position),status='')


def undo_targeting(state: MenuState) -> MenuState:
    if state.selected_positions:
        return replace(state,selected_positions=state.selected_positions[:-1],status='')
    return replace(state,selected_targets=state.selected_targets[:-1],status='')


def confirm_targeting(state: MenuState, preview: AvailableSelectionPreview) -> ActionSelection | None:
    if not state.active or not preview.can_confirm or not state.selected_targets:
        return None
    return ActionSelection(state.selected_action,state.selected_targets,state.selected_positions)
