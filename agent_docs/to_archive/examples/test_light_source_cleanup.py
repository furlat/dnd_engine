"""Tests for light source cleanup on entity death and item destruction.

Verifies that:
1. Entity death removes attached light sources from GridMap
2. Item destruction removes attached light sources
3. Torch + entity death cleans up properly
4. Torch destruction while lit calls extinguish via _on_destroy
5. Zone spell cleanup (existing system 2) still works
6. Multiple light sources on one entity are all cleaned up
7. No stale references after death cleanup
"""

import sys
from uuid import uuid4

from dnd.utils import reset_combat_state, setup_combat_arena, deal_damage_to, get_hp
from dnd.entity import Entity
from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton, create_caster
from dnd.actions_functional import setup_standard_actions
from dnd.items.test_items import create_torch
from dnd.spells.conjuration import Darkness

# Test tracking
passed = 0
failed = 0


def check(description: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {description}")
    else:
        failed += 1
        print(f"  [FAIL] {description}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print(f"{'='*60}")


def tile_at(x: int, y: int) -> Tile:
    grid = get_map()
    t = grid.get_tile(x, y)
    assert t is not None, f"No tile at ({x}, {y})"
    return t


# =============================================================================
# Test 1: Entity death removes attached light sources
# =============================================================================
section("Entity death removes attached light sources")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

entity = create_skeleton(name="Torch Bearer", position=(5, 5))
setup_standard_actions(entity)
Entity.update_all_entities_senses()

# Add a light source directly anchored to the entity
light_uuid = grid.add_light_source(
    position=(5, 5),
    bright_radius_feet=20,
    dim_radius_feet=20,
    anchor_uuid=entity.uuid
)

check("Light source exists in GridMap", light_uuid in grid._light_sources)
check("Light source attached to entity", light_uuid in entity.get_attached_light_sources())

# Verify some tiles are illuminated
center_tile = tile_at(5, 5)
check("Center tile is bright", center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Kill the entity via deal_damage_to (triggers DeathEvent -> Dead condition -> cleanup)
entity_hp = get_hp(entity)
deal_damage_to(entity, entity_hp + 10)

check("Entity is dead", "Dead" in entity.active_conditions)
check("Light source removed from GridMap", light_uuid not in grid._light_sources)
check("Light source detached from entity", len(entity.get_attached_light_sources()) == 0)


# =============================================================================
# Test 2: Item destruction removes attached light sources
# =============================================================================
section("Item destruction removes attached light sources")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

# Create a simple breakable item (BaseItem subclass) and attach a light source
from dnd.blocks.base_item import BaseItem
item = BaseItem(
    name="Glowing Orb",
    source_entity_uuid=uuid4(),
    is_pickable=True,
)

# Place on grid and add a light source anchored to it
grid.place_object(item.uuid, (5, 5))
light_uuid = grid.add_light_source(
    position=(5, 5),
    bright_radius_feet=10,
    dim_radius_feet=10,
    anchor_uuid=item.uuid
)

check("Light source exists in GridMap", light_uuid in grid._light_sources)
check("Light source attached to item", light_uuid in item.get_attached_light_sources())

# Destroy the item
item.destroy()

check("Light source removed from GridMap after item destroy", light_uuid not in grid._light_sources)


# =============================================================================
# Test 3: Torch + entity death
# =============================================================================
section("Torch + entity death removes torch light")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

bearer = create_skeleton(name="Torch Bearer", position=(5, 5))
setup_standard_actions(bearer)
Entity.update_all_entities_senses()

# Create torch in inventory and ignite it
torch = create_torch(bearer.uuid)
bearer.inventory.add_item(torch)
torch.ignite(bearer.uuid)

check("Torch is lit", torch.is_lit)
check("Torch light source exists", torch._light_source_uuid is not None)
torch_light_uuid = torch._light_source_uuid
check("Light in GridMap", torch_light_uuid in grid._light_sources)

# The light is anchored to the bearer entity (not the torch item)
check("Light attached to bearer entity", torch_light_uuid in bearer.get_attached_light_sources())

# Verify illumination
nearby_tile = tile_at(6, 5)
check("Nearby tile illuminated", nearby_tile.resolved_light_level != LightLevel.DARKNESS)

# Kill the bearer
bearer_hp = get_hp(bearer)
deal_damage_to(bearer, bearer_hp + 10)

check("Bearer is dead", "Dead" in bearer.active_conditions)
check("Torch light removed from GridMap", torch_light_uuid not in grid._light_sources)
check("Bearer has no attached light sources", len(bearer.get_attached_light_sources()) == 0)


# =============================================================================
# Test 4: Torch destruction while lit
# =============================================================================
section("Torch destruction while lit calls extinguish")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

carrier = create_skeleton(name="Carrier", position=(5, 5))
setup_standard_actions(carrier)
Entity.update_all_entities_senses()

torch2 = create_torch(carrier.uuid)
carrier.inventory.add_item(torch2)
torch2.ignite(carrier.uuid)

check("Torch is lit", torch2.is_lit)
torch2_light_uuid = torch2._light_source_uuid
check("Light in GridMap", torch2_light_uuid in grid._light_sources)

# Destroy the torch directly (not via entity death)
torch2.destroy()

check("Torch extinguished by _on_destroy", not torch2.is_lit)
check("Light removed from GridMap", torch2_light_uuid not in grid._light_sources)
check("Carrier has no attached light sources", len(carrier.get_attached_light_sources()) == 0)


# =============================================================================
# Test 5: Zone spell cleanup (existing system 2 validation)
# =============================================================================
section("Zone spell cleanup (existing behavior)")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

caster = create_caster(level=5, name="Caster", position=(0, 0))
target_dummy = create_skeleton(name="Target", position=(8, 0), faction="monsters")
Entity.update_all_entities_senses()

encounter = setup_combat_arena(caster, target_dummy)
encounter.start_encounter()
encounter.start_turn()

# Cast Darkness at (5, 5) — direct instantiation
dark_spell = Darkness(source_entity_uuid=caster.uuid, end_position=(5, 5))
dark_spell.apply()

# Verify darkness is applied
center = tile_at(5, 5)
check("Darkness zone applied to center tile",
      center.resolved_light_level == LightLevel.MAGICAL_DARKNESS)

# Remove concentration (removes Darkness zone via linked_conditions cleanup)
check("Concentrating condition applied", "Concentrating" in caster.active_conditions)
caster.remove_condition("Concentrating")

# Tiles should be back to normal
center_after = tile_at(5, 5)
check("Darkness removed after concentration break",
      center_after.resolved_light_level != LightLevel.MAGICAL_DARKNESS)


# =============================================================================
# Test 6: Multiple light sources on one entity
# =============================================================================
section("Multiple light sources on one entity")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

multi_entity = create_skeleton(name="Multi Light", position=(5, 5))
setup_standard_actions(multi_entity)
Entity.update_all_entities_senses()

# Attach two light sources
light1 = grid.add_light_source(
    position=(5, 5), bright_radius_feet=10, dim_radius_feet=10,
    anchor_uuid=multi_entity.uuid
)
light2 = grid.add_light_source(
    position=(5, 5), bright_radius_feet=20, dim_radius_feet=20,
    anchor_uuid=multi_entity.uuid
)

check("Two light sources attached", len(multi_entity.get_attached_light_sources()) == 2)
check("Light 1 in GridMap", light1 in grid._light_sources)
check("Light 2 in GridMap", light2 in grid._light_sources)

# Kill the entity
multi_hp = get_hp(multi_entity)
deal_damage_to(multi_entity, multi_hp + 10)

check("Entity is dead", "Dead" in multi_entity.active_conditions)
check("Light 1 removed", light1 not in grid._light_sources)
check("Light 2 removed", light2 not in grid._light_sources)
check("No attached light sources remain", len(multi_entity.get_attached_light_sources()) == 0)


# =============================================================================
# Test 7: No stale references after death cleanup
# =============================================================================
section("No stale light source references after death")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

stale_entity = create_skeleton(name="Stale Check", position=(3, 3))
setup_standard_actions(stale_entity)
Entity.update_all_entities_senses()

light_uuid = grid.add_light_source(
    position=(3, 3), bright_radius_feet=15, dim_radius_feet=15,
    anchor_uuid=stale_entity.uuid
)

# Kill entity
stale_hp = get_hp(stale_entity)
deal_damage_to(stale_entity, stale_hp + 10)

# Verify no light sources reference the dead entity's UUID as anchor
for ls_uuid, ls_data in grid._light_sources.items():
    check(f"Light source {ls_uuid} not anchored to dead entity",
          ls_data.anchor_uuid != stale_entity.uuid)

# Verify the removed light source doesn't appear in any data structure
check("Light UUID not in _light_sources", light_uuid not in grid._light_sources)


# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
