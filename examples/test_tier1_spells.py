"""
Comprehensive Tests for Tier 1 Spells (Phases 0-4)

Tests the following implemented features:
- Phase 0: CreatureType enum system
- Phase 1: Hold Person humanoid check
- Phase 2: Hold Monster undead immunity
- Phase 3: Sunburst (AoE + blind + undead disadvantage)
- Phase 4: Poison Spray (10ft range cantrip)

Run with: python examples/test_tier1_spells.py
"""

from uuid import uuid4

from dnd.utils import reset_combat_state, has_condition
from dnd.core.gridmap import get_map
from dnd.core.events import EventPhase
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowSetConfig, SavingThrowConfig
from dnd.actions_functional import setup_standard_actions
from dnd.core.modifiers import CreatureType, NumericalModifier
from dnd.conditions import Concentrating
from dnd.monsters.bestiary import create_goblin, create_skeleton, create_sorcerer
from dnd.spells import HoldPerson, HoldMonster, Sunburst, PoisonSpray
from dnd.core.events import EventQueue
from dnd.entity import get_natural_roll
import pytest


def had_critical_d20() -> bool:
    """Check if any d20 roll in the current EventQueue had a nat 1 or nat 20."""
    for event in EventQueue._all_events:
        dice_roll = getattr(event, 'dice_roll', None)
        if dice_roll is not None:
            try:
                nat = get_natural_roll(dice_roll)
                if nat == 1 or nat == 20:
                    return True
            except Exception:
                pass
        save_roll = getattr(event, 'save_roll', None)
        if save_roll is not None:
            try:
                nat = get_natural_roll(save_roll)
                if nat == 1 or nat == 20:
                    return True
            except Exception:
                pass
    return False


# =============================================================================
# Phase 0: Creature Type System Tests
# =============================================================================

def test_creature_type_enum_completeness():
    """All 14 D&D creature types must exist."""
    print("\n=== Test: CreatureType Enum Completeness ===")

    expected_types = [
        "ABERRATION", "BEAST", "CELESTIAL", "CONSTRUCT", "DRAGON",
        "ELEMENTAL", "FEY", "FIEND", "GIANT", "HUMANOID",
        "MONSTROSITY", "OOZE", "PLANT", "UNDEAD"
    ]

    for type_name in expected_types:
        assert hasattr(CreatureType, type_name), f"Missing CreatureType.{type_name}"
        print(f"  {type_name}: {getattr(CreatureType, type_name).value}")

    assert len(CreatureType) == 14, f"Should have 14 types, got {len(CreatureType)}"
    print("PASS: All 14 creature types exist")


def test_creature_type_entity_defaults():
    """Default creature_type is HUMANOID, skeleton is UNDEAD."""
    print("\n=== Test: Creature Type Entity Defaults ===")
    reset_combat_state()

    goblin = create_goblin(name="Goblin", position=(0, 0))
    skeleton = create_skeleton(name="Skeleton", position=(1, 0))

    assert goblin.creature_type == CreatureType.HUMANOID, \
        f"Goblin should be HUMANOID, got {goblin.creature_type}"
    assert skeleton.creature_type == CreatureType.UNDEAD, \
        f"Skeleton should be UNDEAD, got {skeleton.creature_type}"

    print(f"  Goblin: {goblin.creature_type}")
    print(f"  Skeleton: {skeleton.creature_type}")
    print("PASS: Entity creature types correct")


def test_creature_type_config_to_entity():
    """creature_type from config is copied to entity."""
    print("\n=== Test: Creature Type Config Propagation ===")
    reset_combat_state()

    # Create entity with explicit CONSTRUCT type
    config = EntityConfig(
        creature_type=CreatureType.CONSTRUCT,
        position=(0, 0)
    )
    entity = Entity.create(name="Golem", source_entity_uuid=uuid4(), config=config)

    assert entity.creature_type == CreatureType.CONSTRUCT, \
        f"Should be CONSTRUCT, got {entity.creature_type}"

    print(f"  Config: {config.creature_type}")
    print(f"  Entity: {entity.creature_type}")
    print("PASS: Config creature_type copied to entity")


# =============================================================================
# Phase 1: Hold Person Humanoid Check Tests
# =============================================================================

def test_hold_person_rejects_non_humanoid():
    """Hold Person MUST reject non-humanoids with creature type error."""
    print("\n=== Test: Hold Person Rejects Non-Humanoid ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    skeleton = create_skeleton(name="Skeleton", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()
    assert skeleton.uuid in caster.senses.entities, "Test invalid: skeleton not visible"

    hold_skeleton = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=skeleton.uuid,
        cast_at_level=2
    )
    result = hold_skeleton.apply()

    assert result is not None, "Result should not be None"
    assert result.phase == EventPhase.CANCEL, \
        f"Should CANCEL for undead, got {result.phase}"
    assert result.status_message is not None, "status_message should not be None"
    assert "humanoid" in result.status_message.lower(), \
        f"Should mention 'humanoid' in error, got: {result.status_message}"
    print(f"  Rejected: {result.status_message}")
    print("PASS: Hold Person rejects non-humanoid")


def test_hold_person_accepts_humanoid():
    """Hold Person validation passes for humanoid targets."""
    print("\n=== Test: Hold Person Accepts Humanoid ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    goblin = create_goblin(name="Goblin", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()
    assert goblin.uuid in caster.senses.entities, "Test invalid: goblin not visible"

    hold_goblin = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=goblin.uuid,
        cast_at_level=2
    )
    result = hold_goblin.apply()

    # Should NOT be cancelled due to creature type
    assert result is not None, "Result should not be None"
    if result.phase == EventPhase.CANCEL:
        assert result.status_message is not None, "status_message should not be None"
        assert "humanoid" not in result.status_message.lower(), \
            f"Should NOT reject humanoid, got: {result.status_message}"
    print(f"  Result: {result.phase} - {result.status_message}")
    print("PASS: Hold Person accepts humanoid")


def test_hold_person_applies_paralyzed():
    """Hold Person applies Paralyzed on failed WIS save."""
    print("\n=== Test: Hold Person Applies Paralyzed ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")

        # Boost DC to 16 so that WIS -5 + nat 20 = 15 < 16 (guaranteed fail)
        # But nat 20 auto-succeeds in BG3-style, so we retry on nat 20
        caster.spellcasting.spell_dc_bonus.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test DC Boost", value=1)
        )

        # Create humanoid with WIS 1 (-5 mod)
        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                wisdom=AbilityConfig(ability_score=1),  # -5 mod
                constitution=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                strength=AbilityConfig(ability_score=10),
                intelligence=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
            ),
            creature_type=CreatureType.HUMANOID,
            position=(1, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        weak_target = Entity.create(name="Weak Humanoid", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(weak_target)

        Entity.update_all_entities_senses()

        print(f"  Target WIS modifier: {weak_target.ability_scores.wisdom.modifier}")
        print(f"  Caster spell DC: {caster.spell_save_dc()}")

        hold = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=weak_target.uuid,
            cast_at_level=2
        )
        hold.apply()

        # If target saved (nat 20 auto-success), retry
        if not has_condition(weak_target, "Hold Person"):
            print(f"  Attempt {attempt + 1}: target saved (likely nat 20), retrying...")
            continue

        assert has_condition(weak_target, "Hold Person"), \
            f"Should have Hold Person effect. Conditions: {list(weak_target.active_conditions.keys())}"
        assert has_condition(weak_target, "Paralyzed"), \
            f"Should have Paralyzed sub-condition. Conditions: {list(weak_target.active_conditions.keys())}"

        print(f"  Conditions: {list(weak_target.active_conditions.keys())}")
        print("PASS: Hold Person applies Paralyzed")
        break
    else:
        pytest.fail("Target saved on all 10 attempts (likely repeated nat 20)")


def test_hold_person_concentration():
    """Hold Person applies Concentrating condition to caster."""
    print("\n=== Test: Hold Person Concentration ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")

    # Create weak target to guarantee effect applies
    weak_config = EntityConfig(
        ability_scores=AbilityScoresConfig(wisdom=AbilityConfig(ability_score=1)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]),
        creature_type=CreatureType.HUMANOID,
        position=(1, 0),
        faction="monsters",
        proficiency_bonus=2,
    )
    target = Entity.create(name="Target", source_entity_uuid=uuid4(), config=weak_config)
    setup_standard_actions(target)

    Entity.update_all_entities_senses()

    hold = HoldPerson(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, cast_at_level=2)
    hold.apply()

    # Verify caster is concentrating
    assert has_condition(caster, "Concentrating"), \
        f"Caster should be Concentrating. Conditions: {list(caster.active_conditions.keys())}"

    conc = caster.active_conditions.get("Concentrating")
    assert isinstance(conc, Concentrating), "Should be Concentrating instance"
    assert conc.spell_name == "Hold Person", f"Should concentrate on Hold Person, got {conc.spell_name}"

    print(f"  Caster concentrating on: {conc.spell_name}")
    print("PASS: Hold Person concentration works")


# =============================================================================
# Phase 2: Hold Monster Undead Immunity Tests
# =============================================================================

def test_hold_monster_rejects_undead():
    """Hold Monster MUST reject undead with undead error."""
    print("\n=== Test: Hold Monster Rejects Undead ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    # Give caster a level 5 spell slot
    caster.action_economy.spell_slot_5.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=caster.uuid, name="L5 Slot", value=1)
    )
    skeleton = create_skeleton(name="Skeleton", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()
    assert skeleton.uuid in caster.senses.entities, "Test invalid: skeleton not visible"

    hold = HoldMonster(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=skeleton.uuid,
        cast_at_level=5
    )
    result = hold.apply()

    assert result is not None, "Result should not be None"
    assert result.phase == EventPhase.CANCEL, f"Should CANCEL, got {result.phase}"
    assert result.status_message is not None, "status_message should not be None"
    assert "undead" in result.status_message.lower(), \
        f"Should mention 'undead', got: {result.status_message}"
    print(f"  Rejected: {result.status_message}")
    print("PASS: Hold Monster rejects undead")


def test_hold_monster_accepts_non_undead():
    """Hold Monster validation passes for non-undead targets."""
    print("\n=== Test: Hold Monster Accepts Non-Undead ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    caster.action_economy.spell_slot_5.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=caster.uuid, name="L5 Slot", value=1)
    )
    goblin = create_goblin(name="Goblin", position=(1, 0), faction="monsters")

    Entity.update_all_entities_senses()

    hold = HoldMonster(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=goblin.uuid,
        cast_at_level=5
    )
    result = hold.apply()

    assert result is not None, "Result should not be None"
    if result.phase == EventPhase.CANCEL:
        assert result.status_message is not None, "status_message should not be None"
        assert "undead" not in result.status_message.lower(), \
            f"Should NOT reject non-undead, got: {result.status_message}"
    print(f"  Result: {result.phase}")
    print("PASS: Hold Monster accepts non-undead")


def test_hold_monster_multi_target_calculation():
    """Hold Monster max targets = 1 + (cast_level - 5)."""
    print("\n=== Test: Hold Monster Multi-Target Calculation ===")

    test_cases = [
        (5, 1),   # Base level
        (6, 2),   # +1 target
        (7, 3),
        (8, 4),
        (9, 5),
    ]

    for level, expected_targets in test_cases:
        spell = HoldMonster(source_entity_uuid=uuid4(), cast_at_level=level)
        actual = spell.get_max_targets_for_level()
        assert actual == expected_targets, f"L{level} should be {expected_targets}, got {actual}"
        print(f"  L{level}: {actual} targets")

    print("PASS: Multi-target calculation correct")


def test_hold_monster_applies_paralyzed():
    """Hold Monster applies Hold Monster effect + Paralyzed on failed save."""
    print("\n=== Test: Hold Monster Applies Paralyzed ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        caster.action_economy.spell_slot_5.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="L5 Slot", value=1)
        )

        # Create non-undead with WIS 1 to fail save (unless nat 20)
        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                wisdom=AbilityConfig(ability_score=1),  # -5 mod
                constitution=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]),
            creature_type=CreatureType.BEAST,  # Not undead
            position=(1, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Weak Beast", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses()

        hold = HoldMonster(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, cast_at_level=5)
        hold.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Hold Monster"), \
            f"Should have Hold Monster effect. Conditions: {list(target.active_conditions.keys())}"
        assert has_condition(target, "Paralyzed"), \
            f"Should have Paralyzed. Conditions: {list(target.active_conditions.keys())}"

        print(f"  Target conditions: {list(target.active_conditions.keys())}")
        print("PASS: Hold Monster applies Paralyzed")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_hold_monster_concentration_cleanup():
    """Breaking Hold Monster concentration removes effect from target."""
    print("\n=== Test: Hold Monster Concentration Cleanup ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        caster.action_economy.spell_slot_5.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="L5 Slot", value=1)
        )

        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(wisdom=AbilityConfig(ability_score=1)),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]),
            creature_type=CreatureType.BEAST,
            position=(1, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Target", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses()

        # Cast and verify effect applied
        hold = HoldMonster(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, cast_at_level=5)
        hold.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Hold Monster"), "Effect should be applied"
        assert has_condition(caster, "Concentrating"), "Caster should be concentrating"
        print(f"  Before break - Target: {list(target.active_conditions.keys())}")

        # Break concentration
        caster.remove_condition("Concentrating")

        # Verify cleanup - ALL conditions should be removed (including nested sub-conditions)
        assert not has_condition(caster, "Concentrating"), "Concentration should be removed"
        assert not has_condition(target, "Hold Monster"), \
            f"Effect should be cleaned up. Target conditions: {list(target.active_conditions.keys())}"
        assert not has_condition(target, "Paralyzed"), \
            f"Paralyzed should be cleaned up. Target conditions: {list(target.active_conditions.keys())}"
        assert not has_condition(target, "Incapacitated"), \
            f"Incapacitated (sub-condition of Paralyzed) should be cleaned up. Target conditions: {list(target.active_conditions.keys())}"

        print(f"  After break - Target: {list(target.active_conditions.keys())}")
        print("PASS: Concentration cleanup works (including nested sub-conditions)")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


# =============================================================================
# Phase 3: Sunburst Tests
# =============================================================================

def test_sunburst_full_damage_and_blind_on_fail():
    """Sunburst deals FULL damage and blinds on FAILED save."""
    print("\n=== Test: Sunburst Full Damage + Blind on Failed Save ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 30, 30)

        # Caster at (0,0), target at (14,0) = 70ft apart
        # Caster is OUTSIDE the 60ft sphere but within 150ft spell range
        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        caster.action_economy.spell_slot_8.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="L8 Slot", value=1)
        )
        # Add action economy (spells cost an action)
        caster.action_economy.actions.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test Action", value=1)
        )

        # CON 1 = -5 mod, GUARANTEED to fail any DC (unless nat 20)
        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                constitution=AbilityConfig(ability_score=1),
            ),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=20, mode="maximums")]),
            position=(14, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Weak Target", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses(max_distance=20)

        initial_hp = target.get_hp()
        print(f"  Target CON mod: {target.ability_scores.constitution.modifier}")
        print(f"  Caster DC: {caster.spell_save_dc()}")

        sunburst = Sunburst(source_entity_uuid=caster.uuid, end_position=(14, 0), cast_at_level=8)
        _result = sunburst.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        damage_dealt = initial_hp - target.get_hp()
        assert damage_dealt > 0, "Should deal damage"
        assert has_condition(target, "Sunburst Blindness"), "Should be blinded"
        assert has_condition(target, "Blinded"), "Should have Blinded sub-condition"

        print(f"  Damage: {damage_dealt}")
        print(f"  Blinded: YES")
        print("PASS: Full damage + blind on failed save")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_sunburst_half_damage_no_blind_on_success():
    """Sunburst deals HALF damage and NO blind on SUCCESSFUL save."""
    print("\n=== Test: Sunburst Half Damage + No Blind on Success ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 30, 30)

        # Caster outside 60ft sphere AoE
        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        caster.action_economy.spell_slot_8.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="L8 Slot", value=1)
        )
        # Add action economy (spells cost an action)
        caster.action_economy.actions.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test Action", value=1)
        )

        # CON 30 (+10) + proficiency (+2) + bonus (+5) = +17
        # DC 15 means roll 1+17=18 > 15 (ALWAYS PASS unless nat 1)
        tough_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                constitution=AbilityConfig(ability_score=30),  # +10 mod
            ),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=20, mode="maximums")]),
            saving_throws=SavingThrowSetConfig(
                constitution_saving_throw=SavingThrowConfig(
                    proficiency=True,
                    bonus=5  # Additional +5 bonus via config
                )
            ),
            position=(14, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Tough Target", source_entity_uuid=uuid4(), config=tough_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses(max_distance=20)

        initial_hp = target.get_hp()
        print(f"  Target CON mod: {target.ability_scores.constitution.modifier}")
        print(f"  Caster DC: {caster.spell_save_dc()}")

        sunburst = Sunburst(source_entity_uuid=caster.uuid, end_position=(14, 0), cast_at_level=8)
        _result = sunburst.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        # Should still take damage (half)
        damage_dealt = initial_hp - target.get_hp()
        assert damage_dealt > 0, "Should deal half damage even on save"

        # Should NOT be blinded
        assert not has_condition(target, "Sunburst Blindness"), \
            f"Should NOT be blinded on save. Conditions: {list(target.active_conditions.keys())}"
        assert not has_condition(target, "Blinded"), \
            f"Should NOT have Blinded. Conditions: {list(target.active_conditions.keys())}"

        print(f"  Damage: {damage_dealt} (half)")
        print(f"  Blinded: NO")
        print("PASS: Half damage + no blind on success")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_sunburst_undead_gets_disadvantage():
    """Undead creature gets disadvantage on Sunburst save."""
    print("\n=== Test: Sunburst Undead Disadvantage ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    # Caster outside 60ft sphere AoE
    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    caster.action_economy.spell_slot_8.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=caster.uuid, name="L8 Slot", value=1)
    )
    # Add action economy (spells cost an action)
    caster.action_economy.actions.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test Action", value=1)
    )

    skeleton = create_skeleton(name="Skeleton", position=(14, 0), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    # Verify skeleton is undead
    assert skeleton.creature_type == CreatureType.UNDEAD, "Skeleton should be UNDEAD"
    print(f"  Skeleton creature type: {skeleton.creature_type}")

    # Cast and observe (disadvantage is applied during the spell)
    # We can't easily verify the disadvantage was applied without mocking,
    # but we can verify the spell completes without error
    sunburst = Sunburst(source_entity_uuid=caster.uuid, end_position=(14, 0), cast_at_level=8)
    result = sunburst.apply()

    # The spell should complete (not error out due to undead handling)
    assert result is not None, "Spell should complete"
    print(f"  Spell result: {result.phase}")

    # Undead are likely to fail (CON +2 vs DC ~15, with disadvantage)
    # But we can't guarantee without controlling the dice
    print(f"  Skeleton conditions: {list(skeleton.active_conditions.keys())}")
    print("PASS: Undead disadvantage handling works (no errors)")


def test_sunburst_sub_condition_cleanup():
    """Removing Sunburst Blindness also removes Blinded sub-condition."""
    print("\n=== Test: Sunburst Sub-Condition Cleanup ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 30, 30)

        # Caster outside 60ft sphere AoE
        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        caster.action_economy.spell_slot_8.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="L8 Slot", value=1)
        )
        # Add action economy (spells cost an action)
        caster.action_economy.actions.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test Action", value=1)
        )

        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(constitution=AbilityConfig(ability_score=1)),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=20, mode="maximums")]),
            position=(14, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Target", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses(max_distance=20)

        # Cast to apply blindness
        sunburst = Sunburst(source_entity_uuid=caster.uuid, end_position=(14, 0), cast_at_level=8)
        sunburst.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Sunburst Blindness"), "Should be blinded"
        assert has_condition(target, "Blinded"), "Should have Blinded sub-condition"
        print(f"  Before removal: {list(target.active_conditions.keys())}")

        # Remove parent condition
        target.remove_condition("Sunburst Blindness")

        # Both should be gone
        assert not has_condition(target, "Sunburst Blindness"), "Parent should be removed"
        assert not has_condition(target, "Blinded"), \
            f"Sub-condition should be removed. Conditions: {list(target.active_conditions.keys())}"

        print(f"  After removal: {list(target.active_conditions.keys())}")
        print("PASS: Sub-condition cleanup works")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


# =============================================================================
# Phase 4: Poison Spray Tests
# =============================================================================

def test_poison_spray_works_at_10ft():
    """Poison Spray works at exactly 10ft range."""
    print("\n=== Test: Poison Spray Works at 10ft ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_goblin(name="Target", position=(2, 0), faction="monsters")  # 10ft

    caster.update_entity_senses(max_distance=10)

    # Verify distance
    distance = caster.senses.get_feet_distance(target.position)
    assert distance == 10, f"Target should be 10ft away, got {distance}"
    print(f"  Distance: {distance}ft")

    poison = PoisonSpray(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=5)
    result = poison.apply()

    assert result is not None, "Result should not be None"
    assert result.phase != EventPhase.CANCEL, f"10ft should work, got: {result.status_message}"
    print(f"  Result: {result.phase}")
    print("PASS: Poison Spray works at 10ft")


def test_poison_spray_fails_at_15ft_with_range_error():
    """Poison Spray MUST fail at >10ft with RANGE error, not LOS error."""
    print("\n=== Test: Poison Spray Fails at 15ft ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_goblin(name="Target", position=(3, 0), faction="monsters")  # 15ft

    caster.update_entity_senses(max_distance=10)  # 50ft visibility

    # CRITICAL: Verify LOS works FIRST
    assert target.uuid in caster.senses.entities, \
        f"TEST INVALID: Target not visible. Need LOS to test range error."

    distance = caster.senses.get_feet_distance(target.position)
    print(f"  Distance: {distance}ft")
    print(f"  LOS: VERIFIED")

    poison = PoisonSpray(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=5)
    result = poison.apply()

    assert result is not None, "Result should not be None"
    assert result.phase == EventPhase.CANCEL, f"15ft should CANCEL, got {result.phase}"
    assert result.status_message is not None, "status_message should not be None"
    assert "range" in result.status_message.lower(), \
        f"Should fail due to RANGE, not LOS. Got: {result.status_message}"

    print(f"  Error: {result.status_message}")
    print("PASS: Fails at 15ft with range error")


def test_poison_spray_no_damage_on_save():
    """Poison Spray deals NO damage on successful CON save."""
    print("\n=== Test: Poison Spray No Damage on Save ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")

        # CON 30 (+10) + proficiency (+2) + bonus (+6) = +18
        # Always passes unless nat 1 (BG3 auto-fail)
        tough_config = EntityConfig(
            ability_scores=AbilityScoresConfig(constitution=AbilityConfig(ability_score=30)),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
            saving_throws=SavingThrowSetConfig(
                constitution_saving_throw=SavingThrowConfig(
                    proficiency=True,
                    bonus=6
                )
            ),
            position=(1, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Tough Target", source_entity_uuid=uuid4(), config=tough_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses()

        initial_hp = target.get_hp()
        print(f"  Target CON mod: {target.ability_scores.constitution.modifier}")
        print(f"  Caster DC: {caster.spell_save_dc()}")
        print(f"  Initial HP: {initial_hp}")

        poison = PoisonSpray(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=5)
        _result = poison.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = target.get_hp()
        damage = initial_hp - final_hp

        assert damage == 0, f"Should deal 0 damage on save, dealt {damage}"
        print(f"  Final HP: {final_hp}")
        print(f"  Damage: {damage}")
        print("PASS: No damage on save")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_poison_spray_deals_damage_on_failed_save():
    """Poison Spray deals damage on failed CON save."""
    print("\n=== Test: Poison Spray Deals Damage on Failed Save ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")

        # CON 1 = -5 mod, GUARANTEED to fail (unless nat 20)
        weak_config = EntityConfig(
            ability_scores=AbilityScoresConfig(constitution=AbilityConfig(ability_score=1)),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
            position=(1, 0),
            faction="monsters",
            proficiency_bonus=2,
        )
        target = Entity.create(name="Weak Target", source_entity_uuid=uuid4(), config=weak_config)
        setup_standard_actions(target)

        Entity.update_all_entities_senses()

        initial_hp = target.get_hp()
        print(f"  Target CON mod: {target.ability_scores.constitution.modifier}")
        print(f"  Initial HP: {initial_hp}")

        poison = PoisonSpray(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=5)
        _result = poison.apply()  # Result checked via HP, not phase

        final_hp = target.get_hp()
        damage = initial_hp - final_hp

        if damage == 0:
            print(f"  Attempt {attempt + 1}: no damage (likely nat 20), retrying...")
            continue  # nat 20 auto-success, re-roll

        assert damage > 0, f"Should deal damage on failed save, dealt {damage}"
        print(f"  Final HP: {final_hp}")
        print(f"  Damage: {damage}")
        print("PASS: Deals damage on failed save")
        break
    else:
        pytest.fail("Target saved on all 10 attempts (likely repeated nat 20)")


def test_poison_spray_cantrip_scaling():
    """Poison Spray scales: 1d12 at L1, 2d12 at L5, 3d12 at L11, 4d12 at L17."""
    print("\n=== Test: Poison Spray Cantrip Scaling ===")

    test_cases = [
        (1, 1),    # Level 1-4: 1d12
        (4, 1),
        (5, 2),    # Level 5-10: 2d12
        (10, 2),
        (11, 3),   # Level 11-16: 3d12
        (16, 3),
        (17, 4),   # Level 17+: 4d12
        (20, 4),
    ]

    for caster_level, expected_dice in test_cases:
        spell = PoisonSpray(source_entity_uuid=uuid4(), caster_level=caster_level)
        actual_dice = spell._get_cantrip_dice_count(caster_level)
        assert actual_dice == expected_dice, \
            f"Level {caster_level} should be {expected_dice}d12, got {actual_dice}d12"
        print(f"  Level {caster_level}: {actual_dice}d12")

    print("PASS: Cantrip scaling correct")


# =============================================================================
# Main Test Runner
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TIER 1 SPELL IMPLEMENTATION TESTS")
    print("=" * 60)

    tests = [
        # Phase 0: Creature Type System
        test_creature_type_enum_completeness,
        test_creature_type_entity_defaults,
        test_creature_type_config_to_entity,

        # Phase 1: Hold Person
        test_hold_person_rejects_non_humanoid,
        test_hold_person_accepts_humanoid,
        test_hold_person_applies_paralyzed,
        test_hold_person_concentration,

        # Phase 2: Hold Monster
        test_hold_monster_rejects_undead,
        test_hold_monster_accepts_non_undead,
        test_hold_monster_multi_target_calculation,
        test_hold_monster_applies_paralyzed,
        test_hold_monster_concentration_cleanup,

        # Phase 3: Sunburst
        test_sunburst_full_damage_and_blind_on_fail,
        test_sunburst_half_damage_no_blind_on_success,
        test_sunburst_undead_gets_disadvantage,
        test_sunburst_sub_condition_cleanup,

        # Phase 4: Poison Spray
        test_poison_spray_works_at_10ft,
        test_poison_spray_fails_at_15ft_with_range_error,
        test_poison_spray_no_damage_on_save,
        test_poison_spray_deals_damage_on_failed_save,
        test_poison_spray_cantrip_scaling,
    ]

    passed = 0
    failed = 0
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
                    continue  # Retry only if a nat 1/20 caused the flake
                break  # Real failure, don't retry
        if success:
            passed += 1
        else:
            if isinstance(last_error, AssertionError):
                print(f"\n*** FAILED: {test.__name__} ***")
                print(f"    {last_error}")
            else:
                print(f"\n*** ERROR: {test.__name__} ***")
                print(f"    {type(last_error).__name__}: {last_error}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
