"""
Test Fighter Factory - Verify Fighter creation at various levels.

This script tests:
1. Level 1 Fighter with default configuration
2. Level 5 Fighter with ASI
3. Level 10 Champion with two fighting styles
4. Level 20 Champion with all features
"""

from dnd.classes.fighter_factory import (
    FighterConfig,
    create_fighter,
    get_proficiency_bonus,
    get_extra_attacks,
    get_action_surge_uses,
    get_indomitable_uses,
)
from dnd.entity import Entity


def test_level_1_fighter():
    """Test basic Level 1 Fighter creation."""
    print("=" * 60)
    print("TEST: Level 1 Fighter")
    print("=" * 60)

    config = FighterConfig(
        level=1,
        name="Recruit",
        base_strength=15,
        base_dexterity=13,
        base_constitution=14,
        base_intelligence=10,
        base_wisdom=12,
        base_charisma=8,
        bonus_plus_2="strength",      # STR = 15 + 2 = 17
        bonus_plus_1="constitution",  # CON = 14 + 1 = 15
        fighting_style="defense",
        equipment_preset="sword_shield",
    )

    fighter = create_fighter(config)

    # Verify proficiency bonus
    assert fighter.proficiency_bonus.normalized_score == 2, \
        f"Expected prof +2, got {fighter.proficiency_bonus.normalized_score}"

    # Verify ability scores
    assert fighter.ability_scores.strength.modifier == 3, \
        f"Expected STR mod +3, got {fighter.ability_scores.strength.modifier}"
    assert fighter.ability_scores.constitution.modifier == 2, \
        f"Expected CON mod +2, got {fighter.ability_scores.constitution.modifier}"

    # Verify conditions
    assert "Second Wind Feature" in fighter.active_conditions, \
        "Missing Second Wind Feature"
    assert "Fighting Style: Defense" in fighter.active_conditions, \
        "Missing Defense Fighting Style"

    # Verify HP: Level 1 = 10 (max d10) + 2 (CON mod) = 12
    hp = fighter.get_hp()
    expected_hp = 10 + 2  # d10 max + CON mod
    assert hp == expected_hp, f"Expected HP {expected_hp}, got {hp}"

    print(f"Name: {fighter.name}")
    print(f"HP: {fighter.get_hp()}")
    print(f"AC: {fighter.ac_bonus().normalized_score}")
    print(f"Prof Bonus: {fighter.proficiency_bonus.normalized_score}")
    print(f"STR: {fighter.ability_scores.strength.ability_score.score} (mod {fighter.ability_scores.strength.modifier})")
    print(f"CON: {fighter.ability_scores.constitution.ability_score.score} (mod {fighter.ability_scores.constitution.modifier})")
    print(f"Conditions: {list(fighter.active_conditions.keys())}")
    print("PASSED!")
    print()

    return fighter


def test_level_5_fighter():
    """Test Level 5 Fighter with Extra Attack."""
    print("=" * 60)
    print("TEST: Level 5 Fighter")
    print("=" * 60)

    config = FighterConfig(
        level=5,
        name="Sir Roland",
        base_strength=15,
        base_dexterity=10,
        base_constitution=14,
        base_intelligence=8,
        base_wisdom=12,
        base_charisma=13,
        bonus_plus_2="strength",      # STR = 17
        bonus_plus_1="constitution",  # CON = 15
        fighting_style="great_weapon",
        equipment_preset="greatsword",
        asi_4=[("strength", 2)],      # STR = 19
    )

    fighter = create_fighter(config)

    # Verify proficiency bonus (Level 5 = +3)
    assert fighter.proficiency_bonus.normalized_score == 3, \
        f"Expected prof +3, got {fighter.proficiency_bonus.normalized_score}"

    # Verify STR after ASI
    assert fighter.ability_scores.strength.ability_score.score == 19, \
        f"Expected STR 19, got {fighter.ability_scores.strength.ability_score.score}"

    # Verify conditions
    assert "Extra Attack" in fighter.active_conditions, \
        "Missing Extra Attack Feature"
    assert "Action Surge Feature" in fighter.active_conditions, \
        "Missing Action Surge Feature"
    assert "Improved Critical" in fighter.active_conditions, \
        "Missing Improved Critical"

    # Verify HP: Level 5 = 10 + 4*6 + 5*2 (CON) = 10 + 24 + 10 = 44
    hp = fighter.get_hp()
    con_mod = fighter.ability_scores.constitution.modifier
    expected_hp = 10 + (4 * 6) + (5 * con_mod)  # L1 max + L2-5 avg + CON per level
    assert hp == expected_hp, f"Expected HP {expected_hp}, got {hp}"

    print(f"Name: {fighter.name}")
    print(f"HP: {fighter.get_hp()}")
    print(f"AC: {fighter.ac_bonus().normalized_score}")
    print(f"Prof Bonus: {fighter.proficiency_bonus.normalized_score}")
    print(f"STR: {fighter.ability_scores.strength.ability_score.score} (mod {fighter.ability_scores.strength.modifier})")
    print(f"Conditions: {list(fighter.active_conditions.keys())}")
    print("PASSED!")
    print()

    return fighter


def test_level_10_champion():
    """Test Level 10 Champion with two fighting styles."""
    print("=" * 60)
    print("TEST: Level 10 Champion")
    print("=" * 60)

    config = FighterConfig(
        level=10,
        name="The Wall",
        base_strength=14,
        base_dexterity=10,
        base_constitution=15,
        base_intelligence=8,
        base_wisdom=13,
        base_charisma=12,
        bonus_plus_2="constitution",  # CON = 17
        bonus_plus_1="strength",      # STR = 15
        fighting_style="defense",
        second_fighting_style="protection",
        equipment_preset="sword_shield",
        asi_4=[("constitution", 2)],  # CON = 19
        asi_6=[("strength", 2)],      # STR = 17
        asi_8=[("constitution", 1), ("strength", 1)],  # CON = 20, STR = 18
    )

    fighter = create_fighter(config)

    # Verify proficiency bonus (Level 10 = +4)
    assert fighter.proficiency_bonus.normalized_score == 4, \
        f"Expected prof +4, got {fighter.proficiency_bonus.normalized_score}"

    # Verify ability scores after ASIs
    assert fighter.ability_scores.constitution.ability_score.score == 20, \
        f"Expected CON 20, got {fighter.ability_scores.constitution.ability_score.score}"
    assert fighter.ability_scores.strength.ability_score.score == 18, \
        f"Expected STR 18, got {fighter.ability_scores.strength.ability_score.score}"

    # Verify both fighting styles
    assert "Fighting Style: Defense" in fighter.active_conditions, \
        "Missing Defense Fighting Style"
    assert "Fighting Style: Protection" in fighter.active_conditions, \
        "Missing Protection Fighting Style"

    # Verify Indomitable
    assert "Indomitable" in fighter.active_conditions, \
        "Missing Indomitable"

    print(f"Name: {fighter.name}")
    print(f"HP: {fighter.get_hp()}")
    print(f"AC: {fighter.ac_bonus().normalized_score}")
    print(f"Prof Bonus: {fighter.proficiency_bonus.normalized_score}")
    print(f"CON: {fighter.ability_scores.constitution.ability_score.score} (mod {fighter.ability_scores.constitution.modifier})")
    print(f"STR: {fighter.ability_scores.strength.ability_score.score} (mod {fighter.ability_scores.strength.modifier})")
    print(f"Conditions: {list(fighter.active_conditions.keys())}")
    print("PASSED!")
    print()

    return fighter


def test_level_20_champion():
    """Test Level 20 Champion with all features."""
    print("=" * 60)
    print("TEST: Level 20 Champion")
    print("=" * 60)

    config = FighterConfig(
        level=20,
        name="Legendary Champion",
        base_strength=15,
        base_dexterity=14,
        base_constitution=13,
        base_intelligence=8,
        base_wisdom=12,
        base_charisma=10,
        bonus_plus_2="strength",
        bonus_plus_1="dexterity",
        fighting_style="archery",
        second_fighting_style="defense",
        equipment_preset="archery",
        asi_4=[("dexterity", 2)],     # DEX = 18
        asi_6=[("dexterity", 2)],     # DEX = 20
        asi_8=[("constitution", 2)],  # CON = 15
        asi_12=[("constitution", 2)], # CON = 17
        asi_14=[("constitution", 2)], # CON = 19
        asi_16=[("constitution", 1), ("wisdom", 1)],  # CON = 20, WIS = 13
        asi_19=[("strength", 2)],     # STR = 19
    )

    fighter = create_fighter(config)

    # Verify proficiency bonus (Level 20 = +6)
    assert fighter.proficiency_bonus.normalized_score == 6, \
        f"Expected prof +6, got {fighter.proficiency_bonus.normalized_score}"

    # Verify key features
    assert "Superior Critical" in fighter.active_conditions, \
        "Missing Superior Critical"
    assert "Survivor" in fighter.active_conditions, \
        "Missing Survivor"
    assert "Extra Attack" in fighter.active_conditions, \
        "Missing Extra Attack"

    # Should NOT have Improved Critical (replaced by Superior)
    assert "Improved Critical" not in fighter.active_conditions, \
        "Should not have Improved Critical at level 15+"

    # Verify Extra Attack has 3 extra attacks
    extra_attack = fighter.active_conditions.get("Extra Attack")
    assert extra_attack is not None
    assert extra_attack.extra_attacks == 3, \
        f"Expected 3 extra attacks, got {extra_attack.extra_attacks}"

    print(f"Name: {fighter.name}")
    print(f"HP: {fighter.get_hp()}")
    print(f"AC: {fighter.ac_bonus().normalized_score}")
    print(f"Prof Bonus: {fighter.proficiency_bonus.normalized_score}")
    print(f"DEX: {fighter.ability_scores.dexterity.ability_score.score} (mod {fighter.ability_scores.dexterity.modifier})")
    print(f"CON: {fighter.ability_scores.constitution.ability_score.score} (mod {fighter.ability_scores.constitution.modifier})")
    print(f"Conditions: {list(fighter.active_conditions.keys())}")
    print(f"Extra Attacks: {extra_attack.extra_attacks}")
    print("PASSED!")
    print()

    return fighter


def test_helper_functions():
    """Test the helper functions for level-based features."""
    print("=" * 60)
    print("TEST: Helper Functions")
    print("=" * 60)

    # Proficiency bonus
    assert get_proficiency_bonus(1) == 2
    assert get_proficiency_bonus(4) == 2
    assert get_proficiency_bonus(5) == 3
    assert get_proficiency_bonus(8) == 3
    assert get_proficiency_bonus(9) == 4
    assert get_proficiency_bonus(12) == 4
    assert get_proficiency_bonus(13) == 5
    assert get_proficiency_bonus(16) == 5
    assert get_proficiency_bonus(17) == 6
    assert get_proficiency_bonus(20) == 6
    print("Proficiency bonus: PASSED")

    # Extra attacks
    assert get_extra_attacks(4) == 0
    assert get_extra_attacks(5) == 1
    assert get_extra_attacks(10) == 1
    assert get_extra_attacks(11) == 2
    assert get_extra_attacks(19) == 2
    assert get_extra_attacks(20) == 3
    print("Extra attacks: PASSED")

    # Action surge uses
    assert get_action_surge_uses(1) == 0
    assert get_action_surge_uses(2) == 1
    assert get_action_surge_uses(16) == 1
    assert get_action_surge_uses(17) == 2
    print("Action surge uses: PASSED")

    # Indomitable uses
    assert get_indomitable_uses(8) == 0
    assert get_indomitable_uses(9) == 1
    assert get_indomitable_uses(12) == 1
    assert get_indomitable_uses(13) == 2
    assert get_indomitable_uses(16) == 2
    assert get_indomitable_uses(17) == 3
    print("Indomitable uses: PASSED")

    print()


def test_validation_errors():
    """Test that invalid configurations raise appropriate errors."""
    print("=" * 60)
    print("TEST: Validation Errors")
    print("=" * 60)

    # Test: Same ability for +2 and +1 bonus
    try:
        config = FighterConfig(
            level=1,
            bonus_plus_2="strength",
            bonus_plus_1="strength",  # Same as +2!
        )
        assert False, "Should have raised error for same bonus abilities"
    except ValueError as e:
        print(f"Same bonus abilities: PASSED (caught: {e})")

    # Test: Second fighting style before level 10
    try:
        config = FighterConfig(
            level=5,
            fighting_style="defense",
            second_fighting_style="archery",
            asi_4=[("strength", 2)],
        )
        assert False, "Should have raised error for early second style"
    except ValueError as e:
        print(f"Early second style: PASSED (caught: {e})")

    # Test: Same fighting style twice
    try:
        config = FighterConfig(
            level=10,
            fighting_style="defense",
            second_fighting_style="defense",
            asi_4=[("strength", 2)],
            asi_6=[("strength", 2)],
            asi_8=[("strength", 2)],
        )
        assert False, "Should have raised error for duplicate style"
    except ValueError as e:
        print(f"Duplicate fighting style: PASSED (caught: {e})")

    # Test: Missing ASI for level
    try:
        config = FighterConfig(
            level=5,
            fighting_style="defense",
            # Missing asi_4!
        )
        assert False, "Should have raised error for missing ASI"
    except ValueError as e:
        print(f"Missing ASI: PASSED (caught: {e})")

    # Test: ASI not totaling +2
    try:
        config = FighterConfig(
            level=4,
            fighting_style="defense",
            asi_4=[("strength", 1)],  # Only +1, should be +2
        )
        assert False, "Should have raised error for invalid ASI total"
    except ValueError as e:
        print(f"Invalid ASI total: PASSED (caught: {e})")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FIGHTER FACTORY TESTS")
    print("=" * 60 + "\n")

    # Clear registry for clean tests
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    test_helper_functions()
    test_validation_errors()

    # Clear again before entity creation tests
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    test_level_1_fighter()
    test_level_5_fighter()
    test_level_10_champion()
    test_level_20_champion()

    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
