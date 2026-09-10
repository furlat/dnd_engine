"""Actual discovery rows become UI selections without executing mechanics."""

import random
from dataclasses import replace

import pygame
import pytest

from dnd.core.base_actions import TargetType
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.world_authoring import project_world_tile
from game.controls import ActionSelection, EndTurn, MenuState, draw_target_preview, handle_menu_event
from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH, project_screen
from game.session import advance_controller, close_session, create_session, discover_player_actions


PANEL = pygame.Rect(700, 0, 260, 640)


@pytest.fixture(scope="module")
def menu_scene():
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        for _ in range(32):
            operation = advance_controller(session)
            if operation.boundary is not None and operation.boundary.status == "waiting_for_human":
                break
        actor = session.encounter.get_current_entity()
        assert actor is not None
        actions = discover_player_actions(session, actor.uuid)
        tiles = tuple(project_world_tile(tile) for position, tile in get_map().get_all_tiles().items()
                      if actor.senses.visible.get(position, False))
        camera = Camera(zoom=0.75, viewport=(960, 640)).with_focus(actor.position)
        yield actions, camera, tiles
    finally:
        close_session(session)
        random.setstate(random_state)


def _press(state, key, scene):
    actions, camera, tiles = scene
    return handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=key),
                             actions, camera, tiles, panel_rect=PANEL)


def test_tab_and_enter_preserve_a_b_a_allocation_from_real_discovery(menu_scene) -> None:
    actions, _, _ = menu_scene
    index = next(index for index, row in enumerate(actions.all_actions)
                 if row.target_type is TargetType.MULTI_ENTITY and row.num_projectiles == 3
                 and row.allow_same_target is not False)
    row = actions.all_actions[index]
    first, second = row.valid_targets
    state = MenuState(selected_action=index)
    before = EventQueue.event_cursor()
    state, command = _press(state, pygame.K_RETURN, menu_scene)
    assert command is None and state.selected_targets == (first.index,)
    state, _ = _press(state, pygame.K_TAB, menu_scene)
    state, command = _press(state, pygame.K_RETURN, menu_scene)
    assert command is None and state.selected_targets == (first.index, second.index)
    state, _ = _press(state, pygame.K_TAB, menu_scene)
    state, command = _press(state, pygame.K_RETURN, menu_scene)
    assert command == ActionSelection(index, (first.index, second.index, first.index))
    assert state.selected_targets == ()
    assert EventQueue.event_cursor() == before


def test_panel_wheel_scrolls_without_changing_the_selected_action_or_allocation(menu_scene, monkeypatch) -> None:
    actions, camera, tiles = menu_scene
    state = MenuState(selected_action=6, selected_targets=(0, 1), target_cursor=1)
    wheel = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
    # Mouse position is the SDL input boundary; discovered actions stay real.
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: PANEL.center)
    scrolled, command = handle_menu_event(state, wheel, actions, camera, tiles, panel_rect=PANEL)
    assert command is None and scrolled == replace(state, scroll=3)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    unchanged, command = handle_menu_event(state, wheel, actions, camera, tiles, panel_rect=PANEL)
    assert command is None and unchanged == state


@pytest.mark.parametrize("quadrant", range(4))
def test_target_preview_uses_disclosed_positions_allocation_and_visible_area(menu_scene, quadrant) -> None:
    actions, _, tiles = menu_scene
    index = next(index for index, row in enumerate(actions.all_actions)
                 if row.target_type is TargetType.MULTI_ENTITY and row.num_projectiles == 3
                 and row.allow_same_target is not False)
    first, second = actions.all_actions[index].valid_targets
    assert first.position is not None and second.position is not None
    camera = Camera(quadrant=quadrant, zoom=0.75, viewport=(960, 640)).with_focus(first.position)
    state = MenuState(selected_action=index, selected_targets=(first.index, second.index, first.index))
    pygame.font.init()
    image = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    before = EventQueue.event_cursor()
    draw_target_preview(image, state, actions, camera, tiles)
    x, y = project_screen(second.position, camera)
    edge = round(x + TILE_WIDTH * camera.zoom / 2), round(y)
    assert image.get_at(edge).a > 0
    hidden = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(hidden, state, actions, camera, (tile for tile in tiles if tile.position != second.position))
    assert hidden.get_at(edge).a == 0

    single = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(single, replace(state, selected_targets=(first.index, second.index)), actions, camera, tiles)
    x, y = project_screen(first.position, camera)
    badge = pygame.Rect(round(x + TILE_WIDTH * camera.zoom * 0.275) - 8,
                        round(y - TILE_HEIGHT * camera.zoom * 0.275) - 8, 16, 16)
    assert pygame.image.tobytes(image.subsurface(badge), "RGBA") != pygame.image.tobytes(single.subsurface(badge), "RGBA")

    area_index, area_cursor, target = next(
        (i, j, target) for i, row in enumerate(actions.all_actions) for j, target in enumerate(row.valid_targets)
        if target.affected_positions and any(position != target.position for position in target.affected_positions)
    )
    affected = next(position for position in target.affected_positions or () if position != target.position)
    support = next(tile for tile in tiles if tile.position == affected)
    camera = camera.with_focus(affected, elevation_steps=support.elevation_steps)
    area = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(area, MenuState(selected_action=area_index, target_cursor=area_cursor), actions, camera, (support,))
    x, y = project_screen(affected, camera, elevation_steps=support.elevation_steps)
    assert area.get_at((round(x + TILE_WIDTH * camera.zoom / 2), round(y))).a > 0
    disabled = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(disabled, state, None, camera, tiles)
    assert pygame.mask.from_surface(disabled).count() == 0
    assert EventQueue.event_cursor() == before


def test_unique_target_rule_and_clear_use_the_disclosed_allocation(menu_scene) -> None:
    actions, _, _ = menu_scene
    index = next(index for index, row in enumerate(actions.all_actions)
                 if row.target_type is TargetType.MULTI_ENTITY and row.num_projectiles == 2
                 and row.allow_same_target is False)
    first, second = actions.all_actions[index].valid_targets
    state, _ = _press(MenuState(selected_action=index), pygame.K_RETURN, menu_scene)
    state, command = _press(state, pygame.K_RETURN, menu_scene)
    assert command is None and state.selected_targets == (first.index,)
    assert state.status == "Choose a different target."
    state, _ = _press(state, pygame.K_TAB, menu_scene)
    state, command = _press(state, pygame.K_RETURN, menu_scene)
    assert command == ActionSelection(index, (first.index, second.index))
    state, _ = _press(state, pygame.K_RETURN, menu_scene)
    state, command = _press(state, pygame.K_BACKSPACE, menu_scene)
    assert command is None and state.selected_targets == ()


def test_map_target_and_human_boundary_gate_return_only_selection_commands(menu_scene) -> None:
    actions, camera, tiles = menu_scene
    index = next(index for index, row in enumerate(actions.all_actions) if row.behavior_id == "action.move")
    target = min(actions.all_actions[index].valid_targets, key=lambda row: row.path_cost or 0)
    assert target.position is not None
    position = project_screen(target.position, camera)
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position)
    before = EventQueue.event_cursor()
    state, command = handle_menu_event(MenuState(selected_action=index), click, actions, camera, tiles, panel_rect=PANEL)
    assert command == ActionSelection(index, (target.index,))

    unavailable = next(index for index, row in enumerate(actions.all_actions) if not row.valid_targets)
    state, command = _press(MenuState(selected_action=unavailable), pygame.K_RETURN, menu_scene)
    assert command is None
    assert state.status == actions.all_actions[unavailable].availability_status.value.replace("_", " ")
    for event in (click, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n)):
        unchanged, command = handle_menu_event(state, event, None, camera, tiles, panel_rect=PANEL)
        assert unchanged == state and command is None
    _, command = _press(state, pygame.K_n, menu_scene)
    assert command == EndTurn()
    state, _ = _press(MenuState(selected_targets=(target.index,)), pygame.K_DOWN, menu_scene)
    assert state.selected_action == 1 and state.selected_targets == ()
    assert EventQueue.event_cursor() == before
