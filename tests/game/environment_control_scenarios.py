"""Authored controls and container actions, captured from both native viewpoints."""

import random
from typing import Literal
from uuid import UUID, uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import ControlLever, StorageChest
from dnd.items.torches import WallTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.senses import SenseMode, SensesType
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def control_history(
    *, program: Literal["light", "door", "chest"] = "light",
    hidden_light: bool = False, observer_darkvision: bool = False,
) -> CapturedHistory:
    """Run real discovered actions; the hidden-light variant uses an actual wall."""
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.environment_controls")
    game = Game()
    try:
        light_key = "hidden_light" if hidden_light else "light"
        light = BaseBlock.get(built.object_uuids[light_key])
        light_control = BaseBlock.get(built.object_uuids[f"{light_key}_control"])
        door = BaseBlock.get(built.object_uuids["door"])
        door_control = BaseBlock.get(built.object_uuids["door_control"])
        second_light = BaseBlock.get(built.object_uuids["second_light"])
        second_control = BaseBlock.get(built.object_uuids["second_control"])
        chest = BaseBlock.get(built.object_uuids["chest"])
        assert isinstance(light, WallTorch) and isinstance(second_light, WallTorch)
        assert isinstance(light_control, ControlLever) and isinstance(door_control, ControlLever)
        assert isinstance(second_control, ControlLever) and isinstance(door, DirectionalDoor)
        assert isinstance(chest, StorageChest)
        placements = (("operator", (2, 7)), ("witness", (10, 6))) if hidden_light else (
            ("operator", (2, 5)), ("witness", (6, 6)))
        if program == "door":
            placements = (("operator", (4, 1)), ("witness", (7, 4)))
        elif program == "chest":
            placements = (("operator", (2, 2)), ("witness", (4, 2)))
        actors: dict[str, Entity] = {}
        for role, position in placements:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "operator" else "enemies",
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "operator" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            if role == "operator" or observer_darkvision:
                actor.senses.add_sense_mode_source(actor.uuid,
                    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
            setup_standard_actions(actor)
            actor.compose_entity()
            actors[role] = actor
        for actor in actors.values():
            game.deploy_entity(actor, actor.position)
        operator, witness = actors["operator"], actors["witness"]
        encounter = Encounter(name="Paired control and container experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity) -> None:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()

        def perform(actor: Entity, *, item_uuid: UUID | None = None,
                    behavior: str | None = None, destination: tuple[int, int] | None = None) -> Event:
            turn(actor)
            available = get_available_actions(actor)
            choices = [
                (row, target) for row in available.all_actions
                if (row.source_item_uuid == item_uuid if item_uuid is not None else row.behavior_id == "action.move")
                and (behavior is None or row.behavior_id == behavior)
                for target in row.valid_targets
                if destination is None or target.position == destination
            ]
            if not choices:
                raise ValueError(f"{actor.name} has no discovered {behavior or item_uuid or destination}")
            row, target = choices[0]
            result = execute_by_index(actor, row.template_name, target.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        turn(operator)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="control room initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=operator.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        if program == "light":
            assert light.is_lit and light_control.is_engaged
            assert (light.uuid in operator.senses.objects) is not hidden_light
            perform(operator, item_uuid=light_control.uuid)
            assert not light.is_lit and not light_control.is_engaged
            if not hidden_light:
                assert (operator.uuid in witness.senses.entities) is observer_darkvision
            perform(witness, item_uuid=light.uuid)
            assert light.is_lit and not light_control.is_engaged
            perform(operator, item_uuid=light_control.uuid)
            assert light.is_lit and light_control.is_engaged
            perform(operator, item_uuid=light_control.uuid)
            assert not light.is_lit and not light_control.is_engaged
            perform(operator, item_uuid=light_control.uuid)
            assert light.is_lit and light_control.is_engaged
            assert second_light.is_lit and second_control.is_engaged
            if hidden_light:
                assert light.uuid not in operator.senses.objects
        elif program == "door":
            assert not door.is_open and not door_control.is_engaged
            perform(operator, item_uuid=door_control.uuid)
            assert door.is_open and door_control.is_engaged
            offered = get_available_actions(operator)
            close_choice = next(row for row in offered.all_actions if row.source_item_uuid == door_control.uuid)
            perform(witness, destination=(8, 4))
            turn(operator)
            assert not any(row.source_item_uuid == door_control.uuid
                           for row in get_available_actions(operator).all_actions)
            refused = execute_by_index(operator, close_choice.template_name,
                close_choice.valid_targets[0].index, available=offered)
            assert refused is not None and refused.canceled
            assert door.is_open and door_control.is_engaged
            perform(operator, item_uuid=second_control.uuid)
            assert not second_light.is_lit and not second_control.is_engaged
            assert door.is_open and door_control.is_engaged
            perform(witness, destination=(9, 4))
            perform(operator, item_uuid=door_control.uuid)
            assert not door.is_open and not door_control.is_engaged
            perform(operator, item_uuid=door_control.uuid)
            assert door.is_open and door_control.is_engaged
            perform(witness, destination=(7, 4))
            perform(operator, item_uuid=door_control.uuid)
            assert not door.is_open and not door_control.is_engaged
            assert not second_light.is_lit
        else:
            contents = set(chest.chest_inventory.items)
            assert contents and not chest.is_open
            perform(operator, item_uuid=chest.uuid, behavior="action.environment.storage_chest.open")
            assert chest.is_open and set(chest.chest_inventory.items) == contents
            perform(operator, item_uuid=chest.uuid, behavior="action.environment.storage_chest.loot_all")
            assert chest.is_open and not chest.chest_inventory.items
            assert contents <= set(operator.inventory.items)
            perform(operator, item_uuid=chest.uuid, behavior="action.environment.storage_chest.close")
            assert not chest.is_open and not chest.chest_inventory.items
            perform(operator, item_uuid=chest.uuid, behavior="action.environment.storage_chest.open")
            assert chest.is_open and not chest.chest_inventory.items
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["operator"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
