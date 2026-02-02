"""
Test MULTI_ENTITY with different targets required + allies filter.

Uses TestBless spell to verify:
1. Can target self and allies
2. Cannot target enemies
3. Cannot target same entity twice (allow_same_target=False)
4. Respects max_targets limit

Run: python examples/test_multi_target_allies.py
"""

from uuid import uuid4

# Reset state first
from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.spells.enchantment import TestBless
from dnd.actions import SpellEvent


def create_test_caster(name: str = "Caster", position: tuple = (0, 0), faction: str = "heroes") -> Entity:
    """Create a caster with spell slots."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=16),  # +3 modifier
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3},
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction
    )

    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )


def create_test_entity(name: str, position: tuple, faction: str) -> Entity:
    """Create a test entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        position=position,
        faction=faction
    )

    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )


def test_target_self_and_allies():
    """Test that TestBless can target self and allies."""
    print("\n=== Test 1: Target Self and Allies ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Cleric", (0, 0), "heroes")
    ally1 = create_test_entity("Fighter", (2, 0), "heroes")
    ally2 = create_test_entity("Rogue", (0, 2), "heroes")

    Entity.update_all_entities_senses()

    # Target self and two allies
    spell = TestBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,  # Self
        extra_target_entity_uuids=[ally1.uuid, ally2.uuid],
        cast_at_level=1
    )

    targets = spell.get_all_targets()
    assert len(targets) == 3, f"Expected 3 targets, got {len(targets)}"

    result = spell.apply()
    assert result is not None, "Spell should execute"
    assert not result.canceled, f"Spell should not be canceled: {result.status_message}"
    assert isinstance(result, SpellEvent), "Result should be SpellEvent"
    assert result.total_targets == 3, f"Expected 3 targets blessed, got {result.total_targets}"

    print(f"  Successfully blessed self + 2 allies ({result.total_targets} targets)")


def test_cannot_target_enemies():
    """Test that TestBless rejects enemy targets."""
    print("\n=== Test 2: Cannot Target Enemies ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Cleric", (0, 0), "heroes")
    enemy = create_test_entity("Goblin", (5, 0), "enemies")

    Entity.update_all_entities_senses()

    # Try to target enemy
    spell = TestBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=1
    )

    result = spell.apply()
    assert result is not None, "Should get result"
    assert result.canceled, "Spell should be canceled when targeting enemy"
    assert result.status_message is not None, "Should have status message"
    assert "not self or an ally" in result.status_message.lower() or "ally" in result.status_message.lower(), \
        f"Expected ally validation message, got: {result.status_message}"

    print(f"  Correctly rejected enemy target: {result.status_message}")


def test_cannot_target_same_twice():
    """Test that TestBless rejects duplicate targets (allow_same_target=False)."""
    print("\n=== Test 3: Cannot Target Same Entity Twice ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Cleric", (0, 0), "heroes")
    ally = create_test_entity("Fighter", (2, 0), "heroes")

    Entity.update_all_entities_senses()

    # Try to target same ally twice
    spell = TestBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[ally.uuid, ally.uuid],  # Duplicates
        cast_at_level=1
    )

    assert spell.allow_same_target == False, "TestBless should NOT allow same target"

    # get_all_targets should filter duplicates due to override
    _targets = spell.get_all_targets()
    # But validation should catch it if duplicates sneak through

    result = spell.apply()
    # The get_all_targets already filters, so it may succeed with 1 target
    # OR the validation catches duplicates in the input
    if result and result.canceled:
        assert result.status_message is not None, "Should have status message"
        assert "multiple times" in result.status_message.lower() or "same" in result.status_message.lower(), \
            f"Expected same-target validation message, got: {result.status_message}"
        print(f"  Correctly rejected duplicate target: {result.status_message}")
    else:
        # get_all_targets filtered the duplicates, so only 1 was targeted
        print(f"  get_all_targets filtered duplicates, only 1 unique target processed")
        assert result is not None and isinstance(result, SpellEvent), "Result should be SpellEvent"
        assert result.total_targets == 1, f"Should have 1 unique target after filtering"


def test_max_targets_limit():
    """Test that TestBless respects max_targets=3."""
    print("\n=== Test 4: Max Targets Limit ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Cleric", (0, 0), "heroes")
    ally1 = create_test_entity("Fighter", (2, 0), "heroes")
    ally2 = create_test_entity("Rogue", (0, 2), "heroes")
    ally3 = create_test_entity("Wizard", (2, 2), "heroes")
    ally4 = create_test_entity("Barbarian", (3, 0), "heroes")  # 5th target

    Entity.update_all_entities_senses()

    # Try to target 5 allies (max is 3)
    spell = TestBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        extra_target_entity_uuids=[ally1.uuid, ally2.uuid, ally3.uuid, ally4.uuid],
        cast_at_level=1
    )

    targets = spell.get_all_targets()
    assert len(targets) == 3, f"Expected max 3 targets, got {len(targets)}"
    assert targets[0] == caster.uuid  # Self is first
    assert targets[1] == ally1.uuid
    assert targets[2] == ally2.uuid

    result = spell.apply()
    assert result is not None and not result.canceled
    assert isinstance(result, SpellEvent), "Result should be SpellEvent"
    assert result.total_targets == 3, f"Expected 3 targets, got {result.total_targets}"

    print(f"  Correctly limited to 3 targets (tried 5)")


def test_mixed_valid_invalid():
    """Test targeting mix of valid allies and invalid enemies."""
    print("\n=== Test 5: Mixed Valid/Invalid Targets ===")

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)  # Create floor tiles for LOS
    caster = create_test_caster("Cleric", (0, 0), "heroes")
    ally = create_test_entity("Fighter", (2, 0), "heroes")
    enemy = create_test_entity("Goblin", (5, 0), "enemies")

    Entity.update_all_entities_senses()

    # Mix of ally and enemy
    spell = TestBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[enemy.uuid],
        cast_at_level=1
    )

    result = spell.apply()
    assert result is not None, "Should get result"
    assert result.canceled, "Spell should be canceled with enemy in targets"
    assert result.status_message is not None, "Should have status message"
    assert "not self or an ally" in result.status_message.lower() or "enemy" in result.status_message.lower() or "ally" in result.status_message.lower(), \
        f"Expected ally validation message, got: {result.status_message}"

    print(f"  Correctly rejected mixed targets: {result.status_message}")


def run_all_tests():
    """Run all multi-target allies filter tests."""
    print("=" * 60)
    print("MULTI-ENTITY ALLIES FILTER TESTS (TestBless)")
    print("=" * 60)

    test_target_self_and_allies()
    test_cannot_target_enemies()
    test_cannot_target_same_twice()
    test_max_targets_limit()
    test_mixed_valid_invalid()

    print("\n" + "=" * 60)
    print("ALL MULTI-ENTITY ALLIES FILTER TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
