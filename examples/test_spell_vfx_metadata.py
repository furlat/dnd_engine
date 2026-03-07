"""Test spell VFX metadata on SpellEvent.

Validates that SpellAction propagates VFX metadata (aoe_shape_type, aoe_radius_ft,
range_type, range_ft, projectile_type) to SpellEvent at declaration time.
"""
from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.actions import SpellEvent
from dnd.spells.evocation import (
    FireBolt, Fireball, BurningHands, LightningBolt, IceStorm, MagicMissile,
    CureWounds, ShockingGrasp, Shatter, FlameStrike,
)
from dnd.spells.necromancy import ChillTouch, InflictWounds


passed = 0
failed = 0


def check(test_name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {test_name}")
    else:
        failed += 1
        print(f"  FAIL: {test_name} {detail}")


def get_declaration_event(spell_class, caster, target=None, position=None, **kwargs) -> SpellEvent:
    """Create a spell instance and get its declaration event."""
    spell_kwargs = {
        "source_entity_uuid": caster.uuid,
        "use_register": False,
    }
    if target:
        spell_kwargs["target_entity_uuid"] = target.uuid
    if position:
        spell_kwargs["end_position"] = position
    spell_kwargs.update(kwargs)
    spell = spell_class(**spell_kwargs)
    event = spell._create_declaration_event(use_register=False)
    assert isinstance(event, SpellEvent), f"Expected SpellEvent, got {type(event)}"
    return event


# =============================================================================
# Setup
# =============================================================================
print("=" * 60)
print("TEST: Spell VFX Metadata on SpellEvent")
print("=" * 60)

reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 30, 30)

caster = create_skeleton(name="Wizard", position=(5, 5), faction="party")
target = create_skeleton(name="Skeleton", position=(10, 5), faction="undead")
Entity.update_all_entities_senses()


# =============================================================================
# Test 1: Fireball - ranged AoE sphere with orb projectile
# =============================================================================
print("\n--- Test 1: Fireball ---")
event = get_declaration_event(Fireball, caster, position=(10, 5))
check("aoe_shape_type is 'sphere'", event.aoe_shape_type == "sphere", f"got {event.aoe_shape_type}")
check("aoe_radius_ft is 20", event.aoe_radius_ft == 20, f"got {event.aoe_radius_ft}")
check("range_type is 'ranged'", event.range_type == "ranged", f"got {event.range_type}")
check("range_ft is 150", event.range_ft == 150, f"got {event.range_ft}")
check("projectile_type is 'orb'", event.projectile_type == "orb", f"got {event.projectile_type}")

# =============================================================================
# Test 2: Fire Bolt - single target ranged with bolt projectile
# =============================================================================
print("\n--- Test 2: Fire Bolt ---")
event = get_declaration_event(FireBolt, caster, target=target)
check("aoe_shape_type is None", event.aoe_shape_type is None, f"got {event.aoe_shape_type}")
check("aoe_radius_ft is None", event.aoe_radius_ft is None, f"got {event.aoe_radius_ft}")
check("range_type is 'ranged'", event.range_type == "ranged", f"got {event.range_type}")
check("range_ft is 120", event.range_ft == 120, f"got {event.range_ft}")
check("projectile_type is 'bolt'", event.projectile_type == "bolt", f"got {event.projectile_type}")

# =============================================================================
# Test 3: Burning Hands - self-origin AoE cone, no projectile
# =============================================================================
print("\n--- Test 3: Burning Hands ---")
event = get_declaration_event(BurningHands, caster, position=(6, 5))
check("aoe_shape_type is 'cone'", event.aoe_shape_type == "cone", f"got {event.aoe_shape_type}")
check("aoe_radius_ft is 15", event.aoe_radius_ft == 15, f"got {event.aoe_radius_ft}")
check("range_type is 'self'", event.range_type == "self", f"got {event.range_type}")
check("projectile_type is None", event.projectile_type is None, f"got {event.projectile_type}")

# =============================================================================
# Test 4: Lightning Bolt - self-origin AoE line, no projectile
# =============================================================================
print("\n--- Test 4: Lightning Bolt ---")
event = get_declaration_event(LightningBolt, caster, position=(15, 5))
check("aoe_shape_type is 'line'", event.aoe_shape_type == "line", f"got {event.aoe_shape_type}")
check("aoe_radius_ft is 100", event.aoe_radius_ft == 100, f"got {event.aoe_radius_ft}")
check("range_type is 'self'", event.range_type == "self", f"got {event.range_type}")
check("projectile_type is None", event.projectile_type is None, f"got {event.projectile_type}")

# =============================================================================
# Test 5: Cure Wounds - touch, no AoE, no projectile
# =============================================================================
print("\n--- Test 5: Cure Wounds ---")
event = get_declaration_event(CureWounds, caster, target=target)
check("aoe_shape_type is None", event.aoe_shape_type is None, f"got {event.aoe_shape_type}")
check("range_type is 'touch'", event.range_type == "touch", f"got {event.range_type}")
check("range_ft is 5", event.range_ft == 5, f"got {event.range_ft}")
check("projectile_type is None", event.projectile_type is None, f"got {event.projectile_type}")

# =============================================================================
# Test 6: Magic Missile - ranged multi-entity with dart projectile
# =============================================================================
print("\n--- Test 6: Magic Missile ---")
event = get_declaration_event(MagicMissile, caster, target=target)
check("range_type is 'ranged'", event.range_type == "ranged", f"got {event.range_type}")
check("range_ft is 120", event.range_ft == 120, f"got {event.range_ft}")
check("projectile_type is 'dart'", event.projectile_type == "dart", f"got {event.projectile_type}")
check("aoe_shape_type is None", event.aoe_shape_type is None, f"got {event.aoe_shape_type}")

# =============================================================================
# Test 7: Ice Storm - ranged AoE cylinder with rain projectile
# =============================================================================
print("\n--- Test 7: Ice Storm ---")
event = get_declaration_event(IceStorm, caster, position=(10, 5))
check("aoe_shape_type is 'cylinder'", event.aoe_shape_type == "cylinder", f"got {event.aoe_shape_type}")
check("range_type is 'ranged'", event.range_type == "ranged", f"got {event.range_type}")
check("projectile_type is 'rain'", event.projectile_type == "rain", f"got {event.projectile_type}")
check("aoe_radius_ft is 20", event.aoe_radius_ft == 20, f"got {event.aoe_radius_ft}")

# =============================================================================
# Test 8: Shocking Grasp - touch with touch projectile
# =============================================================================
print("\n--- Test 8: Shocking Grasp ---")
event = get_declaration_event(ShockingGrasp, caster, target=target)
check("range_type is 'touch'", event.range_type == "touch", f"got {event.range_type}")
check("projectile_type is 'touch'", event.projectile_type == "touch", f"got {event.projectile_type}")

# =============================================================================
# Test 9: Serialization - all fields serialize cleanly
# =============================================================================
print("\n--- Test 9: Serialization ---")
event = get_declaration_event(Fireball, caster, position=(10, 5))
data = event.model_dump(mode='json')
check("aoe_shape_type serializes", data.get("aoe_shape_type") == "sphere")
check("aoe_radius_ft serializes", data.get("aoe_radius_ft") == 20)
check("range_type serializes", data.get("range_type") == "ranged")
check("range_ft serializes", data.get("range_ft") == 150)
check("projectile_type serializes", data.get("projectile_type") == "orb")

# Also test null serialization
event2 = get_declaration_event(CureWounds, caster, target=target)
data2 = event2.model_dump(mode='json')
check("null aoe_shape_type serializes", data2.get("aoe_shape_type") is None)
check("null projectile_type serializes", data2.get("projectile_type") is None)

# =============================================================================
# Test 10: Shatter - ranged AoE sphere with orb
# =============================================================================
print("\n--- Test 10: Shatter ---")
event = get_declaration_event(Shatter, caster, position=(10, 5))
check("aoe_shape_type is 'sphere'", event.aoe_shape_type == "sphere", f"got {event.aoe_shape_type}")
check("projectile_type is 'orb'", event.projectile_type == "orb", f"got {event.projectile_type}")
check("aoe_radius_ft is 10", event.aoe_radius_ft == 10, f"got {event.aoe_radius_ft}")

# =============================================================================
# Test 11: FlameStrike - ranged cylinder with radiance
# =============================================================================
print("\n--- Test 11: FlameStrike ---")
event = get_declaration_event(FlameStrike, caster, position=(10, 5))
check("aoe_shape_type is 'cylinder'", event.aoe_shape_type == "cylinder", f"got {event.aoe_shape_type}")
check("projectile_type is 'radiance'", event.projectile_type == "radiance", f"got {event.projectile_type}")

# =============================================================================
# Test 12: Necromancy spell projectile types
# =============================================================================
print("\n--- Test 12: Necromancy projectile types ---")
event = get_declaration_event(ChillTouch, caster, target=target)
check("ChillTouch projectile_type is 'orb'", event.projectile_type == "orb", f"got {event.projectile_type}")

event = get_declaration_event(InflictWounds, caster, target=target)
check("InflictWounds projectile_type is 'touch'", event.projectile_type == "touch", f"got {event.projectile_type}")
check("InflictWounds range_type is 'touch'", event.range_type == "touch", f"got {event.range_type}")


# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
print("=" * 60)

if failed > 0:
    raise SystemExit(1)
