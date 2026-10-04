"""Creature and destination selection stays in the existing human command route."""
import pygame
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, get_extra_position_options, register_spell
from dnd.core.events import EventQueue
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.spells.transmutation import Telekinesis
from dnd.world_authoring import project_world_tile
from game.controls import ActionSelection, MenuState, handle_menu_event
from game.projection import Camera, project_screen
from game.session import discover_player_actions, execute_player_action, player_position_options
from tests.engine.test_telekinesis_landing import scene as scene, cast
from tests.game.test_session import session as session, _advance_to_human

PANEL = pygame.Rect(750, 0, 210, 640)


@pytest.mark.parametrize("retained", [False, True])
def test_two_stage_selection_undo_and_confirm_submit_one_creature_and_destination(scene, retained):
    caster, target = scene
    target.faction = caster.faction
    register_spell(caster, Telekinesis)
    if retained:
        result = cast(caster, target, (6, 2))
        assert not result.canceled
        caster.action_economy.reset_all_costs()
    available = get_available_actions(caster)
    behavior = "action.spell.telekinesis.move" if retained else "spell.telekinesis"
    index, row = next((i, row) for i, row in enumerate(available.all_actions)
        if row.behavior_id == behavior)
    recipient = next(option for option in row.valid_targets if option.target_uuid == target.uuid)
    state = MenuState(selected_action=index, target_cursor=row.valid_targets.index(recipient))
    tiles = tuple(project_world_tile(tile) for position, tile in get_map().get_all_tiles().items()
        if caster.senses.visible.get(position, False))
    camera = Camera(zoom=.75, viewport=(960, 640)).with_focus((6, 4))
    cursor = EventQueue.event_cursor()

    def event(value, options=()):
        nonlocal state
        state, command = handle_menu_event(state, value, available, camera, tiles,
            panel_rect=PANEL, next_position_options=options)
        return command

    def key(value, options=()):
        return event(pygame.event.Event(pygame.KEYDOWN, key=value), options)

    assert key(pygame.K_RETURN) is None
    assert state.selected_targets == (recipient.index,)
    assert state.selected_positions == (target.position,)
    assert key(pygame.K_RETURN) is None
    options = tuple(get_extra_position_options(caster, row, recipient))
    destination = (7, 3)
    assert destination in options
    assert event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
        pos=project_screen(destination, camera)), options) is None
    assert state.selected_positions[-1] == destination
    assert key(pygame.K_BACKSPACE) is None
    assert state.selected_positions == (target.position,)
    assert key(pygame.K_p, (destination,)) is None
    command = key(pygame.K_RETURN)
    assert isinstance(command, ActionSelection)
    assert command == ActionSelection(index, (recipient.index,), (destination,))
    assert not state.selected_positions and EventQueue.event_cursor() == cursor
    result = execute_available_action(caster, row, recipient,
        extra_target_positions=list(command.extra_target_positions))
    assert result is not None and not result.canceled and target.position == destination
    assert caster.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("source_item", [False, True])
def test_live_session_queries_then_commits_typed_creature_destination(session, source_item):
    _advance_to_human(session, [])
    actor = session.encounter.get_current_entity()
    assert actor is not None
    if source_item:
        device = build_spell_device(item_id="environment.fireball_cannon", name="Telekinetic device",
            spell_templates=[Telekinesis(source_entity_uuid=actor.uuid, template=True, cast_origin="source_item")],
            charges=2)
        device.place_on_grid((actor.position[0] + 1, actor.position[1]))
        Entity.update_all_entities_senses()
    else:
        actor.register_action(Telekinesis(source_entity_uuid=actor.uuid, template=True, alt_skip_slot=True))
    choices = discover_player_actions(session, actor.uuid)
    row = next(row for row in choices.entity_actions if row.behavior_id == "spell.telekinesis")
    target = next(option for option in row.valid_targets
        if option.target_uuid in session.player_uuids and option.target_uuid != actor.uuid)
    cursor = EventQueue.event_cursor()
    options = player_position_options(session, actor.uuid, row, target)
    destination = next(position for position in options if position != target.position)
    assert EventQueue.event_cursor() == cursor
    operation = execute_player_action(session, actor.uuid, row, target, extra_target_positions=(destination,))
    assert operation.roots and not any(root.canceled for root in operation.roots)
    recipient = session.game.entities[target.target_uuid]
    assert recipient.position == destination and actor.action_economy.actions.normalized_score == 0
