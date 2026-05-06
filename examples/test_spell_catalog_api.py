"""Focused tests for the backend spell catalog API.

Run with:
    python examples/test_spell_catalog_api.py
"""

import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dnd.actions import SpellEvent
from dnd.core.base_object import BaseObject
from dnd.spells import ALL_SPELLS, FireBolt
from server.event_server import app
from server.spell_catalog import build_spell_catalog


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  PASSED: {message}")


def test_catalog_builder() -> None:
    before_registry_count = len(BaseObject._registry)
    catalog = build_spell_catalog()
    after_registry_count = len(BaseObject._registry)

    check(bool(catalog.version), "catalog has a version")
    check(len(catalog.spells) == len(ALL_SPELLS), "catalog enumerates every ALL_SPELLS entry")
    check(after_registry_count == before_registry_count, "catalog build does not register spell templates")

    ids = [spell.id for spell in catalog.spells]
    check(len(ids) == len(set(ids)), "catalog spell ids are unique")

    by_id = {spell.id: spell for spell in catalog.spells}
    fire_bolt = by_id["fire_bolt"]
    check(fire_bolt.name == "Fire Bolt", "Fire Bolt has stable display name")
    check(fire_bolt.level == 0, "Fire Bolt is a cantrip")
    check(fire_bolt.projectile_type == "bolt", "Fire Bolt exposes projectile type")
    check(fire_bolt.range_type == "ranged" and fire_bolt.range_ft == 120, "Fire Bolt exposes range metadata")
    check(fire_bolt.attack_roll is True, "Fire Bolt is marked as attack-roll spell")
    check(fire_bolt.vfx is not None and fire_bolt.vfx.route_hint == "single_projectile", "Fire Bolt has projectile route hint")

    magic_missile = by_id["magic_missile"]
    check(magic_missile.projectile_type == "dart", "Magic Missile exposes dart projectile")
    check(magic_missile.multi_target is not None, "Magic Missile exposes multi-target metadata")
    if magic_missile.multi_target is None:
        raise AssertionError("Magic Missile multi-target metadata missing")
    check(magic_missile.multi_target.projectiles_per_cast == 3, "Magic Missile exposes base dart count")
    check(magic_missile.multi_target.allow_same_target is True, "Magic Missile allows repeated targets")
    check(magic_missile.vfx is not None and magic_missile.vfx.route_hint == "missile_volley", "Magic Missile uses volley route")

    fireball = by_id["fireball"]
    check(fireball.aoe_shape_type == "sphere", "Fireball exposes sphere AoE")
    check(fireball.aoe_radius_ft == 20, "Fireball exposes AoE radius")
    check(fireball.projectile_type == "orb", "Fireball exposes projectile type")
    check(fireball.saving_throw is not None and fireball.saving_throw.ability == "DEX", "Fireball exposes save ability")
    check(fireball.vfx is not None and fireball.vfx.route_hint == "aoe_projectile", "Fireball uses AoE projectile route")

    catalog.model_dump(mode="json")
    check(True, "catalog response serializes to JSON-compatible data")


def test_catalog_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/catalog/spells")
    check(response.status_code == 200, "spell catalog endpoint returns 200")
    data = response.json()
    check(data["version"], "endpoint includes version")
    check(len(data["spells"]) == len(ALL_SPELLS), "endpoint returns every spell")
    ids = {entry["id"] for entry in data["spells"]}
    check({"fire_bolt", "magic_missile", "fireball"}.issubset(ids), "endpoint includes key VFX spells")


def test_spell_event_includes_spell_id() -> None:
    spell = FireBolt(source_entity_uuid=uuid4(), target_entity_uuid=uuid4(), use_register=False)
    event = spell._create_declaration_event(use_register=False)
    check(isinstance(event, SpellEvent), "Fire Bolt declaration creates a SpellEvent")
    if event is None:
        raise AssertionError("Fire Bolt declaration did not create an event")
    check(event.spell_id == "fire_bolt", "SpellEvent carries stable spell_id")


def main() -> None:
    print("\n=== Spell Catalog API Tests ===")
    test_catalog_builder()
    test_catalog_endpoint()
    test_spell_event_includes_spell_id()
    print("\nALL SPELL CATALOG API TESTS PASSED")


if __name__ == "__main__":
    main()
