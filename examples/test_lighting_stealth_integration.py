"""
Integration tests for Lighting + Stealth cross-cutting behavior.

Key gaps covered:
- Reactive/incremental senses updates (no manual update_all_entities_senses)
- SPATIAL_PERCEIVABILITY_CHANGED -> SpatialSensesCallback pipeline
- SPATIAL_LIGHT_CHANGED -> senses re-filtering
- Light + stealth combined scenarios
- Hide action at various light levels
- Torch bearer visibility
- Magical darkness combat
"""

from uuid import uuid4
from dnd.utils import reset_combat_state, has_condition
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.core.base_block import LightLevel, SensesType, SenseMode
from dnd.core.base_tiles import dark_floor_factory
from dnd.conditions import Hidden, Invisible
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_by_index
from dnd.actions import Hide
from dnd.monsters.bestiary import create_skeleton
from dnd.items.test_items import Torch, create_torch
from dnd.encounter import Encounter
from dnd.controller import HumanController

# ─── Test tracking ────────────────────────────────────────────────────────────

passed = 0
failed = 0


def check(description: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"  [PASS] {description}")
        passed += 1
    else:
        print(f"  [FAIL] {description}")
        failed += 1


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print(f"{'='*60}")


def create_dark_grid(width: int, height: int) -> None:
    """Create an all-dark tile grid."""
    grid = get_map()
    for x in range(width):
        for y in range(height):
            tile = dark_floor_factory((x, y))
            grid.set_tile(x, y, tile=tile, fire_event=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Reactive Perceivability Updates (no manual senses refresh)
# ═══════════════════════════════════════════════════════════════════════════════

def test_hidden_reactively_removes_from_senses() -> None:
    """Applying Hidden should reactively remove target from observer senses
    without calling update_all_entities_senses()."""
    section("Hidden reactively removes from senses")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Target", position=(5, 1), faction="monsters")

    # Initial senses setup - only call once
    Entity.update_all_entities_senses()
    check("Target initially visible to observer", target.uuid in observer.senses.entities)

    # Apply Hidden with very high stealth (exceeds any passive perception)
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=99,
    )
    target.add_condition(hidden)

    # NO update_all_entities_senses() - reactive update should handle it
    check("Target NOT in observer senses after Hidden (reactive)",
          target.uuid not in observer.senses.entities)
    check("Hidden condition applied", has_condition(target, "Hidden"))

    # Remove Hidden - target should reappear reactively
    target.remove_condition("Hidden")
    check("Target back in observer senses after Hidden removed (reactive)",
          target.uuid in observer.senses.entities)


def test_invisible_reactively_removes_from_senses() -> None:
    """Applying Invisible should reactively remove target from observer senses."""
    section("Invisible reactively removes from senses")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Target", position=(5, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target initially visible", target.uuid in observer.senses.entities)

    # Apply Invisible
    invis = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)

    # Reactive: target should disappear
    check("Target NOT in observer senses after Invisible (reactive)",
          target.uuid not in observer.senses.entities)

    # Give observer TRUESIGHT - need full senses refresh for sense mode change
    observer.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60))
    Entity.update_all_entities_senses()
    check("Target visible to TRUESIGHT observer", target.uuid in observer.senses.entities)

    # Remove Invisible - verify cleanup
    target.remove_condition("Invisible")
    check("Target still visible after Invisible removed", target.uuid in observer.senses.entities)


def test_hidden_reactive_with_different_perception_observers() -> None:
    """Hidden should be reactive per-observer based on passive perception.
    High perception observer keeps seeing target, low perception loses it."""
    section("Hidden reactive with different perception observers")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 5)

    target = create_skeleton(name="Hider", position=(5, 2), faction="monsters")
    low_obs = create_skeleton(name="LowPerception", position=(0, 2), faction="heroes")
    high_obs = create_skeleton(name="HighPerception", position=(9, 2), faction="heroes")

    Entity.update_all_entities_senses()

    low_pp = low_obs.get_passive_perception()
    _ = high_obs.get_passive_perception()

    # Both skeletons have same stats - they'll have same passive perception
    # So we'll set stealth to exactly their PP to test the boundary
    # stealth_result > PP means hidden, stealth_result <= PP means visible
    stealth_dc = low_pp + 1  # Just above low perception

    # If both have same PP, both will lose the target. Let's verify the basic reactive behavior
    check(f"Low observer PP: {low_pp}", low_pp > 0)
    check("Target visible to low observer initially", target.uuid in low_obs.senses.entities)
    check("Target visible to high observer initially", target.uuid in high_obs.senses.entities)

    # Apply Hidden with DC above their passive perception
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=stealth_dc,
    )
    target.add_condition(hidden)

    # Both should lose the target (same PP, stealth > PP)
    check("Low observer lost target (reactive)", target.uuid not in low_obs.senses.entities)
    check("High observer lost target (reactive)", target.uuid not in high_obs.senses.entities)

    # Now remove and re-hide with DC exactly equal to PP (should be visible: DC <= PP)
    target.remove_condition("Hidden")
    check("Both see target again after Hidden removed",
          target.uuid in low_obs.senses.entities and target.uuid in high_obs.senses.entities)

    hidden2 = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=low_pp,  # Equal to PP - NOT hidden (DC must exceed PP)
    )
    target.add_condition(hidden2)
    # stealth_dc == PP: is_perceivable_by checks stealth_dc > passive_perception
    # So equal means still perceivable
    check("Target visible when stealth DC equals PP (reactive)",
          target.uuid in low_obs.senses.entities)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Reactive Light Change Updates
# ═══════════════════════════════════════════════════════════════════════════════

def test_darkness_obscurement_hides_entity_reactively() -> None:
    """Adding darkness obscurement to a target's tile should reactively
    remove the target from observer senses."""
    section("Darkness obscurement hides entity reactively")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Target", position=(5, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target initially visible (bright floor)", target.uuid in observer.senses.entities)

    # Add DARKNESS obscurement to target's tile
    darkness_uuid = uuid4()
    target_tile = grid.get_tile(5, 1)
    assert target_tile is not None
    target_tile.add_obscurement(darkness_uuid, LightLevel.DARKNESS)

    # Reactive: target should vanish (observer has no darkvision)
    check("Target NOT visible after DARKNESS on tile (reactive)",
          target.uuid not in observer.senses.entities)

    # Remove obscurement - target should reappear
    target_tile.remove_light_modifier(darkness_uuid)
    check("Target visible again after darkness removed (reactive)",
          target.uuid in observer.senses.entities)


def test_light_source_reveals_entity_in_dark() -> None:
    """Adding illumination to a dark tile should reactively reveal an entity there."""
    section("Light source reveals entity in dark")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    # Give darkvision initially so observer can see in darkness
    observer.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))

    target = create_skeleton(name="Target", position=(3, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target visible via darkvision in dark", target.uuid in observer.senses.entities)

    # Remove darkvision - need full refresh since sense modes changed
    observer.senses.sense_modes.clear()
    Entity.update_all_entities_senses()
    check("Target NOT visible without darkvision in dark",
          target.uuid not in observer.senses.entities)

    # Add bright illumination to target's tile
    light_uuid = uuid4()
    target_tile = grid.get_tile(3, 1)
    assert target_tile is not None
    target_tile.add_illumination(light_uuid, LightLevel.BRIGHT_LIGHT)

    # Also illuminate observer's tile so observer is in lit area
    obs_light_uuid = uuid4()
    obs_tile = grid.get_tile(0, 1)
    assert obs_tile is not None
    obs_tile.add_illumination(obs_light_uuid, LightLevel.BRIGHT_LIGHT)

    # Reactive: target should now be visible
    check("Target visible after illumination added (reactive)",
          target.uuid in observer.senses.entities)


def test_gridmap_light_source_add_updates_senses() -> None:
    """GridMap.add_light_source() should fire events that update senses."""
    section("GridMap light source add updates senses")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Target", position=(3, 1), faction="monsters")

    Entity.update_all_entities_senses()
    # Both in darkness, no darkvision - can't see each other
    check("Target NOT visible in all-dark (no darkvision)",
          target.uuid not in observer.senses.entities)

    # Add light source that illuminates both positions
    # Position (1,1), bright 20ft = 4 tiles covers both (0,1) and (3,1)
    grid.add_light_source(position=(1, 1), bright_radius_feet=20, dim_radius_feet=40)

    # The light source should fire SPATIAL_LIGHT_CHANGED events
    # which trigger the senses callback to re-filter entities
    check("Target visible after light source added (reactive)",
          target.uuid in observer.senses.entities)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Light + Stealth Cross-Cutting
# ═══════════════════════════════════════════════════════════════════════════════

def test_hidden_in_darkness_darkvision_observer() -> None:
    """Entity hidden in darkness tile. Observer with darkvision can see the tile
    (DARKNESS -> DIM) but target's stealth_dc > observer's PP -> NOT visible."""
    section("Hidden in darkness + darkvision observer")
    reset_combat_state()
    _grid = get_map()
    create_dark_grid(10, 3)

    observer = create_skeleton(name="DarkvisionObserver", position=(0, 1), faction="heroes")
    observer.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))

    target = create_skeleton(name="Hider", position=(5, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target visible to darkvision observer in dark",
          target.uuid in observer.senses.entities)

    # Hide with high stealth
    pp = observer.get_passive_perception()
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=pp + 10,  # Well above observer's perception
    )
    target.add_condition(hidden)

    # Darkvision can see the tile (DIM), but stealth_dc > PP -> hidden
    check("Target NOT visible (hidden in dark, stealth > PP)",
          target.uuid not in observer.senses.entities)
    check("Hidden condition is active", has_condition(target, "Hidden"))


def test_hidden_in_darkness_then_torch_lit() -> None:
    """Target hidden in dark tile. Tile becomes VERY_BRIGHT from torch.
    SPATIAL_LIGHT_CHANGED should fire Hidden's reveal handler -> Hidden removed."""
    section("Hidden in darkness then torch lights tile to VERY_BRIGHT")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    observer.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))

    target = create_skeleton(name="Hider", position=(3, 1), faction="monsters")

    Entity.update_all_entities_senses()

    # Apply Hidden
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=99,
    )
    target.add_condition(hidden)
    check("Target hidden", has_condition(target, "Hidden"))
    check("Target NOT visible to observer", target.uuid not in observer.senses.entities)

    # Add VERY_BRIGHT illumination to target's tile
    # Hidden reveal handler triggers on SPATIAL_LIGHT_CHANGED when tile becomes VERY_BRIGHT
    torch_uuid = uuid4()
    target_tile = grid.get_tile(3, 1)
    assert target_tile is not None
    target_tile.add_illumination(torch_uuid, LightLevel.VERY_BRIGHT)

    check("Tile is now VERY_BRIGHT",
          target_tile.resolved_light_level == LightLevel.VERY_BRIGHT)
    check("Hidden removed by very bright light", not has_condition(target, "Hidden"))
    check("Target visible again after revealed", target.uuid in observer.senses.entities)


def test_hidden_in_dim_light_then_fog_darkens() -> None:
    """Target hidden in DIM_LIGHT. Fog adds DARKNESS obscurement.
    Hidden stays active, but observer without darkvision can't see tile at all."""
    section("Hidden in dim light then fog darkens tile")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Hider", position=(5, 1), faction="monsters")

    # Dim the target's tile
    dim_uuid = uuid4()
    target_tile = grid.get_tile(5, 1)
    assert target_tile is not None
    target_tile.add_obscurement(dim_uuid, LightLevel.DIM_LIGHT)

    Entity.update_all_entities_senses()

    # Target visible in DIM_LIGHT (still enough light to see)
    check("Target visible in dim light", target.uuid in observer.senses.entities)

    # Apply Hidden
    pp = observer.get_passive_perception()
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=pp + 10,
    )
    target.add_condition(hidden)
    check("Target hidden (stealth > PP)", target.uuid not in observer.senses.entities)

    # Add DARKNESS fog to target's tile
    fog_uuid = uuid4()
    target_tile.add_obscurement(fog_uuid, LightLevel.DARKNESS)
    check("Tile resolved to DARKNESS",
          target_tile.resolved_light_level == LightLevel.DARKNESS)

    # Hidden condition should still be active (darkness doesn't break hidden)
    check("Hidden still active", has_condition(target, "Hidden"))
    # Observer without darkvision can't see tile at all
    check("Target NOT in observer senses (dark + hidden)",
          target.uuid not in observer.senses.entities)


def test_invisible_entity_in_darkness_truesight_observer() -> None:
    """Target is Invisible + in DARKNESS tile. Observer with TRUESIGHT bypasses both."""
    section("Invisible in darkness + TRUESIGHT observer")
    reset_combat_state()
    _grid = get_map()
    create_dark_grid(10, 3)

    observer = create_skeleton(name="TruesightObserver", position=(0, 1), faction="heroes")
    observer.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60))

    target = create_skeleton(name="InvisHider", position=(3, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target visible to TRUESIGHT in dark", target.uuid in observer.senses.entities)

    # Apply Invisible
    invis = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invis)

    # TRUESIGHT should bypass both invisibility AND darkness
    check("Target STILL visible to TRUESIGHT despite Invisible + dark",
          target.uuid in observer.senses.entities)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Hide Action in Various Light Levels
# ═══════════════════════════════════════════════════════════════════════════════

def test_hide_in_darkness_succeeds() -> None:
    """Entity alone in DARKNESS tile can hide (no enemies see them)."""
    section("Hide in darkness succeeds")
    reset_combat_state()
    _grid = get_map()
    create_dark_grid(10, 3)

    entity = create_skeleton(name="Hider", position=(5, 1), faction="heroes")
    setup_standard_actions(entity)
    # Create distant enemy with no darkvision - can't see hider
    enemy = create_skeleton(name="Enemy", position=(0, 1), faction="monsters")

    Entity.update_all_entities_senses()
    # Enemy can't see hider (all dark, no darkvision)
    check("Enemy cannot see hider in darkness", entity.uuid not in enemy.senses.entities)

    # Set up encounter for action economy
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()
    # Make sure it's hider's turn
    current = encounter.get_current_entity()
    if current is None or current.uuid != entity.uuid:
        encounter.next_turn()  # auto ends current + starts next

    hide = Hide(source_entity_uuid=entity.uuid)
    result = hide.apply()

    check("Hide action succeeded", result is not None and not result.canceled)
    check("Hidden condition applied", has_condition(entity, "Hidden"))


def test_hide_in_bright_light_no_enemies_succeeds() -> None:
    """Entity alone (no enemies in LOS) in BRIGHT_LIGHT can hide."""
    section("Hide in bright light with no visible enemies succeeds")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    entity = create_skeleton(name="Hider", position=(5, 1), faction="heroes")
    setup_standard_actions(entity)

    Entity.update_all_entities_senses()

    # No enemies at all - should succeed even in bright light
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    hide = Hide(source_entity_uuid=entity.uuid)
    result = hide.apply()

    check("Hide succeeded with no enemies", result is not None and not result.canceled)
    check("Hidden applied", has_condition(entity, "Hidden"))


def test_non_revealing_actions_comprehensive() -> None:
    """Dodge and Disengage should not break Hidden condition."""
    section("Non-revealing actions preserve Hidden")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    entity = create_skeleton(name="Hider", position=(5, 1), faction="heroes")
    setup_standard_actions(entity)

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply Hidden directly (we already tested Hide action)
    hidden = Hidden(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        stealth_result=30,
    )
    entity.add_condition(hidden)
    check("Hidden applied", has_condition(entity, "Hidden"))

    # Execute Dodge - should NOT break Hidden
    available = get_available_actions(entity)
    dodge_found = False
    for action_info in available.self_actions:
        if action_info.template_name == "Dodge":
            execute_by_index(entity, "Dodge", 0)
            dodge_found = True
            break
    check("Dodge action found and executed", dodge_found)
    check("Hidden persists after Dodge", has_condition(entity, "Hidden"))

    # Need more actions for Disengage - end turn, start new one
    encounter.next_turn()  # next_turn auto-ends current turn and starts next

    # Re-apply Hidden for fresh test
    if not has_condition(entity, "Hidden"):
        hidden2 = Hidden(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            stealth_result=30,
        )
        entity.add_condition(hidden2)

    # Execute Disengage
    available2 = get_available_actions(entity)
    disengage_found = False
    for action_info in available2.self_actions:
        if action_info.template_name == "Disengage":
            execute_by_index(entity, "Disengage", 0)
            disengage_found = True
            break
    check("Disengage action found and executed", disengage_found)
    check("Hidden persists after Disengage", has_condition(entity, "Hidden"))


def test_movement_while_hidden_persists() -> None:
    """Moving while Hidden should NOT break Hidden (movement is not a reveal trigger)."""
    section("Movement while Hidden persists")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    entity = create_skeleton(name="Hider", position=(5, 1), faction="heroes")
    setup_standard_actions(entity)

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply Hidden
    hidden = Hidden(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        stealth_result=30,
    )
    entity.add_condition(hidden)
    check("Hidden applied", has_condition(entity, "Hidden"))

    # Execute Move to adjacent tile
    available = get_available_actions(entity)
    moved = False
    for action_info in available.position_actions:
        if action_info.template_name == "Move":
            # Move to adjacent position
            if len(action_info.valid_targets) > 0:
                execute_by_index(entity, "Move", 0)
                moved = True
                break
    check("Move action executed", moved)
    check("Hidden persists after movement", has_condition(entity, "Hidden"))


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: Torch Bearer Visibility
# ═══════════════════════════════════════════════════════════════════════════════

def test_torch_bearer_sees_enemies_in_dark_cave() -> None:
    """In all-dark cave, adding a light source at carrier position reveals enemies."""
    section("Torch bearer sees enemies in dark cave")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    carrier = create_skeleton(name="TorchBearer", position=(0, 1), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(3, 1), faction="monsters")
    # No darkvision on carrier

    Entity.update_all_entities_senses()
    check("Carrier can't see enemy in dark (no darkvision)",
          enemy.uuid not in carrier.senses.entities)

    # Add light source at carrier position: 20ft bright = 4 tiles, 40ft dim = 8 tiles
    # Enemy is 3 tiles = 15ft away, well within bright radius
    grid.add_light_source(
        position=(0, 1),
        bright_radius_feet=20,
        dim_radius_feet=40,
        anchor_uuid=carrier.uuid,
    )

    # Need senses refresh after adding anchored light source
    Entity.update_all_entities_senses()
    check("Carrier can now see enemy via torch light",
          enemy.uuid in carrier.senses.entities)

    # Verify the tile lighting
    enemy_tile = grid.get_tile(3, 1)
    assert enemy_tile is not None
    resolved = enemy_tile.resolved_light_level
    check(f"Enemy tile illuminated ({resolved.name})",
          resolved.value >= LightLevel.DIM_LIGHT.value)


def test_torch_bearer_movement_updates_visibility() -> None:
    """Moving a torch bearer with anchored light should update which enemies are visible."""
    section("Torch bearer movement updates visibility")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(15, 3)

    carrier = create_skeleton(name="TorchBearer", position=(0, 1), faction="heroes")
    # dim_radius_feet is ADDITIVE on bright: total range = 20 + 10 = 30ft = 6 tiles
    # Place enemy at 8 tiles = 40ft, beyond total range
    far_enemy = create_skeleton(name="FarEnemy", position=(8, 1), faction="monsters")

    # Add light source anchored to carrier: 20ft bright (4 tiles), +10ft dim (total 6 tiles)
    grid.add_light_source(
        position=(0, 1),
        bright_radius_feet=20,
        dim_radius_feet=10,
        anchor_uuid=carrier.uuid,
    )

    Entity.update_all_entities_senses()
    # Far enemy is 8 tiles = 40ft away - outside total light range (30ft = 6 tiles)
    check("Far enemy NOT visible initially (40ft, outside 30ft total light range)",
          far_enemy.uuid not in carrier.senses.entities)

    # Move carrier closer using Entity.update_entity_position
    Entity.update_entity_position(carrier, (5, 1))
    Entity.update_all_entities_senses()

    # Now far enemy is 3 tiles = 15ft away - within bright radius (20ft)
    check("Far enemy visible after carrier moved closer",
          far_enemy.uuid in carrier.senses.entities)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6: Magical Darkness Combat
# ═══════════════════════════════════════════════════════════════════════════════

def test_magical_darkness_blocks_targeting() -> None:
    """Entity in MAGICAL_DARKNESS tile should not be targetable
    (not in attacker's senses.entities)."""
    section("Magical darkness blocks targeting")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    attacker = create_skeleton(name="Attacker", position=(0, 1), faction="heroes")
    setup_standard_actions(attacker)
    target = create_skeleton(name="Target", position=(2, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target initially visible", target.uuid in attacker.senses.entities)

    # Apply MAGICAL_DARKNESS to target's tile
    md_uuid = uuid4()
    target_tile = grid.get_tile(2, 1)
    assert target_tile is not None
    target_tile.add_obscurement(md_uuid, LightLevel.MAGICAL_DARKNESS)

    # Even darkvision can't see through magical darkness
    attacker.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
    Entity.update_all_entities_senses()

    check("Target NOT visible in magical darkness (even with darkvision)",
          target.uuid not in attacker.senses.entities)

    # Verify via available actions: target should not be in attack targets
    available = get_available_actions(attacker)
    target_in_attacks = False
    for action_info in available.entity_actions:
        for t in action_info.valid_targets:
            if t.target_uuid == target.uuid:
                target_in_attacks = True
                break
    check("Target NOT in attack valid_targets", not target_in_attacks)


def test_devils_sight_sees_through_magical_darkness() -> None:
    """Entity with DEVIL'S_SIGHT can see through magical darkness."""
    section("Devil's Sight sees through magical darkness")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 3)

    # Place at melee range (1 tile = 5ft) so skeleton's shortsword can reach
    observer = create_skeleton(name="WarlockObserver", position=(0, 1), faction="heroes")
    observer.senses.sense_modes.append(
        SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120)
    )
    setup_standard_actions(observer)

    target = create_skeleton(name="Target", position=(1, 1), faction="monsters")

    Entity.update_all_entities_senses()
    check("Target initially visible", target.uuid in observer.senses.entities)

    # Apply MAGICAL_DARKNESS to target's tile
    md_uuid = uuid4()
    target_tile = grid.get_tile(1, 1)
    assert target_tile is not None
    target_tile.add_obscurement(md_uuid, LightLevel.MAGICAL_DARKNESS)

    Entity.update_all_entities_senses()

    # Devil's Sight sees through all darkness including magical
    check("Target visible despite magical darkness (Devil's Sight)",
          target.uuid in observer.senses.entities)

    # Verify target is targetable (within melee range)
    available = get_available_actions(observer)
    target_in_attacks = False
    for action_info in available.entity_actions:
        for t in action_info.valid_targets:
            if t.target_uuid == target.uuid:
                target_in_attacks = True
                break
    check("Target IS in attack valid_targets (Devil's Sight)", target_in_attacks)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 7: Torch + Stealth Interaction (three-zone light: very bright / bright / dim)
# ═══════════════════════════════════════════════════════════════════════════════

def test_torch_three_light_zones() -> None:
    """Torch produces VERY_BRIGHT (10ft), BRIGHT_LIGHT (20ft), DIM_LIGHT (40ft)."""
    section("Torch three light zones")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(12, 3)

    carrier = create_skeleton(name="TorchCarrier", position=(0, 1), faction="heroes")
    Entity.update_all_entities_senses()

    torch = create_torch(carrier.uuid)
    carrier.loot_item(torch)
    torch.ignite(carrier.uuid)

    # Carrier tile (0,1) should be VERY_BRIGHT (within 10ft = 2 tiles)
    carrier_tile = grid.get_tile(0, 1)
    assert carrier_tile is not None
    check("Carrier tile is VERY_BRIGHT",
          carrier_tile.resolved_light_level == LightLevel.VERY_BRIGHT)

    # Tile at 1 tile away (5ft) — still within very bright radius (10ft)
    tile_1 = grid.get_tile(1, 1)
    assert tile_1 is not None
    check("Tile 5ft away is VERY_BRIGHT",
          tile_1.resolved_light_level == LightLevel.VERY_BRIGHT)

    # Tile at 3 tiles away (15ft) — beyond very bright (10ft), within bright (20ft)
    tile_3 = grid.get_tile(3, 1)
    assert tile_3 is not None
    check("Tile 15ft away is BRIGHT_LIGHT",
          tile_3.resolved_light_level == LightLevel.BRIGHT_LIGHT)

    # Tile at 5 tiles away (25ft) — beyond bright (20ft), within dim (40ft)
    tile_5 = grid.get_tile(5, 1)
    assert tile_5 is not None
    check("Tile 25ft away is DIM_LIGHT",
          tile_5.resolved_light_level == LightLevel.DIM_LIGHT)

    # Tile at 9 tiles away (45ft) — beyond total range (40ft), should be DARKNESS
    tile_9 = grid.get_tile(9, 1)
    assert tile_9 is not None
    check("Tile 45ft away is DARKNESS (beyond range)",
          tile_9.resolved_light_level == LightLevel.DARKNESS)


def test_torch_very_bright_reveals_hidden_enemy() -> None:
    """When torch carrier moves near a hidden enemy, VERY_BRIGHT zone reveals them."""
    section("Torch VERY_BRIGHT reveals hidden enemy")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    carrier = create_skeleton(name="TorchCarrier", position=(0, 1), faction="heroes")
    # Give carrier darkvision so they can see in dim/dark
    carrier.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]
    hidden_enemy = create_skeleton(name="HiddenEnemy", position=(5, 1), faction="monsters")

    Entity.update_all_entities_senses()

    # Hide the enemy with very high stealth (impossible to beat with passive perception)
    hidden_cond = Hidden(
        source_entity_uuid=hidden_enemy.uuid,
        target_entity_uuid=hidden_enemy.uuid,
        stealth_result=99,
    )
    hidden_enemy.add_condition(hidden_cond)
    check("Enemy is hidden", has_condition(hidden_enemy, "Hidden"))
    check("Enemy NOT visible to carrier (high stealth DC)",
          hidden_enemy.uuid not in carrier.senses.entities)

    # Ignite torch on carrier — enemy at 5 tiles (25ft) is in DIM zone (beyond 20ft bright)
    torch = create_torch(carrier.uuid)
    carrier.loot_item(torch)
    torch.ignite(carrier.uuid)

    enemy_tile = grid.get_tile(5, 1)
    assert enemy_tile is not None
    check("Enemy tile is DIM_LIGHT (25ft, beyond bright radius)",
          enemy_tile.resolved_light_level == LightLevel.DIM_LIGHT)
    check("Enemy still hidden in DIM_LIGHT",
          has_condition(hidden_enemy, "Hidden"))

    # Move carrier closer so enemy is within VERY_BRIGHT (10ft = 2 tiles)
    Entity.update_entity_position(carrier, (4, 1))
    Entity.update_all_entities_senses()

    # Enemy at (5,1), carrier at (4,1) — 1 tile = 5ft, within very bright
    enemy_tile_after = grid.get_tile(5, 1)
    assert enemy_tile_after is not None
    check("Enemy tile is now VERY_BRIGHT after carrier moved close",
          enemy_tile_after.resolved_light_level == LightLevel.VERY_BRIGHT)
    check("Hidden removed by VERY_BRIGHT torch light",
          not has_condition(hidden_enemy, "Hidden"))
    check("Enemy now visible to carrier",
          hidden_enemy.uuid in carrier.senses.entities)


def test_torch_bright_zone_does_not_reveal_hidden() -> None:
    """BRIGHT_LIGHT from torch does NOT auto-reveal hidden enemies (only VERY_BRIGHT does)."""
    section("Torch BRIGHT zone does NOT reveal hidden")
    reset_combat_state()
    grid = get_map()
    create_dark_grid(10, 3)

    carrier = create_skeleton(name="TorchCarrier", position=(0, 1), faction="heroes")
    carrier.senses.sense_modes = [SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)]
    hidden_enemy = create_skeleton(name="HiddenEnemy", position=(3, 1), faction="monsters")

    Entity.update_all_entities_senses()

    # Hide the enemy
    hidden_cond = Hidden(
        source_entity_uuid=hidden_enemy.uuid,
        target_entity_uuid=hidden_enemy.uuid,
        stealth_result=99,
    )
    hidden_enemy.add_condition(hidden_cond)
    check("Enemy is hidden", has_condition(hidden_enemy, "Hidden"))

    # Ignite torch — enemy at 3 tiles (15ft) is in BRIGHT zone (10-20ft)
    torch = create_torch(carrier.uuid)
    carrier.loot_item(torch)
    torch.ignite(carrier.uuid)

    enemy_tile = grid.get_tile(3, 1)
    assert enemy_tile is not None
    check("Enemy tile is BRIGHT_LIGHT (15ft from torch)",
          enemy_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT)
    check("Enemy still hidden — BRIGHT_LIGHT does not auto-reveal",
          has_condition(hidden_enemy, "Hidden"))
    check("Enemy NOT visible (stealth DC too high)",
          hidden_enemy.uuid not in carrier.senses.entities)


# ═══════════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Lighting + Stealth Integration Tests")
    print("=" * 60)

    # Section 1: Reactive perceivability
    test_hidden_reactively_removes_from_senses()
    test_invisible_reactively_removes_from_senses()
    test_hidden_reactive_with_different_perception_observers()

    # Section 2: Reactive light changes
    test_darkness_obscurement_hides_entity_reactively()
    test_light_source_reveals_entity_in_dark()
    test_gridmap_light_source_add_updates_senses()

    # Section 3: Light + stealth cross-cutting
    test_hidden_in_darkness_darkvision_observer()
    test_hidden_in_darkness_then_torch_lit()
    test_hidden_in_dim_light_then_fog_darkens()
    test_invisible_entity_in_darkness_truesight_observer()

    # Section 4: Hide action at various light levels
    test_hide_in_darkness_succeeds()
    test_hide_in_bright_light_no_enemies_succeeds()
    test_non_revealing_actions_comprehensive()
    test_movement_while_hidden_persists()

    # Section 5: Torch bearer visibility
    test_torch_bearer_sees_enemies_in_dark_cave()
    test_torch_bearer_movement_updates_visibility()

    # Section 6: Magical darkness
    test_magical_darkness_blocks_targeting()
    test_devils_sight_sees_through_magical_darkness()

    # Section 7: Torch + stealth interaction
    test_torch_three_light_zones()
    test_torch_very_bright_reveals_hidden_enemy()
    test_torch_bright_zone_does_not_reveal_hidden()

    # Results
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if failed > 0:
        exit(1)
    else:
        print("ALL TESTS PASSED!")
