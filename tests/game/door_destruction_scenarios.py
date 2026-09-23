"""Real door commands and ordinary object damage, recorded for both sides."""

import random
from typing import Literal
from uuid import uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import execute_available_action, execute_use_action, get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.content.items.environment_item_builders import build_authored_door, build_directional_wall
from dnd.controller import HumanController
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.item_types import DoorSwing, ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.world_authoring import set_world_tile_elevation
from game.player_facts import ObjectDamageFact, ObjectDestroyedFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, RecordedSequence, capture_history


DoorProgram = Literal["preview", "passage", "break-closed", "break-open"]


def review_actor(game: Game, name: str, position: tuple[int, int], *, strength: int = 10) -> Entity:
    """Compose the same clothed sword bearer for door and hardware stories."""
    actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes",
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=strength)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(actor)
    install_body_response(actor, BLOOD_BODY_RESPONSE)
    actor.install_initial_items((
        (build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN),
        (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
        (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
    ))
    actor.compose_entity()
    game.deploy_entity(actor, position)
    return actor


def take_turn(encounter: Encounter, actor: Entity, *, fresh: bool = False) -> None:
    if fresh:
        encounter.next_turn()
    while encounter.get_current_entity() is not actor:
        encounter.next_turn()
    actor.update_entity_senses()


def walk(actor: Entity, destination: tuple[int, int], *, accepted: bool = True,
         dice: tuple[int, ...] = ()) -> Event:
    actor.update_entity_senses()
    origin = actor.position
    with fixed_dice_faces(*dice):
        result = Move(source_entity_uuid=actor.uuid, end_position=destination,
            path=[origin, destination], prefer_safe=False).apply()
    assert result is not None
    if accepted:
        assert not result.canceled, result.status_message
        assert actor.position == destination
    else:
        assert actor.position == origin
    return result


def attack_object(actor: Entity, target: BaseItem, face: int, *, additional_dice: tuple[int, ...] = ()) -> Event:
    actor.update_entity_senses()
    choices = [(row, choice) for row in get_available_actions(actor).all_actions
        if row.behavior_id == "action.attack_object"
        for choice in row.valid_targets if choice.target_uuid == target.uuid]
    assert choices, f"{actor.name} cannot discover an attack on {target.name}"
    row, choice = choices[0]
    with fixed_dice_faces(face, *additional_dice):
        result = execute_available_action(actor, row, choice)
    assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
    return result


def door_destruction_history(*, item_id: str = "environment.door.indoor_door_shabby",
        program: DoorProgram = "preview", swing: Literal["inward", "outward"] = "outward",
        jammed: bool = False, raised: bool = False, late_snapshot: bool = False) -> CapturedHistory:
    """One door, adjoining walls, and independent observers on its two sides."""
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        if raised:
            author = uuid4()
            for x in range(3, 9):
                for y in range(2, 7):
                    set_world_tile_elevation((x, y), author_uuid=author, height=2,
                        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
        for y in (2, 3, 5, 6):
            build_directional_wall().place_on_grid((5, y), boundary_direction=CardinalDirection.EAST)
        door = build_authored_door(item_id, swing=DoorSwing(swing),
            destruction_outcome="jammed" if jammed else "clear", hit_points=12)
        door.place_on_grid((5, 4), boundary_direction=CardinalDirection.EAST)
        actors = {role: review_actor(game, role.title(), position)
                  for role, position in (("attacker", (4, 4)), ("witness", (6, 4)))}
        attacker, witness = actors["attacker"], actors["witness"]
        encounter = Encounter(name="Doors and their remains", source_entity_uuid=attacker.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, attacker)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Two sides of a doorway", start_cursor=0, end_cursor=baseline,
            observer_uuid=attacker.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        def use(actor: Entity, name: str) -> None:
            take_turn(encounter, actor)
            result = execute_use_action(actor, door.uuid, name)
            assert result is not None and not result.canceled
            assert door.is_open is (name == "Open Door")
            assert door.swing is DoorSwing(swing)

        if program in ("preview", "passage", "break-open"):
            use(attacker, "Open Door")
        if program == "preview":
            use(attacker, "Close Door")
        elif program == "passage":
            take_turn(encounter, witness)
            walk(witness, (6, 5))
            take_turn(encounter, attacker)
            walk(attacker, (5, 4))
            assert "Close Door" not in {action.name for action in door.get_use_actions(attacker.uuid)}
            walk(attacker, (6, 4))
            use(attacker, "Close Door")
            use(attacker, "Open Door")
            walk(attacker, (5, 4))
            walk(attacker, (4, 4))
            use(attacker, "Close Door")
        else:
            attack_object(attacker, door, 4)
            assert door.get_hp() == 8 and door.get_position() == (5, 4)
            take_turn(encounter, attacker, fresh=True)
            attack_object(attacker, door, 8)
            assert door.get_hp() == 0 and door.get_position() == (5, 4)
            assert door.integrity is ItemIntegrity.DESTROYED
            take_turn(encounter, witness)
            walk(witness, (6, 5))
            take_turn(encounter, attacker)
            walk(attacker, (5, 4))
            walk(attacker, (6, 4), accepted=not jammed)
        if late_snapshot:
            baseline = EventQueue.event_cursor()
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["attacker"]
        if late_snapshot:
            before, _ = reduce_interval(None, primary.initialization)
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


def check_saved_door(history: CapturedHistory, *, item_id: str, program: DoorProgram,
                     swing: str = "outward", jammed: bool = False, raised: bool = False) -> None:
    """Check saved public outcomes after the producer has reset the native game."""
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    assert set(history.views) == {"attacker", "witness"}
    for role, original in history.views.items():
        saved = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
        door, = (obj for obj in state.objects.values() if obj.item.item_id == item_id)
        assert door.item.door_swing is DoorSwing(swing)
        assert door.placement.base_height_steps == (2 if raised else 0)
        assert state.senses is not None
        # Each observer's floor is known; the opposite door-owner cell may be
        # occluded even while its boundary frame is visible.
        assert state.tiles[state.senses.position].elevation_steps == door.placement.base_height_steps
        destructions = []
        damages = []
        for root in roots:
            damages.extend(node.fact for node in root.events if isinstance(node.fact, ObjectDamageFact)
                           and node.fact.object_uuid == door.item.item_uuid)
            destructions.extend(node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)
                                and node.fact.object_uuid == door.item.item_uuid)
            state = reduce_lineage(state, root)
        if program.startswith("break-"):
            destruction, = destructions
            assert [damage.resulting_hp for damage in damages] == [8, 0], role
            assert destruction.replacement_uuid is None
            wreck = state.objects[door.item.item_uuid]
            assert wreck.item.integrity is ItemIntegrity.DESTROYED
            assert wreck.item.item_id == item_id
            assert wreck.item.destruction_outcome == ('jammed' if jammed else 'clear')
            assert wreck.placement == door.placement
            assert wreck.item.boundary_structure is not None
            assert (WorldEdgeChannel.MOVEMENT in wreck.item.boundary_structure.blocked_channels) is jammed
            assert wreck.item.remnant_state is not None
            assert wreck.item.remnant_state.door_open is (program == "break-open")
            assert wreck.item.remnant_state.door_swing is DoorSwing(swing)
        else:
            assert not destructions and not damages
            assert state.objects[door.item.item_uuid].item.is_open is False
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("item_id", tuple(DOOR_PROFILES))
def test_every_door_family_records_actual_open_and_close(item_id: str) -> None:
    check_saved_door(door_destruction_history(item_id=item_id), item_id=item_id, program="preview")


@pytest.mark.parametrize("item_id,program,swing,jammed,raised", (
    ("environment.door.indoor_door_shabby", "passage", "inward", False, True),
    ("environment.door.fantasy_a1", "passage", "inward", False, False),
    ("environment.door.desert_c1", "passage", "outward", False, False),
    ("environment.door.indoor_door_elegant", "break-closed", "outward", False, False),
    ("environment.door.indoor_door_shabby", "break-open", "inward", False, True),
    ("environment.door.fantasy_a1", "break-open", "inward", False, False),
    ("environment.door.desert_c5", "break-closed", "outward", False, False),
    ("environment.door.desert_a1", "break-closed", "outward", True, False),
))
def test_door_passage_and_destruction_replay(item_id, program, swing, jammed, raised) -> None:
    history = door_destruction_history(item_id=item_id, program=program, swing=swing, jammed=jammed, raised=raised)
    check_saved_door(history, item_id=item_id, program=program, swing=swing, jammed=jammed, raised=raised)
