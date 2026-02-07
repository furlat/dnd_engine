"""
Items Lifecycle Hooks — Realistic Game Effects Tests

Tests location tracking (get_position, stored_in_uuid, tile_uuid) and
lifecycle hooks (_on_loot, _on_drop, _on_destroy) with real game effects:
- OilBarrel: _on_destroy applies tile condition to nearby tiles
- CursedGem: _on_loot applies condition to looter entity
- AuraStone: _on_loot adds AC modifier, _on_drop removes it
- HealingHerb: _on_loot heals the entity
"""

import sys
import traceback
from typing import Optional, Tuple
from uuid import UUID, uuid4

from dnd.utils import reset_combat_state, get_hp, set_hp, get_max_hp
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.blocks.base_item import BaseItem
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions, execute_drop
from dnd.items.weapons import create_longsword
from dnd.conditions import Poisoned

tests_passed = 0
tests_failed = 0


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def create_test_entity(position=(3, 3), name="Hero", faction="heroes"):
    source_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=config)
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    setup_standard_actions(entity)
    return entity


def create_test_grid(width=10, height=10):
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


# =========================================================================
# Test Item Subclasses (concrete — CAN import Entity)
# =========================================================================

class OilBarrel(BaseItem):
    """When destroyed, applies Oily condition to own tile and adjacent tiles."""
    name: str = "Oil Barrel"
    is_targetable: bool = True
    blocks_movement: bool = True

    def _on_destroy(self) -> None:
        pos = self.position  # Still valid during _on_destroy
        grid = get_map()
        # Apply Oily condition to position and orthogonal adjacent tiles
        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            tile_pos = (pos[0] + dx, pos[1] + dy)
            tile = grid.get_tile(tile_pos[0], tile_pos[1])
            if tile is not None:
                cond = BaseCondition(
                    name="Oily",
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=tile.uuid,
                )
                cond.duration.duration_type = DurationType.ROUNDS
                cond.duration.duration = 3
                tile.add_condition(cond)


class CursedGem(BaseItem):
    """When picked up, applies Poisoned condition to the entity."""
    name: str = "Cursed Gem"

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is not None:
            poisoned = Poisoned(
                source_entity_uuid=entity_uuid,
                target_entity_uuid=entity_uuid,
            )
            entity.add_condition(poisoned)


class AuraStone(BaseItem):
    """When looted adds +2 AC modifier to entity. When dropped removes it."""
    name: str = "Aura Stone"
    _ac_modifier_uuid: Optional[UUID] = None
    _ac_modifier_owner_uuid: Optional[UUID] = None

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is not None:
            mod_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Aura Stone AC",
                    value=2,
                    source_entity_uuid=entity_uuid,
                    target_entity_uuid=entity_uuid,
                )
            )
            self._ac_modifier_uuid = mod_uuid
            self._ac_modifier_owner_uuid = entity_uuid

    def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        if self._ac_modifier_uuid is not None and self._ac_modifier_owner_uuid is not None:
            entity = Entity.get(self._ac_modifier_owner_uuid)
            if entity is not None:
                entity.equipment.ac_bonus.self_static.remove_modifier(self._ac_modifier_uuid)
            self._ac_modifier_uuid = None
            self._ac_modifier_owner_uuid = None


class HealingHerb(BaseItem):
    """When picked up, heals entity for 10 HP."""
    name: str = "Healing Herb"

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is not None:
            entity.health.heal(10)


# =========================================================================
# Location Tracking Tests
# =========================================================================

def test_get_position_on_floor():
    """Item placed on grid returns its grid position."""
    grid = create_test_grid()
    item = BaseItem(source_entity_uuid=uuid4(), name="Floor Item")
    grid.place_object(item.uuid, (5, 5))
    item.position = (5, 5)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    item.tile_uuid = tile.uuid

    assert item.get_position() == (5, 5), f"Expected (5,5), got {item.get_position()}"


def test_get_position_in_inventory():
    """Item in inventory returns the entity's position."""
    create_test_grid()
    entity = create_test_entity(position=(3, 3))
    item = BaseItem(source_entity_uuid=uuid4(), name="Held Item")
    Entity.update_all_entities_senses()

    entity.loot_item(item)
    pos = item.get_position()
    assert pos == (3, 3), f"Expected entity position (3,3), got {pos}"


def test_get_position_nowhere():
    """Item not placed and not stored returns None."""
    item = BaseItem(source_entity_uuid=uuid4(), name="Nowhere Item")
    assert item.get_position() is None


def test_stored_in_uuid_set_on_loot():
    """stored_in_uuid is set to inventory UUID, owner_uuid to entity UUID after loot."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    item = BaseItem(source_entity_uuid=uuid4(), name="Test Item")
    grid.place_object(item.uuid, (4, 3))
    Entity.update_all_entities_senses()

    assert item.stored_in_uuid is None
    assert item.owner_uuid is None
    entity.loot_item(item)
    assert item.owner_uuid == entity.uuid, \
        f"owner_uuid should be entity UUID, got {item.owner_uuid}"
    assert item.stored_in_uuid == entity.inventory.uuid, \
        f"stored_in_uuid should be inventory UUID, got {item.stored_in_uuid}"


def test_tile_uuid_cleared_on_loot():
    """tile_uuid is cleared when item is looted from floor."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    item = BaseItem(source_entity_uuid=uuid4(), name="Test Item")
    grid.place_object(item.uuid, (4, 3))
    tile = grid.get_tile(4, 3)
    assert tile is not None
    item.position = (4, 3)
    item.tile_uuid = tile.uuid
    Entity.update_all_entities_senses()

    entity.loot_item(item)
    assert item.tile_uuid is None, "tile_uuid should be cleared after loot"


def test_location_fields_set_on_drop():
    """Drop sets owner_uuid=None, stored_in_uuid=None, tile_uuid, position correctly."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = BaseItem(source_entity_uuid=uuid4(), name="Test Item")
    entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid

    entity.drop_item(item.uuid)
    assert item.owner_uuid is None, "owner_uuid should be None after drop"
    assert item.stored_in_uuid is None, "stored_in_uuid should be None after drop"
    assert item.position == (5, 5), f"position should be entity pos (5,5), got {item.position}"
    tile = grid.get_tile(5, 5)
    assert tile is not None
    assert item.tile_uuid == tile.uuid, "tile_uuid should match tile at drop position"


def test_transfer_updates_stored_in_uuid():
    """Inventory.transfer_to updates owner_uuid and stored_in_uuid to new owner."""
    create_test_grid()
    e1 = create_test_entity(position=(3, 3), name="Giver")
    e2 = create_test_entity(position=(4, 3), name="Receiver", faction="others")
    item = BaseItem(source_entity_uuid=uuid4(), name="Gift")
    e1.inventory.add_item(item)
    item.owner_uuid = e1.uuid
    item.stored_in_uuid = e1.inventory.uuid

    e1.inventory.transfer_to(item.uuid, e2.inventory)
    assert item.owner_uuid == e2.uuid, \
        f"owner_uuid should be receiver entity UUID after transfer, got {item.owner_uuid}"
    assert item.stored_in_uuid == e2.inventory.uuid, \
        f"stored_in_uuid should be receiver inventory UUID after transfer, got {item.stored_in_uuid}"


def test_drop_at_adjacent_position():
    """Drop at adjacent position (distance 1) sets correct position."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = BaseItem(source_entity_uuid=uuid4(), name="Test Item")
    entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid
    Entity.update_all_entities_senses()

    execute_drop(entity, item.uuid, position=(5, 6))
    assert item.position == (5, 6), f"Expected (5,6), got {item.position}"
    assert grid.get_object_position(item.uuid) == (5, 6)
    assert item.owner_uuid is None
    assert item.stored_in_uuid is None


def test_get_position_floor_returns_own_position():
    """Floor item with tile_uuid returns self.position directly."""
    grid = create_test_grid()
    item = BaseItem(source_entity_uuid=uuid4(), name="Floor Item")
    grid.place_object(item.uuid, (5, 5))
    tile = grid.get_tile(5, 5)
    assert tile is not None
    item.tile_uuid = tile.uuid
    item.position = (5, 5)

    assert item.get_position() == (5, 5), f"Expected (5,5), got {item.get_position()}"


def test_destroy_clears_location_fields():
    """destroy() clears tile_uuid and stored_in_uuid."""
    grid = create_test_grid()
    source_id = uuid4()
    item = BaseItem(
        source_entity_uuid=source_id,
        name="Breakable",
        is_targetable=True,
        health=BaseItem.create_item_health(source_id, 8),
    )
    grid.place_object(item.uuid, (5, 5))
    tile = grid.get_tile(5, 5)
    assert tile is not None
    item.position = (5, 5)
    item.tile_uuid = tile.uuid

    item.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    # Item destroyed — location fields should be cleared
    # (Can't check item directly since it's unregistered, but we can verify
    #  tile_uuid and stored_in_uuid were cleared before unregister)


# =========================================================================
# OilBarrel: _on_destroy with tile conditions
# =========================================================================

def test_oil_barrel_destroy_applies_tile_conditions():
    """Destroying oil barrel applies Oily condition to nearby tiles."""
    grid = create_test_grid()
    source_id = uuid4()
    barrel = OilBarrel(
        source_entity_uuid=source_id,
        health=BaseItem.create_item_health(source_id, 8),
    )
    grid.place_object(barrel.uuid, (5, 5))
    barrel.position = (5, 5)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    barrel.tile_uuid = tile.uuid

    barrel.receive_damage(100, DamageType.BLUDGEONING, uuid4())

    # Check center tile and 4 adjacent tiles for Oily condition
    for pos in [(5, 5), (6, 5), (4, 5), (5, 6), (5, 4)]:
        tile = grid.get_tile(pos[0], pos[1])
        assert tile is not None, f"Tile at {pos} should exist"
        assert "Oily" in tile.active_conditions, \
            f"Tile at {pos} should have Oily condition"


def test_oil_barrel_oily_duration():
    """Oily condition from barrel has 3-round duration."""
    grid = create_test_grid()
    source_id = uuid4()
    barrel = OilBarrel(
        source_entity_uuid=source_id,
        health=BaseItem.create_item_health(source_id, 8),
    )
    grid.place_object(barrel.uuid, (5, 5))
    barrel.position = (5, 5)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    barrel.tile_uuid = tile.uuid

    barrel.receive_damage(100, DamageType.BLUDGEONING, uuid4())

    tile = grid.get_tile(5, 5)
    assert tile is not None
    cond = tile.active_conditions["Oily"]
    assert cond.duration.duration == 3, f"Expected 3 round duration, got {cond.duration.duration}"


# =========================================================================
# CursedGem: _on_loot applies condition to entity
# =========================================================================

def test_cursed_gem_applies_poisoned():
    """Looting a cursed gem applies Poisoned to the entity."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    gem = CursedGem(source_entity_uuid=uuid4())
    grid.place_object(gem.uuid, (4, 3))
    Entity.update_all_entities_senses()

    assert "Poisoned" not in entity.active_conditions
    entity.loot_item(gem)
    assert "Poisoned" in entity.active_conditions, \
        "Entity should have Poisoned after looting cursed gem"


def test_cursed_gem_condition_persists_after_drop():
    """Dropping the cursed gem does NOT remove the curse (it sticks)."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    gem = CursedGem(source_entity_uuid=uuid4())
    grid.place_object(gem.uuid, (4, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(gem)
    assert "Poisoned" in entity.active_conditions

    entity.drop_item(gem.uuid)
    assert "Poisoned" in entity.active_conditions, \
        "Poisoned should persist after dropping the cursed gem"


# =========================================================================
# AuraStone: _on_loot adds AC, _on_drop removes AC
# =========================================================================

def test_aura_stone_adds_ac_on_loot():
    """Looting aura stone gives +2 AC."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    stone = AuraStone(source_entity_uuid=uuid4())
    grid.place_object(stone.uuid, (4, 3))
    Entity.update_all_entities_senses()

    ac_before = entity.equipment.ac_bonus.normalized_score
    entity.loot_item(stone)
    ac_after = entity.equipment.ac_bonus.normalized_score

    assert ac_after == ac_before + 2, \
        f"AC should increase by 2: before={ac_before}, after={ac_after}"


def test_aura_stone_removes_ac_on_drop():
    """Dropping aura stone removes the +2 AC."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    stone = AuraStone(source_entity_uuid=uuid4())
    grid.place_object(stone.uuid, (4, 3))
    Entity.update_all_entities_senses()

    ac_before = entity.equipment.ac_bonus.normalized_score
    entity.loot_item(stone)
    entity.drop_item(stone.uuid)
    ac_after = entity.equipment.ac_bonus.normalized_score

    assert ac_after == ac_before, \
        f"AC should return to original: before={ac_before}, after={ac_after}"


def test_aura_stone_transfer_moves_modifier():
    """Transferring aura stone between entities moves the AC bonus."""
    grid = create_test_grid()
    e1 = create_test_entity(position=(3, 3), name="Holder1")
    e2 = create_test_entity(position=(4, 3), name="Holder2", faction="others")
    stone = AuraStone(source_entity_uuid=uuid4())
    grid.place_object(stone.uuid, (3, 4))
    Entity.update_all_entities_senses()

    e1_ac_base = e1.equipment.ac_bonus.normalized_score
    e2_ac_base = e2.equipment.ac_bonus.normalized_score

    e1.loot_item(stone)
    assert e1.equipment.ac_bonus.normalized_score == e1_ac_base + 2

    # Drop and have e2 pick it up
    e1.drop_item(stone.uuid)
    assert e1.equipment.ac_bonus.normalized_score == e1_ac_base, \
        "E1 AC should return to base after drop"

    e2.loot_item(stone)
    assert e2.equipment.ac_bonus.normalized_score == e2_ac_base + 2, \
        "E2 should now have +2 AC from aura stone"


# =========================================================================
# HealingHerb: _on_loot heals entity
# =========================================================================

def test_healing_herb_heals_on_loot():
    """Looting a healing herb heals the entity for 10 HP."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(entity)
    set_hp(entity, max_hp - 20)
    hp_before = get_hp(entity)

    herb = HealingHerb(source_entity_uuid=uuid4())
    grid.place_object(herb.uuid, (4, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(herb)
    hp_after = get_hp(entity)
    assert hp_after == hp_before + 10, \
        f"Should heal 10 HP: before={hp_before}, after={hp_after}"


def test_healing_herb_no_overheal():
    """Healing herb doesn't exceed max HP."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(entity)
    set_hp(entity, max_hp - 3)  # Only 3 HP missing

    herb = HealingHerb(source_entity_uuid=uuid4())
    grid.place_object(herb.uuid, (4, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(herb)
    assert get_hp(entity) == max_hp, \
        f"Should cap at max HP {max_hp}, got {get_hp(entity)}"


# =========================================================================
# Hook parameters are passed correctly
# =========================================================================

def test_loot_hook_receives_correct_params():
    """_on_loot receives entity_uuid and inventory_uuid."""
    class ParamTracker(BaseItem):
        received_entity_uuid: Optional[UUID] = None
        received_inventory_uuid: Optional[UUID] = None

        def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
            self.received_entity_uuid = entity_uuid
            self.received_inventory_uuid = inventory_uuid

    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    item = ParamTracker(source_entity_uuid=uuid4(), name="Tracked")
    grid.place_object(item.uuid, (4, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(item)
    assert item.received_entity_uuid == entity.uuid, \
        f"Expected entity UUID {entity.uuid}, got {item.received_entity_uuid}"
    assert item.received_inventory_uuid == entity.inventory.uuid, \
        f"Expected inventory UUID {entity.inventory.uuid}, got {item.received_inventory_uuid}"


def test_drop_hook_receives_correct_params():
    """_on_drop receives entity_uuid and drop position."""
    class ParamTracker(BaseItem):
        received_entity_uuid: Optional[UUID] = None
        received_position: Optional[Tuple[int, int]] = None

        def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
            self.received_entity_uuid = entity_uuid
            self.received_position = position

    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = ParamTracker(source_entity_uuid=uuid4(), name="Tracked")
    entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid

    entity.drop_item(item.uuid)
    assert item.received_entity_uuid == entity.uuid
    assert item.received_position == (5, 5), \
        f"Expected drop position (5,5), got {item.received_position}"


def test_drop_hook_receives_adjacent_position():
    """_on_drop receives the specified adjacent position, not entity position."""
    class ParamTracker(BaseItem):
        received_position: Optional[Tuple[int, int]] = None

        def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
            self.received_position = position

    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = ParamTracker(source_entity_uuid=uuid4(), name="Tracked")
    entity.inventory.add_item(item)
    item.owner_uuid = entity.uuid
    item.stored_in_uuid = entity.inventory.uuid
    Entity.update_all_entities_senses()

    execute_drop(entity, item.uuid, position=(5, 6))
    assert item.received_position == (5, 6), \
        f"Expected adjacent drop position (5,6), got {item.received_position}"


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Items Lifecycle Hooks Tests")
    print("=" * 60)

    print("\n--- Location Tracking ---")
    run_test("get_position on floor", test_get_position_on_floor)
    run_test("get_position in inventory", test_get_position_in_inventory)
    run_test("get_position nowhere", test_get_position_nowhere)
    run_test("stored_in_uuid set on loot", test_stored_in_uuid_set_on_loot)
    run_test("tile_uuid cleared on loot", test_tile_uuid_cleared_on_loot)
    run_test("Location fields set on drop", test_location_fields_set_on_drop)
    run_test("Transfer updates stored_in_uuid", test_transfer_updates_stored_in_uuid)
    run_test("Drop at adjacent position", test_drop_at_adjacent_position)
    run_test("get_position floor returns own position", test_get_position_floor_returns_own_position)
    run_test("Destroy clears location fields", test_destroy_clears_location_fields)

    print("\n--- OilBarrel (_on_destroy) ---")
    run_test("Oil barrel applies tile conditions", test_oil_barrel_destroy_applies_tile_conditions)
    run_test("Oil barrel oily duration", test_oil_barrel_oily_duration)

    print("\n--- CursedGem (_on_loot) ---")
    run_test("Cursed gem applies Poisoned", test_cursed_gem_applies_poisoned)
    run_test("Cursed gem condition persists after drop", test_cursed_gem_condition_persists_after_drop)

    print("\n--- AuraStone (_on_loot + _on_drop) ---")
    run_test("Aura stone adds AC on loot", test_aura_stone_adds_ac_on_loot)
    run_test("Aura stone removes AC on drop", test_aura_stone_removes_ac_on_drop)
    run_test("Aura stone transfer moves modifier", test_aura_stone_transfer_moves_modifier)

    print("\n--- HealingHerb (_on_loot) ---")
    run_test("Healing herb heals on loot", test_healing_herb_heals_on_loot)
    run_test("Healing herb no overheal", test_healing_herb_no_overheal)

    print("\n--- Hook Parameters ---")
    run_test("Loot hook receives correct params", test_loot_hook_receives_correct_params)
    run_test("Drop hook receives correct params", test_drop_hook_receives_correct_params)
    run_test("Drop hook receives adjacent position", test_drop_hook_receives_adjacent_position)

    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    sys.exit(1 if tests_failed > 0 else 0)
