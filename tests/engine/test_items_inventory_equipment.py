"""Engine semantic tests for items, inventory, and equipment."""

from uuid import UUID, uuid4

from dnd.actions.operations import execute_use_action, setup_standard_actions
from dnd.blocks.base_item import (
    BaseItem,
    UsableItem,
)
from dnd.blocks.equipment import (
    BodyArmor,
    Shield,
    Weapon,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.types.equipment import BodyPart, WeaponProperty, WeaponSlot
from dnd.blocks.inventory import Inventory
from dnd.core.base_block import BaseBlock
from dnd.types.world import LightLevel
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventQueue,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialEffectInteractionEvent,
)
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.core.gridmap import get_map
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.items.armors import CHAIN_MAIL_RECIPE, SHIELD_RECIPE
from dnd.items.consumables import (
    HEALING_POTION_RECIPE,
    healing_potion_recipe,
)
from dnd.items.environment_content import DOOR_RECIPE
from dnd.items.environment_interactables import (
    StorageChest,
    DoorObject,
)
from dnd.items.torches import TORCH_RECIPE, Torch, WallTorch
from dnd.items.weapons import (
    GREATSWORD_RECIPE,
    SHORTBOW_RECIPE,
    SHORTSWORD_RECIPE,
    WARHAMMER_RECIPE,
)
from dnd.monsters.bestiary import create_skeleton
from tests.engine.support import get_hp, reset_combat_state, set_hp


def reset_item_state(
    width: int = 6,
    height: int = 3,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Clear global state and create a rectangular item test grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    for tile in grid._tiles.values():
        tile.default_light = default_light


def put_in_inventory(entity: Entity, item: BaseItem) -> None:
    """Insert an item and set the location fields that Entity.loot_item would set."""
    assert entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid


def test_eb_13_001_floor_loot_and_drop_update_authoritative_location() -> None:
    """EB-13-001: floor, inventory, and dropped item state are mutually exclusive."""
    reset_item_state()
    entity = create_skeleton(name="Collector", position=(0, 0), darkvision=False)
    item = BaseItem(source_entity_uuid=uuid4(), name="Silver Key", weight=1)

    item.place_on_grid((1, 0))

    assert item.tile_uuid is not None
    assert item.get_position() == (1, 0)
    assert get_map().get_object_position(item.uuid) == (1, 0)

    assert entity.loot_item(item)

    assert entity.inventory.has_item(item.uuid)
    assert item.owner_uuid == entity.uuid
    assert item.stored_in_uuid == entity.inventory.uuid
    assert item.tile_uuid is None
    assert get_map().get_object_position(item.uuid) is None
    assert item.get_position() == entity.position

    dropped = entity.drop_item(item.uuid, position=(0, 1))

    assert dropped is item
    assert not entity.inventory.has_item(item.uuid)
    assert item.owner_uuid is None
    assert item.stored_in_uuid is None
    assert item.tile_uuid is not None
    assert item.get_position() == (0, 1)
    assert get_map().get_object_position(item.uuid) == (0, 1)


def test_eb_13_002_inventory_stack_merge_can_consume_or_split_items() -> None:
    """EB-13-002: same stack_id items merge up to max_stack and unregister consumed objects."""
    reset_item_state()
    entity = create_skeleton(name="Alchemist", position=(0, 0), darkvision=False)
    first = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    second = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    third = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    first.stack_count = 8
    second.stack_count = 2
    third.stack_count = 5

    assert entity.inventory.add_item(first)
    assert entity.inventory.add_item(second)

    assert first.stack_count == 10
    assert second.stack_count == 0
    assert not entity.inventory.has_item(second.uuid)
    assert BaseBlock.get(second.uuid) is None

    assert entity.inventory.add_item(third)

    assert first.stack_count == 10
    assert third.stack_count == 5
    assert entity.inventory.has_item(third.uuid)
    assert entity.inventory.item_count == 2


def test_eb_13_003_inventory_capacity_and_transfer_update_container_fields() -> None:
    """EB-13-003: inventories enforce capacity and transfer updates owner/storage."""
    reset_item_state()
    source_owner = uuid4()
    target_owner = uuid4()
    source = Inventory(source_entity_uuid=source_owner, name="Source")
    target = Inventory(source_entity_uuid=target_owner, name="Target", max_slots=1)
    item = BaseItem(source_entity_uuid=source_owner, name="Gem", weight=2)
    blocker = BaseItem(source_entity_uuid=target_owner, name="Blocker", weight=1)

    assert source.add_item(item)
    item.owner_uuid = source_owner
    item.stored_in_uuid = source.uuid
    assert target.add_item(blocker)

    assert not source.transfer_to(item.uuid, target)
    assert source.has_item(item.uuid)
    assert item.owner_uuid == source_owner
    assert item.stored_in_uuid == source.uuid

    target.remove_item(blocker.uuid)

    assert source.transfer_to(item.uuid, target)
    assert not source.has_item(item.uuid)
    assert target.has_item(item.uuid)
    assert item.owner_uuid == target_owner
    assert item.stored_in_uuid == target.uuid


def test_eb_13_012_partial_stack_merge_is_atomic_on_capacity_failure() -> None:
    """EB-13-012: failed stack insertion leaves both stacks unchanged."""
    reset_item_state()
    inventory = Inventory(source_entity_uuid=uuid4(), name="Tight Pack", weight_capacity=10)
    existing = materialize_item(
        HEALING_POTION_RECIPE,
        inventory.source_entity_uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    incoming = materialize_item(
        HEALING_POTION_RECIPE,
        inventory.source_entity_uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    existing.stack_count = 8
    incoming.stack_count = 5
    existing.weight = 1
    incoming.weight = 1

    assert inventory.add_item(existing)

    result = inventory.add_item(incoming)

    assert not result
    assert existing.stack_count == 8
    assert incoming.stack_count == 5
    assert not inventory.has_item(incoming.uuid)
    assert inventory.total_weight == 8


def test_eb_13_017_transfer_to_existing_stack_consumes_incoming_location() -> None:
    """EB-13-017: transfer into an existing stack consumes the incoming object cleanly."""
    reset_item_state()
    source_owner = uuid4()
    target_owner = uuid4()
    source = Inventory(source_entity_uuid=source_owner, name="Source")
    target = Inventory(source_entity_uuid=target_owner, name="Target")
    incoming = materialize_item(
        HEALING_POTION_RECIPE,
        source_owner,
        origin=ItemRuntimeOrigin.STARTER,
    )
    existing = materialize_item(
        HEALING_POTION_RECIPE,
        target_owner,
        origin=ItemRuntimeOrigin.STARTER,
    )
    incoming.stack_count = 2
    existing.stack_count = 8

    assert source.add_item(incoming)
    incoming.owner_uuid = source_owner
    incoming.stored_in_uuid = source.uuid
    assert target.add_item(existing)
    existing.owner_uuid = target_owner
    existing.stored_in_uuid = target.uuid

    assert source.transfer_to(incoming.uuid, target)

    assert not source.has_item(incoming.uuid)
    assert not target.has_item(incoming.uuid)
    assert target.has_item(existing.uuid)
    assert existing.stack_count == 10
    assert existing.owner_uuid == target_owner
    assert existing.stored_in_uuid == target.uuid
    assert incoming.stack_count == 0
    assert BaseBlock.get(incoming.uuid) is None
    assert incoming.owner_uuid is None
    assert incoming.stored_in_uuid is None


def test_eb_13_004_equip_and_unequip_move_items_between_inventory_and_equipment() -> None:
    """EB-13-004: Entity equip helpers move item ownership between containers."""
    reset_item_state()
    entity = create_skeleton(name="Duelist", position=(0, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    put_in_inventory(entity, sword)

    assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)

    assert entity.equipment.weapon_melee_main is sword
    assert not entity.inventory.has_item(sword.uuid)
    assert sword.is_equipped
    assert sword.equipped_slot == WeaponSlot.MELEE_MAIN.value
    assert sword.owner_uuid == entity.uuid
    assert sword.stored_in_uuid == entity.equipment.uuid
    assert sword.source_entity_uuid == entity.uuid

    unequipped = entity.unequip_item(WeaponSlot.MELEE_MAIN)

    assert unequipped is sword
    assert entity.equipment.weapon_melee_main is None
    assert entity.inventory.has_item(sword.uuid)
    assert not sword.is_equipped
    assert sword.equipped_slot is None
    assert sword.stored_in_uuid == entity.inventory.uuid


def test_eb_13_005_equipment_validates_weapon_slots_and_replaces_existing_items() -> None:
    """EB-13-005: weapon slots enforce type rules and auto-unequip replacements."""
    reset_item_state()
    entity = create_skeleton(name="Armsmaster", position=(0, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    replacement = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    bow = materialize_item(
        SHORTBOW_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    warhammer = materialize_item(
        WARHAMMER_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

    assert entity.equipment.weapon_melee_main is replacement
    assert not sword.is_equipped
    assert sword.equipped_slot is None

    try:
        entity.equipment.equip(bow, WeaponSlot.MELEE_MAIN)
        assert False, "Ranged weapon equipped in melee slot"
    except ValueError as exc:
        assert "Ranged weapon" in str(exc)

    try:
        entity.equipment.equip(warhammer, WeaponSlot.MELEE_OFF)
        assert False, "Non-light weapon equipped in off-hand slot"
    except ValueError as exc:
        assert "LIGHT" in str(exc)


def test_eb_13_006_equipment_hooks_apply_and_remove_modifiers() -> None:
    """EB-13-006: equip hooks can add modifiers and unequip hooks clean them up."""
    reset_item_state()
    entity = create_skeleton(name="Armored Scout", position=(0, 0), darkvision=False)
    armor = materialize_item(
        CHAIN_MAIL_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )

    assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE

    entity.equipment.equip(armor)
    entity.equipment.equip(shield)

    assert entity.equipment.body_armor is armor
    assert entity.equipment.weapon_melee_off is shield
    assert armor.is_equipped
    assert shield.is_equipped
    assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

    entity.equipment.unequip(BodyPart.BODY)
    entity.equipment.unequip(WeaponSlot.MELEE_OFF)

    assert entity.equipment.body_armor is None
    assert entity.equipment.weapon_melee_off is None
    assert not armor.is_equipped
    assert not shield.is_equipped
    assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE


def test_eb_13_013_canceled_high_level_equip_preserves_inventory_item() -> None:
    """EB-13-013: canceled high-level equip preserves both containers."""
    reset_item_state()
    entity = create_skeleton(name="Interrupted Duelist", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    put_in_inventory(entity, sword)

    def cancel_weapon_equip(event: Event, _source_entity_uuid) -> Event:
        return event.cancel(status_message="Test cancels weapon equip")

    entity.add_event_handler(
        EventHandler(
            name="Cancel Weapon Equip",
            source_entity_uuid=entity.uuid,
            validation_only=True,
            event_processor=cancel_weapon_equip,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.WEAPON_EQUIP,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=entity.uuid,
                )
            ],
        )
    )

    result = entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)

    assert result is False
    assert entity.equipment.weapon_melee_main is original_weapon
    assert original_weapon is not None
    assert original_weapon.is_equipped
    assert not sword.is_equipped
    assert entity.inventory.has_item(sword.uuid)
    assert sword.owner_uuid == entity.uuid
    assert sword.stored_in_uuid == entity.inventory.uuid


def test_eb_13_014_two_handed_melee_conflicts_auto_displace_by_equip_order() -> None:
    """EB-13-014: newer equips displace conflicting melee hand items."""
    reset_item_state()
    entity = create_skeleton(name="Overloaded Warrior", position=(0, 0), darkvision=False)
    greatsword = materialize_item(
        GREATSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    put_in_inventory(entity, greatsword)
    put_in_inventory(entity, shield)

    assert entity.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)
    assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)

    assert entity.equipment.weapon_melee_main is None
    assert entity.equipment.weapon_melee_off is shield
    assert not greatsword.is_equipped
    assert greatsword.equipped_slot is None
    assert shield.is_equipped
    assert shield.equipped_slot == WeaponSlot.MELEE_OFF.value
    assert entity.inventory.has_item(greatsword.uuid)
    assert greatsword.owner_uuid == entity.uuid
    assert greatsword.stored_in_uuid == entity.inventory.uuid

    second = create_skeleton(name="Shielded Warrior", position=(1, 0), darkvision=False)
    original_weapon = second.equipment.weapon_melee_main
    second_greatsword = materialize_item(
        GREATSWORD_RECIPE,
        second.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    second_shield = materialize_item(
        SHIELD_RECIPE,
        second.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    put_in_inventory(second, second_greatsword)
    put_in_inventory(second, second_shield)

    assert second.equip_item(second_shield.uuid, WeaponSlot.MELEE_OFF)
    assert second.equip_item(second_greatsword.uuid, WeaponSlot.MELEE_MAIN)

    assert second.equipment.weapon_melee_main is second_greatsword
    assert second.equipment.weapon_melee_off is None
    assert second_greatsword.is_equipped
    assert second_greatsword.equipped_slot == WeaponSlot.MELEE_MAIN.value
    assert not second_shield.is_equipped
    assert second_shield.equipped_slot is None
    assert second.inventory.has_item(second_shield.uuid)
    if original_weapon is not None:
        assert not original_weapon.is_equipped
        assert second.inventory.has_item(original_weapon.uuid)


def test_eb_13_015_heavy_armor_strength_requirement_reduces_speed() -> None:
    """EB-13-015: heavy armor strength requirements are contextual speed rules."""
    reset_item_state()
    entity = create_skeleton(name="Armored Skeleton", position=(0, 0), darkvision=False)
    chain_mail = materialize_item(
        CHAIN_MAIL_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    assert entity.ability_scores.strength.ability_score.score == 10
    assert entity.action_economy.movement.normalized_score == 30

    assert entity.equipment.equip(chain_mail)

    assert chain_mail.strength_requirement == 13
    assert entity.equipment.body_armor is chain_mail
    assert entity.action_economy.movement.normalized_score == 20

    strength_boost = NumericalModifier(
        name="Temporary Strength",
        value=3,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    entity.ability_scores.strength.ability_score.self_static.add_value_modifier(strength_boost)

    assert entity.ability_scores.strength.ability_score.score == 13
    assert entity.action_economy.movement.normalized_score == 30

    entity.ability_scores.strength.ability_score.self_static.remove_value_modifier(strength_boost.uuid)

    assert entity.action_economy.movement.normalized_score == 20

    entity.equipment.unequip(BodyPart.BODY)

    assert entity.action_economy.movement.normalized_score == 30


def test_eb_13_016_canceled_direct_equip_preserves_existing_slot_item() -> None:
    """EB-13-016: direct Equipment.equip cancellation preserves the current slot."""
    reset_item_state()
    entity = create_skeleton(name="Direct Equip Duelist", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
    replacement = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert original_weapon is not None
    assert original_weapon.is_equipped

    def cancel_weapon_equip(event: Event, _source_entity_uuid) -> Event:
        return event.cancel(status_message="Test cancels direct weapon equip")

    entity.add_event_handler(
        EventHandler(
            name="Cancel Direct Weapon Equip",
            source_entity_uuid=entity.uuid,
            validation_only=True,
            event_processor=cancel_weapon_equip,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.WEAPON_EQUIP,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=entity.uuid,
                )
            ],
        )
    )

    result = entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

    assert result is False
    assert entity.equipment.weapon_melee_main is original_weapon
    assert original_weapon.is_equipped
    assert original_weapon.stored_in_uuid == entity.equipment.uuid
    assert not replacement.is_equipped
    assert replacement.equipped_slot is None
    assert replacement.owner_uuid is None
    assert replacement.stored_in_uuid is None


def test_eb_13_018_destroying_equipped_item_clears_slot_and_item_effects() -> None:
    """EB-13-018: equipped item destruction clears slots and derived values."""
    reset_item_state()
    entity = create_skeleton(name="Shield Breaker", position=(0, 0), darkvision=False)
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    shield.is_targetable = True
    shield.health = BaseItem.create_item_health(entity.uuid, hp=4)
    base_ac = entity.ac_bonus().normalized_score

    assert entity.equipment.equip(shield)
    assert entity.equipment.weapon_melee_off is shield
    assert entity.ac_bonus().normalized_score == base_ac + 2

    damage = shield.receive_damage(99, DamageType.BLUDGEONING, entity.uuid)

    assert damage > 0
    assert entity.equipment.weapon_melee_off is None
    assert entity.ac_bonus().normalized_score == base_ac
    assert not shield.is_equipped
    assert shield.equipped_slot is None
    assert shield.owner_uuid is None
    assert shield.stored_in_uuid is None
    assert BaseBlock.get(shield.uuid) is None

    armor = materialize_item(
        CHAIN_MAIL_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    armor.is_targetable = True
    armor.health = BaseItem.create_item_health(entity.uuid, hp=4)

    assert entity.equipment.equip(armor)
    assert entity.equipment.body_armor is armor
    assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert entity.action_economy.movement.normalized_score == 20

    armor_damage = armor.receive_damage(99, DamageType.BLUDGEONING, entity.uuid)

    assert armor_damage > 0
    assert entity.equipment.body_armor is None
    assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE
    assert entity.action_economy.movement.normalized_score == 30
    assert not armor.is_equipped
    assert armor.equipped_slot is None
    assert armor.owner_uuid is None
    assert armor.stored_in_uuid is None
    assert BaseBlock.get(armor.uuid) is None


def test_eb_13_019_equipment_damage_bonuses_are_counted_once() -> None:
    """EB-13-019: weapon damage composes each equipment bonus once."""
    reset_item_state()
    entity = create_skeleton(name="Damage Auditor", position=(0, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    bow = materialize_item(
        SHORTBOW_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    assert entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    assert entity.equipment.equip(bow, WeaponSlot.RANGED_MAIN)

    def damage_bonus(slot: WeaponSlot) -> int:
        damages = entity.equipment.get_damages(slot, entity.ability_scores)
        assert damages[0].damage_bonus is not None
        return damages[0].damage_bonus.normalized_score

    melee_base = damage_bonus(WeaponSlot.MELEE_MAIN)
    ranged_base = damage_bonus(WeaponSlot.RANGED_MAIN)

    entity.equipment.damage_bonus.self_static.add_value_modifier(
        NumericalModifier(
            name="General Weapon Focus",
            value=3,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
    )
    entity.equipment.melee_damage_bonus.self_static.add_value_modifier(
        NumericalModifier(
            name="Melee Style",
            value=5,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
    )
    entity.equipment.ranged_damage_bonus.self_static.add_value_modifier(
        NumericalModifier(
            name="Ranged Style",
            value=7,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
    )

    assert damage_bonus(WeaponSlot.MELEE_MAIN) == melee_base + 3 + 5
    assert damage_bonus(WeaponSlot.RANGED_MAIN) == ranged_base + 3 + 7


def test_eb_13_007_usable_item_actions_inject_user_and_item_identity() -> None:
    """EB-13-007: use actions are item-bound copies and depleted items expose none."""
    reset_item_state()
    entity = create_skeleton(name="Drinker", position=(0, 0), darkvision=False)
    potion = materialize_item(
        healing_potion_recipe(heal_amount=4),
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert isinstance(potion, UsableItem)
    put_in_inventory(entity, potion)

    actions = potion.get_use_actions(entity.uuid)

    assert len(actions) == 1
    assert actions[0].source_entity_uuid == entity.uuid
    assert actions[0].source_item_uuid == potion.uuid
    assert actions[0].uuid != potion.use_action_templates[0].uuid

    potion.charges = 0

    assert potion.get_use_actions(entity.uuid) == []


def test_eb_13_008_consumable_use_actions_consume_charges_and_stacks() -> None:
    """EB-13-008: successful item use consumes charge, stack, and finally the item."""
    reset_item_state()
    entity = create_skeleton(name="Patient", position=(0, 0), darkvision=False)
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert isinstance(potion, UsableItem)
    potion.stack_count = 2
    put_in_inventory(entity, potion)
    set_hp(entity, 1)

    first = execute_use_action(entity, potion.uuid, "Drink Potion")

    assert first is not None and not first.canceled
    assert get_hp(entity) == 8
    assert potion.stack_count == 1
    assert potion.charges == potion.max_charges
    assert entity.inventory.has_item(potion.uuid)
    assert BaseBlock.get(potion.uuid) is potion
    assert entity.action_economy.bonus_actions.normalized_score == 0

    # The second stack unit is consumed on a second legal turn, not by
    # bypassing the potion's bonus-action budget.
    entity.action_economy.reset_all_costs()
    second = execute_use_action(entity, potion.uuid, "Drink Potion")

    assert second is not None and not second.canceled
    assert get_hp(entity) == 15
    assert entity.action_economy.bonus_actions.normalized_score == 0
    assert not entity.inventory.has_item(potion.uuid)
    assert BaseBlock.get(potion.uuid) is None


def test_eb_13_020_generic_use_actions_require_sufficient_charges() -> None:
    """EB-13-020: generic usable actions cannot overspend item charges."""
    reset_item_state()
    entity = create_skeleton(name="Careful Patient", position=(0, 0), darkvision=False)
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert isinstance(potion, UsableItem)
    potion.charges = 1
    potion.max_charges = 2
    potion.use_action_templates[0].charge_cost = 2
    put_in_inventory(entity, potion)
    set_hp(entity, 1)

    assert potion.get_use_actions(entity.uuid) == []
    try:
        execute_use_action(entity, potion.uuid, "Drink Potion")
        assert False, "Use action executed without enough item charges"
    except ValueError as exc:
        assert "not found" in str(exc)

    assert get_hp(entity) == 1
    assert potion.charges == 1
    assert entity.inventory.has_item(potion.uuid)
    assert BaseBlock.get(potion.uuid) is potion


def test_eb_13_021_raw_inventory_add_rehomes_existing_locations() -> None:
    """EB-13-021: raw Inventory.add_item creates one authoritative location."""
    reset_item_state()
    first_owner = create_skeleton(name="First Holder", position=(0, 0), darkvision=False)
    second_owner = create_skeleton(name="Second Holder", position=(2, 0), darkvision=False)
    floor_item = BaseItem(source_entity_uuid=uuid4(), name="Map Case", weight=1)
    transferred_item = BaseItem(source_entity_uuid=uuid4(), name="Coin Purse", weight=1)

    floor_item.place_on_grid((1, 0))

    assert first_owner.inventory.add_item(floor_item)
    assert first_owner.inventory.has_item(floor_item.uuid)
    assert floor_item.owner_uuid == first_owner.uuid
    assert floor_item.stored_in_uuid == first_owner.inventory.uuid
    assert floor_item.tile_uuid is None
    assert get_map().get_object_position(floor_item.uuid) is None
    assert floor_item.get_position() == first_owner.position

    assert first_owner.inventory.add_item(transferred_item)
    assert first_owner.inventory.has_item(transferred_item.uuid)

    assert second_owner.inventory.add_item(transferred_item)

    assert not first_owner.inventory.has_item(transferred_item.uuid)
    assert second_owner.inventory.has_item(transferred_item.uuid)
    assert transferred_item.owner_uuid == second_owner.uuid
    assert transferred_item.stored_in_uuid == second_owner.inventory.uuid
    assert transferred_item.get_position() == second_owner.position


def test_eb_13_022_melee_and_ranged_slots_are_parallel_loadouts() -> None:
    """EB-13-022: melee and ranged equipment slots are parallel loadout sets."""
    reset_item_state()
    entity = create_skeleton(name="Loadout Switcher", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Practice Target", position=(1, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    bow = materialize_item(
        SHORTBOW_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    base_ac = entity.ac_bonus().normalized_score
    put_in_inventory(entity, sword)
    put_in_inventory(entity, shield)
    put_in_inventory(entity, bow)
    setup_standard_actions(entity)

    assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert entity.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)
    entity.update_entity_senses(max_distance=20)

    action_names = {action.template_name for action in entity.get_available_actions().entity_actions}

    assert entity.equipment.weapon_melee_main is sword
    assert entity.equipment.weapon_melee_off is shield
    assert entity.equipment.weapon_ranged_main is bow
    assert WeaponProperty.TWO_HANDED in bow.properties
    assert entity.ac_bonus().normalized_score == base_ac + 2
    assert "Attack_MELEE_MAIN" in action_names
    assert "Attack_RANGED_MAIN" in action_names
    assert target.uuid in entity.senses.entities


def test_eb_13_009_environment_use_actions_are_stateful_and_spatial() -> None:
    """EB-13-009: environment items provide state-dependent use actions."""
    reset_item_state()
    entity = create_skeleton(name="Explorer", position=(0, 0), darkvision=False)
    door = materialize_item(
        DOOR_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DoorObject,
    )
    get_map().place_object(door.uuid, (1, 0))
    entity.update_entity_senses(max_distance=5)

    assert door.uuid in entity.senses.objects
    assert door.blocks_movement
    assert [action.name for action in door.get_use_actions(entity.uuid)] == ["Open Door"]

    event = execute_use_action(entity, door.uuid, "Open Door")

    assert event is not None and not event.canceled
    assert door.is_open
    assert not door.blocks_movement
    assert [action.name for action in door.get_use_actions(entity.uuid)] == ["Close Door"]


def test_eb_13_010_breakable_items_destroy_and_spill_nested_inventory() -> None:
    """EB-13-010: destroying a container unregisters it and spills contents."""
    reset_item_state()
    chest = StorageChest(
        source_entity_uuid=uuid4(),
        is_targetable=True,
        health=BaseItem.create_item_health(uuid4(), hp=4),
    )
    gem = BaseItem(source_entity_uuid=uuid4(), name="Gem")
    assert chest.chest_inventory.add_item(gem)
    gem.owner_uuid = chest.uuid
    gem.stored_in_uuid = chest.chest_inventory.uuid
    chest.place_on_grid((2, 1))

    damage = chest.receive_damage(99, DamageType.BLUDGEONING, uuid4())

    assert damage > 0
    assert BaseBlock.get(chest.uuid) is None
    assert get_map().get_object_position(chest.uuid) is None
    assert BaseBlock.get(gem.uuid) is gem
    assert get_map().get_object_position(gem.uuid) == (2, 1)
    assert gem.owner_uuid is None
    assert gem.stored_in_uuid is None
    assert gem.tile_uuid is not None


def test_eb_13_011_torch_lifecycle_manages_attached_light_sources() -> None:
    """EB-13-011: torch use creates anchored light and drop cleanup removes it."""
    reset_item_state(default_light=LightLevel.DARKNESS)
    grid = get_map()
    entity = create_skeleton(name="Torchbearer", position=(0, 0), darkvision=False)
    torch = materialize_item(
        TORCH_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    put_in_inventory(entity, torch)
    origin_tile = grid.get_tile(0, 0)
    drop_tile = grid.get_tile(1, 0)
    assert origin_tile is not None
    assert drop_tile is not None

    assert torch.is_lit is False
    assert origin_tile.resolved_light_level == LightLevel.DARKNESS

    event = execute_use_action(entity, torch.uuid, "Ignite Torch")

    assert event is not None and not event.canceled
    assert torch.is_lit
    assert torch._light_source_uuid is not None
    assert origin_tile.resolved_light_level == LightLevel.VERY_BRIGHT
    flame_events = [
        candidate
        for candidate in EventQueue.get_events_by_type(
            EventType.SPATIAL_EFFECT_INTERACTION
        )
        if isinstance(candidate, SpatialEffectInteractionEvent)
        and candidate.operation is SpatialEffectInteractionOperation.IGNITE
        and candidate.source_object_uuid == torch.uuid
    ]
    assert [candidate.phase for candidate in flame_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    parent_ids = {candidate.parent_event for candidate in flame_events}
    assert len(parent_ids) == 1
    parent_id = next(iter(parent_ids))
    assert parent_id is not None
    flame_parent = EventQueue.get_event_by_uuid(parent_id)
    assert flame_parent is not None
    assert flame_parent.lineage_uuid == event.lineage_uuid

    dropped = entity.drop_item(torch.uuid, (1, 0))

    assert dropped is torch
    assert torch.is_lit is False
    assert torch._light_source_uuid is None
    assert grid.get_object_position(torch.uuid) == (1, 0)
    assert origin_tile.resolved_light_level == LightLevel.DARKNESS
    assert drop_tile.resolved_light_level == LightLevel.DARKNESS


def test_torches_do_not_commit_lit_state_without_a_light_anchor() -> None:
    """Invalid portable and fixture anchors cannot create partial lit state."""
    reset_item_state(default_light=LightLevel.DARKNESS)
    portable = materialize_item(
        TORCH_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    fixture = WallTorch(source_entity_uuid=uuid4())

    portable.ignite(uuid4())
    fixture.light()

    assert portable.is_lit is False
    assert portable._light_source_uuid is None
    assert fixture.is_lit is False
    assert fixture._light_source_uuid is None


def test_item_damage_declaration_veto_prevents_breakage() -> None:
    """Breakable objects must honor the canonical damage declaration veto."""
    reset_item_state()
    source = create_skeleton(name="Source", position=(0, 0))
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name="Protected Crate",
        is_targetable=True,
        health=BaseItem.create_item_health(uuid4(), hp=8),
    )
    hp_before = item.get_hp()

    def veto_damage(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Object damage vetoed")

    item.add_event_handler(
        EventHandler(
            source_entity_uuid=item.uuid,
            name="Protect object from damage",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=item.uuid,
                ),
            ],
            event_processor=veto_damage,
        )
    )

    applied = item.receive_damage(
        99,
        DamageType.BLUDGEONING,
        source.uuid,
    )

    assert applied == 0
    assert item.get_hp() == hp_before
    assert BaseBlock.get(item.uuid) is item


if __name__ == "__main__":
    tests = [
        test_eb_13_001_floor_loot_and_drop_update_authoritative_location,
        test_eb_13_002_inventory_stack_merge_can_consume_or_split_items,
        test_eb_13_003_inventory_capacity_and_transfer_update_container_fields,
        test_eb_13_012_partial_stack_merge_is_atomic_on_capacity_failure,
        test_eb_13_017_transfer_to_existing_stack_consumes_incoming_location,
        test_eb_13_004_equip_and_unequip_move_items_between_inventory_and_equipment,
        test_eb_13_005_equipment_validates_weapon_slots_and_replaces_existing_items,
        test_eb_13_006_equipment_hooks_apply_and_remove_modifiers,
        test_eb_13_013_canceled_high_level_equip_preserves_inventory_item,
        test_eb_13_014_two_handed_melee_conflicts_auto_displace_by_equip_order,
        test_eb_13_015_heavy_armor_strength_requirement_reduces_speed,
        test_eb_13_016_canceled_direct_equip_preserves_existing_slot_item,
        test_eb_13_018_destroying_equipped_item_clears_slot_and_item_effects,
        test_eb_13_019_equipment_damage_bonuses_are_counted_once,
        test_eb_13_007_usable_item_actions_inject_user_and_item_identity,
        test_eb_13_008_consumable_use_actions_consume_charges_and_stacks,
        test_eb_13_020_generic_use_actions_require_sufficient_charges,
        test_eb_13_021_raw_inventory_add_rehomes_existing_locations,
        test_eb_13_022_melee_and_ranged_slots_are_parallel_loadouts,
        test_eb_13_009_environment_use_actions_are_stateful_and_spatial,
        test_eb_13_010_breakable_items_destroy_and_spill_nested_inventory,
        test_eb_13_011_torch_lifecycle_manages_attached_light_sources,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: PASS")
