"""Fixed-window stories captured from ordinary native actions for both observers."""

import random
import json
from pathlib import Path
from typing import Literal

from dnd.actions import TraverseConnector
from dnd.controller import HumanController
from dnd.core.creature_types import Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.content.items.window_builders import place_window
from dnd.content.items.window_definitions import WINDOW_DEFINITIONS
from dnd.items.environment import DirectionalWall
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import review_actor, take_turn, attack_item, walk


def window_history(*, family: str = "environment.window.fantasy_g8",
                   program: Literal["insert-cross-wall", "parent"] = "insert-cross-wall",
                   hidden_insert: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        assembly = place_window(family, (5, 4), CardinalDirection.EAST)
        media = json.loads((Path(__file__).resolve().parents[2] / "game/data/window_media_sources.json").read_text())
        sibling = media["solid_siblings"][family.removeprefix("environment.window.fantasy_")]
        for y in (3, 5):
            DirectionalWall(source_entity_uuid=assembly.wall.uuid,
                item_id=f"environment.wall.fantasy_{sibling}",
                name="Matching solid wall", material=WINDOW_DEFINITIONS[family].wall_material,
                include_in_senses_objects=True,
            ).place_on_grid((5, y), boundary_direction=CardinalDirection.EAST)
        if hidden_insert and assembly.insert is not None:
            assembly.insert.stealth_dc = 100
        attacker = review_actor(game, "Attacker", (4, 4))
        attacker.size = Size.SMALL
        witness = review_actor(game, "Witness", (7, 4))
        actors = {"attacker": attacker, "witness": witness}
        encounter = Encounter(name="Fixed windows", source_entity_uuid=attacker.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, attacker)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Two sides of a window", start_cursor=0, end_cursor=baseline,
            observer_uuid=attacker.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        walk(attacker, (5, 4))
        take_turn(encounter, attacker, fresh=True)

        def break_item(item) -> None:
            while item.integrity is ItemIntegrity.INTACT:
                take_turn(encounter, attacker, fresh=True)
                attack_item(attacker, item, 8)

        if program == "insert-cross-wall":
            if assembly.insert is not None:
                take_turn(encounter, attacker)
                attack_item(attacker, assembly.insert, 4)
                assert assembly.insert.integrity is ItemIntegrity.INTACT
                break_item(assembly.insert)
            take_turn(encounter, attacker, fresh=True)
            choices = TraverseConnector(source_entity_uuid=attacker.uuid).get_discovery_variants(attacker)
            assert len(choices) == 1
            result = choices[0].apply()
            assert result is not None and not result.canceled, result.status_message if result else None
            assert attacker.position == (6, 4)
            break_item(assembly.wall)
            take_turn(encounter, attacker, fresh=True)
            walk(attacker, (5, 4))
        else:
            break_item(assembly.wall)
            take_turn(encounter, attacker, fresh=True)
            walk(attacker, (6, 4))
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["attacker"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
