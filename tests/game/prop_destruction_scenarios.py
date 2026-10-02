"""Native prop interactions and attacks, recorded from two observers."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import Attack
from dnd.actions_functional import execute_available_action, execute_use_action, get_available_actions, register_spell
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.world_prop_builders import WORLD_PROP_PROFILES
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.environment_interactables import StorageChest
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt
from dnd.world_authoring import set_world_tile_elevation
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import attack_item, review_actor, take_turn, walk


def prop_destruction_history(*, item_id: str, opened: bool = False,
                             late_snapshot: bool = False, elevation: int = 0,
                             access: Literal["none", "bow", "fire-bolt"] = "none") -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    if elevation:
        for x in range(2, 11):
            for y in range(2, 8):
                set_world_tile_elevation((x, y), author_uuid=uuid4(), height=elevation,
                                         surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    game = Game()
    try:
        profile = WORLD_PROP_PROFILES.get(item_id)
        offsets = profile.footprint_offsets if profile is not None else ((0, 0),)
        left = 5 + min(x for x, _ in offsets)
        right = 5 + max(x for x, _ in offsets)
        bottom = 4 + min(y for _, y in offsets)
        origin = (left - 1, 4)
        actors = {role: review_actor(game, role.title(), position,
                                    ranged=access == "bow" and role == "attacker",
                                    faction=role if access != "none" else "heroes")
                  for role, position in (("attacker", origin),
                      ("witness", (right + 3 if access != "none" else 8, 4)))}
        attacker = actors["attacker"]
        if access == "fire-bolt":
            register_spell(attacker, FireBolt, caster_level=1)
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

        def shoot(*, accepted: bool) -> None:
            target = actors["witness"]
            take_turn(encounter, attacker, fresh=True)
            action = (FireBolt(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
                      if access == "fire-bolt" else Attack(source_entity_uuid=attacker.uuid,
                          target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.RANGED_MAIN))
            assert action.validate_requirements_for_discovery() is accepted
            choices = [(row, choice) for row in get_available_actions(attacker).all_actions
                if row.behavior_id == ("spell.fire_bolt" if access == "fire-bolt" else "action.attack")
                and (access == "fire-bolt" or row.weapon_slot == WeaponSlot.RANGED_MAIN.value)
                for choice in row.valid_targets if choice.target_uuid == target.uuid]
            assert bool(choices) is accepted
            hp, budget = target.get_hp(), attacker.action_economy.actions.normalized_score
            with fixed_dice_faces(15, 4):
                result = execute_available_action(attacker, *choices[0]) if accepted else action.apply()
            assert result is not None and result.canceled is not accepted
            assert (target.get_hp() < hp) is accepted
            assert attacker.action_economy.actions.normalized_score == budget - int(accepted)

        if access != "none" and item.blocks_walking(attacker.uuid):
            budget = attacker.action_economy.movement.normalized_score
            walk(attacker, (left, 4), accepted=False)
            assert attacker.action_economy.movement.normalized_score == budget
            shoot(accepted=not item.blocks_propagation())
            # Actual legal detour, then a successful shot from the far corner.
            detour = ([(origin[0], y) for y in range(3, bottom - 2, -1)]
                      + [(x, bottom - 1) for x in range(left, right + 2)])
            for point in detour:
                take_turn(encounter, attacker, fresh=True)
                walk(attacker, point)
            shoot(accepted=True)
            for point in [*reversed(detour[:-1]), origin]:
                take_turn(encounter, attacker, fresh=True)
                walk(attacker, point)
        if opened:
            result = execute_use_action(attacker, item.uuid, "Open Chest")
            assert result is not None and not result.canceled
            assert item.get_spatial_open_state() is True
        if profile is not None and not profile.blocks_movement:
            # Both halves of the intact covering, before its real damage/break.
            crossing = [(x, 4) for x in range(left, right + 2)]
            for position in [*crossing, *reversed(crossing[:-1]), origin]:
                take_turn(encounter, attacker, fresh=True)
                walk(attacker, position)
        for damage in (4, *((8,) * ((item.get_hp() + 7) // 8))):
            if item.integrity is ItemIntegrity.DESTROYED:
                break
            take_turn(encounter, attacker, fresh=True)
            attack_item(attacker, item, damage)
        assert item.integrity is ItemIntegrity.DESTROYED and item.get_position() == (5, 4)
        if access != "none":
            shoot(accepted=True)
        if loot is not None:
            assert loot.get_position() == (5, 4)
            assert loot.owner_uuid is None and loot.stored_in_uuid is None
        take_turn(encounter, attacker, fresh=True)
        for x in range(left, right + 2):
            walk(attacker, (x, 4))
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
