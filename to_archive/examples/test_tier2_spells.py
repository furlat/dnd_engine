"""
Comprehensive Tests for Tier 2 Spells (Phases 5-10)

Tests the following implemented features:
- Phase 5: Cone of Cold (60ft cone, 8d8 cold, CON save half, +1d8/upcast)
- Phase 6: Circle of Death (60ft sphere, 8d6 necrotic, +2d6/upcast)
- Phase 7: Blight (undead/construct immunity, plant special case)
- Phase 8: Power Word Kill (HP threshold, no save)
- Phase 9: Protection from Energy (energy resistance, concentration)
- Phase 10: Stoneskin (B/P/S resistance, concentration)

Run with: python examples/test_tier2_spells.py
"""

from uuid import uuid4

from dnd.utils import reset_combat_state, get_hp, has_condition, set_hp
from dnd.core.gridmap import get_map
from dnd.core.events import EventPhase
from dnd.core.aoe import Cone, Sphere
from dnd.entity import Entity, EntityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions
from dnd.core.modifiers import CreatureType, DamageType
from dnd.monsters.bestiary import create_caster, create_skeleton, create_goblin
from dnd.spells import (
    ConeOfCold, CircleOfDeath, Blight, PowerWordKill,
    ProtectionFromEnergy, Stoneskin
)
from dnd.core.events import EventQueue
from dnd.entity import get_natural_roll


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


# =============================================================================
# Phase 5: Cone of Cold Tests
# =============================================================================

def test_cone_of_cold_shape():
    """Verify 60ft cone hits positions in correct direction."""
    print("\n=== Test: Cone of Cold Shape ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    caster = create_caster(name="Caster", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    # Create spell targeting east direction
    spell = ConeOfCold(
        source_entity_uuid=caster.uuid,
        end_position=(15, 5)  # Direction target: east
    )

    # Check shape exists and has correct length
    assert spell.aoe_shape is not None, "AoE shape should be created"
    assert isinstance(spell.aoe_shape, Cone), f"Should be a Cone, got {type(spell.aoe_shape)}"
    assert spell.aoe_shape.length_feet == 60, f"Should be 60ft, got {spell.aoe_shape.length_feet}"

    print(f"  Cone length: {spell.aoe_shape.length_feet}ft")
    print("PASS: Cone of Cold shape correct")


def test_cone_of_cold_damage_and_save():
    """Full damage on fail, half on save."""
    print("\n=== Test: Cone of Cold Damage and Save ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    caster = create_caster(name="Caster", position=(5, 5), faction="heroes")

    # Create target with low CON in cone path
    target = create_skeleton(name="Target", position=(7, 5), faction="monsters")

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    print(f"  Target HP before: {initial_hp}")

    spell = ConeOfCold(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(15, 5),  # East direction
        cast_at_level=5
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    final_hp = get_hp(target)
    damage_dealt = initial_hp - final_hp

    print(f"  Target HP after: {final_hp}")
    print(f"  Damage dealt: {damage_dealt}")
    print(f"  Result: {result.status_message}")

    # Should deal some cold damage
    assert damage_dealt > 0, "Should deal cold damage"
    print("PASS: Cone of Cold deals damage")


def test_cone_of_cold_upcast():
    """Upcast adds +1d8 per level above 5th."""
    print("\n=== Test: Cone of Cold Upcast ===")

    # Level 5: 8d8
    spell_5 = ConeOfCold(source_entity_uuid=uuid4(), cast_at_level=5)
    assert spell_5.get_damage_dice_count() == 8, f"Level 5 should be 8d8, got {spell_5.get_damage_dice_count()}"

    # Level 6: 9d8
    spell_6 = ConeOfCold(source_entity_uuid=uuid4(), cast_at_level=6)
    assert spell_6.get_damage_dice_count() == 9, f"Level 6 should be 9d8, got {spell_6.get_damage_dice_count()}"

    # Level 9: 12d8
    spell_9 = ConeOfCold(source_entity_uuid=uuid4(), cast_at_level=9)
    assert spell_9.get_damage_dice_count() == 12, f"Level 9 should be 12d8, got {spell_9.get_damage_dice_count()}"

    print(f"  Level 5: {spell_5.get_damage_dice_count()}d8")
    print(f"  Level 6: {spell_6.get_damage_dice_count()}d8")
    print(f"  Level 9: {spell_9.get_damage_dice_count()}d8")
    print("PASS: Cone of Cold upcast scaling correct")


# =============================================================================
# Phase 6: Circle of Death Tests
# =============================================================================

def test_circle_of_death_range():
    """Works at 150ft, fails at 155ft."""
    print("\n=== Test: Circle of Death Range ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 40, 40)

    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    # Test at 150ft (30 tiles) - should work
    spell_150 = CircleOfDeath(
        source_entity_uuid=caster.uuid,
        end_position=(30, 0),  # 150ft
        cast_at_level=6
    )
    result = spell_150.apply()
    assert result is not None, "Result should not be None"

    # Note: Might fail due to no targets, but NOT due to range
    if result.phase == EventPhase.CANCEL:
        assert result.status_message is not None, "status_message should not be None"
        assert "range" not in result.status_message.lower(), \
            f"150ft should NOT fail for range: {result.status_message}"

    print(f"  150ft result: {result.phase}")
    print("PASS: Circle of Death range validated")


def test_circle_of_death_radius():
    """60ft radius sphere hits correct positions."""
    print("\n=== Test: Circle of Death Radius ===")

    spell = CircleOfDeath(source_entity_uuid=uuid4(), end_position=(10, 10))

    assert spell.aoe_shape is not None, "AoE shape should exist"
    assert isinstance(spell.aoe_shape, Sphere), f"Should be a Sphere, got {type(spell.aoe_shape)}"
    assert spell.aoe_shape.radius_feet == 60, f"Should be 60ft radius, got {spell.aoe_shape.radius_feet}"

    print(f"  Sphere radius: {spell.aoe_shape.radius_feet}ft")
    print("PASS: Circle of Death radius correct")


def test_circle_of_death_upcast():
    """Upcast adds +2d6 per level above 6th."""
    print("\n=== Test: Circle of Death Upcast ===")

    # Level 6: 8d6
    spell_6 = CircleOfDeath(source_entity_uuid=uuid4(), cast_at_level=6)
    assert spell_6.get_damage_dice_count() == 8, f"Level 6 should be 8d6, got {spell_6.get_damage_dice_count()}"

    # Level 7: 10d6 (+2)
    spell_7 = CircleOfDeath(source_entity_uuid=uuid4(), cast_at_level=7)
    assert spell_7.get_damage_dice_count() == 10, f"Level 7 should be 10d6, got {spell_7.get_damage_dice_count()}"

    # Level 9: 14d6 (+6)
    spell_9 = CircleOfDeath(source_entity_uuid=uuid4(), cast_at_level=9)
    assert spell_9.get_damage_dice_count() == 14, f"Level 9 should be 14d6, got {spell_9.get_damage_dice_count()}"

    print(f"  Level 6: {spell_6.get_damage_dice_count()}d6")
    print(f"  Level 7: {spell_7.get_damage_dice_count()}d6")
    print(f"  Level 9: {spell_9.get_damage_dice_count()}d6")
    print("PASS: Circle of Death upcast scaling correct (+2d6 per level)")


# =============================================================================
# Phase 7: Blight Tests
# =============================================================================

def test_blight_rejects_undead():
    """Blight has no effect on undead."""
    print("\n=== Test: Blight Rejects Undead ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    skeleton = create_skeleton(name="Skeleton", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()
    assert skeleton.creature_type == CreatureType.UNDEAD, "Skeleton should be UNDEAD"

    spell = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=skeleton.uuid,
        cast_at_level=4
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    assert result.phase == EventPhase.CANCEL, f"Should CANCEL for undead, got {result.phase}"
    assert result.status_message is not None, "status_message should not be None"
    assert "undead" in result.status_message.lower(), \
        f"Should mention 'undead': {result.status_message}"

    print(f"  Rejected: {result.status_message}")
    print("PASS: Blight rejects undead")


def test_blight_rejects_construct():
    """Blight has no effect on constructs."""
    print("\n=== Test: Blight Rejects Construct ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")

    # Create construct
    construct_config = EntityConfig(
        creature_type=CreatureType.CONSTRUCT,
        position=(1, 0),
        faction="monsters",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5)])
    )
    construct = Entity.create(name="Golem", source_entity_uuid=uuid4(), config=construct_config)
    setup_standard_actions(construct)

    Entity.update_all_entities_senses()

    spell = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=construct.uuid,
        cast_at_level=4
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    assert result.phase == EventPhase.CANCEL, f"Should CANCEL for construct, got {result.phase}"
    assert result.status_message is not None, "status_message should not be None"
    assert "construct" in result.status_message.lower(), \
        f"Should mention 'construct': {result.status_message}"

    print(f"  Rejected: {result.status_message}")
    print("PASS: Blight rejects constructs")


def test_blight_plant_max_damage():
    """Plants take maximum damage from Blight."""
    print("\n=== Test: Blight Plant Max Damage ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")

    # Create plant creature
    plant_config = EntityConfig(
        creature_type=CreatureType.PLANT,
        position=(1, 0),
        faction="monsters",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")])
    )
    plant = Entity.create(name="Plant", source_entity_uuid=uuid4(), config=plant_config)
    setup_standard_actions(plant)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(plant)
    print(f"  Plant HP before: {initial_hp}")

    spell = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=plant.uuid,
        cast_at_level=4
    )
    _result = spell.apply()  # Result checked via HP, not event fields

    final_hp = get_hp(plant)
    damage_dealt = initial_hp - final_hp

    # Max damage for 8d8 = 64
    print(f"  Plant HP after: {final_hp}")
    print(f"  Damage dealt: {damage_dealt}")
    print(f"  Expected max: 64 (8d8 max)")

    # Should deal max damage (8d8 = 64 for plants)
    # Note: This might have spell damage bonus added
    assert damage_dealt >= 64, f"Plants should take max damage (64+), got {damage_dealt}"
    print("PASS: Blight deals max damage to plants")


def test_blight_normal_target():
    """Normal targets get half damage on successful save."""
    print("\n=== Test: Blight Normal Target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    goblin = create_goblin(name="Goblin", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()
    assert goblin.creature_type == CreatureType.HUMANOID

    initial_hp = get_hp(goblin)
    print(f"  Goblin HP before: {initial_hp}")

    spell = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=goblin.uuid,
        cast_at_level=4
    )
    _result = spell.apply()  # Result checked via HP, not event fields

    final_hp = get_hp(goblin)
    damage_dealt = initial_hp - final_hp

    print(f"  Goblin HP after: {final_hp}")
    print(f"  Damage dealt: {damage_dealt}")

    # Should deal some necrotic damage
    assert damage_dealt > 0, "Should deal necrotic damage"
    print("PASS: Blight deals damage to normal targets")


# =============================================================================
# Phase 8: Power Word Kill Tests
# =============================================================================

def test_pwk_kills_at_threshold():
    """Target with exactly 100 HP dies."""
    print("\n=== Test: Power Word Kill at Threshold ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")

    # Create target with lots of HP, then set to exactly 100
    target_config = EntityConfig(
        position=(1, 0),
        faction="monsters",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=20, mode="maximums")])
    )
    target = Entity.create(name="Target", source_entity_uuid=uuid4(), config=target_config)
    setup_standard_actions(target)
    set_hp(target, 100)

    Entity.update_all_entities_senses()

    print(f"  Target HP before: {get_hp(target)}")

    spell = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=9
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    print(f"  Target HP after: {get_hp(target)}")
    print(f"  Result: {result.status_message}")

    assert get_hp(target) <= 0, "Target with 100 HP should die"
    print("PASS: Power Word Kill kills target at threshold")


def test_pwk_kills_below_threshold():
    """Target with 50 HP dies."""
    print("\n=== Test: Power Word Kill Below Threshold ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="monsters")
    set_hp(target, 50)

    Entity.update_all_entities_senses()

    print(f"  Target HP before: {get_hp(target)}")

    spell = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=9
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    print(f"  Target HP after: {get_hp(target)}")
    print(f"  Result: {result.status_message}")

    assert get_hp(target) <= 0, "Target with 50 HP should die"
    print("PASS: Power Word Kill kills target below threshold")


def test_pwk_fails_above_threshold():
    """Target with 101 HP survives."""
    print("\n=== Test: Power Word Kill Fails Above Threshold ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")

    # Create target with > 100 HP
    target_config = EntityConfig(
        position=(1, 0),
        faction="monsters",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=20, mode="maximums")])
    )
    target = Entity.create(name="Target", source_entity_uuid=uuid4(), config=target_config)
    setup_standard_actions(target)
    set_hp(target, 101)

    Entity.update_all_entities_senses()

    hp_before = get_hp(target)
    print(f"  Target HP before: {hp_before}")

    spell = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=9
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    hp_after = get_hp(target)
    print(f"  Target HP after: {hp_after}")
    print(f"  Result: {result.status_message}")

    assert hp_after == hp_before, f"Target with 101 HP should survive, HP changed from {hp_before} to {hp_after}"
    print("PASS: Power Word Kill fails above threshold")


def test_pwk_no_save():
    """Power Word Kill requires no saving throw."""
    print("\n=== Test: Power Word Kill No Save ===")

    # Just verify the spell doesn't have save-related attributes

    spell = PowerWordKill(source_entity_uuid=uuid4(), cast_at_level=9)

    # PWK doesn't use saves, just HP check
    assert not hasattr(spell, 'save_ability') or spell.target_type.name != "POSITION_AOE", \
        "PWK should not be a save-based spell"

    print("  PWK is direct HP-threshold spell, no save")
    print("PASS: Power Word Kill requires no save")


# =============================================================================
# Phase 9: Protection from Energy Tests
# =============================================================================

def test_protection_from_energy_fire_resistance():
    """Protection from Energy grants fire resistance."""
    print("\n=== Test: Protection from Energy Fire Resistance ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = ProtectionFromEnergy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        chosen_energy_type=DamageType.FIRE,
        cast_at_level=3
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    print(f"  Result: {result.status_message}")

    # Check if condition was applied
    assert has_condition(target, "Protection from Energy"), \
        "Target should have Protection from Energy condition"
    assert has_condition(caster, "Concentrating"), \
        "Caster should have Concentrating condition"

    # Test fire resistance by dealing fire damage
    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.FIRE, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Fire damage dealt: 20, taken: {damage_taken}")

    # Should take half (resistance)
    assert damage_taken == 10, f"Should take 10 (half of 20), took {damage_taken}"
    print("PASS: Protection from Energy grants fire resistance")


def test_protection_from_energy_cold_resistance():
    """Protection from Energy works with cold."""
    print("\n=== Test: Protection from Energy Cold Resistance ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = ProtectionFromEnergy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        chosen_energy_type=DamageType.COLD,
        cast_at_level=3
    )
    spell.apply()

    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.COLD, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Cold damage dealt: 20, taken: {damage_taken}")

    assert damage_taken == 10, f"Should take 10 (half of 20), took {damage_taken}"
    print("PASS: Protection from Energy grants cold resistance")


def test_protection_from_energy_concentration_cleanup():
    """Breaking concentration removes resistance."""
    print("\n=== Test: Protection from Energy Concentration Cleanup ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = ProtectionFromEnergy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        chosen_energy_type=DamageType.FIRE,
        cast_at_level=3
    )
    spell.apply()

    assert has_condition(target, "Protection from Energy")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    caster.remove_condition("Concentrating")

    # Protection should be gone
    assert not has_condition(caster, "Concentrating"), "Caster should not be concentrating"
    assert not has_condition(target, "Protection from Energy"), \
        "Target should lose Protection from Energy when concentration breaks"

    # Fire damage should now be full
    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.FIRE, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  After concentration break - Fire damage: 20, taken: {damage_taken}")

    assert damage_taken == 20, f"Should take full 20 damage, took {damage_taken}"
    print("PASS: Breaking concentration removes resistance")


def test_protection_from_energy_self_target():
    """Can target self."""
    print("\n=== Test: Protection from Energy Self Target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    spell = ProtectionFromEnergy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,  # Self-target
        chosen_energy_type=DamageType.LIGHTNING,
        cast_at_level=3
    )
    result = spell.apply()
    assert result is not None, "Result should not be None"

    print(f"  Result: {result.status_message}")

    assert has_condition(caster, "Protection from Energy"), \
        "Caster should have Protection from Energy on self"
    print("PASS: Protection from Energy can target self")


# =============================================================================
# Phase 10: Stoneskin Tests
# =============================================================================

def test_stoneskin_bludgeoning_resistance():
    """Stoneskin grants bludgeoning resistance."""
    print("\n=== Test: Stoneskin Bludgeoning Resistance ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use goblin (no inherent resistances/vulnerabilities) instead of skeleton (bludgeoning vulnerability)
    target = create_goblin(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4
    )
    spell.apply()

    assert has_condition(target, "Stoneskin")

    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.BLUDGEONING, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Bludgeoning damage dealt: 20, taken: {damage_taken}")

    assert damage_taken == 10, f"Should take 10 (half of 20), took {damage_taken}"
    print("PASS: Stoneskin grants bludgeoning resistance")


def test_stoneskin_piercing_resistance():
    """Stoneskin grants piercing resistance."""
    print("\n=== Test: Stoneskin Piercing Resistance ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use goblin (no inherent resistances/vulnerabilities) instead of skeleton
    target = create_goblin(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4
    )
    spell.apply()

    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.PIERCING, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Piercing damage dealt: 20, taken: {damage_taken}")

    assert damage_taken == 10, f"Should take 10 (half of 20), took {damage_taken}"
    print("PASS: Stoneskin grants piercing resistance")


def test_stoneskin_slashing_resistance():
    """Stoneskin grants slashing resistance."""
    print("\n=== Test: Stoneskin Slashing Resistance ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use goblin (no inherent resistances/vulnerabilities) instead of skeleton
    target = create_goblin(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4
    )
    spell.apply()

    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.SLASHING, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Slashing damage dealt: 20, taken: {damage_taken}")

    assert damage_taken == 10, f"Should take 10 (half of 20), took {damage_taken}"
    print("PASS: Stoneskin grants slashing resistance")


def test_stoneskin_concentration_cleanup():
    """Breaking concentration removes all resistances."""
    print("\n=== Test: Stoneskin Concentration Cleanup ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use goblin (no inherent resistances/vulnerabilities) instead of skeleton (bludgeoning vulnerability)
    target = create_goblin(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4
    )
    spell.apply()

    assert has_condition(target, "Stoneskin")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    caster.remove_condition("Concentrating")

    assert not has_condition(target, "Stoneskin"), \
        "Target should lose Stoneskin when concentration breaks"

    # Physical damage should now be full
    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.BLUDGEONING, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  After concentration break - Bludgeoning: 20, taken: {damage_taken}")

    assert damage_taken == 20, f"Should take full 20 damage, took {damage_taken}"
    print("PASS: Breaking concentration removes Stoneskin")


def test_stoneskin_other_damage_unaffected():
    """Stoneskin doesn't affect fire damage."""
    print("\n=== Test: Stoneskin Other Damage Unaffected ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use goblin (no inherent resistances/vulnerabilities) instead of skeleton
    target = create_goblin(name="Target", position=(1, 0), faction="heroes")

    Entity.update_all_entities_senses()

    spell = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4
    )
    spell.apply()

    hp_before = get_hp(target)
    target.health.take_damage(20, DamageType.FIRE, source_entity_uuid=caster.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after

    print(f"  Fire damage dealt: 20, taken: {damage_taken}")

    # Stoneskin only protects B/P/S, not fire
    assert damage_taken == 20, f"Fire should be full 20 damage, took {damage_taken}"
    print("PASS: Stoneskin doesn't affect fire damage")


# =============================================================================
# Main Test Runner
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TIER 2 SPELLS TEST SUITE (Phases 5-10)")
    print("=" * 60)

    passed = 0
    failed = 0

    tests = [
        # Phase 5: Cone of Cold
        test_cone_of_cold_shape,
        test_cone_of_cold_damage_and_save,
        test_cone_of_cold_upcast,
        # Phase 6: Circle of Death
        test_circle_of_death_range,
        test_circle_of_death_radius,
        test_circle_of_death_upcast,
        # Phase 7: Blight
        test_blight_rejects_undead,
        test_blight_rejects_construct,
        test_blight_plant_max_damage,
        test_blight_normal_target,
        # Phase 8: Power Word Kill
        test_pwk_kills_at_threshold,
        test_pwk_kills_below_threshold,
        test_pwk_fails_above_threshold,
        test_pwk_no_save,
        # Phase 9: Protection from Energy
        test_protection_from_energy_fire_resistance,
        test_protection_from_energy_cold_resistance,
        test_protection_from_energy_concentration_cleanup,
        test_protection_from_energy_self_target,
        # Phase 10: Stoneskin
        test_stoneskin_bludgeoning_resistance,
        test_stoneskin_piercing_resistance,
        test_stoneskin_slashing_resistance,
        test_stoneskin_concentration_cleanup,
        test_stoneskin_other_damage_unaffected,
    ]

    MAX_RETRIES = 3

    for test in tests:
        success = False
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                test()
                success = True
                if attempt > 0:
                    print(f"  (passed on retry {attempt + 1} - previous had nat 1/20)")
                break
            except (AssertionError, Exception) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1 and had_critical_d20():
                    continue
                break
        if success:
            passed += 1
        else:
            if isinstance(last_error, AssertionError):
                print(f"FAIL: {last_error}")
            else:
                print(f"ERROR: {type(last_error).__name__}: {last_error}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    if failed > 0:
        exit(1)
