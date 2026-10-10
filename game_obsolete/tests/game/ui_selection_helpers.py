"""Submit an explicit prefix through the native preview and shared UI reducer."""

from dnd.actions_functional import preview_available_selection
from dnd.core.base_actions import AvailableActionInfo, AvailableTarget
from dnd.entity import Entity
from game.controls import begin_targeting, targeting_values, append_target, append_position


def selected_prefix(actor: Entity, row: AvailableActionInfo, index: int,
                    targets: tuple[AvailableTarget,...], positions: tuple[tuple[int,int],...] = ()):
    state=begin_targeting(index)
    preview=preview_available_selection(actor,row)
    for target in targets:
        state=append_target(state,preview,target.index)
        preview=preview_available_selection(actor,row,targeting_values(state,row),state.selected_positions)
    for point in positions:
        state=append_position(state,preview,point)
        preview=preview_available_selection(actor,row,targeting_values(state,row),state.selected_positions)
    return state,preview
