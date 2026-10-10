"""The human uses the same primary-dependent choices admitted by the engine."""
from dataclasses import replace

import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from game.controls import ActionSelection, confirm_targeting, undo_targeting, selection_target_pool
from tests.game.ui_selection_helpers import selected_prefix
from game.projection import Camera
from tests.engine.test_chain_lightning_selection import scene as scene


@pytest.mark.parametrize("branches", [False, True])
def test_primary_dependent_choices_and_partial_confirmation_are_one_cast(scene, branches):
    caster, (primary, secondary, _, _) = scene
    choices = get_available_actions(caster)
    index, row = next((i, row) for i, row in enumerate(choices.all_actions)
                     if row.behavior_id == "spell.chain_lightning" and row.cast_at_level == 6)
    target = next(option for option in row.valid_targets if option.target_uuid == primary.uuid)
    cursor = EventQueue.event_cursor()
    state, preview = selected_prefix(caster,row,index,(target,))
    assert state.selected_targets == (target.index,)
    state = undo_targeting(state)
    assert state.selected_targets == ()
    selected = (target,)
    if branches:
        assert target.secondary_targets is not None
        branch = next(option for option in target.secondary_targets if option.target_uuid == secondary.uuid)
        selected += (branch,)
    state, preview = selected_prefix(caster,row,index,selected)
    command = confirm_targeting(state,preview)
    assert isinstance(command, ActionSelection) and EventQueue.event_cursor() == cursor
    pool = selection_target_pool(row, command.target_indices)
    selected = [next(option for option in pool if option.index == selected_index)
                for selected_index in command.target_indices]
    assert [option.target_uuid for option in selected] == ([primary.uuid, secondary.uuid] if branches else [primary.uuid])
    with fixed_dice_faces(*([2] * 100)):
        result = execute_available_action(caster, row, selected[0],
            extra_target_uuids=[str(option.target_uuid) for option in selected[1:]])
    assert result is not None and not result.canceled
    assert caster.action_economy.spell_slot_6.normalized_score == 1
    assert primary.get_normal_hp() == 220
    assert secondary.get_normal_hp() == (220 if branches else 240)
