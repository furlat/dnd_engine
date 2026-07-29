"""Active coverage for the archived advanced item-world behavior matrix.

The July test rework moved ``test_items_phase1_advanced.py`` outside pytest
collection without recording where its 36 behavioral cases went.  This module
keeps an explicit old-case-to-active-selector ledger and restores the missing
world, visibility, targeting, and lifecycle combinations using current APIs.
"""

from uuid import UUID, uuid4

from dnd.actions_functional import execute_drop, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.blocks.equipment import EquipmentConfig, Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.inventory import Inventory
from dnd.core.base_block import BaseBlock
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemRarity
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.items.weapons import LONGSWORD_RECIPE
from tests.engine.support import reset_combat_state


THIS_FILE = "tests/manual/test_131_advanced_item_world_legacy_contract.py"
BOOK_ITEMS_FILE = "tests/engine/test_items_inventory_equipment.py"
BOOK_CONDITIONS_FILE = "tests/engine/test_condition_lifecycle.py"

VISION_DESTROY_SELECTOR = (
    f"{THIS_FILE}::test_vision_blocker_hides_then_destroy_reveals_floor_item_and_entity"
)
VISION_PORTABLE_SELECTOR = (
    f"{THIS_FILE}::test_portable_vision_blocker_drop_and_pickup_update_los"
)
MOVEMENT_SELECTOR = (
    f"{THIS_FILE}::test_movement_blocker_destroy_reopens_cached_paths"
)
ISOLATION_SELECTOR = (
    f"{THIS_FILE}::test_inventory_removes_floor_item_from_grid_senses_and_object_targets"
)
DROP_SELECTOR = (
    f"{THIS_FILE}::test_drop_is_explicit_lifecycle_operation_not_discovered_action"
)
COLOCATED_SELECTOR = (
    f"{THIS_FILE}::test_dropped_and_colocated_items_preserve_grid_and_visibility"
)
PICKUP_VISIBILITY_SELECTOR = (
    f"{THIS_FILE}::test_pickup_removes_floor_visibility_for_other_observers"
)
NON_TARGET_SELECTOR = (
    f"{THIS_FILE}::test_nonbreakable_or_unseen_items_are_not_object_targets"
)
PICKUP_BOUNDARY_SELECTOR = (
    f"{THIS_FILE}::test_pickup_targets_respect_capacity_and_five_foot_range"
)
DESTROY_SELECTOR = (
    f"{THIS_FILE}::test_destroy_cleans_colocated_grid_entries"
)
INVENTORY_VALUE_SELECTOR = (
    f"{THIS_FILE}::test_inventory_weight_equippable_flags_and_tag_filters"
)
ROUND_TRIP_SELECTOR = (
    f"{THIS_FILE}::test_multiple_loot_drop_and_colocation_round_trips"
)
TRANSFER_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_003_inventory_capacity_and_transfer_update_container_fields"
)
LOCATION_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_001_floor_loot_and_drop_update_authoritative_location"
)
CONDITION_DESTROY_SELECTOR = (
    f"{BOOK_CONDITIONS_FILE}::test_eb_07_013_item_conditions_index_expire_and_destroy_cleanly"
)


LEGACY_CASE_TO_ACTIVE_SELECTOR: dict[str, str] = {
    "test_vision_blocked_by_object": VISION_DESTROY_SELECTOR,
    "test_destroy_vision_blocker_reveals_items": VISION_DESTROY_SELECTOR,
    "test_destroy_vision_blocker_reveals_entity": VISION_DESTROY_SELECTOR,
    "test_drop_vision_blocking_item_blocks_los": VISION_PORTABLE_SELECTOR,
    "test_pickup_vision_blocker_unblocks_los": VISION_PORTABLE_SELECTOR,
    "test_movement_blocked_by_object": MOVEMENT_SELECTOR,
    "test_destroy_movement_blocker_opens_path": MOVEMENT_SELECTOR,
    "test_looted_item_not_on_ground": LOCATION_SELECTOR,
    "test_looted_item_not_in_senses": ISOLATION_SELECTOR,
    "test_inventory_item_not_targetable_by_attack_object": ISOLATION_SELECTOR,
    "test_inventory_item_not_targetable_by_pickup": ISOLATION_SELECTOR,
    "test_drop_action_works": DROP_SELECTOR,
    "test_drop_action_not_in_available_actions": DROP_SELECTOR,
    "test_drop_fires_on_drop_hook": DROP_SELECTOR,
    "test_drop_invalid_item_uuid": DROP_SELECTOR,
    "test_dropped_item_visible_to_nearby_entity": COLOCATED_SELECTOR,
    "test_drop_multiple_items_same_position": COLOCATED_SELECTOR,
    "test_multiple_items_at_same_position": COLOCATED_SELECTOR,
    "test_pickup_one_of_multiple_items_leaves_others": COLOCATED_SELECTOR,
    "test_two_entities_see_same_item": COLOCATED_SELECTOR,
    "test_one_entity_picks_up_other_loses_visibility": PICKUP_VISIBILITY_SELECTOR,
    "test_transfer_between_entity_inventories": TRANSFER_SELECTOR,
    "test_non_breakable_item_not_attack_target": NON_TARGET_SELECTOR,
    "test_item_not_visible_not_targetable": NON_TARGET_SELECTOR,
    "test_pickup_full_inventory_fails": PICKUP_BOUNDARY_SELECTOR,
    "test_pickup_at_exactly_5ft": PICKUP_BOUNDARY_SELECTOR,
    "test_pickup_at_10ft_fails": PICKUP_BOUNDARY_SELECTOR,
    "test_destroy_item_with_conditions_cleans_up": CONDITION_DESTROY_SELECTOR,
    "test_destroy_all_items_at_position": DESTROY_SELECTOR,
    "test_item_zero_weight_in_inventory": INVENTORY_VALUE_SELECTOR,
    "test_stack_count_affects_weight": INVENTORY_VALUE_SELECTOR,
    "test_loot_multiple_items_sequentially": ROUND_TRIP_SELECTOR,
    "test_loot_and_drop_round_trip": LOCATION_SELECTOR,
    "test_place_object_then_place_another_at_same_position": ROUND_TRIP_SELECTOR,
    "test_equippable_item_flags": INVENTORY_VALUE_SELECTOR,
    "test_item_tags_filtering": INVENTORY_VALUE_SELECTOR,
}


class DropTrackingItem(BaseItem):
    """Item fixture whose public state proves that the drop hook ran."""

    dropped: bool = False

    def _on_drop(self, entity_uuid: UUID, position: tuple[int, int]) -> None:
        self.dropped = True


def reset_item_world(width: int = 20, height: int = 20) -> None:
    """Reset every engine registry and build one bright rectangular floor."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_actor(
    position: tuple[int, int],
    *,
    name: str = "Hero",
    faction: str = "heroes",
) -> Entity:
    """Create the minimal current-architecture actor needed by item actions."""
    actor_uuid = uuid4()
    actor = Entity.create(
        source_entity_uuid=actor_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    )
                ],
            ),
            equipment=EquipmentConfig(),
            action_economy=ActionEconomyConfig(),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )
    actor.equipment.equip(
        materialize_item(
            LONGSWORD_RECIPE,
            actor.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(actor)
    return actor


def create_floor_item(
    position: tuple[int, int] | None = None,
    *,
    name: str = "Potion",
    weight: float = 1.0,
) -> BaseItem:
    """Create a pickable item, optionally in one authoritative floor slot."""
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name=name,
        is_pickable=True,
        weight=weight,
        value=50,
    )
    if position is not None:
        item.place_on_grid(position)
    return item


def create_breakable(
    position: tuple[int, int],
    *,
    name: str,
    blocks_vision: bool = False,
    blocks_movement: bool = False,
) -> BaseItem:
    """Create a destructible floor object with explicit blocking capabilities."""
    source_uuid = uuid4()
    item = BaseItem(
        source_entity_uuid=source_uuid,
        name=name,
        is_pickable=False,
        is_targetable=True,
        health=BaseItem.create_item_health(source_uuid, 8),
        blocks_vision_field=blocks_vision,
        blocks_movement=blocks_movement,
        weight=50,
    )
    item.place_on_grid(position)
    return item


def object_target_uuids(entity: Entity, action_name: str) -> set[UUID]:
    """Return object UUIDs currently offered under one discovered action."""
    return {
        target.target_uuid
        for action in entity.get_available_actions().object_actions
        if action.template_name == action_name
        for target in action.valid_targets
        if target.target_uuid is not None
    }


def test_legacy_advanced_item_manifest_accounts_for_all_36_cases() -> None:
    """Every displaced named case has one explicit maintained selector."""
    assert len(LEGACY_CASE_TO_ACTIVE_SELECTOR) == 36
    assert all(case.startswith("test_") for case in LEGACY_CASE_TO_ACTIVE_SELECTOR)
    assert all(
        selector.startswith("tests/") and "::test_" in selector
        for selector in LEGACY_CASE_TO_ACTIVE_SELECTOR.values()
    )


def test_vision_blocker_hides_then_destroy_reveals_floor_item_and_entity() -> None:
    """Floor blockers censor both objects and actors until destruction."""
    reset_item_world()
    observer = create_actor((1, 5), name="Observer")
    blocker = create_breakable(
        (3, 5),
        name="Barricade",
        blocks_vision=True,
        blocks_movement=True,
    )
    hidden_item = create_floor_item((5, 5), name="Hidden Gem")
    hidden_actor = create_actor((5, 5), name="Hidden Enemy", faction="monsters")

    Entity.update_all_entities_senses()

    assert hidden_item.uuid not in observer.senses.objects
    assert hidden_actor.uuid not in observer.senses.entities

    blocker.receive_damage(100, DamageType.BLUDGEONING, observer.uuid)
    Entity.update_all_entities_senses()

    assert BaseBlock.get(blocker.uuid) is None
    assert hidden_item.uuid in observer.senses.objects
    assert hidden_actor.uuid in observer.senses.entities


def test_portable_vision_blocker_drop_and_pickup_update_los() -> None:
    """Dropping and looting a portable blocker invalidate observer FOV."""
    reset_item_world()
    watcher = create_actor((1, 5), name="Watcher")
    dropper = create_actor((3, 5), name="Dropper", faction="helpers")
    hidden_item = create_floor_item((5, 5), name="Far Gem")
    blocker = BaseItem(
        source_entity_uuid=dropper.uuid,
        name="Portable Wall",
        blocks_vision_field=True,
        blocks_movement=True,
        is_pickable=True,
    )
    assert dropper.inventory.add_item(blocker)
    Entity.update_all_entities_senses()
    assert hidden_item.uuid in watcher.senses.objects

    dropped = execute_drop(dropper, blocker.uuid)
    Entity.update_all_entities_senses()

    assert dropped is not None and not dropped.canceled
    assert hidden_item.uuid not in watcher.senses.objects

    picker = create_actor((3, 4), name="Picker", faction="helpers")
    assert picker.loot_item(blocker)
    Entity.update_all_entities_senses()

    assert hidden_item.uuid in watcher.senses.objects


def test_movement_blocker_destroy_reopens_cached_paths() -> None:
    """Destroying an object invalidates and recomputes path availability."""
    reset_item_world()
    blocker = create_breakable(
        (3, 5),
        name="Wooden Gate",
        blocks_movement=True,
    )
    mover = create_actor((2, 5), name="Mover")
    Entity.update_all_entities_senses()
    assert (3, 5) not in mover.senses.paths

    blocker.receive_damage(100, DamageType.BLUDGEONING, mover.uuid)
    Entity.update_all_entities_senses()

    assert BaseBlock.get(blocker.uuid) is None
    assert (3, 5) in mover.senses.paths


def test_inventory_removes_floor_item_from_grid_senses_and_object_targets() -> None:
    """One loot operation removes every floor-facing representation."""
    reset_item_world()
    grid = get_map()
    actor = create_actor((3, 3))
    source_uuid = uuid4()
    crate = BaseItem(
        source_entity_uuid=source_uuid,
        name="Portable Crate",
        is_pickable=True,
        is_targetable=True,
        health=BaseItem.create_item_health(source_uuid, 16),
    )
    crate.place_on_grid((4, 3))
    Entity.update_all_entities_senses()
    assert crate.uuid in actor.senses.objects

    assert actor.loot_item(crate)
    Entity.update_all_entities_senses()

    assert grid.get_object_position(crate.uuid) is None
    assert crate.uuid not in grid.get_objects_at((4, 3))
    assert crate.uuid not in actor.senses.objects
    assert crate.uuid not in object_target_uuids(actor, "Attack Object")
    assert crate.uuid not in object_target_uuids(actor, "Pick Up")


def test_drop_is_explicit_lifecycle_operation_not_discovered_action() -> None:
    """Drop routes explicitly, fires its hook, and handles a foreign UUID."""
    reset_item_world()
    actor = create_actor((5, 5))
    item = DropTrackingItem(source_entity_uuid=actor.uuid, name="Trackable")
    assert actor.inventory.add_item(item)

    available_names = {
        action.template_name for action in actor.get_available_actions().all_actions
    }
    assert "Drop" not in available_names

    event = execute_drop(actor, item.uuid)

    assert event is not None and not event.canceled
    assert item.dropped is True
    assert not actor.inventory.has_item(item.uuid)
    assert get_map().get_object_position(item.uuid) == actor.position

    invalid = execute_drop(actor, uuid4())
    assert invalid is not None and invalid.canceled


def test_dropped_and_colocated_items_preserve_grid_and_visibility() -> None:
    """Each item keeps independent membership when several share one tile."""
    reset_item_world()
    grid = get_map()
    dropper = create_actor((5, 5), name="Dropper")
    watcher_a = create_actor((5, 6), name="Watcher A", faction="others")
    watcher_b = create_actor((6, 5), name="Watcher B", faction="others")
    first = create_floor_item(name="Gem One")
    second = create_floor_item(name="Gem Two")
    assert dropper.inventory.add_item(first)
    assert dropper.inventory.add_item(second)
    Entity.update_all_entities_senses()
    assert first.uuid not in watcher_a.senses.objects

    execute_drop(dropper, first.uuid)
    execute_drop(dropper, second.uuid)
    Entity.update_all_entities_senses()

    assert {first.uuid, second.uuid} <= set(grid.get_objects_at((5, 5)))
    assert {first.uuid, second.uuid} <= set(watcher_a.senses.objects)
    assert {first.uuid, second.uuid} <= set(watcher_b.senses.objects)

    assert dropper.loot_item(first)

    assert grid.get_object_position(first.uuid) is None
    assert grid.get_object_position(second.uuid) == (5, 5)
    assert second.uuid in grid.get_objects_at((5, 5))


def test_pickup_removes_floor_visibility_for_other_observers() -> None:
    """A floor pickup is removed from every observer, not only the picker."""
    reset_item_world()
    item = create_floor_item((5, 5), name="Shared Gem")
    picker = create_actor((5, 4), name="Picker")
    watcher = create_actor((5, 6), name="Watcher", faction="others")
    Entity.update_all_entities_senses()
    assert item.uuid in watcher.senses.objects

    assert picker.loot_item(item)
    Entity.update_all_entities_senses()

    assert item.uuid not in watcher.senses.objects


def test_nonbreakable_or_unseen_items_are_not_object_targets() -> None:
    """Object actions require both current visibility and a breakable target."""
    reset_item_world()
    grid = get_map()
    actor = create_actor((1, 5))
    pillar = BaseItem(
        source_entity_uuid=uuid4(),
        name="Indestructible Pillar",
        is_targetable=True,
        is_pickable=False,
        health=None,
    )
    pillar.place_on_grid((2, 5))
    for y in range(10):
        grid.set_tile(3, y, walkable=False, visible=False, name="Wall")
    hidden = create_floor_item((5, 5), name="Hidden Gem")
    Entity.update_all_entities_senses()

    assert hidden.uuid not in actor.senses.objects
    assert pillar.uuid not in object_target_uuids(actor, "Attack Object")
    assert hidden.uuid not in object_target_uuids(actor, "Pick Up")


def test_pickup_targets_respect_capacity_and_five_foot_range() -> None:
    """Pick Up includes an adjacent diagonal, excludes ten feet and full bags."""
    reset_item_world()
    actor = create_actor((3, 3))
    adjacent = create_floor_item((4, 4), name="Close Gem")
    distant = create_floor_item((5, 3), name="Far Gem")
    Entity.update_all_entities_senses()

    targets = object_target_uuids(actor, "Pick Up")
    assert adjacent.uuid in targets
    assert distant.uuid not in targets

    actor.inventory.max_slots = actor.inventory.item_count
    Entity.update_all_entities_senses()

    assert adjacent.uuid not in object_target_uuids(actor, "Pick Up")


def test_destroy_cleans_colocated_grid_entries() -> None:
    """Destroy removes only the matching identity from a shared floor cell."""
    reset_item_world()
    grid = get_map()
    first = create_breakable((5, 5), name="Burning Crate")
    second = create_breakable((5, 5), name="Other Crate")
    assert len(grid.get_objects_at((5, 5))) == 2

    first.receive_damage(100, DamageType.FIRE, uuid4())

    assert BaseBlock.get(first.uuid) is None
    assert second.uuid in grid.get_objects_at((5, 5))

    second.receive_damage(100, DamageType.BLUDGEONING, uuid4())

    assert grid.get_objects_at((5, 5)) == set()


def test_inventory_weight_equippable_flags_and_tag_filters() -> None:
    """Inventory value semantics preserve zero weight, stacks, and tags."""
    reset_combat_state()
    inventory = Inventory(source_entity_uuid=uuid4(), weight_capacity=10)
    feather = BaseItem(source_entity_uuid=uuid4(), name="Feather", weight=0)
    arrows = BaseItem(
        source_entity_uuid=uuid4(),
        name="Arrows",
        weight=0.5,
        stack_count=5,
        tags=["weapon", "ammunition"],
    )
    potions = [
        BaseItem(
            source_entity_uuid=uuid4(),
            name=name,
            tags=["consumable", tag],
        )
        for name, tag in (("Health Potion", "healing"), ("Mana Potion", "magic"))
    ]
    ring = EquippableItem(
        source_entity_uuid=uuid4(),
        name="Magic Ring",
        rarity=ItemRarity.RARE,
    )

    for item in (feather, arrows, *potions, ring):
        assert inventory.add_item(item)

    assert inventory.total_weight == 2.5
    assert inventory.item_count == 5
    assert inventory.find_items_by_tag("consumable") == potions
    assert inventory.find_items_by_tag("weapon") == [arrows]
    assert inventory.find_items_by_tag("healing") == [potions[0]]
    assert inventory.find_items_by_tag("nonexistent") == []
    assert ring.is_equippable is True
    assert ring.is_pickable is True
    assert ring.is_usable is False
    assert ring.rarity is ItemRarity.RARE

    too_heavy = BaseItem(
        source_entity_uuid=uuid4(),
        name="Cannonballs",
        weight=5,
        stack_count=3,
    )
    assert inventory.can_add(too_heavy) is False


def test_multiple_loot_drop_and_colocation_round_trips() -> None:
    """Sequential loot and drop preserve one location per item."""
    reset_item_world()
    grid = get_map()
    actor = create_actor((3, 3))
    items = [
        create_floor_item((4, 3), name=f"Gem {index}")
        for index in range(5)
    ]
    Entity.update_all_entities_senses()

    for item in items:
        assert actor.loot_item(item)

    assert actor.inventory.item_count >= len(items)
    assert all(actor.inventory.has_item(item.uuid) for item in items)
    assert all(grid.get_object_position(item.uuid) is None for item in items)

    dropped = actor.drop_item(items[0].uuid)
    another = create_floor_item(name="Another Gem")
    another.place_on_grid(actor.position)

    assert dropped is items[0]
    assert grid.get_object_position(items[0].uuid) == actor.position
    assert {items[0].uuid, another.uuid} <= set(grid.get_objects_at(actor.position))
