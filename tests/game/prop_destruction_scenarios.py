"""Native prop interactions and attacks, recorded from two observers."""

import random

from dnd.actions_functional import execute_use_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.environment_interactables import StorageChest
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import attack_object, review_actor, take_turn, walk


def prop_destruction_history(*, item_id: str, opened: bool = False,
                             late_snapshot: bool = False) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        actors = {role: review_actor(game, role.title(), position)
                  for role, position in (("attacker", (4, 4)), ("witness", (8, 4)))}
        attacker = actors["attacker"]
        item = build_authored_item(item_id, attacker.uuid)
        loot = None
        if isinstance(item, StorageChest):
            loot = build_authored_item("consumable.healing_potion", attacker.uuid)
            assert item.chest_inventory.add_item(loot)
            loot.owner_uuid = item.uuid
            loot.stored_in_uuid = item.chest_inventory.uuid
        item.place_on_grid((5, 4))
        encounter = Encounter(name="Props and their remains", source_entity_uuid=attacker.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, attacker)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Prop and witnesses", start_cursor=0, end_cursor=baseline,
            observer_uuid=attacker.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)
        if opened:
            result = execute_use_action(attacker, item.uuid, "Open Chest")
            assert result is not None and not result.canceled
            assert item.get_spatial_open_state() is True
        for damage in (4, *((8,) * ((item.get_hp() + 7) // 8))):
            if item.integrity is ItemIntegrity.DESTROYED:
                break
            take_turn(encounter, attacker, fresh=True)
            attack_object(attacker, item, damage)
        assert item.integrity is ItemIntegrity.DESTROYED and item.get_position() == (5, 4)
        if loot is not None:
            assert loot.get_position() == (5, 4)
            assert loot.owner_uuid is None and loot.stored_in_uuid is None
        take_turn(encounter, attacker, fresh=True)
        walk(attacker, (5, 4))
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
