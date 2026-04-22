"""Focused checks for equipment visual metadata and factory inventory swaps."""

import sys
import traceback

sys.path.insert(0, ".")

from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.core.events import BodyPart
from dnd.core.gridmap import get_map
from dnd.utils import reset_combat_state
from server.api_models import APIEquipmentOverview


tests_passed = 0
tests_failed = 0


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    get_map().create_rectangle(0, 0, 10, 10)
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def slot_item(overview: APIEquipmentOverview, slot_name: str):
    for slot in overview.slots:
        if slot.slot == slot_name:
            return slot.item
    raise AssertionError(f"Missing slot {slot_name}")


def inventory_item(entity, name: str, variant_id: str | None = None):
    for item in entity.inventory.items.values():
        if item.name != name:
            continue
        if variant_id is None or item.visual_variant_id == variant_id:
            return item
    raise AssertionError(f"Missing inventory item {name} variant={variant_id}")


def test_sorcerer_has_swappable_visual_clothing():
    sorc = create_sorcerer(SorcererConfig(
        level=5,
        name="Visual Sorcerer",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    ))

    overview = APIEquipmentOverview.create(sorc)
    body = slot_item(overview, "body_armor")
    boots = slot_item(overview, "boots")

    assert body is not None
    assert body.name == "Robes"
    assert body.visual_item_name == "Robes"
    assert body.visual_variant_id == "81000005"
    assert boots is not None
    assert boots.name == "Cloth Shoes"
    assert boots.visual_item_name == "Cloth Shoes"
    assert boots.visual_variant_id == "b0000004"
    assert sorc.ac_bonus().normalized_score == 15

    alt_robes = inventory_item(sorc, "Robes", "81000001")
    alt_shoes = inventory_item(sorc, "Cloth Shoes", "b0000005")
    wizard_hat = inventory_item(sorc, "Wizard's Hat", "h0000011")
    assert alt_robes is not None
    assert alt_shoes is not None
    assert wizard_hat.visual_item_name == "Wizard's Hat"

    equippable = sorc.get_equippable_items()
    assert any(e["item_uuid"] == str(alt_robes.uuid) for e in equippable.get("body_armor", []))
    assert any(e["item_uuid"] == str(alt_shoes.uuid) for e in equippable.get("boots", []))
    assert any(e["item_uuid"] == str(wizard_hat.uuid) for e in equippable.get("helmet", []))

    old_body_uuid = sorc.equipment.body_armor.uuid
    assert sorc.equip_item(alt_robes.uuid, BodyPart.BODY)

    overview = APIEquipmentOverview.create(sorc)
    body = slot_item(overview, "body_armor")
    assert body is not None
    assert body.visual_variant_id == "81000001"
    assert old_body_uuid in sorc.inventory.items
    assert sorc.ac_bonus().normalized_score == 15

    assert sorc.equip_item(wizard_hat.uuid, BodyPart.HEAD)
    overview = APIEquipmentOverview.create(sorc)
    helmet = slot_item(overview, "helmet")
    assert helmet is not None
    assert helmet.name == "Wizard's Hat"
    assert helmet.visual_variant_id == "h0000011"


def test_fighter_has_swappable_visual_boots():
    fighter = create_fighter(FighterConfig(
        level=5,
        name="Visual Fighter",
        equipment_preset="archery",
        fighting_style="archery",
        asi_4=[("dexterity", 2)],
    ))

    overview = APIEquipmentOverview.create(fighter)
    boots = slot_item(overview, "boots")

    assert boots is not None
    assert boots.name == "Leather Boots"
    assert boots.visual_item_name == "Leather Boots"
    assert boots.visual_variant_id == "b0000009"

    alt_shoes = inventory_item(fighter, "Cloth Shoes")
    helmet = inventory_item(fighter, "Iron Helmet", "h0000008")
    equippable = fighter.get_equippable_items()
    assert any(e["item_uuid"] == str(alt_shoes.uuid) for e in equippable.get("boots", []))
    assert any(e["item_uuid"] == str(helmet.uuid) for e in equippable.get("helmet", []))

    old_boots_uuid = fighter.equipment.boots.uuid
    assert fighter.equip_item(alt_shoes.uuid, BodyPart.FEET)

    overview = APIEquipmentOverview.create(fighter)
    boots = slot_item(overview, "boots")
    assert boots is not None
    assert boots.name == "Cloth Shoes"
    assert boots.visual_variant_id is None
    assert old_boots_uuid in fighter.inventory.items

    assert fighter.equip_item(helmet.uuid, BodyPart.HEAD)
    overview = APIEquipmentOverview.create(fighter)
    equipped_helmet = slot_item(overview, "helmet")
    assert equipped_helmet is not None
    assert equipped_helmet.name == "Iron Helmet"
    assert equipped_helmet.visual_variant_id == "h0000008"


print("\n=== Equipment Visual Metadata Tests ===")
run_test("sorcerer visual clothing can be swapped", test_sorcerer_has_swappable_visual_clothing)
run_test("fighter visual boots can be swapped", test_fighter_has_swappable_visual_boots)

print(f"\nResults: {tests_passed} passed, {tests_failed} failed")
if tests_failed:
    sys.exit(1)
