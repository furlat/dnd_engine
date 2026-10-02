"""Actual public gear changes retained before independent item-media replay."""

from uuid import uuid4

from dnd.actions_functional import execute_use_action, execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.conditions import Blinded
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, capture_history


def item_transfer_history(*, include_floor_robe=True, initial_hand=WeaponSlot.MELEE_MAIN,
                          drop_position=(3, 3)):
    reset_engine_runtime()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        actors = []
        for name, position in (("Original holder", (3, 3)), ("Recipient", (4, 3))):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes" if name == "Original holder" else "villains",
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False)))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),))
            actors.append(actor)
        original, recipient = actors
        dagger = build_authored_item("weapon.assassin_dagger", original.uuid)
        coating = build_authored_item("consumable.weapon_coat.fire", original.uuid)
        spare = build_authored_item("apparel.robes.wizard", original.uuid)
        original.install_initial_items(((dagger, initial_hand), (coating, None), (spare, None)))
        for actor in actors:
            actor.compose_entity()
            setup_standard_actions(actor)
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Retained item transfer", source_entity_uuid=original.uuid)
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        baseline = EventQueue.event_cursor()
        before, _ = reduce_interval(None, capture_interval(name="Item transfer", start_cursor=0,
            end_cursor=baseline, observer_uuid=original.uuid,
            battlefield_id=battlefield.definition.battlefield_id))
        result = execute_use_action(original, coating.uuid,
            "Coat Main Hand" if initial_hand is WeaponSlot.MELEE_MAIN else "Coat Off Hand")
        assert result is not None and not result.canceled
        other_hand = WeaponSlot.MELEE_OFF if initial_hand is WeaponSlot.MELEE_MAIN else WeaponSlot.MELEE_MAIN
        assert original.unequip_item(initial_hand) is dagger
        assert original.equip_item(dagger.uuid, other_hand)
        assert original.unequip_item(other_hand) is dagger
        for item in (dagger, spare) if include_floor_robe else (dagger,):
            actions = get_available_actions(original)
            row = next(row for row in actions.all_actions
                       if row.behavior_id == "action.core.drop" and row.source_item_uuid == item.uuid)
            target = next(target for target in row.valid_targets if target.position == drop_position)
            result = execute_by_index(original, row.template_name, target.index, available=actions)
            assert result is not None and not result.canceled
        encounter.next_turn()
        floor_actions = get_available_actions(recipient)
        row = next(row for row in floor_actions.all_actions if row.behavior_id == "action.pick_up")
        target = next(target for target in row.valid_targets if target.target_uuid == dagger.uuid)
        result = execute_by_index(recipient, row.template_name, target.index, available=floor_actions)
        assert result is not None and not result.canceled
        assert recipient.equip_item(dagger.uuid, WeaponSlot.MELEE_OFF)
        attack_actions = get_available_actions(recipient)
        attack_row = next(row for row in attack_actions.all_actions
                          if row.behavior_id == "action.attack" and row.weapon_slot == WeaponSlot.MELEE_OFF.value)
        target = next(row for row in attack_row.valid_targets if row.target_uuid == original.uuid)
        with fixed_dice_faces(15, *([1] * 12)):
            result = execute_by_index(recipient, attack_row.template_name, target.index, available=attack_actions)
        assert result is not None and not result.canceled
        dagger.remove_condition("Flaming Coat")
        Entity.update_all_entities_senses()
        captured = capture_history(before, (), observers=(ObserverCapture("holder", original.uuid, baseline),))
        return original.uuid, recipient.uuid, dagger.uuid, captured, floor_actions
    finally:
        game.close()
        reset_engine_runtime()


def inventory_transfer_history(*, low_level=False, hidden=False):
    """Public non-equipped transfer, with the giver as recorded observer."""
    reset_engine_runtime()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        actors = tuple(Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes"))
                       for name, position in (("Giver", (3, 3)), ("Receiver", (4, 3))))
        giver, receiver = actors
        item = build_authored_item("weapon.dagger", giver.uuid)
        giver.install_initial_items(((item, None),))
        if hidden:
            giver.add_condition(Blinded(source_entity_uuid=giver.uuid, target_entity_uuid=giver.uuid))
        for actor in actors:
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Inventory transfer", source_entity_uuid=giver.uuid)
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        baseline = EventQueue.event_cursor()
        before, _ = reduce_interval(None, capture_interval(name="Before inventory transfer", start_cursor=0,
            end_cursor=baseline, observer_uuid=giver.uuid,
            battlefield_id=battlefield.definition.battlefield_id))
        assert (giver.inventory.transfer_to(item.uuid, receiver.inventory) if low_level else receiver.loot_item(item))
        captured = capture_history(before, (), observers=(ObserverCapture("giver", giver.uuid, baseline),))
        after, _ = reduce_interval(before, capture_interval(name="Inventory transfer", start_cursor=baseline,
            end_cursor=EventQueue.event_cursor(), observer_uuid=giver.uuid,
            battlefield_id=battlefield.definition.battlefield_id))
        return giver.uuid, receiver.uuid, item.uuid, captured, after
    finally:
        game.close()
        reset_engine_runtime()
