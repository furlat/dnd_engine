"""Actual public gear changes retained before independent item-media replay."""

from uuid import uuid4
from dataclasses import replace

from dnd.actions_functional import execute_use_action, execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item, materialize_item_definition
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS, AUTHORED_WEARABLE_DEFINITIONS
from dnd.items.authored_variant_inventory import AUTHORED_ITEM_VARIANT_CATEGORIES
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
                          drop_position=(3, 3), roster_outfit=False, roster_backpack=False, weapon_item_id=None,
                          coating_item_id: str | None = "consumable.weapon_coat.fire"):
    reset_engine_runtime()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        actors = []
        transferred_apparel = []
        for name, position in (("Original holder", (3, 3)), ("Recipient", (4, 3))):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes" if name == "Original holder" else "villains",
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody2" if roster_outfit and name == "Recipient" else "NakedBody", has_beard=False)))
            if not roster_outfit:
                actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),))
            elif name == "Original holder":
                for category_name, item_id, slot, partial in (("Common Clothes", "apparel.common_clothes", BodyPart.BODY, True),
                                                              ("Cloak", "apparel.cloak", BodyPart.CLOAK, False)):
                    category = next(row for row in AUTHORED_ITEM_VARIANT_CATEGORIES if row.base_category == category_name)
                    variant = next(row for row in category.variants if "roster-derived" in row.tags
                                   and (not partial or row.registration_render_layer is not None))
                    definition = replace(AUTHORED_WEARABLE_DEFINITIONS[item_id], visual_item_name=category_name,
                                         visual_variant_id=variant.visual_variant_id)
                    item = materialize_item_definition(definition, actor.uuid)
                    actor.install_initial_items(((item, slot),))
                    transferred_apparel.append((item, slot))
            if roster_backpack and name == "Original holder":
                quiver = build_authored_item("gear.quiver", actor.uuid)
                actor.install_initial_items(((quiver, BodyPart.BACKPACK),))
                transferred_apparel.append((quiver, BodyPart.BACKPACK))
            actors.append(actor)
        original, recipient = actors
        if weapon_item_id is not None:
            dagger = build_authored_item(weapon_item_id, original.uuid)
        elif roster_outfit:
            category = next(row for row in AUTHORED_ITEM_VARIANT_CATEGORIES if row.base_category == "Scimitar")
            variant = next(row for row in category.variants if "roster-derived" in row.tags)
            dagger = materialize_item_definition(replace(AUTHORED_WEAPON_DEFINITIONS["weapon.scimitar"],
                visual_item_name="Scimitar", visual_variant_id=variant.visual_variant_id), original.uuid)
        else:
            dagger = build_authored_item("weapon.assassin_dagger", original.uuid)
        coating = build_authored_item(coating_item_id, original.uuid) if coating_item_id is not None else None
        spare = build_authored_item("apparel.robes.wizard", original.uuid)
        original.install_initial_items(((dagger, initial_hand), (spare, None)) + (((coating, None),) if coating is not None else ()))
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
        if coating is not None:
            result = execute_use_action(original, coating.uuid,
                "Coat Main Hand" if initial_hand is WeaponSlot.MELEE_MAIN else "Coat Off Hand")
            assert result is not None and not result.canceled
        other_hand = WeaponSlot.MELEE_OFF if initial_hand is WeaponSlot.MELEE_MAIN else WeaponSlot.MELEE_MAIN
        assert original.unequip_item(initial_hand) is dagger
        if other_hand in original.equipment.compatible_slots_for_actor(dagger):
            assert original.equip_item(dagger.uuid, other_hand)
            assert original.unequip_item(other_hand) is dagger
        for item, slot in transferred_apparel:
            assert original.unequip_item(slot) is item
        dropped = ((dagger, spare) if include_floor_robe else (dagger,)) + tuple(item for item, _ in transferred_apparel)
        for item in dropped:
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
        recipient_hand = (WeaponSlot.MELEE_OFF if WeaponSlot.MELEE_OFF in recipient.equipment.compatible_slots_for_actor(dagger)
                          else WeaponSlot.MELEE_MAIN)
        assert recipient.equip_item(dagger.uuid, recipient_hand)
        for item, slot in transferred_apparel:
            actions = get_available_actions(recipient)
            row = next(row for row in actions.all_actions if row.behavior_id == "action.pick_up")
            target = next(target for target in row.valid_targets if target.target_uuid == item.uuid)
            result = execute_by_index(recipient, row.template_name, target.index, available=actions)
            assert result is not None and not result.canceled
            assert recipient.equip_item(item.uuid, slot)
        attack_actions = get_available_actions(recipient)
        attack_row = next(row for row in attack_actions.all_actions
                          if row.behavior_id == "action.attack" and row.weapon_slot == recipient_hand.value)
        target = next(row for row in attack_row.valid_targets if row.target_uuid == original.uuid)
        with fixed_dice_faces(15, *([1] * 12)):
            result = execute_by_index(recipient, attack_row.template_name, target.index, available=attack_actions)
        assert result is not None and not result.canceled
        if coating_item_id == "consumable.weapon_coat.basic_poison":
            for _ in range(10):
                dagger.advance_duration("Basic Poison")
        elif coating is not None:
            dagger.remove_condition("Flaming Coat")
        Entity.update_all_entities_senses()
        observers = (ObserverCapture("holder", original.uuid, baseline),)
        if roster_outfit:
            observers += (ObserverCapture("recipient", recipient.uuid, baseline),)
        captured = capture_history(before, (), observers=observers)
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
