"""Pure pose selection for received environment state and finite transitions."""

from dnd.core.item_types import ItemRemnantState
from game.environment_art import (
    EnvironmentArt, EnvironmentBank, EnvironmentDoorArt, EnvironmentTrapArt,
    sample_environment_frame, select_environment_destruction,
)
from game.world_animation import WorldTransitionSample


def remnant_bank(art: EnvironmentArt, item_id: str,
                  state: ItemRemnantState | None, *, outcome: str | None = None) -> EnvironmentBank | None:
    return select_environment_destruction(art, item_id, door_open=state.door_open if state is not None else None,
        swing=state.door_swing.value if state is not None and state.door_swing is not None else None,
        mechanism_state=state.mechanism_state.value if state is not None and state.mechanism_state is not None else None,
        outcome=outcome)


def door_pose(art: EnvironmentDoorArt, swing: str, is_open: bool,
              transition: WorldTransitionSample | None) -> tuple[EnvironmentBank, int]:
    bank = art.openings[swing]
    if transition is None:
        return bank, bank.frame_count - 1 if is_open else 0
    if transition.elapsed_ms < 0:
        return bank, bank.frame_count - 1 if transition.transition.previous == "true" else 0
    return bank, sample_environment_frame(bank, transition.elapsed_ms,
        reverse=transition.transition.current == "false")


def trap_pose(art: EnvironmentTrapArt, state: str,
              transition: WorldTransitionSample | None) -> tuple[EnvironmentBank, int]:
    if transition is not None and transition.transition.field == "activation":
        frame = sample_environment_frame(art.intact, transition.elapsed_ms)
        if state == "activated":
            frame = min(frame, art.state_frames[state])
        return art.intact, frame
    return art.intact, art.state_frames[state]
