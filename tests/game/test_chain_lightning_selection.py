"""The human uses the same primary-dependent choices admitted by the engine."""
from dataclasses import replace

import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from game.controls import ActionSelection, MenuState, handle_menu_event, selection_target_pool
from game.projection import Camera
from tests.engine.test_chain_lightning_selection import scene as scene


@pytest.mark.parametrize("branches", [False, True])
def test_primary_dependent_choices_and_partial_confirmation_are_one_cast(scene, branches):
    caster, (primary, secondary, _, _) = scene
    choices = get_available_actions(caster)
    index, row = next((i, row) for i, row in enumerate(choices.all_actions)
                     if row.behavior_id == "spell.chain_lightning" and row.cast_at_level == 6)
    target = next(option for option in row.valid_targets if option.target_uuid == primary.uuid)
    state = MenuState(selected_action=index, target_cursor=row.valid_targets.index(target))
    camera = Camera(viewport=(960, 640))
    panel = pygame.Rect(750, 0, 210, 640)
    cursor = EventQueue.event_cursor()

    def key(value):
        nonlocal state
        state, command = handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=value),
            choices, camera, (), panel_rect=panel)
        return command

    assert key(pygame.K_RETURN) is None
    assert state.selected_targets == (target.index,)
    assert key(pygame.K_BACKSPACE) is None
    assert state.selected_targets == ()
    state = replace(state, target_cursor=row.valid_targets.index(target))
    assert key(pygame.K_RETURN) is None
    if branches:
        assert target.secondary_targets is not None
        branch = next(option for option in target.secondary_targets if option.target_uuid == secondary.uuid)
        state = replace(state, target_cursor=target.secondary_targets.index(branch))
        assert key(pygame.K_RETURN) is None
    command = key(pygame.K_SPACE)
    assert isinstance(command, ActionSelection)
    assert not state.selected_targets and EventQueue.event_cursor() == cursor
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
