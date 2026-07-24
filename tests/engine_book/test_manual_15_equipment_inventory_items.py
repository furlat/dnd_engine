"""Manual Chapter 15 checks for equipment, inventory, and items."""

from uuid import uuid4

from dnd.actions_functional import execute_use_action, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.inventory import Inventory
from dnd.core.base_actions import AvailableActionInfo
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.items import (
    DirectionalDoor,
    create_greatsword,
    create_healing_potion,
    create_shield,
    create_shortbow,
    create_shortsword,
)
from dnd.utils import reset_combat_state


def reset_item_tutorial_state(width: int = 8, height: int = 4) -> None:
    """Clear global state and create a small item tutorial arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_item_actor(
    name: str,
    position: tuple[int, int],
    faction: str = "heroes",
    strength: int = 14,
    dexterity: int = 14,
) -> Entity:
    """Create an actor with inventory, equipment, health, and action resources."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=2,
                        mode="maximums",
                    )
                ],
            ),
            action_economy=ActionEconomyConfig(movement=30),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )


def put_in_inventory(entity: Entity, item: BaseItem) -> None:
    """Store an item in an actor inventory for examples that start with carried gear."""
    assert entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid


def find_action(actions, template_name: str) -> AvailableActionInfo:
    """Return the discovered action row with the requested template name."""
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def test_floor_inventory_and_drop_are_authoritative_item_locations() -> None:
    """Floor, inventory, and dropped item state are mutually exclusive."""
    reset_item_tutorial_state()
    hero = create_item_actor("Collector", (0, 0))
    key = BaseItem(source_entity_uuid=uuid4(), name="Silver Key", weight=1)

    key.place_on_grid((1, 0))

    assert key.tile_uuid is not None
    assert key.get_position() == (1, 0)
    assert get_map().get_object_position(key.uuid) == (1, 0)

    assert hero.loot_item(key)

    assert hero.inventory.has_item(key.uuid)
    assert key.owner_uuid == hero.uuid
    assert key.stored_in_uuid == hero.inventory.uuid
    assert key.tile_uuid is None
    assert get_map().get_object_position(key.uuid) is None
    assert key.get_position() == hero.position

    dropped = hero.drop_item(key.uuid, position=(0, 1))

    assert dropped is key
    assert not hero.inventory.has_item(key.uuid)
    assert key.owner_uuid is None
    assert key.stored_in_uuid is None
    assert key.tile_uuid is not None
    assert key.get_position() == (0, 1)
    assert get_map().get_object_position(key.uuid) == (0, 1)


def test_inventory_stacks_merge_and_capacity_failure_is_atomic() -> None:
    """Stacking consumes compatible item objects only when the insert can succeed."""
    reset_item_tutorial_state()
    inventory = Inventory(source_entity_uuid=uuid4(), name="Potion Satchel", weight_capacity=10)
    existing = create_healing_potion(inventory.source_entity_uuid)
    incoming = create_healing_potion(inventory.source_entity_uuid)
    third = create_healing_potion(inventory.source_entity_uuid)
    existing.weight = 1
    incoming.weight = 1
    third.weight = 1
    existing.stack_count = 8
    incoming.stack_count = 2
    third.stack_count = 5

    assert inventory.add_item(existing)
    assert inventory.add_item(incoming)

    assert existing.stack_count == 10
    assert incoming.stack_count == 0
    assert BaseBlock.get(incoming.uuid) is None
    assert inventory.item_count == 1

    result = inventory.add_item(third)

    assert result is False
    assert existing.stack_count == 10
    assert third.stack_count == 5
    assert not inventory.has_item(third.uuid)
    assert inventory.total_weight == 10


def test_high_level_equip_and_unequip_move_items_between_inventory_and_equipment() -> None:
    """Entity equipment helpers rehome carried gear across inventory and equipment."""
    reset_item_tutorial_state()
    hero = create_item_actor("Duelist", (0, 0))
    sword = create_shortsword(hero.uuid)
    put_in_inventory(hero, sword)

    assert hero.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)

    assert hero.equipment.weapon_melee_main is sword
    assert not hero.inventory.has_item(sword.uuid)
    assert sword.is_equipped
    assert sword.equipped_slot == WeaponSlot.MELEE_MAIN.value
    assert sword.owner_uuid == hero.uuid
    assert sword.stored_in_uuid == hero.equipment.uuid

    unequipped = hero.unequip_item(WeaponSlot.MELEE_MAIN)

    assert unequipped is sword
    assert hero.equipment.weapon_melee_main is None
    assert hero.inventory.has_item(sword.uuid)
    assert not sword.is_equipped
    assert sword.equipped_slot is None
    assert sword.stored_in_uuid == hero.inventory.uuid


def test_two_handed_melee_and_off_hand_conflicts_displace_by_equip_order() -> None:
    """New melee equips displace conflicts based on the Two-Handed property."""
    reset_item_tutorial_state()
    hero = create_item_actor("Greatsword Guard", (0, 0))
    greatsword = create_greatsword(hero.uuid)
    shield = create_shield(hero.uuid)
    put_in_inventory(hero, greatsword)
    put_in_inventory(hero, shield)

    assert hero.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)
    assert hero.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)

    assert hero.equipment.weapon_melee_main is None
    assert hero.equipment.weapon_melee_off is shield
    assert not greatsword.is_equipped
    assert hero.inventory.has_item(greatsword.uuid)
    assert greatsword.stored_in_uuid == hero.inventory.uuid

    second = create_item_actor("Shielded Guard", (1, 0))
    second_greatsword = create_greatsword(second.uuid)
    second_shield = create_shield(second.uuid)
    put_in_inventory(second, second_greatsword)
    put_in_inventory(second, second_shield)

    assert second.equip_item(second_shield.uuid, WeaponSlot.MELEE_OFF)
    assert second.equip_item(second_greatsword.uuid, WeaponSlot.MELEE_MAIN)

    assert second.equipment.weapon_melee_main is second_greatsword
    assert second.equipment.weapon_melee_off is None
    assert second_greatsword.is_equipped
    assert second.inventory.has_item(second_shield.uuid)
    assert not second_shield.is_equipped


def test_melee_and_ranged_slots_are_parallel_videogame_loadouts() -> None:
    """A shielded melee loadout can coexist with a ranged weapon loadout."""
    reset_item_tutorial_state()
    hero = create_item_actor("Loadout Switcher", (0, 0), "heroes")
    target = create_item_actor("Practice Target", (1, 0), "monsters")
    sword = create_shortsword(hero.uuid)
    shield = create_shield(hero.uuid)
    bow = create_shortbow(hero.uuid)
    base_ac = hero.ac_bonus().normalized_score
    put_in_inventory(hero, sword)
    put_in_inventory(hero, shield)
    put_in_inventory(hero, bow)
    setup_standard_actions(hero)

    assert hero.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert hero.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert hero.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)
    Entity.update_all_entities_senses(max_distance=20)

    available = get_available_actions(hero)
    melee_attack = find_action(available, "Attack_MELEE_MAIN")
    ranged_attack = find_action(available, "Attack_RANGED_MAIN")

    assert hero.equipment.weapon_melee_main is sword
    assert hero.equipment.weapon_melee_off is shield
    assert hero.equipment.weapon_ranged_main is bow
    assert hero.ac_bonus().normalized_score == base_ac + 2
    assert [target_info.target_uuid for target_info in melee_attack.valid_targets] == [target.uuid]
    assert [target_info.target_uuid for target_info in ranged_attack.valid_targets] == [target.uuid]


def test_consumable_use_actions_bind_to_items_and_consume_stacks() -> None:
    """Usable items expose cloned actions and successful use spends item charges."""
    reset_item_tutorial_state()
    hero = create_item_actor("Patient", (0, 0))
    potion = create_healing_potion(hero.uuid, heal_amount=7)
    potion.stack_count = 2
    put_in_inventory(hero, potion)
    hero.receive_damage(10, DamageType.SLASHING, source_entity_uuid=hero.uuid)
    hp_before = hero.get_hp()

    actions = potion.get_use_actions(hero.uuid)

    assert len(actions) == 1
    assert actions[0].source_entity_uuid == hero.uuid
    assert actions[0].source_item_uuid == potion.uuid
    assert actions[0].uuid != potion.use_action_templates[0].uuid

    first = execute_use_action(hero, potion.uuid, "Drink Potion")

    assert first is not None and not first.canceled
    assert first.phase == EventPhase.COMPLETION
    assert hero.get_hp() == hp_before + 7
    assert potion.stack_count == 1
    assert hero.inventory.has_item(potion.uuid)

    hero.action_economy.reset_all_costs()
    second = execute_use_action(hero, potion.uuid, "Drink Potion")

    assert second is not None and not second.canceled
    assert not hero.inventory.has_item(potion.uuid)
    assert BaseBlock.get(potion.uuid) is None


def test_environment_objects_surface_stateful_use_actions_from_the_grid() -> None:
    """Usable environment items expose actions based on object state and position."""
    reset_item_tutorial_state()
    hero = create_item_actor("Explorer", (0, 0))
    door = DirectionalDoor(source_entity_uuid=uuid4())
    get_map().place_object(door.uuid, (1, 0))
    hero.update_entity_senses(max_distance=10)

    assert door.uuid in hero.senses.objects
    assert door.blocks_directional_movement("north")
    assert [action.name for action in door.get_use_actions(hero.uuid)] == ["Open Door"]

    event = execute_use_action(hero, door.uuid, "Open Door")

    assert event is not None and not event.canceled
    assert door.is_open
    assert not door.blocks_directional_movement("north")
    assert [action.name for action in door.get_use_actions(hero.uuid)] == ["Close Door"]
