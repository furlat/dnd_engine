"""Tutorial tests for item locations, inventory, equipment, and usable objects."""

from uuid import UUID, uuid4

from dnd.actions.operations import execute_use_action
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import (
    BaseItem,
    UsableItem,
)
from dnd.core.events.item_events import (
    ItemChargeConsumptionEvent,
)
from dnd.blocks.equipment import (
    BodyArmor,
    EquipmentConfig,
    Shield,
    Weapon,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.inventory import Inventory
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.presentation import ActionPresentationKind
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.types.conditions import ConditionTag
from dnd.types.equipment import BodyPart, WeaponProperty, WeaponSlot
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.resolution_events import (
    Range,
    RangeType,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.items.consumables import (
    GREATER_INVISIBILITY_POTION_RECIPE,
    HASTE_POTION_RECIPE,
    HEALING_POTION_RECIPE,
    healing_potion_recipe,
)
from dnd.items.armors import CHAIN_MAIL_RECIPE, SHIELD_RECIPE
from dnd.items.environment import DirectionalDoor as TutorialDoor
from dnd.items.environment_content import directional_door_recipe
from dnd.items.weapons import (
    GREATSWORD_RECIPE,
    SHORTBOW_RECIPE,
    SHORTSWORD_RECIPE,
)
from dnd.conditions import GreaterInvisibilityEffect
from dnd.spells.transmutation import HasteEffect


def reset_item_tutorial_state() -> None:
    """Clear global state and create a small tutorial grid."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 8, 4)


def create_tutorial_actor(
    name: str,
    position: tuple[int, int] = (0, 0),
    strength: int = 14,
    dexterity: int = 14,
) -> Entity:
    """Create a plain actor with inventory, equipment, HP, and action economy."""
    actor_id = uuid4()
    config = EntityConfig(
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
                HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
            ]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction="heroes",
    )
    return Entity.create(source_entity_uuid=actor_id, name=name, config=config)


def put_in_inventory(entity: Entity, item: BaseItem) -> None:
    """Store an item in an actor inventory through the real inventory boundary."""
    assert entity.inventory.add_item(item)


def create_tutorial_hand_crossbow(source_id: UUID) -> Weapon:
    """Create a light ranged weapon for ranged off-hand loadout examples."""
    return Weapon(
        source_entity_uuid=source_id,
        name="Tutorial Hand Crossbow",
        description="A light one-handed ranged weapon for loadout examples.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.LIGHT],
        range=Range(type=RangeType.RANGE, normal=30, long=120),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus",
        ),
    )


def test_first_item_example_prints_visible_location_lifecycle(capsys) -> None:
    """One item prints floor, inventory, and dropped location states."""
    reset_item_tutorial_state()
    collector = create_tutorial_actor("Collector", position=(0, 0))
    key = BaseItem(source_entity_uuid=uuid4(), name="Silver Key", weight=1)

    key.place_on_grid((1, 0))
    floor_state = (
        key.get_position(),
        get_map().get_object_position(key.uuid),
        key.owner_uuid is None,
        key.stored_in_uuid is None,
        key.tile_uuid is not None,
    )

    assert collector.loot_item(key)
    inventory_state = (
        collector.inventory.has_item(key.uuid),
        key.owner_uuid == collector.uuid,
        key.stored_in_uuid == collector.inventory.uuid,
        key.tile_uuid is None,
        key.get_position(),
        get_map().get_object_position(key.uuid),
    )

    dropped = collector.drop_item(key.uuid, position=(0, 1))
    drop_state = (
        dropped is key,
        collector.inventory.has_item(key.uuid),
        key.owner_uuid is None,
        key.stored_in_uuid is None,
        key.tile_uuid is not None,
        key.get_position(),
        get_map().get_object_position(key.uuid),
    )

    readout_lines = [
        f"item: {key.name}",
        f"floor position: item={floor_state[0]}, map={floor_state[1]}",
        (
            "floor fields: "
            f"owner missing={floor_state[2]}, "
            f"stored missing={floor_state[3]}, "
            f"tile set={floor_state[4]}"
        ),
        f"inventory contains item: {inventory_state[0]}",
        (
            "inventory fields: "
            f"owner set={inventory_state[1]}, "
            f"stored set={inventory_state[2]}, "
            f"tile cleared={inventory_state[3]}"
        ),
        f"inventory position follows actor: {inventory_state[4]}",
        f"map position while carried: {inventory_state[5]}",
        f"drop returned same item: {drop_state[0]}",
        f"drop position: item={drop_state[5]}, map={drop_state[6]}",
        (
            "drop fields: "
            f"in inventory={drop_state[1]}, "
            f"owner missing={drop_state[2]}, "
            f"stored missing={drop_state[3]}, "
            f"tile set={drop_state[4]}"
        ),
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "item: Silver Key",
        "floor position: item=(1, 0), map=(1, 0)",
        "floor fields: owner missing=True, stored missing=True, tile set=True",
        "inventory contains item: True",
        "inventory fields: owner set=True, stored set=True, tile cleared=True",
        "inventory position follows actor: (0, 0)",
        "map position while carried: None",
        "drop returned same item: True",
        "drop position: item=(0, 1), map=(0, 1)",
        "drop fields: in inventory=False, owner missing=True, stored missing=True, tile set=True",
    ]
    assert readout_lines == expected_lines
    assert dropped is key
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_items_move_between_floor_inventory_and_drop_locations(capsys) -> None:
    """An item has one authoritative location at a time."""
    reset_item_tutorial_state()
    collector = create_tutorial_actor("Collector", position=(0, 0))
    key = BaseItem(source_entity_uuid=uuid4(), name="Silver Key", weight=1)

    key.place_on_grid((1, 0))

    assert key.owner_uuid is None
    assert key.stored_in_uuid is None
    assert key.tile_uuid is not None
    assert key.get_position() == (1, 0)
    assert get_map().get_object_position(key.uuid) == (1, 0)
    floor_state = (
        key.get_position(),
        get_map().get_object_position(key.uuid),
        key.owner_uuid is None,
        key.stored_in_uuid is None,
        key.tile_uuid is not None,
    )

    assert collector.loot_item(key)

    assert collector.inventory.has_item(key.uuid)
    assert key.owner_uuid == collector.uuid
    assert key.stored_in_uuid == collector.inventory.uuid
    assert key.tile_uuid is None
    assert key.get_position() == collector.position
    assert get_map().get_object_position(key.uuid) is None
    inventory_state = (
        collector.inventory.has_item(key.uuid),
        key.owner_uuid == collector.uuid,
        key.stored_in_uuid == collector.inventory.uuid,
        key.tile_uuid is None,
        key.get_position(),
        get_map().get_object_position(key.uuid),
    )

    dropped = collector.drop_item(key.uuid, position=(0, 1))

    assert dropped is key
    assert not collector.inventory.has_item(key.uuid)
    assert key.owner_uuid is None
    assert key.stored_in_uuid is None
    assert key.tile_uuid is not None
    assert key.get_position() == (0, 1)
    assert get_map().get_object_position(key.uuid) == (0, 1)
    drop_state = (
        dropped is key,
        collector.inventory.has_item(key.uuid),
        key.owner_uuid is None,
        key.stored_in_uuid is None,
        key.tile_uuid is not None,
        key.get_position(),
        get_map().get_object_position(key.uuid),
    )

    location_lines = [
        f"floor position: item={floor_state[0]}, map={floor_state[1]}",
        (
            "floor ownership: "
            f"owner_missing={floor_state[2]}, "
            f"stored_missing={floor_state[3]}, "
            f"tile_set={floor_state[4]}"
        ),
        f"inventory contains item: {inventory_state[0]}",
        (
            "inventory ownership: "
            f"owner_set={inventory_state[1]}, "
            f"stored_set={inventory_state[2]}, "
            f"tile_cleared={inventory_state[3]}"
        ),
        f"inventory position: item={inventory_state[4]}, map={inventory_state[5]}",
        f"drop returned same item: {drop_state[0]}",
        f"drop position: item={drop_state[5]}, map={drop_state[6]}",
        (
            "drop ownership: "
            f"in_inventory={drop_state[1]}, "
            f"owner_missing={drop_state[2]}, "
            f"stored_missing={drop_state[3]}, "
            f"tile_set={drop_state[4]}"
        ),
    ]

    print("\n".join(location_lines))

    expected_location_lines = [
        "floor position: item=(1, 0), map=(1, 0)",
        "floor ownership: owner_missing=True, stored_missing=True, tile_set=True",
        "inventory contains item: True",
        "inventory ownership: owner_set=True, stored_set=True, tile_cleared=True",
        "inventory position: item=(0, 0), map=None",
        "drop returned same item: True",
        "drop position: item=(0, 1), map=(0, 1)",
        "drop ownership: in_inventory=False, owner_missing=True, stored_missing=True, tile_set=True",
    ]
    assert location_lines == expected_location_lines
    assert capsys.readouterr().out.splitlines() == expected_location_lines


def test_inventory_stacks_and_capacity_are_atomic(capsys) -> None:
    """Stack merges consume incoming objects only when the full insert succeeds."""
    reset_item_tutorial_state()
    alchemist = create_tutorial_actor("Alchemist")
    first = materialize_item(
        HEALING_POTION_RECIPE,
        alchemist.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    second = materialize_item(
        HEALING_POTION_RECIPE,
        alchemist.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    third = materialize_item(
        HEALING_POTION_RECIPE,
        alchemist.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    first.stack_count = 8
    second.stack_count = 2
    third.stack_count = 5

    assert alchemist.inventory.add_item(first)
    assert alchemist.inventory.add_item(second)

    assert first.stack_count == 10
    assert second.stack_count == 0
    assert not alchemist.inventory.has_item(second.uuid)
    assert BaseBlock.get(second.uuid) is None
    merge_state = (
        first.stack_count,
        second.stack_count,
        alchemist.inventory.has_item(second.uuid),
        BaseBlock.get(second.uuid) is None,
        alchemist.inventory.item_count,
    )

    assert alchemist.inventory.add_item(third)

    assert first.stack_count == 10
    assert third.stack_count == 5
    assert alchemist.inventory.item_count == 2
    overflow_state = (
        first.stack_count,
        third.stack_count,
        alchemist.inventory.item_count,
    )

    tight_pack = Inventory(
        source_entity_uuid=alchemist.uuid,
        name="Tight Pack",
        weight_capacity=10,
    )
    existing = materialize_item(
        healing_potion_recipe(heal_amount=4),
        alchemist.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    incoming = materialize_item(
        healing_potion_recipe(heal_amount=4),
        alchemist.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    existing.stack_count = 8
    incoming.stack_count = 5
    existing.weight = 1
    incoming.weight = 1

    assert tight_pack.add_item(existing)
    result = tight_pack.add_item(incoming)

    assert result is False
    assert existing.stack_count == 8
    assert incoming.stack_count == 5
    assert not tight_pack.has_item(incoming.uuid)
    assert tight_pack.total_weight == 8

    stack_lines = [
        f"merge stack count: first={merge_state[0]}, second={merge_state[1]}",
        f"second consumed: in_inventory={merge_state[2]}, unregistered={merge_state[3]}",
        f"inventory count after merge: {merge_state[4]}",
        (
            "third stack carried separately: "
            f"first={overflow_state[0]}, third={overflow_state[1]}, "
            f"item_count={overflow_state[2]}"
        ),
        f"overweight insert accepted: {result}",
        (
            "tight pack after reject: "
            f"existing={existing.stack_count}, incoming={incoming.stack_count}, "
            f"has_incoming={tight_pack.has_item(incoming.uuid)}, "
            f"weight={tight_pack.total_weight}"
        ),
    ]

    print("\n".join(stack_lines))

    expected_stack_lines = [
        "merge stack count: first=10, second=0",
        "second consumed: in_inventory=False, unregistered=True",
        "inventory count after merge: 1",
        "third stack carried separately: first=10, third=5, item_count=2",
        "overweight insert accepted: False",
        "tight pack after reject: existing=8, incoming=5, has_incoming=False, weight=8",
    ]
    assert stack_lines == expected_stack_lines
    assert capsys.readouterr().out.splitlines() == expected_stack_lines


def test_equipment_moves_items_and_applies_equipment_effects(capsys) -> None:
    """Equipping gear moves it out of inventory and applies item hooks."""
    reset_item_tutorial_state()
    guard = create_tutorial_actor("Guard", strength=10)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        guard.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        guard.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    armor = materialize_item(
        CHAIN_MAIL_RECIPE,
        guard.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    put_in_inventory(guard, sword)
    put_in_inventory(guard, shield)
    put_in_inventory(guard, armor)

    base_ac = guard.ac_bonus().normalized_score
    base_movement = guard.action_economy.movement.normalized_score

    assert guard.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert guard.equipment.weapon_melee_main is sword
    assert not guard.inventory.has_item(sword.uuid)
    assert sword.is_equipped
    assert sword.equipped_slot == WeaponSlot.MELEE_MAIN.value
    assert sword.stored_in_uuid == guard.equipment.uuid
    sword_state = (
        guard.equipment.weapon_melee_main is sword,
        guard.inventory.has_item(sword.uuid),
        sword.is_equipped,
        sword.equipped_slot,
        sword.stored_in_uuid == guard.equipment.uuid,
    )

    assert guard.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert guard.equipment.weapon_melee_off is shield
    assert guard.ac_bonus().normalized_score == base_ac + 2
    shield_state = (
        guard.equipment.weapon_melee_off is shield,
        guard.ac_bonus().normalized_score,
    )

    assert guard.equip_item(armor.uuid, BodyPart.BODY)
    assert guard.equipment.body_armor is armor
    assert armor.is_equipped
    assert guard.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert guard.action_economy.movement.normalized_score == base_movement - 10
    armor_state = (
        guard.equipment.body_armor is armor,
        armor.is_equipped,
        guard.skill_set.stealth.skill_bonus.advantage,
        guard.action_economy.movement.normalized_score,
    )

    unequipped = guard.unequip_item(WeaponSlot.MELEE_MAIN)

    assert unequipped is sword
    assert guard.equipment.weapon_melee_main is None
    assert guard.inventory.has_item(sword.uuid)
    assert not sword.is_equipped
    assert sword.stored_in_uuid == guard.inventory.uuid
    unequip_state = (
        unequipped is sword,
        guard.equipment.weapon_melee_main is None,
        guard.inventory.has_item(sword.uuid),
        sword.is_equipped,
        sword.stored_in_uuid == guard.inventory.uuid,
    )

    equipment_lines = [
        f"base ac/movement: {base_ac}/{base_movement}",
        (
            "sword equipped: "
            f"slot_main={sword_state[0]}, "
            f"in_inventory={sword_state[1]}, "
            f"is_equipped={sword_state[2]}, "
            f"slot={sword_state[3]}, "
            f"in_equipment={sword_state[4]}"
        ),
        f"shield equipped: offhand={shield_state[0]}, ac={base_ac}->{shield_state[1]}",
        (
            "armor equipped: "
            f"body={armor_state[0]}, "
            f"is_equipped={armor_state[1]}, "
            f"stealth={armor_state[2].value}, "
            f"movement={base_movement}->{armor_state[3]}"
        ),
        (
            "unequip sword: "
            f"same_item={unequip_state[0]}, "
            f"main_empty={unequip_state[1]}, "
            f"in_inventory={unequip_state[2]}, "
            f"is_equipped={unequip_state[3]}, "
            f"stored_in_inventory={unequip_state[4]}"
        ),
    ]

    print("\n".join(equipment_lines))

    expected_equipment_lines = [
        "base ac/movement: 12/30",
        "sword equipped: slot_main=True, in_inventory=False, is_equipped=True, slot=MELEE_MAIN, in_equipment=True",
        "shield equipped: offhand=True, ac=12->14",
        "armor equipped: body=True, is_equipped=True, stealth=Disadvantage, movement=30->20",
        "unequip sword: same_item=True, main_empty=True, in_inventory=True, is_equipped=False, stored_in_inventory=True",
    ]
    assert equipment_lines == expected_equipment_lines
    assert capsys.readouterr().out.splitlines() == expected_equipment_lines


def test_two_handed_melee_displaces_by_order_while_ranged_loadout_stays_parallel(
    capsys,
) -> None:
    """Melee hand conflicts displace older gear; ranged slots are independent."""
    reset_item_tutorial_state()
    warrior = create_tutorial_actor("Warrior")
    greatsword = materialize_item(
        GREATSWORD_RECIPE,
        warrior.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        warrior.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    put_in_inventory(warrior, greatsword)
    put_in_inventory(warrior, shield)

    assert warrior.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)
    assert warrior.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)

    assert warrior.equipment.weapon_melee_main is None
    assert warrior.equipment.weapon_melee_off is shield
    assert not greatsword.is_equipped
    assert greatsword.equipped_slot is None
    assert warrior.inventory.has_item(greatsword.uuid)
    first_case = (
        warrior.equipment.weapon_melee_main,
        warrior.equipment.weapon_melee_off.name
        if warrior.equipment.weapon_melee_off
        else None,
        greatsword.is_equipped,
        greatsword.equipped_slot,
        warrior.inventory.has_item(greatsword.uuid),
    )

    second = create_tutorial_actor("Second Warrior", position=(2, 0))
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
    assert second.inventory.has_item(second_shield.uuid)
    assert second_greatsword.is_equipped
    assert not second_shield.is_equipped
    second_case = (
        second.equipment.weapon_melee_main.name
        if second.equipment.weapon_melee_main
        else None,
        second.equipment.weapon_melee_off,
        second.inventory.has_item(second_shield.uuid),
        second_greatsword.is_equipped,
        second_shield.is_equipped,
    )

    skirmisher = create_tutorial_actor("Skirmisher", position=(4, 0))
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        skirmisher.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    skirmisher_shield = materialize_item(
        SHIELD_RECIPE,
        skirmisher.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    bow = materialize_item(
        SHORTBOW_RECIPE,
        skirmisher.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    main_crossbow = create_tutorial_hand_crossbow(skirmisher.uuid)
    off_crossbow = create_tutorial_hand_crossbow(skirmisher.uuid)
    for item in [sword, skirmisher_shield, bow, main_crossbow, off_crossbow]:
        put_in_inventory(skirmisher, item)

    assert skirmisher.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert skirmisher.equip_item(skirmisher_shield.uuid, WeaponSlot.MELEE_OFF)
    assert skirmisher.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)

    melee_main = skirmisher.equipment.weapon_melee_main
    melee_off = skirmisher.equipment.weapon_melee_off
    ranged_main = skirmisher.equipment.weapon_ranged_main
    assert melee_main is not None
    assert melee_off is not None
    assert ranged_main is not None
    assert melee_main is sword
    assert melee_off is skirmisher_shield
    assert ranged_main is bow
    assert WeaponProperty.TWO_HANDED in bow.properties
    assert WeaponProperty.RANGED in bow.properties
    bow_state = (
        melee_main.name,
        melee_off.name,
        ranged_main.name,
        WeaponProperty.TWO_HANDED in bow.properties,
        WeaponProperty.RANGED in bow.properties,
    )

    assert skirmisher.equip_item(main_crossbow.uuid, WeaponSlot.RANGED_MAIN)
    assert skirmisher.equip_item(off_crossbow.uuid, WeaponSlot.RANGED_OFF)

    melee_main = skirmisher.equipment.weapon_melee_main
    melee_off = skirmisher.equipment.weapon_melee_off
    ranged_main = skirmisher.equipment.weapon_ranged_main
    ranged_off = skirmisher.equipment.weapon_ranged_off
    assert melee_main is not None
    assert melee_off is not None
    assert ranged_main is not None
    assert ranged_off is not None
    assert melee_main is sword
    assert melee_off is skirmisher_shield
    assert ranged_main is main_crossbow
    assert ranged_off is off_crossbow
    assert skirmisher.inventory.has_item(bow.uuid)
    parallel_state = (
        melee_main.name,
        melee_off.name,
        ranged_main.name,
        ranged_off.name,
        skirmisher.inventory.has_item(bow.uuid),
    )

    loadout_lines = [
        (
            "greatsword then shield: "
            f"main={first_case[0]}, "
            f"off={first_case[1]}, "
            f"greatsword_equipped={first_case[2]}, "
            f"greatsword_slot={first_case[3]}, "
            f"greatsword_in_inventory={first_case[4]}"
        ),
        (
            "shield then greatsword: "
            f"main={second_case[0]}, "
            f"off={second_case[1]}, "
            f"shield_in_inventory={second_case[2]}, "
            f"greatsword_equipped={second_case[3]}, "
            f"shield_equipped={second_case[4]}"
        ),
        (
            "melee plus bow: "
            f"melee={bow_state[0]} + {bow_state[1]}, "
            f"ranged={bow_state[2]}, "
            f"bow_two_handed={bow_state[3]}, "
            f"bow_ranged={bow_state[4]}"
        ),
        (
            "paired crossbows: "
            f"melee={parallel_state[0]} + {parallel_state[1]}, "
            f"ranged={parallel_state[2]} + {parallel_state[3]}, "
            f"bow_in_inventory={parallel_state[4]}"
        ),
    ]

    print("\n".join(loadout_lines))

    expected_loadout_lines = [
        "greatsword then shield: main=None, off=Shield, greatsword_equipped=False, greatsword_slot=None, greatsword_in_inventory=True",
        "shield then greatsword: main=Greatsword, off=None, shield_in_inventory=True, greatsword_equipped=True, shield_equipped=False",
        "melee plus bow: melee=Shortsword + Shield, ranged=Shortbow, bow_two_handed=True, bow_ranged=True",
        "paired crossbows: melee=Shortsword + Shield, ranged=Tutorial Hand Crossbow + Tutorial Hand Crossbow, bow_in_inventory=True",
    ]
    assert loadout_lines == expected_loadout_lines
    assert capsys.readouterr().out.splitlines() == expected_loadout_lines


def test_usable_items_and_environment_objects_expose_item_bound_actions(capsys) -> None:
    """Usable items clone actions with user and item identity at use time."""
    reset_item_tutorial_state()
    patient = create_tutorial_actor("Patient")
    potion = materialize_item(
        HEALING_POTION_RECIPE,
        patient.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )
    potion.stack_count = 2
    put_in_inventory(patient, potion)

    full_hp = patient.get_hp()
    damage_taken = patient.receive_damage(6, DamageType.SLASHING, patient.uuid)
    wounded_hp = patient.get_hp()
    assert damage_taken == 6
    assert wounded_hp == full_hp - 6

    drink = potion.get_use_actions(patient.uuid)[0]

    assert drink.name == "Drink Potion"
    assert drink.source_entity_uuid == patient.uuid
    assert drink.source_item_uuid == potion.uuid
    assert drink.uuid != potion.use_action_templates[0].uuid
    drink_clone_state = (
        drink.name,
        drink.source_entity_uuid == patient.uuid,
        drink.source_item_uuid == potion.uuid,
        drink.uuid != potion.use_action_templates[0].uuid,
    )

    first_drink = execute_use_action(patient, potion.uuid, "Drink Potion")

    assert isinstance(first_drink, ActionEvent)
    assert not first_drink.canceled
    assert first_drink.presentation_kind is ActionPresentationKind.DRINK
    assert patient.get_hp() == full_hp
    assert patient.action_economy.bonus_actions.normalized_score == 0
    assert potion.stack_count == 1
    assert patient.inventory.has_item(potion.uuid)
    charge_events = EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
    assert [event.phase for event in charge_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    charge_completion = charge_events[-1]
    assert isinstance(charge_completion, ItemChargeConsumptionEvent)
    assert charge_completion.item_uuid == potion.uuid
    assert charge_completion.amount == 1
    assert charge_completion.charges_before == 1
    assert charge_completion.charges_after == 1
    assert charge_completion.stack_count_before == 2
    assert charge_completion.stack_count_after == 1
    assert not charge_completion.item_destroyed
    assert charge_completion.parent_lineage == first_drink.lineage_uuid
    assert charge_completion.lineage_uuid in first_drink.children_lineages
    assert charge_completion.parent_event is not None
    charge_parent = EventQueue.get_event_by_uuid(charge_completion.parent_event)
    assert charge_parent is not None
    assert charge_parent.phase is EventPhase.EFFECT
    first_drink_state = (
        first_drink.canceled,
        patient.get_hp(),
        potion.stack_count,
        patient.inventory.has_item(potion.uuid),
    )

    patient.receive_damage(2, DamageType.SLASHING, patient.uuid)
    wounded_again = patient.get_hp()
    blocked_second_drink = execute_use_action(patient, potion.uuid, "Drink Potion")

    assert blocked_second_drink is None
    assert patient.get_hp() == wounded_again
    assert potion.stack_count == 1
    assert len(EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)) == 4

    patient.action_economy.reset_all_costs()
    second_drink = execute_use_action(patient, potion.uuid, "Drink Potion")

    assert second_drink is not None and not second_drink.canceled
    assert not patient.inventory.has_item(potion.uuid)
    assert BaseBlock.get(potion.uuid) is None
    second_drink_state = (
        second_drink.canceled,
        patient.get_hp(),
        patient.inventory.has_item(potion.uuid),
        BaseBlock.get(potion.uuid) is not None,
    )

    door = materialize_item(
        directional_door_recipe(display_name="Tutorial Door"),
        patient.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=TutorialDoor,
    )
    door.place_on_grid((1, 0))
    patient.update_entity_senses(max_distance=5)

    assert door.uuid in patient.senses.objects
    assert door.blocks_movement_east
    assert [action.name for action in door.get_use_actions(patient.uuid)] == ["Open Door"]
    door_actions_before = [action.name for action in door.get_use_actions(patient.uuid)]

    open_event = execute_use_action(patient, door.uuid, "Open Door")

    assert open_event is not None and not open_event.canceled
    assert door.is_open
    assert not door.blocks_movement_east
    assert [action.name for action in door.get_use_actions(patient.uuid)] == ["Close Door"]
    door_actions_after = [action.name for action in door.get_use_actions(patient.uuid)]

    use_lines = [
        f"hp before potion: full={full_hp}, wounded={wounded_hp}, damage_taken={damage_taken}",
        (
            "drink action clone: "
            f"name={drink_clone_state[0]}, "
            f"user_set={drink_clone_state[1]}, "
            f"item_set={drink_clone_state[2]}, "
            f"fresh_uuid={drink_clone_state[3]}"
        ),
        (
            "after first drink: "
            f"canceled={first_drink_state[0]}, "
            f"hp={first_drink_state[1]}, "
            f"stack={first_drink_state[2]}, "
            f"still_carried={first_drink_state[3]}"
        ),
        f"before second drink: hp={wounded_again}",
        "second drink in same turn: blocked=True, stack=1",
        (
            "after second drink: "
            f"canceled={second_drink_state[0]}, "
            f"hp={second_drink_state[1]}, "
            f"still_carried={second_drink_state[2]}, "
            f"block_exists={second_drink_state[3]}"
        ),
        f"door visible: {door.uuid in patient.senses.objects}",
        (
            "door actions: "
            f"before={door_actions_before}, "
            f"after={door_actions_after}, "
            f"is_open={door.is_open}, "
            f"blocks_east={door.blocks_movement_east}"
        ),
    ]

    print("\n".join(use_lines))

    expected_use_lines = [
        "hp before potion: full=18, wounded=12, damage_taken=6",
        "drink action clone: name=Drink Potion, user_set=True, item_set=True, fresh_uuid=True",
        "after first drink: canceled=False, hp=18, stack=1, still_carried=True",
        "before second drink: hp=16",
        "second drink in same turn: blocked=True, stack=1",
        "after second drink: canceled=False, hp=18, still_carried=False, block_exists=False",
        "door visible: True",
        "door actions: before=['Open Door'], after=['Close Door'], is_open=True, blocks_east=False",
    ]
    assert use_lines == expected_use_lines
    assert capsys.readouterr().out.splitlines() == expected_use_lines


def test_condition_potion_keeps_presentation_and_condition_log_in_one_lineage() -> None:
    """A condition potion exposes one drink action with a readable child effect."""
    reset_item_tutorial_state()
    actor = create_tutorial_actor("Potion Tester")
    potion = materialize_item(
        HASTE_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(actor, potion)

    completion = execute_use_action(actor, potion.uuid, "Drink Haste Potion")

    assert isinstance(completion, ActionEvent)
    assert not completion.canceled
    assert completion.presentation_kind is ActionPresentationKind.DRINK
    assert completion.model_dump(mode="json")["presentation_kind"] == "drink"
    assert "Haste" in actor.active_conditions
    condition_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
        if event.phase is EventPhase.COMPLETION
        and event.parent_lineage == completion.lineage_uuid
    ]
    assert len(condition_completions) == 1
    condition_log = condition_completions[0].combat_log
    assert condition_log is not None
    assert "gains" in condition_log.compact
    assert "Haste" in condition_log.compact
    assert completion.combat_log is not None
    assert condition_log.compact in {
        sub_entry.compact for sub_entry in completion.combat_log.sub_entries
    }


def test_magic_condition_potions_preserve_magical_origin_and_haste_lethargy() -> None:
    """Magic-item conditions retain their origin and exact removal behavior."""
    reset_item_tutorial_state()
    actor = create_tutorial_actor("Magic Potion Tester")
    haste_potion = materialize_item(
        HASTE_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(actor, haste_potion)
    haste_potion_uuid = haste_potion.uuid
    base_speed = actor.action_economy.movement.normalized_score
    base_ac = actor.equipment.ac_bonus.normalized_score

    haste_completion = execute_use_action(
        actor,
        haste_potion.uuid,
        "Drink Haste Potion",
    )

    assert haste_completion is not None and not haste_completion.canceled
    haste = actor.active_conditions.get("Haste")
    assert isinstance(haste, HasteEffect)
    assert haste.tags == {ConditionTag.MAGICAL}
    assert haste.apply_lethargy is True
    assert "Concentrating" not in actor.active_conditions
    assert actor.action_economy.movement.normalized_score == base_speed * 2
    assert actor.equipment.ac_bonus.normalized_score == base_ac + 2
    assert (
        actor.saving_throws.get_saving_throw("dexterity").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    assert actor.action_economy.resources["haste_action"].current == 1
    assert not actor.inventory.has_item(haste_potion_uuid)
    assert BaseBlock.get(haste_potion_uuid) is None

    actor.remove_condition_by_uuid(haste.uuid, parent_event=haste_completion)

    assert "Haste" not in actor.active_conditions
    assert "Haste Lethargy" in actor.active_conditions
    assert actor.action_economy.action_permission.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 0

    reset_item_tutorial_state()
    actor = create_tutorial_actor("Invisibility Potion Tester")
    invisibility_potion = materialize_item(
        GREATER_INVISIBILITY_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(actor, invisibility_potion)

    invisibility_completion = execute_use_action(
        actor,
        invisibility_potion.uuid,
        "Drink Greater Invisibility Potion",
    )

    assert (
        invisibility_completion is not None
        and not invisibility_completion.canceled
    )
    invisibility = actor.active_conditions.get("Invisible")
    assert isinstance(invisibility, GreaterInvisibilityEffect)
    assert invisibility.tags == {ConditionTag.MAGICAL}
