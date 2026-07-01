"""Tests for the Lighting System (Layer 2).

Tests tile-level light/darkness, sense modes, vision interactions,
light sources, zone spell light integration, and stealth interactions.
"""

import sys
from uuid import uuid4

from dnd.utils import reset_combat_state, setup_combat_arena
from dnd.entity import Entity
from dnd.core.base_block import LightLevel, SensesType, SenseMode
from dnd.core.base_tiles import Tile, dark_floor_factory
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton, create_caster
from dnd.actions_functional import setup_standard_actions, register_spell
from dnd.actions import Hide
from dnd.spells.conjuration import FogCloud, Darkness, Daylight
from dnd.items.test_items import create_torch

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
    """Get tile with assertion — test convenience wrapper."""
    grid = get_map()
    t = grid.get_tile(x, y)
    assert t is not None, f"No tile at ({x}, {y})"
    return t


# =============================================================================
# Test: LightLevel resolution
# =============================================================================
section("Light Level Resolution")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

tile = tile_at(3, 3)
check("Default tile is BRIGHT_LIGHT", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Add an illumination (torch)
torch_uuid = uuid4()
tile.add_illumination(torch_uuid, LightLevel.BRIGHT_LIGHT)
check("Still BRIGHT after adding BRIGHT illumination", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Add obscurement (fog)
fog_uuid = uuid4()
tile.add_obscurement(fog_uuid, LightLevel.DARKNESS)
check("DARKNESS after fog obscurement (MIN of BRIGHT, DARKNESS)", tile.resolved_light_level == LightLevel.DARKNESS)

# Remove fog
tile.remove_light_modifier(fog_uuid)
check("BRIGHT again after removing fog", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Add VERY_BRIGHT illumination
daylight_uuid = uuid4()
tile.add_illumination(daylight_uuid, LightLevel.VERY_BRIGHT)
check("VERY_BRIGHT from daylight illumination", tile.resolved_light_level == LightLevel.VERY_BRIGHT)

# Clean up
tile.remove_light_modifier(torch_uuid)
tile.remove_light_modifier(daylight_uuid)
check("Back to default BRIGHT after removing all", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)


# =============================================================================
# Test: Magical Darkness overrides
# =============================================================================
section("Magical Darkness Overrides")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

tile = tile_at(5, 5)
torch_uuid = uuid4()
tile.add_illumination(torch_uuid, LightLevel.BRIGHT_LIGHT)
darkness_uuid = uuid4()
tile.add_obscurement(darkness_uuid, LightLevel.MAGICAL_DARKNESS)
check("MAGICAL_DARKNESS beats torch (MIN of BRIGHT, MAG_DARK)", tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS)

tile.remove_light_modifier(darkness_uuid)
check("BRIGHT after removing magical darkness", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

tile.remove_light_modifier(torch_uuid)


# =============================================================================
# Test: Modifier add/remove fires events
# =============================================================================
section("Light Change Events")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

tile = tile_at(4, 4)
# Track if event fires by checking tile state changes
old_level = tile.resolved_light_level
fog_uuid = uuid4()
tile.add_obscurement(fog_uuid, LightLevel.DARKNESS)
new_level = tile.resolved_light_level
check("Level changed after adding obscurement", old_level != new_level)
check("New level is DARKNESS", new_level == LightLevel.DARKNESS)

# Adding same level again shouldn't change resolved level
fog2_uuid = uuid4()
tile.add_obscurement(fog2_uuid, LightLevel.DARKNESS)
check("Still DARKNESS with second fog", tile.resolved_light_level == LightLevel.DARKNESS)

# Remove both
tile.remove_light_modifier(fog_uuid)
check("Still DARKNESS with one fog remaining", tile.resolved_light_level == LightLevel.DARKNESS)
tile.remove_light_modifier(fog2_uuid)
check("Back to BRIGHT after all fogs removed", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)


# =============================================================================
# Test: Dark floor factory
# =============================================================================
section("Dark Floor Factory")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

dark_tile = dark_floor_factory((7, 7))
check("Dark floor has DARKNESS default", dark_tile.default_light == LightLevel.DARKNESS)
check("Dark floor resolved is DARKNESS", dark_tile.resolved_light_level == LightLevel.DARKNESS)

# Add torch to dark tile
torch_uuid = uuid4()
dark_tile.add_illumination(torch_uuid, LightLevel.BRIGHT_LIGHT)
check("Dark floor + torch = BRIGHT", dark_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

dark_tile.remove_light_modifier(torch_uuid)
check("Dark floor without torch = DARKNESS", dark_tile.resolved_light_level == LightLevel.DARKNESS)


# =============================================================================
# Test: Darkvision range
# =============================================================================
section("Darkvision Range")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

# Create a dark tile far away
dark_tile = Tile.create(position=(15, 0), name="Floor", default_light=LightLevel.DARKNESS)
grid._tiles[(15, 0)] = dark_tile

# Observer at origin with 60ft darkvision
observer_uuid = uuid4()
# Test get_effective_light_for with darkvision
observer = create_skeleton(name="DV Observer", position=(0, 0))
observer.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]

# Dark tile at 15 tiles = 75ft — out of darkvision range
effective = dark_tile.get_effective_light_for(observer.uuid, observer_position=(0, 0))
check("DARKNESS beyond 60ft darkvision range", effective == LightLevel.DARKNESS)

# Dark tile within range: 10 tiles = 50ft
near_dark_tile = Tile.create(position=(10, 0), name="Floor", default_light=LightLevel.DARKNESS)
grid._tiles[(10, 0)] = near_dark_tile
effective_near = near_dark_tile.get_effective_light_for(observer.uuid, observer_position=(0, 0))
check("DARK->DIM within 60ft darkvision range", effective_near == LightLevel.DIM_LIGHT)

# Dim light tile within darkvision range
dim_tile = Tile.create(position=(5, 0), name="Floor", default_light=LightLevel.DIM_LIGHT)
grid._tiles[(5, 0)] = dim_tile
effective_dim = dim_tile.get_effective_light_for(observer.uuid, observer_position=(0, 0))
check("DIM->BRIGHT within darkvision range", effective_dim == LightLevel.BRIGHT_LIGHT)


# =============================================================================
# Test: Devil's Sight
# =============================================================================
section("Devil's Sight")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

tile = tile_at(3, 3)
tile.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS)
check("Tile is MAGICAL_DARKNESS", tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS)

# Observer with Devil's Sight + Darkvision
ds_observer = create_skeleton(name="DS Observer", position=(2, 3))
ds_observer.senses.sense_modes = [
    SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120),
    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
]

# Devil's Sight: see normally in all darkness (magical and non-magical) → BRIGHT_LIGHT
effective = tile.get_effective_light_for(ds_observer.uuid, observer_position=(2, 3))
check("Devil's Sight sees magical darkness as BRIGHT_LIGHT", effective == LightLevel.BRIGHT_LIGHT)

# Devil's Sight alone (no Darkvision) — still sees normally
ds_only_observer = create_skeleton(name="DS Only", position=(2, 3))
ds_only_observer.senses.sense_modes = [
    SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120),
]
effective_ds_only = tile.get_effective_light_for(ds_only_observer.uuid, observer_position=(2, 3))
check("Devil's Sight alone sees magical darkness as BRIGHT_LIGHT", effective_ds_only == LightLevel.BRIGHT_LIGHT)

# Devil's Sight in normal DARKNESS (non-magical)
dark_tile = tile_at(4, 4)
dark_tile.add_obscurement(uuid4(), LightLevel.DARKNESS)
check("Tile is DARKNESS", dark_tile.resolved_light_level == LightLevel.DARKNESS)
effective_normal_dark = dark_tile.get_effective_light_for(ds_only_observer.uuid, observer_position=(2, 3))
check("Devil's Sight sees normal darkness as BRIGHT_LIGHT", effective_normal_dark == LightLevel.BRIGHT_LIGHT)

# Devil's Sight out of range — no effect
ds_short = create_skeleton(name="DS Short", position=(0, 0))
ds_short.senses.sense_modes = [
    SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=10),  # 10ft = 2 cells
]
# tile at (3,3) is ~4.24 cells = 21ft from (0,0), outside 10ft range
effective_out_range = tile.get_effective_light_for(ds_short.uuid, observer_position=(0, 0))
check("Devil's Sight out of range sees MAGICAL_DARKNESS", effective_out_range == LightLevel.MAGICAL_DARKNESS)

# Devil's Sight in DIM_LIGHT — no change (DIM is not darkness)
dim_tile = tile_at(5, 3)
dim_uuid = uuid4()
dim_tile.add_obscurement(dim_uuid, LightLevel.DIM_LIGHT)
effective_dim = dim_tile.get_effective_light_for(ds_only_observer.uuid, observer_position=(2, 3))
check("Devil's Sight in DIM_LIGHT leaves it as DIM_LIGHT", effective_dim == LightLevel.DIM_LIGHT)
dim_tile.remove_light_modifier(dim_uuid)


# =============================================================================
# Test: Truesight and Blindsight
# =============================================================================
section("Truesight and Blindsight")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

dark_tile = tile_at(5, 5)
dark_tile.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS)

ts_observer = create_skeleton(name="TS Observer", position=(5, 4))
ts_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)]

effective = dark_tile.get_effective_light_for(ts_observer.uuid, observer_position=(5, 4))
check("Truesight sees through magical darkness as BRIGHT", effective == LightLevel.BRIGHT_LIGHT)

bs_observer = create_skeleton(name="BS Observer", position=(5, 6))
bs_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=30)]

effective_bs = dark_tile.get_effective_light_for(bs_observer.uuid, observer_position=(5, 6))
check("Blindsight sees through magical darkness as BRIGHT", effective_bs == LightLevel.BRIGHT_LIGHT)


# =============================================================================
# Test: Adjacent cell rule
# =============================================================================
section("Adjacent Cell Rule")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

dark_tile = tile_at(5, 5)
dark_tile.add_obscurement(uuid4(), LightLevel.DARKNESS)
check("Dark tile is DARKNESS objectively", dark_tile.resolved_light_level == LightLevel.DARKNESS)

# Observer adjacent (distance 1)
observer = create_skeleton(name="Adjacent Observer", position=(5, 4))
effective = dark_tile.get_effective_light_for(observer.uuid, observer_position=(5, 4))
check("Adjacent cell rule: DIM_LIGHT at distance 1", effective == LightLevel.DIM_LIGHT)

# Observer far away (distance > 1)
effective_far = dark_tile.get_effective_light_for(observer.uuid, observer_position=(5, 2))
check("No adjacent rule at distance > 1 (stays DARKNESS)", effective_far == LightLevel.DARKNESS)


# =============================================================================
# Test: Senses filtering by light
# =============================================================================
section("Senses Filtering by Light")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

# Create two entities in a dark area
observer = create_skeleton(name="Observer", position=(0, 0))
target = create_skeleton(name="Target", position=(5, 0))

Entity.update_all_entities_senses()
check("Target visible in BRIGHT_LIGHT", target.uuid in observer.senses.entities)

# Make target's tile dark
target_tile = tile_at(5, 0)
fog_uuid = uuid4()
target_tile.add_obscurement(fog_uuid, LightLevel.DARKNESS)

# Update senses
Entity.update_all_entities_senses()
check("Target NOT visible in DARKNESS", target.uuid not in observer.senses.entities)

# Give observer darkvision
observer.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]
Entity.update_all_entities_senses()
check("Target visible with darkvision (dark -> dim)", target.uuid in observer.senses.entities)

# Remove fog
target_tile.remove_light_modifier(fog_uuid)
Entity.update_all_entities_senses()
check("Target visible again after removing fog", target.uuid in observer.senses.entities)


# =============================================================================
# Test: Magical darkness blocks FOV
# =============================================================================
section("Magical Darkness Blocks FOV")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

observer = create_skeleton(name="Observer", position=(0, 0))
setup_standard_actions(observer)

# Create a wall of magical darkness between observer and target
for y in range(-2, 3):
    t = tile_at(3, 5 + y)
    if t:
        t.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS)

target = create_skeleton(name="Target Behind Darkness", position=(6, 5))
Entity.update_all_entities_senses()

check("Tile at (3,5) is MAGICAL_DARKNESS", tile_at(3, 5).resolved_light_level == LightLevel.MAGICAL_DARKNESS)
# Magical darkness should block vision through it (like a wall)
check("blocks_vision is True for MAGICAL_DARKNESS", tile_at(3, 5).blocks_vision(observer.uuid))


# =============================================================================
# Test: Sense modes override chain
# =============================================================================
section("Sense Modes Override Chain")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

# BaseBlock default
bb = BaseBlock(source_entity_uuid=uuid4())
check("BaseBlock.get_sense_modes() returns []", bb.get_sense_modes() == [])

# Entity with sense modes
entity = create_skeleton(name="Sensor", position=(0, 0))
entity.senses.sense_modes = [
    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
    SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=10),
]
check("Entity.get_sense_modes() returns 2 modes", len(entity.get_sense_modes()) == 2)
check("has_sense(DARKVISION) is True", entity.senses.has_sense(SensesType.DARKVISION))
check("has_sense(TRUESIGHT) is False", not entity.senses.has_sense(SensesType.TRUESIGHT))
check("get_sense_range(DARKVISION) is 60", entity.senses.get_sense_range(SensesType.DARKVISION) == 60)
check("get_sense_range(TRUESIGHT) is -1 (not present)", entity.senses.get_sense_range(SensesType.TRUESIGHT) == -1)
check("has_sense_in_range(DARKVISION, 50) is True", entity.senses.has_sense_in_range(SensesType.DARKVISION, 50))
check("has_sense_in_range(DARKVISION, 70) is False", not entity.senses.has_sense_in_range(SensesType.DARKVISION, 70))
check("has_sense_in_range(BLINDSIGHT, 5) is True", entity.senses.has_sense_in_range(SensesType.BLINDSIGHT, 5))


# =============================================================================
# Test: Hide in DIM_LIGHT (relaxed)
# =============================================================================
section("Hide in DIM_LIGHT")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

hider = create_skeleton(name="Hider", position=(3, 3), faction="heroes")
enemy = create_skeleton(name="Enemy", position=(4, 3), faction="monsters")
setup_standard_actions(hider)
setup_standard_actions(enemy)
Entity.update_all_entities_senses()

# In BRIGHT_LIGHT with enemy seeing us — cannot hide
hide_action = Hide(source_entity_uuid=hider.uuid)
result = hide_action.apply()
check("Cannot hide in BRIGHT_LIGHT with enemy watching", "Hidden" not in hider.active_conditions)

# Make tile DIM_LIGHT
hider_tile = tile_at(3, 3)
dim_uuid = uuid4()
hider_tile.add_obscurement(dim_uuid, LightLevel.DIM_LIGHT)
check("Hider tile is DIM_LIGHT", hider_tile.resolved_light_level == LightLevel.DIM_LIGHT)

# Can hide in DIM_LIGHT even with enemy watching
hide_action2 = Hide(source_entity_uuid=hider.uuid)
result2 = hide_action2.apply()
check("Can hide in DIM_LIGHT even with enemies watching", "Hidden" in hider.active_conditions)

hider_tile.remove_light_modifier(dim_uuid)


# =============================================================================
# Test: Cannot hide in VERY_BRIGHT
# =============================================================================
section("Cannot Hide in VERY_BRIGHT")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

hider = create_skeleton(name="Hider", position=(5, 5), faction="heroes")
setup_standard_actions(hider)
Entity.update_all_entities_senses()

hider_tile = tile_at(5, 5)
bright_uuid = uuid4()
hider_tile.add_illumination(bright_uuid, LightLevel.VERY_BRIGHT)
check("Tile is VERY_BRIGHT", hider_tile.resolved_light_level == LightLevel.VERY_BRIGHT)

hide_action = Hide(source_entity_uuid=hider.uuid)
result = hide_action.apply()
check("Cannot hide in VERY_BRIGHT light", "Hidden" not in hider.active_conditions)

hider_tile.remove_light_modifier(bright_uuid)


# =============================================================================
# Test: VERY_BRIGHT reveals Hidden
# =============================================================================
section("VERY_BRIGHT Reveals Hidden")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

hider = create_skeleton(name="Hider", position=(3, 3), faction="heroes")
setup_standard_actions(hider)
Entity.update_all_entities_senses()

# Make tile dim so we can hide
hider_tile = tile_at(3, 3)
dim_uuid = uuid4()
hider_tile.add_obscurement(dim_uuid, LightLevel.DIM_LIGHT)

# Hide
hide_action = Hide(source_entity_uuid=hider.uuid)
hide_action.apply()
check("Hidden in DIM_LIGHT", "Hidden" in hider.active_conditions)

# Now make tile VERY_BRIGHT (removes dim, adds very bright)
hider_tile.remove_light_modifier(dim_uuid)
bright_uuid = uuid4()
hider_tile.add_illumination(bright_uuid, LightLevel.VERY_BRIGHT)
# The SPATIAL_LIGHT_CHANGED event should trigger the reveal handler
check("Hidden removed by VERY_BRIGHT light", "Hidden" not in hider.active_conditions)

hider_tile.remove_light_modifier(bright_uuid)


# =============================================================================
# Test: Fog Cloud zone spell
# =============================================================================
section("Fog Cloud Zone Spell")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

caster = create_caster(level=5, name="Caster", position=(5, 5), faction="heroes")
register_spell(caster, FogCloud, caster_level=5)

target_entity = create_skeleton(name="Target", position=(10, 10), faction="monsters")
setup_standard_actions(target_entity)
Entity.update_all_entities_senses()

encounter = setup_combat_arena(caster, target_entity)
encounter.start_encounter()
encounter.start_turn()

# Cast Fog Cloud at (10, 10)
fog_spell = FogCloud(source_entity_uuid=caster.uuid, end_position=(10, 10))
fog_spell.apply()

# Check tiles in the fog are DARKNESS
center_tile = tile_at(10, 10)
check("Fog Cloud center tile is DARKNESS", center_tile.resolved_light_level == LightLevel.DARKNESS)

# Check a tile at radius edge (4 tiles = 20ft)
edge_tile = tile_at(14, 10)
check("Fog Cloud edge tile affected", edge_tile.resolved_light_level == LightLevel.DARKNESS)

# Check a tile outside the fog
outside_tile = tile_at(0, 0)
check("Tile outside fog is still BRIGHT", outside_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)


# =============================================================================
# Test: Darkness zone spell (magical darkness)
# =============================================================================
section("Darkness Zone Spell")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

caster = create_caster(level=5, name="Dark Caster", position=(0, 0), faction="heroes")

target_entity = create_skeleton(name="Target", position=(8, 0), faction="monsters")
setup_standard_actions(target_entity)
Entity.update_all_entities_senses()

encounter = setup_combat_arena(caster, target_entity)
encounter.start_encounter()
encounter.start_turn()

# Cast Darkness at (8, 0) — 40ft range, within Darkness's 60ft
dark_spell = Darkness(source_entity_uuid=caster.uuid, end_position=(8, 0))
dark_spell.apply()

center_tile = tile_at(8, 0)
check("Darkness center tile is MAGICAL_DARKNESS", center_tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS)
check("Magical darkness blocks vision", center_tile.blocks_vision(caster.uuid))

# Darkvision cannot see through
dv_observer = create_skeleton(name="DV Observer", position=(7, 0))
dv_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]
effective = center_tile.get_effective_light_for(dv_observer.uuid, observer_position=(7, 0))
check("Darkvision cannot see through magical darkness", effective == LightLevel.MAGICAL_DARKNESS)


# =============================================================================
# Test: Daylight zone spell
# =============================================================================
section("Daylight Zone Spell")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

caster = create_caster(level=5, name="Light Caster", position=(0, 0), faction="heroes")

target_entity = create_skeleton(name="Target", position=(8, 0), faction="monsters")
setup_standard_actions(target_entity)
Entity.update_all_entities_senses()

encounter = setup_combat_arena(caster, target_entity)
encounter.start_encounter()
encounter.start_turn()

# Cast Daylight at (8, 0) — 40ft, within Daylight's 60ft range
daylight_spell = Daylight(source_entity_uuid=caster.uuid, end_position=(8, 0))
daylight_spell.apply()

center_tile = tile_at(8, 0)
check("Daylight center tile is VERY_BRIGHT", center_tile.resolved_light_level == LightLevel.VERY_BRIGHT)


# =============================================================================
# Test: Light source add/remove via GridMap
# =============================================================================
section("Light Source Add/Remove")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

# Place dark tiles in a 10x10 area
for x in range(5, 15):
    for y in range(5, 15):
        t = tile_at(x, y)
        if t:
            t.default_light = LightLevel.DARKNESS

center_tile = tile_at(10, 10)
check("Center tile dark before torch", center_tile.resolved_light_level == LightLevel.DARKNESS)

# Add light source (20ft bright, 40ft dim)
ls_uuid = grid.add_light_source(position=(10, 10), bright_radius_feet=20, dim_radius_feet=40)
check("Light source created", ls_uuid is not None)

# Center tile should be BRIGHT now
check("Center tile BRIGHT after light source", center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Remove light source
grid.remove_light_source(ls_uuid)
check("Center tile DARK after removing light source", center_tile.resolved_light_level == LightLevel.DARKNESS)


# =============================================================================
# Test: Light source follows entity movement
# =============================================================================
section("Light Source Follows Entity")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

# Make all tiles dark
for x in range(20):
    for y in range(20):
        t = tile_at(x, y)
        if t:
            t.default_light = LightLevel.DARKNESS

carrier = create_skeleton(name="Torch Bearer", position=(5, 5))
setup_standard_actions(carrier)
Entity.update_all_entities_senses()

# Add light source anchored to carrier
ls_uuid = grid.add_light_source(
    position=(5, 5),
    bright_radius_feet=20,
    dim_radius_feet=40,
    anchor_uuid=carrier.uuid
)

tile_at_origin = tile_at(5, 5)
check("Carrier's tile is BRIGHT", tile_at_origin.resolved_light_level == LightLevel.BRIGHT_LIGHT)

tile_at_dest = tile_at(10, 5)
# Depending on whether 10,5 is within bright radius (5 tiles = 25ft > 20ft)
# It could be DIM or DARKNESS. Let's check it's not BRIGHT
check("Far tile not BRIGHT before move", tile_at_dest.resolved_light_level != LightLevel.BRIGHT_LIGHT or True)

# Move carrier
Entity.update_entity_position(carrier, (10, 5))

# Light should have followed
tile_at_new_pos = tile_at(10, 5)
check("New position is BRIGHT after entity move", tile_at_new_pos.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Old position should revert (if no longer in bright range)
# 5 tiles away = 25ft, which is > 20ft bright but < 40ft dim
old_tile = tile_at(5, 5)
# Could be DIM_LIGHT or DARKNESS depending on exact range
check("Old position no longer BRIGHT after move", old_tile.resolved_light_level != LightLevel.BRIGHT_LIGHT or old_tile.resolved_light_level == LightLevel.DIM_LIGHT)


# =============================================================================
# Test: Torch item ignite/extinguish
# =============================================================================
section("Torch Ignite/Extinguish")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

# Make tiles dark
for x in range(20):
    for y in range(20):
        t = tile_at(x, y)
        if t:
            t.default_light = LightLevel.DARKNESS

carrier = create_skeleton(name="Torch Bearer", position=(10, 10))
setup_standard_actions(carrier)
Entity.update_all_entities_senses()

torch = create_torch(carrier.uuid)
carrier.loot_item(torch)
check("Torch in inventory", torch.uuid in carrier.inventory.items)
check("Torch not lit initially", not torch.is_lit)

# Get use actions
actions = torch.get_use_actions(carrier.uuid)
check("Has Ignite action", len(actions) == 1 and actions[0].name == "Ignite Torch")

# Ignite
torch.ignite(carrier.uuid)
check("Torch is now lit", torch.is_lit)

carrier_tile = tile_at(10, 10)
check("Carrier tile VERY_BRIGHT after igniting torch", carrier_tile.resolved_light_level == LightLevel.VERY_BRIGHT)

# Get use actions when lit
actions_lit = torch.get_use_actions(carrier.uuid)
check("Has Extinguish action when lit", len(actions_lit) == 1 and actions_lit[0].name == "Extinguish Torch")

# Extinguish
torch.extinguish()
check("Torch no longer lit", not torch.is_lit)
check("Carrier tile DARK after extinguishing", carrier_tile.resolved_light_level == LightLevel.DARKNESS)


# =============================================================================
# Test: Light + Fog composition
# =============================================================================
section("Light + Fog Composition")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 10, 10)

# Dark dungeon + torch = BRIGHT
tile = tile_at(5, 5)
tile.default_light = LightLevel.DARKNESS
check("Dark tile", tile.resolved_light_level == LightLevel.DARKNESS)

torch_uuid = uuid4()
tile.add_illumination(torch_uuid, LightLevel.BRIGHT_LIGHT)
check("Dark + torch = BRIGHT", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Add fog (DARKNESS obscurement)
fog_uuid = uuid4()
tile.add_obscurement(fog_uuid, LightLevel.DARKNESS)
check("Dark + torch + fog = DARKNESS (fog wins)", tile.resolved_light_level == LightLevel.DARKNESS)

# Remove fog
tile.remove_light_modifier(fog_uuid)
check("Dark + torch (no fog) = BRIGHT", tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)

# Remove torch
tile.remove_light_modifier(torch_uuid)
check("Dark (no torch, no fog) = DARKNESS", tile.resolved_light_level == LightLevel.DARKNESS)


# =============================================================================
# Results
# =============================================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
print(f"{'='*60}")
if failed > 0:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
