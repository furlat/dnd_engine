"""Real mixed-loadout object attacks and Fireball breach, captured for both players."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door, build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import AreaReachEvent, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt, Fireball
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.door_destruction_scenarios import review_actor, take_turn


ObjectAttackProgram = Literal["bow-melee", "bow-unarmed", "fire-bolt", "fireball-breach"]


def object_attack_history(*, program: ObjectAttackProgram) -> CapturedHistory:
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        source = Entity.create(uuid4(), "Attacker", config=EntityConfig(
            position=(3, 4) if program == "fireball-breach" else (3, 3), faction="heroes",
            action_economy=ActionEconomyConfig(spell_slots={3: 1}),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
        equipment: list[tuple[BaseItem, BodyPart | WeaponSlot]] = [
            (build_authored_item("apparel.robes.red_mage", source.uuid), BodyPart.BODY),
            (build_authored_item("apparel.cloth_shoes.red", source.uuid), BodyPart.FEET)]
        if program != "fireball-breach":
            equipment.append((build_authored_item("weapon.longbow", source.uuid), WeaponSlot.RANGED_MAIN))
            if program != "bow-unarmed":
                equipment.append((build_authored_item("weapon.longsword", source.uuid), WeaponSlot.MELEE_MAIN))
        source.install_initial_items(tuple(equipment))
        setup_standard_actions(source)
        install_body_response(source, BLOOD_BODY_RESPONSE)
        if program in ("fire-bolt", "fireball-breach"):
            register_spell(source, FireBolt if program == "fire-bolt" else Fireball, caster_level=1 if program == "fire-bolt" else 5)
        if program != "fireball-breach":
            source.equipment.activate_weapon_slot(WeaponSlot.RANGED_MAIN)
        source.compose_entity()
        game.deploy_entity(source, source.position)
        if program == "fireball-breach":
            witness = review_actor(game, "Beyond both doors", (9, 4), faction="enemies")
            doors = [build_authored_door("environment.door.desert_c7", hit_points=4)
                     for _ in range(2)]
            for door, x in zip(doors, (7, 9), strict=True):
                door.place_on_grid((x, 4), boundary_direction=CardinalDirection.WEST)
            # Two complete partitions make the doorway, rather than a detour,
            # the only route into each next room inside the original radius.
            for x, y in get_map().get_all_tiles():
                if x in (7, 9) and y != 4:
                    build_directional_wall().place_on_grid((x, y), boundary_direction=CardinalDirection.WEST)
            target = None
        else:
            witness = review_actor(game, "Witness", (6, 5))
            target = build_authored_item("environment.blocker.crate", source.uuid)
            target.place_on_grid((6, 3) if program == "fire-bolt" else (4, 3))

        actors = {"attacker": source, "witness": witness}
        encounter = Encounter(name="Shared attacks and destructible recipients", source_entity_uuid=source.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, source)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Objects and actual equipped loadout", start_cursor=0,
            end_cursor=baseline, observer_uuid=source.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        if program == "fireball-breach":
            choices = [(row, choice) for row in get_available_actions(source).all_actions
                if row.behavior_id == "spell.fireball" for choice in row.valid_targets
                if choice.position == (5, 4)]
            assert choices
            with fixed_dice_faces(*([1] * 200)):
                result = execute_available_action(source, *choices[0])
            assert isinstance(result, SpellEvent) and not result.canceled
            assert all(door.integrity is ItemIntegrity.DESTROYED for door in doors)
            stages = [event for _, event in EventQueue.iter_events_since(baseline)
                      if isinstance(event, AreaReachEvent) and event.phase is EventPhase.COMPLETION]
            assert len(stages) == 3
        else:
            assert target is not None
            slots = (WeaponSlot.MELEE_MAIN,) if program == "fire-bolt" else (
                WeaponSlot.RANGED_MAIN, WeaponSlot.MELEE_MAIN)
            for index, slot in enumerate(slots):
                if index:
                    take_turn(encounter, source, fresh=True)
                behavior = "spell.fire_bolt" if program == "fire-bolt" else "action.attack"
                choices = [(row, choice) for row in get_available_actions(source).all_actions
                    if row.behavior_id == behavior and (program == "fire-bolt" or row.weapon_slot == slot.value)
                    for choice in row.valid_targets if choice.target_uuid == target.uuid]
                assert choices
                with fixed_dice_faces(19, 4, 4):
                    result = execute_available_action(source, *choices[0])
                assert isinstance(result, (AttackEvent, SpellEvent)) and not result.canceled
                assert result.target_kind == "object"

        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["attacker"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
