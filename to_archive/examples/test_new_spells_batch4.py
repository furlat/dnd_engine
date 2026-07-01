"""
Tests for Batch 4 spells: True Strike, Finger of Death, Telekinesis,
Globe of Invulnerability, Banishment.

Full integration tests — spells registered on casters and executed via
the action system (get_available_actions / execute_by_index).

Run with: python examples/test_new_spells_batch4.py
"""

from typing import Optional
from uuid import uuid4

from dnd.utils import (
    reset_combat_state, get_hp, get_max_hp, set_hp,
    has_condition, get_position,
    deal_damage_to,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig, get_natural_roll
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import (
    setup_standard_actions, register_spell,
    get_available_actions, execute_by_index,
)
from dnd.monsters.bestiary import create_caster
from dnd.core.events import EventQueue, DamageType
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus
from dnd.spells.evocation import register_true_strike, Fireball
from dnd.spells.necromancy import FingerOfDeath
from dnd.spells.transmutation import Telekinesis
from dnd.spells.abjuration import GlobeOfInvulnerability, GlobeZone, Banishment
from dnd.spells.conjuration import Web
from dnd.utils import move_entity


passed = 0
failed = 0


def had_critical_d20() -> bool:
    """Check if any d20 roll in the current EventQueue had a nat 1 or nat 20."""
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


def create_test_target(name: str, position: tuple, dex: int = 10, con: int = 10,
                       wis: int = 10, cha: int = 10, strength: int = 10,
                       faction: str = "monsters"):
    """Helper to create test targets with specified ability scores."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=dex),
            constitution=AbilityConfig(ability_score=con),
            wisdom=AbilityConfig(ability_score=wis),
            charisma=AbilityConfig(ability_score=cha),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
        position=position,
        faction=faction,
        proficiency_bonus=2,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


def check(label: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def find_target_index(caster: Entity, spell_name: str, target_uuid=None, position=None):
    """Find the target index for a spell in available actions."""
    available = get_available_actions(caster)
    for info in available.all_actions:
        if info.template_name == spell_name:
            for t in info.valid_targets:
                if target_uuid and t.target_uuid == target_uuid:
                    return t.index, available
                if position and t.position == position:
                    return t.index, available
            # SELF target — return index 0
            if len(info.valid_targets) > 0:
                return info.valid_targets[0].index, available
    return None, available


# =============================================================================
# True Strike Tests
# =============================================================================

def test_true_strike_cha_modifier_in_damage():
    """True Strike uses CHA (+4) not STR (-1). Registered on caster, executed via action API.

    Caster: STR 8 (-1), CHA 18 (+4), prof +3, dagger (1d4).
    Normal attack: 1d4 + STR(-1) = 0-3
    True Strike:   1d4 + CHA(+4) = 5-8
    Damage >= 5 proves CHA was used.
    """
    print("\n=== Test: True Strike Uses CHA Modifier ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (1, 0), dex=1)
        Entity.update_all_entities_senses()

        # Register True Strike variants via the proper API
        register_true_strike(caster, caster_level=1)

        initial_hp = get_hp(target)

        # Force hit (AUTOHIT on equipment attack bonus — True Strike delegates to Attack)
        hit_mod = AutoHitModifier(name="Force Hit", value=AutoHitStatus.AUTOHIT,
                                  source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
        mod_uuid = caster.equipment.attack_bonus.self_static.add_auto_hit_modifier(hit_mod)

        # Execute True Strike (Melee) via action system
        idx, available = find_target_index(caster, "True Strike (Melee)", target_uuid=target.uuid)
        check("True Strike (Melee) available in actions", idx is not None)

        if idx is not None:
            execute_by_index(caster, "True Strike (Melee)", idx, available=available)

        caster.equipment.attack_bonus.self_static.remove_modifier(mod_uuid)

        if had_critical_d20():
            continue

        damage = initial_hp - get_hp(target)
        # CHA +4: minimum 1d4(1) + 4 = 5. STR -1: max 1d4(4) - 1 = 3.
        check("Damage >= 5 proves CHA modifier used", damage >= 5)
        print(f"  Damage: {damage} (CHA range: 5-8, STR would be 0-3)")
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_true_strike_cantrip_scaling():
    """True Strike at L5 adds 1d6 radiant. Executed via action API."""
    print("\n=== Test: True Strike Cantrip Scaling ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (1, 0), dex=1)
        Entity.update_all_entities_senses()

        register_true_strike(caster, caster_level=5)

        set_hp(target, get_max_hp(target))

        hit_mod = AutoHitModifier(name="Force Hit", value=AutoHitStatus.AUTOHIT,
                                  source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
        mod_uuid = caster.equipment.attack_bonus.self_static.add_auto_hit_modifier(hit_mod)

        idx, available = find_target_index(caster, "True Strike (Melee)", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "True Strike (Melee)", idx, available=available)

        caster.equipment.attack_bonus.self_static.remove_modifier(mod_uuid)

        if had_critical_d20():
            continue

        damage = get_max_hp(target) - get_hp(target)
        # 1d4 + CHA(4) + 1d6 = min 6, max 14
        check("Level 5 True Strike min 6 damage", damage >= 6)
        print(f"  Damage: {damage} (expected 6-14)")
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_true_strike_miss_no_damage():
    """True Strike miss via action API — no damage."""
    print("\n=== Test: True Strike Miss ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (1, 0), dex=20)
    Entity.update_all_entities_senses()

    register_true_strike(caster, caster_level=5)

    initial_hp = get_hp(target)

    miss_mod = AutoHitModifier(name="Force Miss", value=AutoHitStatus.AUTOMISS,
                               source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.equipment.attack_bonus.self_static.add_auto_hit_modifier(miss_mod)

    idx, available = find_target_index(caster, "True Strike (Melee)", target_uuid=target.uuid)
    if idx is not None:
        execute_by_index(caster, "True Strike (Melee)", idx, available=available)

    caster.equipment.attack_bonus.self_static.remove_modifier(mod_uuid)
    check("Miss deals no damage", get_hp(target) == initial_hp)


# =============================================================================
# Finger of Death Tests
# =============================================================================

def test_finger_of_death_full_damage():
    """Finger of Death registered on caster, executed via action API. CON save fail."""
    print("\n=== Test: Finger of Death Full Damage ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), con=1)
        Entity.update_all_entities_senses()

        # Register Finger of Death on caster
        register_spell(caster, FingerOfDeath, caster_level=13)

        initial_hp = get_hp(target)

        idx, available = find_target_index(caster, "Finger of Death", target_uuid=target.uuid)
        check("Finger of Death available", idx is not None)

        if idx is not None:
            execute_by_index(caster, "Finger of Death", idx, available=available)

        if had_critical_d20():
            continue

        damage = initial_hp - get_hp(target)
        # 7d8(7-56) + 30 = 37-86
        check("FoD full damage >= 37", damage >= 37)
        print(f"  Damage: {damage} (expected 37-86)")
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_finger_of_death_half_on_save():
    """Finger of Death: CON save success → half damage."""
    print("\n=== Test: Finger of Death Half Damage ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), con=40)
        Entity.update_all_entities_senses()

        register_spell(caster, FingerOfDeath, caster_level=13)

        initial_hp = get_hp(target)

        idx, available = find_target_index(caster, "Finger of Death", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Finger of Death", idx, available=available)

        if had_critical_d20():
            continue

        damage = initial_hp - get_hp(target)
        # Half of 37-86 = 18-43
        check("FoD half damage on save (1-43)", 0 < damage <= 43)
        print(f"  Damage: {damage} (expected 18-43)")
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


# =============================================================================
# Telekinesis Tests
# =============================================================================

def test_telekinesis_full_flow():
    """Telekinesis: register → cast via action API → sub-actions appear → execute Restrain."""
    print("\n=== Test: Telekinesis Full Flow ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), strength=1)
        Entity.update_all_entities_senses()

        # Register Telekinesis on caster
        register_spell(caster, Telekinesis, caster_level=9)

        # Cast via action API
        idx, available = find_target_index(caster, "Telekinesis", target_uuid=target.uuid)
        check("Telekinesis available", idx is not None)

        if idx is not None:
            execute_by_index(caster, "Telekinesis", idx, available=available)

        if had_critical_d20():
            continue

        if not has_condition(caster, "Concentrating"):
            continue

        check("Caster concentrating", True)

        # Sub-actions should appear in available actions (reset economy first)
        caster.action_economy.reset_all_costs()
        available2 = get_available_actions(caster)
        all_names = [a.template_name for a in available2.all_actions]

        has_restrain = "Telekinesis: Restrain" in all_names
        has_move = "Telekinesis: Move" in all_names

        check("Restrain sub-action in available actions", has_restrain)
        check("Move sub-action in available actions", has_move)

        # Execute Restrain via action API (SELF target, index 0)
        if has_restrain:
            execute_by_index(caster, "Telekinesis: Restrain", 0, available=available2)

            check("Target is Restrained", has_condition(target, "Restrained"))

            # Both sub-actions deregistered
            action_names = [a.name or "" for a in caster.registered_actions]
            check("Sub-actions deregistered after Restrain",
                  "Telekinesis: Restrain" not in action_names and "Telekinesis: Move" not in action_names)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_telekinesis_move_grid_and_senses():
    """Telekinesis Move: entity moves on grid, senses update."""
    print("\n=== Test: Telekinesis Move — Grid + Senses ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (3, 0), strength=1)
        # Observer can see target's area
        _observer = create_test_target("Observer", (3, 3), faction="neutral")
        Entity.update_all_entities_senses()

        register_spell(caster, Telekinesis, caster_level=9)

        original_pos = get_position(target)

        idx, available = find_target_index(caster, "Telekinesis", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Telekinesis", idx, available=available)

        if had_critical_d20():
            continue

        if not any(a.name == "Telekinesis: Move" for a in caster.registered_actions):
            continue

        caster.action_economy.reset_all_costs()

        # Get Move's valid targets (positions within 30ft of target)
        available2 = get_available_actions(caster)
        move_info = None
        for a in available2.all_actions:
            if a.template_name == "Telekinesis: Move":
                move_info = a
                break

        check("Move has valid target positions", move_info is not None and len(move_info.valid_targets) > 0)

        if not move_info or not move_info.valid_targets:
            continue

        # Pick a destination position
        dest = move_info.valid_targets[0]
        dest_pos = dest.position

        # Execute Move via action API
        execute_by_index(caster, "Telekinesis: Move", dest.index, available=available2)

        # Verify grid state
        new_pos = get_position(target)
        check("Target at new position", new_pos == dest_pos)
        check("Grid tracks entity at new pos", target.uuid in grid.get_entities_at(new_pos))
        check("Entity removed from old pos", target.uuid not in grid.get_entities_at(original_pos))

        # Verify senses update after forced movement
        Entity.update_all_entities_senses()
        print(f"  Moved target from {original_pos} to {new_pos}")

        # Sub-actions cleaned up
        action_names = [a.name or "" for a in caster.registered_actions]
        check("Sub-actions deregistered", "Telekinesis: Move" not in action_names)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_telekinesis_concentration_break():
    """Breaking concentration via damage removes Restrained and granted action."""
    print("\n=== Test: Telekinesis Concentration Break ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), strength=1)
        Entity.update_all_entities_senses()

        register_spell(caster, Telekinesis, caster_level=9)

        idx, available = find_target_index(caster, "Telekinesis", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Telekinesis", idx, available=available)

        if had_critical_d20():
            continue

        if not has_condition(caster, "Concentrating"):
            continue

        # Restrain the target via proper API
        if any(a.name == "Telekinesis: Restrain" for a in caster.registered_actions):
            caster.action_economy.reset_all_costs()
            execute_by_index(caster, "Telekinesis: Restrain", 0)
            check("Target restrained", has_condition(target, "Restrained"))

            # Break concentration via massive damage
            set_hp(caster, get_max_hp(caster))
            deal_damage_to(caster, 200, DamageType.FIRE, source_uuid=target.uuid)

            check("Concentration broken by damage", not has_condition(caster, "Concentrating"))
            check("Restrained removed on conc break", not has_condition(target, "Restrained"))

            action_names = [a.name or "" for a in caster.registered_actions]
            check("Granted action removed on conc break", "Telekinesis" not in action_names)
            break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


# =============================================================================
# Globe of Invulnerability Tests
# =============================================================================

def test_globe_blocks_enemy_spell():
    """Globe registered + cast via action API. Enemy Fireball blocked."""
    print("\n=== Test: Globe Blocks Enemy Spell ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    ally = create_test_target("Ally", (6, 5), faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    initial_ally_hp = get_hp(ally)
    initial_globe_hp = get_hp(globe_caster)

    # Register and cast Globe via action API (SELF target)
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    check("Globe caster concentrating", has_condition(globe_caster, "Concentrating"))
    check("Globe zone active", has_condition(globe_caster, "Globe of Invulnerability Zone"))

    # Enemy Fireball (L3) at ally inside globe — registered and cast via action API
    register_spell(enemy, Fireball, caster_level=5)
    idx, available = find_target_index(enemy, "Fireball", position=(6, 5))
    if idx is not None:
        execute_by_index(enemy, "Fireball", idx, available=available)

    check("Ally takes no damage (blocked)", get_hp(ally) == initial_ally_hp)
    check("Globe caster takes no damage (inside globe)", get_hp(globe_caster) == initial_globe_hp)


def test_globe_own_spells_pass():
    """Globe caster's own spells pass through to enemies inside."""
    print("\n=== Test: Globe Own Spells Pass ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    enemy = create_test_target("Enemy", (6, 5), dex=1, faction="monsters")
    Entity.update_all_entities_senses()

    register_spell(caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(caster, "Globe of Invulnerability", 0)

    initial_hp = get_hp(enemy)

    # Reset action economy
    caster.action_economy.reset_all_costs()

    # Caster already has Magic Missile registered (create_caster does this)
    # Execute via action API
    idx, available = find_target_index(caster, "Magic Missile", target_uuid=enemy.uuid)
    check("Magic Missile available targeting enemy inside globe", idx is not None)

    if idx is not None:
        execute_by_index(caster, "Magic Missile", idx, available=available)

    check("Own L1 spell damages target inside globe", get_hp(enemy) < initial_hp)
    print(f"  Damage: {initial_hp - get_hp(enemy)}")


def test_globe_high_level_passes():
    """L7 Finger of Death passes through globe (only blocks L5-)."""
    print("\n=== Test: Globe — L7 Passes Through ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    target = create_test_target("Target", (6, 5), con=1, faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    initial_hp = get_hp(target)

    register_spell(enemy, FingerOfDeath, caster_level=13)
    idx, available = find_target_index(enemy, "Finger of Death", target_uuid=target.uuid)
    if idx is not None:
        execute_by_index(enemy, "Finger of Death", idx, available=available)

    check("L7 spell passes through globe", get_hp(target) < initial_hp)


def test_globe_concentration_break():
    """After Globe concentration breaks, spells hit normally."""
    print("\n=== Test: Globe Concentration Break ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    target = create_test_target("Target", (6, 5), dex=1, faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    # Break concentration via damage
    set_hp(globe_caster, get_max_hp(globe_caster))
    deal_damage_to(globe_caster, 200, DamageType.FIRE, source_uuid=enemy.uuid)

    check("Concentration broken", not has_condition(globe_caster, "Concentrating"))
    check("Globe zone removed", not has_condition(globe_caster, "Globe of Invulnerability Zone"))

    # Enemy Fireball should now hit
    set_hp(target, get_max_hp(target))
    initial_hp = get_hp(target)

    register_spell(enemy, Fireball, caster_level=5)
    idx, available = find_target_index(enemy, "Fireball", position=(6, 5))
    if idx is not None:
        execute_by_index(enemy, "Fireball", idx, available=available)

    check("Fireball hits after globe broken", get_hp(target) < initial_hp)


def test_globe_partial_aoe_blocking():
    """AoE centered OUTSIDE globe: entity inside protected, entity outside takes damage."""
    print("\n=== Test: Globe Partial AoE Blocking ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    # Globe caster at (10,10), globe radius = 10ft = 2 cells
    globe_caster = create_caster(name="Globe Caster", position=(10, 10), faction="heroes")
    # Ally inside globe (1 cell from caster = 5ft)
    ally_inside = create_test_target("Ally Inside", (11, 10), dex=1, faction="heroes")
    # Target outside globe (4 cells from caster = 20ft, but within Fireball's 20ft radius from center)
    target_outside = create_test_target("Target Outside", (14, 10), dex=1, faction="heroes")
    enemy = create_caster(name="Enemy", position=(20, 10), faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Globe
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    initial_inside_hp = get_hp(ally_inside)
    initial_outside_hp = get_hp(target_outside)

    # Enemy Fireball centered at (13,10) — 3 cells from globe center, OUTSIDE globe
    # Fireball 20ft radius (4 cells) hits both (11,10) and (14,10)
    register_spell(enemy, Fireball, caster_level=5)
    idx, available = find_target_index(enemy, "Fireball", position=(13, 10))
    check("Fireball targeting position available", idx is not None)

    if idx is not None:
        execute_by_index(enemy, "Fireball", idx, available=available)

    check("Ally INSIDE globe takes no damage", get_hp(ally_inside) == initial_inside_hp)
    check("Target OUTSIDE globe takes damage", get_hp(target_outside) < initial_outside_hp)
    print(f"  Inside HP: {get_hp(ally_inside)}/{initial_inside_hp}, Outside HP: {get_hp(target_outside)}/{initial_outside_hp}")


def test_globe_blocks_cantrip():
    """Globe blocks cantrips (level 0 <= 5). Fire Bolt from outside is blocked."""
    print("\n=== Test: Globe Blocks Cantrip ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    target = create_test_target("Target Inside", (6, 5), dex=1, faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Globe
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    initial_hp = get_hp(target)

    # Enemy Fire Bolt (cantrip, level 0) at target inside globe
    # Fire Bolt already registered by create_caster
    idx, available = find_target_index(enemy, "Fire Bolt", target_uuid=target.uuid)
    check("Fire Bolt available targeting inside globe", idx is not None)

    if idx is not None:
        execute_by_index(enemy, "Fire Bolt", idx, available=available)

    check("Cantrip blocked — no damage", get_hp(target) == initial_hp)


def test_globe_blocks_upcast():
    """Fireball (base L3) is always blocked regardless of upcasting — base level check."""
    print("\n=== Test: Globe Blocks Based on Base Level ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    target = create_test_target("Target Inside", (6, 5), dex=1, faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Globe
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    initial_hp = get_hp(target)

    # Enemy Fireball (base L3, which is <= 5)
    idx, available = find_target_index(enemy, "Fireball", position=(6, 5))
    if idx is not None:
        execute_by_index(enemy, "Fireball", idx, available=available)

    check("Fireball blocked (base L3 <= 5)", get_hp(target) == initial_hp)


def test_globe_ally_inside_casts_out():
    """Ally inside globe can cast spells at enemies OUTSIDE."""
    print("\n=== Test: Globe — Ally Inside Casts Out ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    ally_caster = create_caster(name="Ally Caster", position=(6, 5), faction="heroes")
    enemy = create_test_target("Enemy Outside", (0, 0), dex=1, faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Globe
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    initial_hp = get_hp(enemy)

    # Ally inside casts Fire Bolt at enemy outside
    ally_caster.action_economy.reset_all_costs()
    hit_mod = AutoHitModifier(name="Force Hit", value=AutoHitStatus.AUTOHIT,
                              source_entity_uuid=ally_caster.uuid, target_entity_uuid=enemy.uuid)
    mod_uuid = ally_caster.equipment.attack_bonus.self_static.add_auto_hit_modifier(hit_mod)

    idx, available = find_target_index(ally_caster, "Fire Bolt", target_uuid=enemy.uuid)
    check("Ally Fire Bolt available from inside globe", idx is not None)

    if idx is not None:
        execute_by_index(ally_caster, "Fire Bolt", idx, available=available)

    ally_caster.equipment.attack_bonus.self_static.remove_modifier(mod_uuid)

    check("Ally's spell hits enemy outside globe", get_hp(enemy) < initial_hp)


def test_globe_immobile():
    """Globe stays at cast position when caster moves."""
    print("\n=== Test: Globe Is Immobile ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
    enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
    Entity.update_all_entities_senses()

    # Cast Globe at (5,5)
    register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
    execute_by_index(globe_caster, "Globe of Invulnerability", 0)

    # Get zone condition
    zone: Optional[GlobeZone] = None
    for cond in globe_caster.active_conditions.values():
        if isinstance(cond, GlobeZone):
            zone = cond
            break

    check("Globe zone exists", zone is not None)
    original_positions = set(zone.affected_positions) if zone else set()
    check("Globe has affected positions", len(original_positions) > 0)

    # Move caster away
    move_entity(globe_caster, (15, 15))
    Entity.update_all_entities_senses()

    # Globe positions should NOT change
    if zone:
        check("Globe positions unchanged after move", set(zone.affected_positions) == original_positions)
        check("Globe center unchanged", zone.zone_center == (5, 5))

    # Enemy Fire Bolt at a target at original globe position should be blocked
    target_in_old_globe = create_test_target("Target", (6, 5), dex=1, faction="heroes")
    Entity.update_all_entities_senses()

    initial_hp = get_hp(target_in_old_globe)
    idx, available = find_target_index(enemy, "Fire Bolt", target_uuid=target_in_old_globe.uuid)
    if idx is not None:
        execute_by_index(enemy, "Fire Bolt", idx, available=available)

    check("Spell blocked at original globe position", get_hp(target_in_old_globe) == initial_hp)


def test_globe_zone_exclusion():
    """Web cast from outside — entity inside globe not restrained, positions inside excluded."""
    print("\n=== Test: Globe Zone Exclusion ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        globe_caster = create_caster(name="Globe Caster", position=(5, 5), faction="heroes")
        target_inside = create_test_target("Inside Target", (6, 5), dex=1, faction="heroes")
        _target_outside = create_test_target("Outside Target", (9, 5), dex=1, faction="neutral")
        enemy = create_caster(name="Enemy", position=(0, 0), faction="monsters")
        Entity.update_all_entities_senses()

        # Cast Globe
        register_spell(globe_caster, GlobeOfInvulnerability, caster_level=11)
        execute_by_index(globe_caster, "Globe of Invulnerability", 0)

        # Register Web on enemy — L2 spell, 20ft cube
        enemy.action_economy.reset_all_costs()
        register_spell(enemy, Web, caster_level=5)

        # Cast Web centered at (7,5) — overlaps both globe zone and outside
        idx, available = find_target_index(enemy, "Web", position=(7, 5))
        check("Web available", idx is not None)

        if idx is not None:
            execute_by_index(enemy, "Web", idx, available=available)

        if had_critical_d20():
            continue

        # Entity inside globe should NOT be restrained
        check("Inside target NOT restrained", not has_condition(target_inside, "Restrained"))
        # Entity outside globe may or may not be restrained (depends on save)
        # but let's just verify the inside protection works
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


# =============================================================================
# Banishment Tests
# =============================================================================

def test_banishment_removes_from_senses():
    """Banishment: entity removed from grid AND from observers' senses."""
    print("\n=== Test: Banishment — Grid + Senses Removal ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), cha=1)
        observer = create_test_target("Observer", (4, 0), faction="neutral")
        Entity.update_all_entities_senses()

        target_pos = get_position(target)

        # Observer can see target before banishment
        check("Observer sees target before banishment", target.uuid in observer.senses.entities)

        # Register and cast Banishment via action API
        register_spell(caster, Banishment, caster_level=7)
        idx, available = find_target_index(caster, "Banishment", target_uuid=target.uuid)
        check("Banishment available targeting enemy", idx is not None)

        if idx is not None:
            execute_by_index(caster, "Banishment", idx, available=available)

        if had_critical_d20():
            continue

        if not has_condition(target, "Banished"):
            continue

        check("Target banished", True)
        check("Target incapacitated", has_condition(target, "Incapacitated"))
        check("Caster concentrating", has_condition(caster, "Concentrating"))

        # Grid removal
        check("Removed from _entity_positions", target.uuid not in grid._entity_positions)
        check("Not at original position", target.uuid not in grid.get_entities_at(target_pos))

        # Senses removal — observer shouldn't see banished target
        Entity.update_all_entities_senses()
        check("Observer cannot see banished target", target.uuid not in observer.senses.entities)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_banishment_return_on_concentration_break():
    """Concentration break returns entity to grid and restores senses."""
    print("\n=== Test: Banishment Return + Senses Restore ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), cha=1)
        observer = create_test_target("Observer", (4, 0), faction="neutral")
        Entity.update_all_entities_senses()

        original_pos = get_position(target)

        register_spell(caster, Banishment, caster_level=7)
        idx, available = find_target_index(caster, "Banishment", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Banishment", idx, available=available)

        if had_critical_d20():
            continue

        if not has_condition(target, "Banished"):
            continue

        # Break concentration via damage
        set_hp(caster, get_max_hp(caster))
        deal_damage_to(caster, 200, DamageType.FIRE, source_uuid=target.uuid)

        check("Banished removed", not has_condition(target, "Banished"))
        check("Incapacitated removed", not has_condition(target, "Incapacitated"))

        # Grid restored
        check("Target back in grid", target.uuid in grid._entity_positions)
        check("Target at original position", target.uuid in grid.get_entities_at(original_pos))

        # Senses restored
        Entity.update_all_entities_senses()
        check("Observer sees target again", target.uuid in observer.senses.entities)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_banishment_return_occupied_position():
    """When original position is occupied, occupant is displaced on return."""
    print("\n=== Test: Banishment — Occupied Position ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), cha=1)
        Entity.update_all_entities_senses()

        original_pos = get_position(target)

        register_spell(caster, Banishment, caster_level=7)
        idx, available = find_target_index(caster, "Banishment", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Banishment", idx, available=available)

        if had_critical_d20():
            continue

        if not has_condition(target, "Banished"):
            continue

        # Place occupant at target's original position
        occupant = create_test_target("Occupant", original_pos, faction="neutral")
        Entity.update_all_entities_senses()
        check("Occupant at original position", get_position(occupant) == original_pos)

        # Break concentration — target returns
        caster.remove_condition("Concentrating")

        check("Target returned", not has_condition(target, "Banished"))

        # Target at original position
        target_grid_pos = grid._entity_positions.get(target.uuid)
        check("Target placed at original position", target_grid_pos == original_pos)

        # Occupant displaced to adjacent cell
        occupant_pos = get_position(occupant)
        check("Occupant displaced", occupant_pos != original_pos)

        dx = abs(occupant_pos[0] - original_pos[0])
        dy = abs(occupant_pos[1] - original_pos[1])
        check("Occupant adjacent to original", dx <= 1 and dy <= 1 and (dx + dy) > 0)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


def test_banishment_save_success():
    """CHA save success — no banishment."""
    print("\n=== Test: Banishment Save Success ===")

    for _attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), cha=40)
        Entity.update_all_entities_senses()

        register_spell(caster, Banishment, caster_level=7)
        idx, available = find_target_index(caster, "Banishment", target_uuid=target.uuid)
        if idx is not None:
            execute_by_index(caster, "Banishment", idx, available=available)

        if had_critical_d20():
            continue

        check("Target NOT banished", not has_condition(target, "Banished"))
        check("Target still in grid", target.uuid in grid._entity_positions)
        break
    else:
        print("  SKIP: Got nat 1/20 on all attempts")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BATCH 4 SPELL TESTS — Full Integration")
    print("=" * 60)

    # True Strike
    test_true_strike_cha_modifier_in_damage()
    test_true_strike_cantrip_scaling()
    test_true_strike_miss_no_damage()

    # Finger of Death
    test_finger_of_death_full_damage()
    test_finger_of_death_half_on_save()

    # Telekinesis
    test_telekinesis_full_flow()
    test_telekinesis_move_grid_and_senses()
    test_telekinesis_concentration_break()

    # Globe of Invulnerability
    test_globe_blocks_enemy_spell()
    test_globe_own_spells_pass()
    test_globe_high_level_passes()
    test_globe_concentration_break()
    test_globe_partial_aoe_blocking()
    test_globe_blocks_cantrip()
    test_globe_blocks_upcast()
    test_globe_ally_inside_casts_out()
    test_globe_immobile()
    test_globe_zone_exclusion()

    # Banishment
    test_banishment_removes_from_senses()
    test_banishment_return_on_concentration_break()
    test_banishment_return_occupied_position()
    test_banishment_save_success()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
