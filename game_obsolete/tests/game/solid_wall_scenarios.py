"""Record real attacks and passage through ordinary walls, then reset the game."""

import random
from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection
from dnd.world_authoring import set_world_tile_elevation
from tests.game.door_destruction_scenarios import attack_item, review_actor, take_turn, walk


def solid_wall_history(item_id: str = "environment.directional_wall", *,
                       material: Material = Material.STONE, raised: bool = False,
                       corner: bool = False, late_snapshot: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        if raised:
            for x in range(3, 9):
                for y in range(2, 7):
                    set_world_tile_elevation((x, y), author_uuid=uuid4(), height=2,
                        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
        wall = (build_directional_wall(material=material) if item_id == "environment.directional_wall"
                else build_authored_item(item_id, uuid4()))
        wall.place_on_grid((5, 4), boundary_direction=CardinalDirection.EAST)
        if corner:
            survivor = build_directional_wall(material=material)
            survivor.place_on_grid((5, 4), boundary_direction=CardinalDirection.NORTH)
        actors = {role: review_actor(game, role.title(), position, strength=18)
                  for role, position in (("attacker", (5, 4)), ("witness", (6, 4)))}
        attacker, witness = actors["attacker"], actors["witness"]
        encounter = Encounter(name="Solid wall breach", source_entity_uuid=attacker.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, attacker)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Solid wall intact", start_cursor=0, end_cursor=baseline,
            observer_uuid=attacker.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        while wall.integrity is ItemIntegrity.INTACT:
            attack_item(attacker, wall, 8)
            if wall.integrity is ItemIntegrity.INTACT:
                take_turn(encounter, attacker, fresh=True)
        take_turn(encounter, witness)
        walk(witness, (6, 5))
        take_turn(encounter, attacker)
        walk(attacker, (6, 4))
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
