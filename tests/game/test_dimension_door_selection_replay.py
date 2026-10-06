"""The existing selection and recorded transfer contracts admit unseen destinations."""

import pygame

from dnd.actions_functional import get_available_actions, get_extra_position_options, register_spell
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import DimensionDoor
from dnd.world_authoring import project_world_tile
from game.controls import ActionSelection, confirm_targeting
from tests.game.ui_selection_helpers import selected_prefix
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import PortalTransferFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.portal_draw import portal_draw_commands
from game.presentation import capture_interval, reduce_interval
from game.projection import Camera
from game.replay import ObserverCapture, capture_history
from tests.engine.test_banishment_dimension_door import scene as scene
from tests.manual.spell_regression_support import create_spell_regression_actor


def test_existing_two_stage_keyboard_route_selects_unseen_dimension_door_destination(scene):
    caster, companion, _ = scene
    for y in range(8):
        get_map().set_tile(9, y, walking_cost=0, blocks_optics=True)
    Entity.update_all_entities_senses(max_distance=125)
    register_spell(caster, DimensionDoor)
    available = get_available_actions(caster)
    index, row = next((i, row) for i, row in enumerate(available.all_actions)
        if row.behavior_id == "spell.dimension_door")
    recipient = next(option for option in row.valid_targets if option.target_uuid == companion.uuid)
    destination = (12, 2)
    assert not caster.senses.visible.get(destination, False)
    state, preview = selected_prefix(caster,row,index,(recipient,))
    assert destination in preview.next_positions and not preview.can_confirm
    state, preview = selected_prefix(caster,row,index,(recipient,),(destination,))
    command = confirm_targeting(state,preview)
    assert command == ActionSelection(index, (recipient.index,), (destination,))


def test_recorded_dimension_door_discloses_each_endpoint_only_to_its_actual_observer():
    reset_engine_runtime()
    battlefield = build_battlefield("battlefield.visibility_open_range")
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={4: 1})
    companion = create_spell_regression_actor("Companion", (3, 2), "heroes")
    departure = create_spell_regression_actor("Departure witness", (2, 5), "heroes")
    arrival = create_spell_regression_actor("Arrival witness", (14, 5), "heroes")
    for y in range(battlefield.definition.height):
        get_map().set_tile(9, y, walking_cost=0, blocks_optics=True)
    Entity.update_all_entities_senses(max_distance=125)
    encounter = Encounter(name="Door rooms", source_entity_uuid=caster.uuid)
    for actor in (caster, companion, departure, arrival):
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
    encounter.start_encounter()
    cursor = EventQueue.event_cursor()
    initial = capture_interval(name="Door rooms", start_cursor=0, end_cursor=cursor,
        observer_uuid=caster.uuid, battlefield_id=battlefield.definition.battlefield_id)
    before, _ = reduce_interval(None, initial)
    register_spell(caster, DimensionDoor)
    template = caster.get_action_template("Dimension Door")
    assert template is not None
    result = template.instantiate(target_entity_uuid=companion.uuid, end_position=(12, 2)).apply()
    assert result is not None and not result.canceled
    recorded = capture_history(before, (), observers=(
        ObserverCapture("departure", departure.uuid, cursor),
        ObserverCapture("arrival", arrival.uuid, cursor)))
    identities = {caster.uuid, companion.uuid}
    reset_engine_runtime()
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = load_animation_data()
    for role, starts, ends in (("departure", {(2, 2), (3, 2)}, {None}),
                              ("arrival", {None}, {(12, 2), (13, 2)})):
        sequence = project_sequence(recorded.views[role])
        state, roots = decode_player_sequence(encode_player_sequence(sequence))
        transfers = [node.fact for root in roots for node in root.events
                     if isinstance(node.fact, PortalTransferFact)]
        assert len(transfers) == 2
        assert {fact.target_entity_uuid for fact in transfers} == identities
        assert {fact.start_position for fact in transfers} == starts
        assert {fact.end_position for fact in transfers} == ends
        assert all(fact.committed and fact.portal_uuid is None for fact in transfers)
        seen = 0
        for root in roots:
            group = bind_choreography(state, root, data)
            assert not group.gaps, group.gaps
            for cue in group.portals:
                elapsed = (cue.fall_start_ms + cue.disappear_ms) / 2
                sample = sample_choreography(group, elapsed)
                for quadrant in range(4):
                    commands = portal_draw_commands(sample.displayed, data, elapsed,
                        Camera(quadrant=quadrant), (), sample.portals)
                    assert commands
                    assert {command.evidence[1] for command in commands} == {
                        "entrance" if role == "departure" else "exit"}
                seen += 1
            state = reduce_lineage(state, root)
        assert seen == 2
    pygame.quit()
