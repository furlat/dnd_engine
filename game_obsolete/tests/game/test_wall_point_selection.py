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
from game.controls import ActionSelection, begin_targeting, append_position, confirm_targeting, undo_targeting
from game.ui.targeting import draw_selection_preview
from tests.game.ui_selection_helpers import selected_prefix
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
                      if row.behavior_id=="spell.wall_of_fire" and {facet.key:facet.value for facet in row.variant_facets}=={"form":"segment"})
    first = next(target for target in row.valid_targets if target.position == (4, 4))
    tiles = tuple(project_world_tile(tile) for position, tile in get_map().get_all_tiles().items()
                  if caster.senses.visible.get(position, False))
    camera = Camera(zoom=.75, viewport=(960, 640)).with_focus((6, 6))
    yield caster, available, index, row, first, tiles, camera
    reset_spell_regression_arena(1, 1)


def test_ordered_selection_undo_and_confirm_preserve_explicit_endpoints(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    before = EventQueue.event_cursor()
    state,preview=selected_prefix(caster,row,index,(first,))
    assert not state.selected_positions and state.selected_targets==(first.index,)
    assert (8,4) in preview.next_positions
    assert append_position(state,preview,(4,4)).selected_positions==()
    state,preview=selected_prefix(caster,row,index,(first,),((8,4),))
    assert state.selected_positions==((8,4),)
    state=undo_targeting(state)
    assert not state.selected_positions and state.selected_targets==(first.index,)
    state,preview=selected_prefix(caster,row,index,(first,),((8,4),))
    command=confirm_targeting(state,preview)
    assert command==ActionSelection(index,(first.index,),((8,4),))
    assert EventQueue.event_cursor()==before
    result=execute_available_action(caster,row,first,extra_target_positions=list(command.extra_target_positions))
    assert isinstance(result,SpellEvent) and not result.canceled
    assert result.area_geometry.path.start==(4,4) and result.area_geometry.path.end==(8,4)


def test_single_point_shorthand_and_action_change_clear_the_path(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    state,preview=selected_prefix(caster,row,index,(first,))
    assert begin_targeting(index).selected_targets==()
    command=confirm_targeting(state,preview)
    assert command==ActionSelection(index,(first.index,))
    result=execute_available_action(caster,row,first)
    assert isinstance(result,SpellEvent) and not result.canceled
    assert result.area_geometry.path.start!=caster.position
    assert result.area_geometry.path.end==(4,4)


def test_point_preview_stays_on_disclosed_supports_without_executing(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    pygame.font.init()
    image=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    cursor=EventQueue.event_cursor()
    state,preview=selected_prefix(caster,row,index,(first,),((8,4),))
    supports={tile.position:tile for tile in tiles}
    points=(first.position,*state.selected_positions)
    draw_selection_preview(image,preview,supports,camera,selected=(first,),points=points)
    assert pygame.mask.from_surface(image).count()>0
    hidden=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    draw_selection_preview(hidden,preview,{},camera,selected=(first,),points=points)
    assert pygame.mask.from_surface(hidden).count()==0
    assert EventQueue.event_cursor()==cursor


def test_admitted_extra_vertex_requires_explicit_confirmation(wall_scene):
    caster, available, index, row, first, tiles, camera = wall_scene
    state,preview=selected_prefix(caster,row,index,(first,),((8,4),))
    assert state.active and state.selected_positions==((8,4),)
    assert confirm_targeting(state,preview)==ActionSelection(index,(first.index,),((8,4),))


def ai_decision(caster):
    projector = SubjectiveAIStateProjector(assignment_id="wall-test", controlled_entity_uuids=(caster.uuid,))
    context = TurnContext(source_entity_uuid=caster.uuid, entity_uuid=caster.uuid)
    state = projector.project_decision(caster, context, reason=DecisionEpochReason.SNAPSHOT)
    template = next(row.template_name for row in caster.get_available_actions().all_actions
                    if row.behavior_id == "spell.wall_of_fire"
                    and {facet.key:facet.value for facet in row.variant_facets} == {"form":"segment"})
    row = next(row for row in state.epoch_build.epoch.affordances.all_rows
               if row.source.template_name==template
               and row.targets[0].position == (4, 4))
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
