#!/usr/bin/env python3
"""
Test Equipment & Inventory API endpoints.

Tests:
1. GET /entity/{uuid}/equipment — slots, ac, inventory
2. GET /entity/{uuid}/equipment/item/{item_uuid} — single item detail
3. GET /entity/{uuid}/equippable-items — inventory items by valid slot
4. POST /entity/{uuid}/equip — equip from inventory (swap)
5. POST /entity/{uuid}/unequip — unequip to inventory
6. Error cases — wrong slot, non-existent item, empty slot
7. GET /entity/{uuid} includes equipment field

Usage:
    # Start server first:
    uvicorn server.event_server:app --reload

    # Run test:
    python examples/server_tests/test_equipment_api.py
"""

import requests
import sys

BASE_URL = "http://localhost:8000"

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


def setup_game():
    """Start simulation, create session, join game."""
    resp = requests.post(f"{BASE_URL}/simulation/start-human")
    assert resp.ok, f"Failed to start simulation: {resp.text}"
    hero_uuid = resp.json()["hero_uuid"]
    print(f"  Hero UUID: {hero_uuid}")

    resp = requests.post(f"{BASE_URL}/session/create", json={
        "player_type": "human", "name": "Test Player"
    })
    assert resp.ok, f"Failed to create session: {resp.text}"
    session_id = resp.json()["session_id"]
    print(f"  Session ID: {session_id}")

    resp = requests.post(f"{BASE_URL}/game/join", json={
        "session_id": session_id, "entity_uuids": [hero_uuid]
    })
    assert resp.ok, f"Failed to join game: {resp.text}"

    return session_id, hero_uuid


def test_get_equipment(hero_uuid):
    print("\n=== Test 1: GET /entity/{uuid}/equipment ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment")
    check("returns 200", resp.ok)
    data = resp.json()

    check("has 'slots'", "slots" in data)
    check("has 'ac'", "ac" in data)
    check("has 'inventory'", "inventory" in data)
    check("13 slots", len(data["slots"]) == 13)

    slot_names = [s["slot"] for s in data["slots"]]
    check("weapon_melee_main exists", "weapon_melee_main" in slot_names)
    check("body_armor exists", "body_armor" in slot_names)

    melee_main = next((s for s in data["slots"] if s["slot"] == "weapon_melee_main"), None)
    if melee_main and melee_main["item"]:
        item = melee_main["item"]
        check("equipped weapon is weapon type", item["item_type"] == "weapon")
        check("weapon has damage_dice", item.get("damage_dice") is not None)
        print(f"    Weapon: {item['name']} ({item['damage_dice']})")

    check("inventory has items", len(data["inventory"]) > 0)
    print(f"    Inventory ({len(data['inventory'])} items):")
    for item in data["inventory"]:
        print(f"      - {item['name']} ({item['item_type']})")

    check("ac > 0", data["ac"] > 0)
    return data


def test_get_item_detail(hero_uuid, equipment_data):
    print("\n=== Test 2: GET /entity/{uuid}/equipment/item/{item_uuid} ===")

    # Equipped item
    equipped = None
    for slot in equipment_data["slots"]:
        if slot["item"]:
            equipped = slot["item"]
            break

    if equipped:
        resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment/item/{equipped['uuid']}")
        check("equipped item returns 200", resp.ok)
        check("name matches", resp.json()["name"] == equipped["name"])

    # Inventory item
    if equipment_data["inventory"]:
        inv = equipment_data["inventory"][0]
        resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment/item/{inv['uuid']}")
        check("inventory item returns 200", resp.ok)
        check("inv item name matches", resp.json()["name"] == inv["name"])

    # Non-existent
    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment/item/00000000-0000-0000-0000-000000000000")
    check("non-existent item returns 404", resp.status_code == 404)


def test_equippable_items(hero_uuid):
    print("\n=== Test 3: GET /entity/{uuid}/equippable-items ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equippable-items")
    check("returns 200", resp.ok)
    data = resp.json()

    check("has entity_uuid", data.get("entity_uuid") == hero_uuid)
    check("has equippable dict", isinstance(data.get("equippable"), dict))

    equippable = data["equippable"]
    if equippable:
        first_slot = list(equippable.keys())[0]
        first_entry = equippable[first_slot][0]
        check("entry has item_uuid", "item_uuid" in first_entry)
        check("entry has item_name", "item_name" in first_entry)
        check("entry has swap_item_name", "swap_item_name" in first_entry)
        check("entry has swap_item_uuid", "swap_item_uuid" in first_entry)

        for slot_name, items in equippable.items():
            for e in items:
                swap = f" (swap: {e['swap_item_name']})" if e.get("swap_item_name") else ""
                print(f"    {slot_name}: {e['item_name']}{swap}")

    return equippable


def test_equip(session_id, hero_uuid, equippable):
    print("\n=== Test 4: POST /entity/{uuid}/equip ===")

    if not equippable:
        check("has equippable items", False)
        return None

    # Pick first equippable item
    target_slot = list(equippable.keys())[0]
    target_entry = equippable[target_slot][0]
    item_uuid = target_entry["item_uuid"]
    item_name = target_entry["item_name"]
    old_name = target_entry.get("swap_item_name")

    print(f"    Equipping {item_name} → {target_slot}" +
          (f" (swapping {old_name})" if old_name else ""))

    resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/equip", json={
        "session_id": session_id,
        "item_uuid": item_uuid,
        "slot": target_slot,
    })
    check("equip returns 200", resp.ok)
    if not resp.ok:
        print(f"    Error: {resp.text}")
        return None

    data = resp.json()
    check("success=true", data.get("success"))
    check("response has equipment", "equipment" in data)

    eq = data["equipment"]
    slot_data = next((s for s in eq["slots"] if s["slot"] == target_slot), None)
    if slot_data and slot_data["item"]:
        check("item now in slot", slot_data["item"]["name"] == item_name)

    inv_names = [i["name"] for i in eq["inventory"]]
    check("item removed from inventory", item_name not in inv_names)
    if old_name:
        check(f"old item '{old_name}' in inventory", old_name in inv_names)

    return {"slot": target_slot, "item_name": item_name}


def test_unequip(session_id, hero_uuid, equip_result):
    print("\n=== Test 5: POST /entity/{uuid}/unequip ===")

    if equip_result:
        target_slot = equip_result["slot"]
        item_name = equip_result["item_name"]
    else:
        # Pick any equipped slot
        resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment")
        slots = resp.json()["slots"]
        equipped = next((s for s in slots if s["item"]), None)
        if not equipped:
            check("found equipped slot", False)
            return
        target_slot = equipped["slot"]
        item_name = equipped["item"]["name"]

    print(f"    Unequipping {item_name} from {target_slot}")

    resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/unequip", json={
        "session_id": session_id,
        "slot": target_slot,
    })
    check("unequip returns 200", resp.ok)
    if not resp.ok:
        print(f"    Error: {resp.text}")
        return

    data = resp.json()
    check("success=true", data.get("success"))

    eq = data["equipment"]
    slot_data = next((s for s in eq["slots"] if s["slot"] == target_slot), None)
    check("slot now empty", slot_data is not None and slot_data["item"] is None)

    inv_names = [i["name"] for i in eq["inventory"]]
    check(f"'{item_name}' now in inventory", item_name in inv_names)


def test_errors(session_id, hero_uuid):
    print("\n=== Test 6: Error cases ===")

    # Non-existent item
    resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/equip", json={
        "session_id": session_id,
        "item_uuid": "00000000-0000-0000-0000-000000000000",
        "slot": "weapon_melee_main",
    })
    check("non-existent item → 404", resp.status_code == 404)

    # Invalid slot name
    eq_resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/equipment")
    inv = eq_resp.json()["inventory"]
    weapon = next((i for i in inv if i["item_type"] == "weapon"), None)
    if weapon:
        resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/equip", json={
            "session_id": session_id,
            "item_uuid": weapon["uuid"],
            "slot": "invalid_slot",
        })
        check("invalid slot → 400", resp.status_code == 400)

    # Unequip empty slot
    empty = next((s for s in eq_resp.json()["slots"] if s["item"] is None), None)
    if empty:
        resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/unequip", json={
            "session_id": session_id,
            "slot": empty["slot"],
        })
        check("unequip empty slot → 400", resp.status_code == 400)

    # Invalid unequip slot
    resp = requests.post(f"{BASE_URL}/entity/{hero_uuid}/unequip", json={
        "session_id": session_id,
        "slot": "nonexistent",
    })
    check("invalid unequip slot → 400", resp.status_code == 400)


def test_entity_full(hero_uuid):
    print("\n=== Test 7: GET /entity/{uuid} includes equipment ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}")
    check("returns 200", resp.ok)
    data = resp.json()
    check("has equipment field", "equipment" in data)
    if data.get("equipment"):
        check("equipment has 13 slots", len(data["equipment"]["slots"]) == 13)
        check("equipment has ac", "ac" in data["equipment"])
        check("equipment has inventory", "inventory" in data["equipment"])


if __name__ == "__main__":
    print("=" * 60)
    print("Equipment & Inventory API Tests")
    print("Requires: uvicorn server.event_server:app --reload")
    print("=" * 60)

    # Quick check server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=2)
    except Exception:
        print("\nERROR: Server not running on localhost:8000")
        print("Start it with: uvicorn server.event_server:app --reload")
        sys.exit(1)

    try:
        session_id, hero_uuid = setup_game()
        eq_data = test_get_equipment(hero_uuid)
        test_get_item_detail(hero_uuid, eq_data)
        equippable = test_equippable_items(hero_uuid)
        equip_result = test_equip(session_id, hero_uuid, equippable)
        test_unequip(session_id, hero_uuid, equip_result)
        test_errors(session_id, hero_uuid)
        test_entity_full(hero_uuid)

        print(f"\n{'=' * 60}")
        print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
        if failed == 0:
            print("ALL TESTS PASSED!")
        else:
            print(f"FAILURES: {failed}")
        print("=" * 60)
        sys.exit(1 if failed else 0)

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
