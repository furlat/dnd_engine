"""Test Equipment & Inventory API models and entity methods.

Tests:
1. APIItemSummary.create() for weapons, armor, shields, usable items
2. APIEquipmentOverview.create() for full equipment state
3. Entity.get_equippable_items() — items in inventory grouped by valid slot
4. Equip from inventory — slot populated, inventory reduced
5. Unequip to inventory — slot empty, inventory has item
6. Swap (equip when slot occupied) — old item goes to inventory
7. Invalid operations (wrong slot type, non-equippable item)
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin
from dnd.items import create_longsword, create_dagger, create_shortsword, create_longbow, create_shield
from dnd.items.armors import create_chain_mail, create_leather_armor
from dnd.items.test_items import create_healing_potion
from dnd.blocks.equipment import Weapon, Shield, Armor, WeaponSlot
from dnd.blocks.base_item import EquippableItem, UsableItem
from dnd.core.events import BodyPart, RingSlot

from server.api_models import APIItemSummary, APIEquipmentOverview, APIEquipmentSlot

passed = 0
failed = 0

def check(desc, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {desc}")
    else:
        failed += 1
        print(f"  FAIL: {desc}")


# =========================================================================
print("\n=== Test 1: APIItemSummary.create() for different item types ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Create items
longsword = create_longsword(entity.uuid)
dagger = create_dagger(entity.uuid)
shield = create_shield(entity.uuid)
chain_mail = create_chain_mail(entity.uuid)
potion = create_healing_potion(entity.uuid)

# Test weapon summary
ws = APIItemSummary.create(longsword)
check("weapon item_type = 'weapon'", ws.item_type == "weapon")
check("weapon has damage_dice", ws.damage_dice is not None)
check("weapon has damage_type", ws.damage_type is not None)
check("weapon name = 'Longsword'", ws.name == "Longsword")
check("weapon rarity is string", isinstance(ws.rarity, str))

# Test dagger weapon summary
ds = APIItemSummary.create(dagger)
check("dagger item_type = 'weapon'", ds.item_type == "weapon")
check("dagger has weapon_properties", len(ds.weapon_properties) > 0)
check("dagger is Finesse", "Finesse" in ds.weapon_properties)
check("dagger is Light", "Light" in ds.weapon_properties)

# Test shield summary
ss = APIItemSummary.create(shield)
check("shield item_type = 'shield'", ss.item_type == "shield")
check("shield has shield_ac_bonus", ss.shield_ac_bonus is not None)
check("shield ac_bonus = 2", ss.shield_ac_bonus == 2)

# Test armor summary
ars = APIItemSummary.create(chain_mail)
check("armor item_type = 'armor'", ars.item_type == "armor")
check("armor has armor_type", ars.armor_type is not None)
check("armor armor_type = 'Heavy'", ars.armor_type == "Heavy")
check("armor has armor_ac", ars.armor_ac is not None)
check("armor ac = 16", ars.armor_ac == 16)

# Test usable item summary
ps = APIItemSummary.create(potion)
check("potion item_type = 'usable'", ps.item_type == "usable")
check("potion is_consumable", ps.is_consumable)
check("potion has charges", ps.charges is not None)


# =========================================================================
print("\n=== Test 2: APIEquipmentOverview.create() ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Goblin comes with a scimitar equipped in MELEE_MAIN
overview = APIEquipmentOverview.create(entity)

check("overview has 13 slots", len(overview.slots) == 13)
check("overview has ac value", isinstance(overview.ac, int))
check("overview inventory is list", isinstance(overview.inventory, list))

# Find the melee_main slot
melee_main = [s for s in overview.slots if s.slot == "weapon_melee_main"]
check("has weapon_melee_main slot", len(melee_main) == 1)
if melee_main:
    check("melee_main has item (goblin's scimitar)", melee_main[0].item is not None)
    if melee_main[0].item:
        check("melee_main item is weapon type", melee_main[0].item.item_type == "weapon")

# Check empty slots
helmet_slot = [s for s in overview.slots if s.slot == "helmet"]
check("has helmet slot", len(helmet_slot) == 1)
if helmet_slot:
    check("helmet slot is empty", helmet_slot[0].item is None)


# =========================================================================
print("\n=== Test 3: get_equippable_items() ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Add items to inventory
longsword = create_longsword(entity.uuid)
dagger = create_dagger(entity.uuid)
leather = create_leather_armor(entity.uuid)

entity.inventory.add_item(longsword)
entity.inventory.add_item(dagger)
entity.inventory.add_item(leather)

equippable = entity.get_equippable_items()

check("equippable is dict", isinstance(equippable, dict))
check("has weapon_melee_main slot", "weapon_melee_main" in equippable)
check("longsword in weapon_melee_main", any(
    e["item_name"] == "Longsword" for e in equippable.get("weapon_melee_main", [])
))
check("dagger in weapon_melee_main", any(
    e["item_name"] == "Dagger" for e in equippable.get("weapon_melee_main", [])
))
# Dagger is Light, so it should also be in weapon_melee_off
check("dagger in weapon_melee_off (Light)", any(
    e["item_name"] == "Dagger" for e in equippable.get("weapon_melee_off", [])
))
# Longsword is NOT Light, so it should NOT be in weapon_melee_off
check("longsword NOT in weapon_melee_off", not any(
    e["item_name"] == "Longsword" for e in equippable.get("weapon_melee_off", [])
))
# Leather armor should be in body_armor
check("leather armor in body_armor", any(
    e["item_name"] == "Leather Armor" for e in equippable.get("body_armor", [])
))

# Check swap info — goblin has scimitar in melee_main
melee_main_entries = equippable.get("weapon_melee_main", [])
if melee_main_entries:
    first = melee_main_entries[0]
    check("swap info has swap_item_name", first["swap_item_name"] is not None)
    check("swap item is Scimitar", first["swap_item_name"] == "Scimitar")


# =========================================================================
print("\n=== Test 4: Equip from inventory ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Unequip the goblin's existing weapon first
entity.equipment.unequip(WeaponSlot.MELEE_MAIN)

# Add a longsword to inventory
longsword = create_longsword(entity.uuid)
entity.inventory.add_item(longsword)
check("inventory has longsword", entity.inventory.has_item(longsword.uuid))
check("melee_main is empty", entity.equipment.weapon_melee_main is None)

inv_count_before = entity.inventory.item_count

# Equip from inventory
entity.inventory.remove_item(longsword.uuid)
entity.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)

check("longsword equipped in melee_main", entity.equipment.weapon_melee_main is not None)
check("equipped weapon is longsword", entity.equipment.weapon_melee_main is longsword)
check("inventory reduced by 1", entity.inventory.item_count == inv_count_before - 1)
check("longsword not in inventory", not entity.inventory.has_item(longsword.uuid))


# =========================================================================
print("\n=== Test 5: Unequip to inventory ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Goblin has scimitar equipped
check("has melee_main weapon", entity.equipment.weapon_melee_main is not None)
weapon_name = entity.equipment.weapon_melee_main.name if entity.equipment.weapon_melee_main else ""

inv_count_before = entity.inventory.item_count

# Unequip to inventory
unequipped = entity.equipment.unequip(WeaponSlot.MELEE_MAIN)
check("unequip returns item", unequipped is not None)
if unequipped:
    check("unequipped item name matches", unequipped.name == weapon_name)
    unequipped.owner_uuid = entity.uuid
    unequipped.stored_in_uuid = entity.inventory.uuid
    entity.inventory.add_item(unequipped)
    check("inventory increased by 1", entity.inventory.item_count == inv_count_before + 1)
    check("item in inventory", entity.inventory.has_item(unequipped.uuid))

check("slot is now empty", entity.equipment.weapon_melee_main is None)


# =========================================================================
print("\n=== Test 6: Swap (equip when slot occupied) ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Goblin has scimitar in melee_main
old_weapon = entity.equipment.weapon_melee_main
check("starts with scimitar", old_weapon is not None and old_weapon.name == "Scimitar")
old_weapon_uuid = old_weapon.uuid if old_weapon else None

# Add longsword to inventory
longsword = create_longsword(entity.uuid)
entity.inventory.add_item(longsword)

# Equip longsword — this should auto-unequip scimitar
# First capture old item, remove new from inventory
old_item_before = entity.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
entity.inventory.remove_item(longsword.uuid)
entity.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)

# Old item was unequipped by equip() internally — add to inventory
if old_item_before is not None:
    old_item_before.owner_uuid = entity.uuid
    old_item_before.stored_in_uuid = entity.inventory.uuid
    entity.inventory.add_item(old_item_before)

check("longsword now equipped", entity.equipment.weapon_melee_main is longsword)
check("old scimitar in inventory", old_weapon_uuid is not None and entity.inventory.has_item(old_weapon_uuid))


# =========================================================================
print("\n=== Test 7: Invalid operations ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Try to equip melee weapon in ranged slot
longsword = create_longsword(entity.uuid)
try:
    entity.equipment.equip(longsword, WeaponSlot.RANGED_MAIN)
    check("melee weapon in ranged slot should fail", False)
except ValueError:
    check("melee weapon in ranged slot raises ValueError", True)

# Try to equip ranged weapon in melee slot
longbow = create_longbow(entity.uuid)
try:
    entity.equipment.equip(longbow, WeaponSlot.MELEE_MAIN)
    check("ranged weapon in melee slot should fail", False)
except ValueError:
    check("ranged weapon in melee slot raises ValueError", True)

# Test equipping non-light weapon in off-hand
try:
    entity.equipment.equip(longsword, WeaponSlot.MELEE_OFF)
    check("non-light weapon in off-hand should fail", False)
except ValueError:
    check("non-light weapon in off-hand raises ValueError", True)


# =========================================================================
print("\n=== Test 8: APIEquipmentOverview reflects inventory items ===")
# =========================================================================

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

# Add items to inventory
dagger = create_dagger(entity.uuid)
potion = create_healing_potion(entity.uuid)
entity.inventory.add_item(dagger)
entity.inventory.add_item(potion)

overview = APIEquipmentOverview.create(entity)
check("inventory has 2 items", len(overview.inventory) == 2)

inv_names = [i.name for i in overview.inventory]
check("dagger in inventory overview", "Dagger" in inv_names)
check("potion in inventory overview", "Potion of Healing" in inv_names)


# =========================================================================
print("\n=== Test 9: APIEntityFull includes equipment field ===")
# =========================================================================

from server.api_models import APIEntityFull

reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)

entity = create_goblin(name="Gobby", position=(5, 5), faction="monsters")
Entity.update_all_entities_senses()

full = APIEntityFull.create(entity)
check("APIEntityFull has equipment field", full.equipment is not None)
if full.equipment:
    check("equipment has slots", len(full.equipment.slots) == 13)
    check("equipment has ac", isinstance(full.equipment.ac, int))


# =========================================================================
# Summary
# =========================================================================

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
