"""Tests for Torch and WallTorch items.

Tests torch ignite/extinguish cycle, WallTorch creation/toggle,
execute_use_action with non-template actions, and light level changes.
"""

import sys
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.entity import Entity
from dnd.core.base_block import LightLevel, BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton
from dnd.actions_functional import (
    setup_standard_actions, execute_use_action, get_available_actions, execute_by_index
)
from dnd.items.test_items import create_torch, create_wall_torch

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
# Setup
# =============================================================================
section("Setup")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

entity = create_skeleton(name="Torchbearer", position=(5, 5), faction="heroes")
setup_standard_actions(entity)
Entity.update_all_entities_senses()
check("Entity created at (5, 5)", entity.position == (5, 5))

# =============================================================================
# Test: Torch SRD radius values (Fix 4)
# =============================================================================
section("Torch SRD Radius")
torch = create_torch(entity.uuid)
check("Torch bright_radius_feet is 20", torch.bright_radius_feet == 20)
check("Torch dim_radius_feet is 20 (SRD standard)", torch.dim_radius_feet == 20)
check("Torch charges is -1 (unlimited)", torch.charges == -1)
check("Torch is_consumable is False", torch.is_consumable is False)

# =============================================================================
# Test: Torch ignite/extinguish cycle
# =============================================================================
section("Torch Ignite/Extinguish Cycle")
entity.loot_item(torch)
check("Torch starts unlit", torch.is_lit is False)

torch.ignite(entity.uuid)
check("Torch is lit after ignite", torch.is_lit is True)
check("Light source UUID exists", torch._light_source_uuid is not None)
check("Grid has light source", torch._light_source_uuid in grid._light_sources)

torch.extinguish()
check("Torch is unlit after extinguish", torch.is_lit is False)
check("Light source UUID cleared", torch._light_source_uuid is None)

# Re-ignite should work
torch.ignite(entity.uuid)
check("Torch re-ignites successfully", torch.is_lit is True)
check("New light source created", torch._light_source_uuid is not None)

# =============================================================================
# Test: Torch NOT destroyed on extinguish
# =============================================================================
section("Torch Survives Extinguish")
torch.extinguish()
retrieved = BaseBlock.get(torch.uuid)
check("Torch still exists after extinguish", retrieved is not None)
check("Torch is same object", retrieved is torch)
check("Torch charges still -1", torch.charges == -1)

# =============================================================================
# Test: Torch use actions via execute_use_action (Fix 1 code path)
# =============================================================================
section("Torch execute_use_action (Fix 1)")

# Ignite via execute_use_action
result = execute_use_action(entity, torch.uuid, "Ignite Torch")
check("execute_use_action Ignite Torch succeeded", result is not None and not result.canceled)
check("Torch is lit after execute_use_action", torch.is_lit is True)

# Extinguish via execute_use_action
result = execute_use_action(entity, torch.uuid, "Extinguish Torch")
check("execute_use_action Extinguish Torch succeeded", result is not None and not result.canceled)
check("Torch is unlit after execute_use_action", torch.is_lit is False)

# Re-ignite to verify toggle cycle works
result = execute_use_action(entity, torch.uuid, "Ignite Torch")
check("Re-ignite via execute_use_action succeeded", result is not None and not result.canceled)
check("Torch is lit again", torch.is_lit is True)

# =============================================================================
# Test: Torch use actions via execute_by_index (server code path)
# =============================================================================
section("Torch execute_by_index (Server Path)")

# Extinguish torch first so we can test ignite
torch.extinguish()
check("Torch extinguished for test", torch.is_lit is False)

actions = get_available_actions(entity)
# Find torch action in object_actions or self_actions
torch_action = None
for a in actions.all_actions:
    if "Ignite Torch" in a.template_name:
        torch_action = a
        break

check("Found Ignite Torch in available actions", torch_action is not None)
if torch_action:
    result = execute_by_index(entity, torch_action.template_name, 0, available=actions)
    check("execute_by_index Ignite Torch succeeded", result is not None and not result.canceled)
    check("Torch is lit after execute_by_index", torch.is_lit is True)

# =============================================================================
# Test: WallTorch creation
# =============================================================================
section("WallTorch Creation")
wt_pos = (8, 8)
wt = create_wall_torch(position=wt_pos, owner_uuid=uuid4(), lit=True)
check("WallTorch created", wt is not None)
check("WallTorch is_pickable is False", wt.is_pickable is False)
check("WallTorch is_equippable is False", wt.is_equippable is False)
check("WallTorch starts lit", wt.is_lit is True)
check("WallTorch has light source", wt._light_source_uuid is not None)
check("WallTorch on grid", wt.uuid in grid._object_positions)
check("WallTorch at correct position", grid.get_object_position(wt.uuid) == wt_pos)
objects_at = grid.get_objects_at(wt_pos)
check("WallTorch in objects_at", wt.uuid in objects_at)
check("WallTorch map_char is diamond", wt.map_char == "\u2666")

# =============================================================================
# Test: WallTorch toggle
# =============================================================================
section("WallTorch Toggle")
old_light_uuid = wt._light_source_uuid
wt.put_out()
check("WallTorch is unlit after put_out", wt.is_lit is False)
check("Light source removed", wt._light_source_uuid is None)
check("Old light source removed from grid", old_light_uuid not in grid._light_sources)

wt.light()
check("WallTorch is lit after light()", wt.is_lit is True)
check("New light source created", wt._light_source_uuid is not None)
check("New light source on grid", wt._light_source_uuid in grid._light_sources)

# =============================================================================
# Test: WallTorch use actions
# =============================================================================
section("WallTorch Use Actions")
# When lit, should return Extinguish action
lit_actions = wt.get_use_actions(entity.uuid)
check("Lit WallTorch returns 1 action", len(lit_actions) == 1)
check("Lit action is Extinguish", lit_actions[0].name == "Extinguish Wall Torch")

wt.put_out()
# When unlit, should return Ignite action
unlit_actions = wt.get_use_actions(entity.uuid)
check("Unlit WallTorch returns 1 action", len(unlit_actions) == 1)
check("Unlit action is Light", unlit_actions[0].name == "Light Wall Torch")

# =============================================================================
# Test: WallTorch use actions via execute_use_action (Fix 1 path)
# =============================================================================
section("WallTorch execute_use_action (Fix 1)")
# WallTorch is unlit from previous test
check("WallTorch starts unlit for this test", wt.is_lit is False)

result = execute_use_action(entity, wt.uuid, "Light Wall Torch")
check("execute_use_action Light Wall Torch succeeded", result is not None and not result.canceled)
check("WallTorch is lit", wt.is_lit is True)

result = execute_use_action(entity, wt.uuid, "Extinguish Wall Torch")
check("execute_use_action Extinguish Wall Torch succeeded", result is not None and not result.canceled)
check("WallTorch is unlit", wt.is_lit is False)

# =============================================================================
# Test: WallTorch created unlit
# =============================================================================
section("WallTorch Created Unlit")
wt_unlit = create_wall_torch(position=(2, 2), owner_uuid=uuid4(), lit=False)
check("Unlit WallTorch starts unlit", wt_unlit.is_lit is False)
check("Unlit WallTorch has no light source", wt_unlit._light_source_uuid is None)

# =============================================================================
# Test: Light levels change with torch ignite/extinguish
# =============================================================================
section("Light Level Changes")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

# Make all tiles dark
for pos, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

entity2 = create_skeleton(name="Torchbearer2", position=(5, 5), faction="heroes")
setup_standard_actions(entity2)
Entity.update_all_entities_senses()

# Check tile starts dark
tile_55 = tile_at(5, 5)
check("Tile (5,5) starts as DARKNESS", tile_55.resolved_light_level == LightLevel.DARKNESS)

# Create wall torch at (5,5) and light it
wt2 = create_wall_torch(position=(5, 5), owner_uuid=uuid4(), lit=True)
# After adding light source, tile should be bright
tile_55_after = tile_at(5, 5)
check("Tile (5,5) is VERY_BRIGHT after wall torch lit",
      tile_55_after.resolved_light_level == LightLevel.VERY_BRIGHT)

# Adjacent tile should be bright or dim (within 15ft = 3 tiles)
tile_adjacent = tile_at(5, 6)
check("Adjacent tile has light (not darkness)",
      tile_adjacent.resolved_light_level != LightLevel.DARKNESS)

# Extinguish
wt2.put_out()
tile_55_ext = tile_at(5, 5)
check("Tile (5,5) reverts to DARKNESS after extinguish",
      tile_55_ext.resolved_light_level == LightLevel.DARKNESS)

# Test carried torch too
torch2 = create_torch(entity2.uuid)
entity2.loot_item(torch2)
torch2.ignite(entity2.uuid)
tile_55_torch = tile_at(5, 5)
check("Tile (5,5) is VERY_BRIGHT after carried torch lit",
      tile_55_torch.resolved_light_level == LightLevel.VERY_BRIGHT)

torch2.extinguish()
tile_55_ext2 = tile_at(5, 5)
check("Tile (5,5) reverts to DARKNESS after carried torch extinguished",
      tile_55_ext2.resolved_light_level == LightLevel.DARKNESS)


# =============================================================================
# Test: Light-change visibility propagation (senses.visible update)
# =============================================================================
section("Light-Change Visibility Propagation")
reset_combat_state()
grid = get_map()
# Walled room: walls around perimeter, floor inside
grid.create_rectangle(0, 0, 16, 16, walkable=False, visible=False, name="Wall")
grid.create_rectangle(1, 1, 14, 14)  # Floor interior

# Make all floor tiles dark
for pos, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

# Create entity at (7,7) centered — no darkvision
observer = create_skeleton(name="Observer", position=(7, 7), faction="heroes", darkvision=False)
setup_standard_actions(observer)

# Create a distant skeleton at (10,7) — 3 tiles away = 15ft
far_skeleton = create_skeleton(name="FarSkel", position=(10, 7), faction="enemies")

# Create an adjacent skeleton at (6,7) — 1 tile away = 5ft
near_skeleton = create_skeleton(name="NearSkel", position=(6, 7), faction="enemies")

Entity.update_all_entities_senses()

# In full darkness, observer sees only 9 tiles (self + 8 adjacent via DIM rule)
dark_visible_count = len(observer.senses.visible)
print(f"  Visible in darkness (no torch): {dark_visible_count}")
check("In darkness, visible is exactly 9 (adjacent-DIM rule)", dark_visible_count == 9)

# Create torch and ignite
torch3 = create_torch(observer.uuid)
observer.loot_item(torch3)
torch3.ignite(observer.uuid)

# Force full senses update to pick up torch light
Entity.update_all_entities_senses()
lit_visible_count = len(observer.senses.visible)
print(f"  Visible with torch: {lit_visible_count}")
check("With torch, visible covers many tiles (> 50)", lit_visible_count > 50)
check("Far skeleton visible with torch", far_skeleton.uuid in observer.senses.entities)
check("Near skeleton visible with torch", near_skeleton.uuid in observer.senses.entities)

# Record seen set size before extinguish
seen_before_extinguish = len(observer.senses.seen)

# --- Extinguish torch → senses.visible should shrink via incremental update ---
torch3.extinguish()

dark_visible_after = len(observer.senses.visible)
print(f"  Visible after extinguish (incremental): {dark_visible_after}")
check("Extinguish restores visible to 9", dark_visible_after == 9)
check("Far skeleton NOT visible in dark", far_skeleton.uuid not in observer.senses.entities)
check("Near skeleton still visible (adjacent-DIM)", near_skeleton.uuid in observer.senses.entities)

# --- senses.seen only accumulates ---
seen_after_extinguish = len(observer.senses.seen)
check("senses.seen did not shrink", seen_after_extinguish >= seen_before_extinguish)

# --- Re-ignite torch → senses.visible should restore ---
torch3.ignite(observer.uuid)
Entity.update_all_entities_senses()
relit_visible_count = len(observer.senses.visible)
print(f"  Visible after re-ignite: {relit_visible_count}")
check("Re-ignite restores senses.visible to lit count", relit_visible_count == lit_visible_count)
check("Far skeleton visible again after re-ignite", far_skeleton.uuid in observer.senses.entities)

# --- Verify incremental path (no full update_all_entities_senses) ---
# Extinguish again and check WITHOUT calling update_all_entities_senses
torch3.extinguish()
incremental_visible = len(observer.senses.visible)
print(f"  Visible after 2nd extinguish (incremental only): {incremental_visible}")
check("2nd extinguish restores visible to 9 (incremental)", incremental_visible == 9)
check("Far skeleton gone after 2nd extinguish (incremental)", far_skeleton.uuid not in observer.senses.entities)

# =============================================================================
# Test: Edge entity — no tiles beyond grid boundary
# =============================================================================
section("Edge Entity Darkness Visibility")
reset_combat_state()
grid = get_map()
# Small 5x5 grid with NO walls — edge tiles are the boundary
grid.create_rectangle(0, 0, 5, 5)

for pos, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

# Entity at (0,0) — corner of grid, only 3 adjacent tiles exist + self = 4
corner_entity = create_skeleton(name="Corner", position=(0, 0), faction="heroes", darkvision=False)
setup_standard_actions(corner_entity)
Entity.update_all_entities_senses()

corner_visible = len(corner_entity.senses.visible)
print(f"  Corner entity visible in darkness: {corner_visible}")
# At (0,0): adjacent tiles are (0,1), (1,0), (1,1) + self = 4
# No tiles beyond grid edge, so no phantom positions
check("Corner entity sees exactly 4 tiles in darkness", corner_visible == 4)

# Entity at (0,2) — edge of grid, 5 adjacent tiles exist + self = 6
# No tiles at (-1,*) so fewer than 9
edge_entity = create_skeleton(name="Edge", position=(0, 2), faction="heroes", darkvision=False)
setup_standard_actions(edge_entity)
Entity.update_all_entities_senses()

edge_visible = len(edge_entity.senses.visible)
print(f"  Edge entity visible in darkness: {edge_visible}")
# At (0,2): adjacent tiles are (0,1), (0,3), (1,1), (1,2), (1,3) + self = 6
check("Edge entity sees exactly 6 tiles in darkness", edge_visible == 6)


# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'='*60}")

if failed > 0:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
    sys.exit(0)
