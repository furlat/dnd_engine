"""Human and AI ordered points execute the same discovered native wall."""

import pygame
import pytest
from dataclasses import replace
from pydantic import ValidationError

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_extra_position_options, register_spell
from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.decision import ExecuteIntent
from dnd.ai.instrumentation import AIInstrumentation, AIInstrumentationContext
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.runtime.execution import AIDecisionValidationError, resolve_policy_intent, validate_policy_intent
from dnd.ai.runtime.state_projection import SubjectiveAIStateProjector
from dnd.controller import TurnContext
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.walls import WallOfFire, WallOfFireZone
from dnd.world_authoring import project_world_tile
from game.controls import ActionSelection, MenuState, draw_target_preview, handle_menu_event
from game.projection import Camera, project_screen
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


PANEL = pygame.Rect(750, 0, 210, 640)


@pytest.fixture
def wall_scene():
    reset_spell_regression_arena(12, 12)
    caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={4: 2})
    register_spell(caster, WallOfFire)
    Entity.update_all_entities_senses()
    available = caster.get_available_actions()
    index, row = next((i, row) for i, row in enumerate(available.all_actions)
                      if "segment, heat left" in row.display_name)
    first = next(target for target in row.valid_targets if target.position == (4, 4))
    tiles = tuple(project_world_tile(tile) for position, tile in get_map().get_all_tiles().items()
                  if caster.senses.visible.get(position, False))
    camera = Camera(zoom=.75, viewport=(960, 640)).with_focus((6, 6))
    yield caster, available, index, row, first, tiles, camera
    reset_spell_regression_arena(1, 1)


def test_clicks_undo_and_confirm_preserve_explicit_endpoints(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    before = EventQueue.event_cursor()
    state = MenuState(selected_action=index)

    def input_event(event, options=()):
        nonlocal state
        state, command = handle_menu_event(state, event, available, camera, tiles,
                                           panel_rect=PANEL, next_position_options=options)
        return command

    def click(position, options=()):
        return input_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                             pos=project_screen(position, camera)), options)

    assert click(first.position) is None
    assert state.selected_positions == ((4, 4),)
    admitted = tuple(get_extra_position_options(caster, row, first))
    assert (8, 4) in admitted
    assert click((4, 4), admitted) is None
    assert state.selected_positions == ((4, 4),)
    assert click((8, 4), admitted) is None
    assert state.selected_positions == ((4, 4), (8, 4))
    assert input_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)) is None
    assert state.selected_positions == ((4, 4),)
    assert click((8, 4), admitted) is None
    command = input_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert command == ActionSelection(index, (first.index,), ((8, 4),))
    assert not state.selected_positions and EventQueue.event_cursor() == before
    result = execute_available_action(caster, row, first, extra_target_positions=list(command.extra_target_positions))
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.area_geometry.path.start == (4, 4) and result.area_geometry.path.end == (8, 4)


def test_keyboard_shorthand_and_action_change_clear_the_path(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    cursor = row.valid_targets.index(first)
    state = MenuState(selected_action=index, target_cursor=cursor)

    def press(key):
        nonlocal state
        state, command = handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=key),
                                           available, camera, tiles, panel_rect=PANEL)
        return command

    assert press(pygame.K_RETURN) is None
    assert state.selected_positions == ((4, 4),)
    assert press(pygame.K_DOWN) is None
    assert not state.selected_positions
    state = MenuState(selected_action=index, target_cursor=cursor)
    assert press(pygame.K_RETURN) is None
    command = press(pygame.K_RETURN)
    assert command == ActionSelection(index, (first.index,))
    result = execute_available_action(caster, row, first)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.area_geometry.path.start != caster.position
    assert result.area_geometry.path.end == (4, 4)


def test_point_preview_stays_on_disclosed_supports_without_executing(wall_scene):
    _, available, index, _, first, tiles, camera = wall_scene
    pygame.font.init()
    image = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    cursor = EventQueue.event_cursor()
    state = MenuState(selected_action=index, selected_targets=(first.index,),
                      selected_positions=((4, 4), (8, 4)))
    draw_target_preview(image, state, available, camera, tiles)
    assert pygame.mask.from_surface(image).count() > 0
    moved_cursor = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(moved_cursor, replace(state, target_cursor=3), available, camera, tiles)
    assert pygame.image.tobytes(image, "RGBA") == pygame.image.tobytes(moved_cursor, "RGBA")
    hidden = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    draw_target_preview(hidden, state, available, camera, ())
    assert pygame.mask.from_surface(hidden).count() == 0
    assert EventQueue.event_cursor() == cursor


def test_keyboard_add_uses_admitted_vertex_without_taking_the_pause_key(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    admitted = tuple(get_extra_position_options(caster, row, first))
    state = MenuState(selected_action=index, selected_targets=(first.index,),
                      selected_positions=((4, 4),), target_cursor=admitted.index((8, 4)))
    unchanged, command = handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
        available, camera, tiles, panel_rect=PANEL, next_position_options=admitted)
    assert command is None and unchanged == state
    state, command = handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p),
        available, camera, tiles, panel_rect=PANEL, next_position_options=admitted)
    assert command is None and state.selected_positions == ((4, 4), (8, 4))
    _, command = handle_menu_event(state, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
        available, camera, tiles, panel_rect=PANEL)
    assert command == ActionSelection(index, (first.index,), ((8, 4),))


def ai_decision(caster):
    projector = SubjectiveAIStateProjector(assignment_id="wall-test", controlled_entity_uuids=(caster.uuid,))
    context = TurnContext(source_entity_uuid=caster.uuid, entity_uuid=caster.uuid)
    state = projector.project_decision(caster, context, reason=DecisionEpochReason.SNAPSHOT)
    row = next(row for row in state.epoch_build.epoch.affordances.all_rows
               if "segment, heat left" in row.display_name and row.targets[0].position == (4, 4))
    return projector, context, state, row


def test_ai_wire_points_and_exact_binding_execute_the_native_wall(wall_scene):
    caster = wall_scene[0]
    projector, context, state, row = ai_decision(caster)
    assert row.position_selection.kind == "path"
    intent = ExecuteIntent.model_validate_json(ExecuteIntent(row_id=row.row_id,
                                          extra_target_positions=((8, 4),)).model_dump_json())
    identity = AIInstrumentationContext(game_id="wall-test", assignment_id="wall-test",
        actor_uuid=str(caster.uuid), decision_id="first", policy=PolicyDescriptor(
            policy_id="test.wall", version="1", display_name="Wall selector"))
    result = resolve_policy_intent(entity=caster, turn_context=context, state=state, intent=intent,
        instrumentation=AIInstrumentation(), instrumentation_context=identity,
        project_world=lambda: projector.project_world(caster, context))
    assert result.step.event is not None and not result.step.event.canceled
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WallOfFireZone))
    assert zone.geometry.path.start == (4, 4) and zone.geometry.path.end == (8, 4)


@pytest.mark.parametrize("points", [((4, 4),), ((20, 4),), ((8, 4), (8, 8))])
def test_ai_rejects_unadmitted_or_excess_vertices_without_costs(wall_scene, points):
    caster = wall_scene[0]
    _, _, state, row = ai_decision(caster)
    before = caster.action_economy.actions.normalized_score
    cursor = EventQueue.event_cursor()
    with pytest.raises(AIDecisionValidationError):
        validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_positions=points))
    assert caster.action_economy.actions.normalized_score == before
    assert EventQueue.event_cursor() == cursor


@pytest.mark.parametrize("selection", ["self", "single"])
def test_ai_extra_points_on_other_selection_kinds_are_rejected_with_row_identity(wall_scene, selection):
    _, _, state, _ = ai_decision(wall_scene[0])
    rows = state.epoch_build.epoch.affordances.all_rows
    if selection == "self":
        row = next(row for row in rows if row.position_selection is None and row.target_type == "self")
    else:
        row = next(row for row in rows if row.position_selection is not None and row.position_selection.kind == "single")
    with pytest.raises(AIDecisionValidationError) as error:
        validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_positions=((8, 4),)))
    assert error.value.row_id == row.row_id


@pytest.mark.parametrize("position", [(1.5, 4), (True, 4), (4,)])
def test_wire_points_require_complete_integer_coordinates(position):
    with pytest.raises(ValidationError):
        ExecuteIntent.model_validate({"row_id": "some-row", "extra_target_positions": [position]})
