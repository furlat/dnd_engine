"""
Test Barbarian Mindless Rage (Berserker Level 6)

Tests:
1. Blocks Charmed condition while raging
2. Blocks Frightened condition while raging
3. Works with both Raging and Frenzied
4. No effect when not raging
"""

from uuid import uuid4

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import EventQueue, WeaponSlot
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_greatsword
from dnd.conditions import Charmed, Frightened

from dnd.classes.rage import (
    RageFeature, FrenzyFeature, Raging, Frenzy
)
from dnd.classes.barbarian import MindlessRage


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0)
) -> Entity:
    """Create a simple barbarian for testing."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=16),
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=6,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    greatsword = create_greatsword(entity.uuid)
    entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    # Add RageFeature (provides rage resource and Rage action)
    rage_feature = RageFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_damage=2,
        rage_uses=3
    )
    entity.add_condition(rage_feature)

    # Add FrenzyFeature (registers Frenzy action)
    frenzy_feature = FrenzyFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_damage=2
    )
    entity.add_condition(frenzy_feature)

    return entity


def create_caster(
    name: str = "Caster",
    position: tuple = (5, 0)
) -> Entity:
    """Create a caster entity for source of charm/fear."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=8),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=16),
            wisdom=AbilityConfig(ability_score=14),
            charisma=AbilityConfig(ability_score=16)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=6,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)
    return entity


def test_mindless_rage_blocks_charmed_while_raging():
    """Test that Charmed is blocked while raging."""
    print("\n=== Test: Mindless Rage Blocks Charmed While Raging ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Mindless Barbarian", position=(0, 0))
    caster = create_caster("Charmer", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Apply Raging condition
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    assert "Raging" in barbarian.active_conditions, "Should be raging"
    print("  Barbarian is raging")

    # Try to apply Charmed
    charmed = Charmed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(charmed)

    # Check if Charmed was blocked
    is_charmed = "Charmed" in barbarian.active_conditions
    print(f"  Charmed applied: {is_charmed}")

    if not is_charmed:
        print("  [PASS] Mindless Rage blocks Charmed while raging")
    else:
        print("  [FAIL] Charmed should be blocked while raging")

    EventQueue.reset()


def test_mindless_rage_blocks_frightened_while_raging():
    """Test that Frightened is blocked while raging."""
    print("\n=== Test: Mindless Rage Blocks Frightened While Raging ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Fearless Barbarian", position=(0, 0))
    caster = create_caster("Frightener", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Apply Raging condition
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    assert "Raging" in barbarian.active_conditions, "Should be raging"
    print("  Barbarian is raging")

    # Try to apply Frightened
    frightened = Frightened(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(frightened)

    # Check if Frightened was blocked
    is_frightened = "Frightened" in barbarian.active_conditions
    print(f"  Frightened applied: {is_frightened}")

    if not is_frightened:
        print("  [PASS] Mindless Rage blocks Frightened while raging")
    else:
        print("  [FAIL] Frightened should be blocked while raging")

    EventQueue.reset()


def test_mindless_rage_works_with_frenzied():
    """Test that Mindless Rage works with Frenzied condition."""
    print("\n=== Test: Mindless Rage Works with Frenzied ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Frenzied Barbarian", position=(0, 0))
    caster = create_caster("Charmer", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Use Frenzy ACTION to properly enter frenzy (creates Raging + Frenzied)
    # Raging is the parent, Frenzied is a sub-condition of Raging
    frenzy_action = Frenzy(
        source_entity_uuid=barbarian.uuid,
        template=False
    )
    result = frenzy_action.apply()
    assert result is not None and not result.canceled, f"Frenzy should succeed: {result.status_message if result else 'None'}"

    assert "Frenzied" in barbarian.active_conditions, "Should be frenzied"
    assert "Raging" in barbarian.active_conditions, "Should be raging (parent condition)"
    print("  Barbarian is frenzied (Raging is parent condition)")

    # Try to apply Charmed
    charmed = Charmed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(charmed)

    is_charmed = "Charmed" in barbarian.active_conditions
    print(f"  Charmed applied: {is_charmed}")

    if not is_charmed:
        print("  [PASS] Mindless Rage blocks Charmed while frenzied")
    else:
        print("  [FAIL] Charmed should be blocked while frenzied")

    EventQueue.reset()


def test_mindless_rage_no_effect_when_not_raging():
    """Test that Mindless Rage has no effect when not raging."""
    print("\n=== Test: Mindless Rage No Effect When Not Raging ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Calm Barbarian", position=(0, 0))
    caster = create_caster("Charmer", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature (but NOT raging)
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Verify NOT raging
    assert "Raging" not in barbarian.active_conditions, "Should NOT be raging"
    assert "Frenzied" not in barbarian.active_conditions, "Should NOT be frenzied"
    print("  Barbarian is NOT raging")

    # Try to apply Charmed - should succeed because not raging
    charmed = Charmed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(charmed)

    is_charmed = "Charmed" in barbarian.active_conditions
    print(f"  Charmed applied: {is_charmed}")

    if is_charmed:
        print("  [PASS] Charmed applies normally when not raging")
    else:
        print("  [FAIL] Charmed should apply when not raging")

    EventQueue.reset()


def test_mindless_rage_only_blocks_specific_conditions():
    """Test that only Charmed and Frightened are blocked."""
    print("\n=== Test: Mindless Rage Only Blocks Specific Conditions ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    from dnd.conditions import Poisoned

    barbarian = create_test_barbarian("Selective Barbarian", position=(0, 0))
    caster = create_caster("Poisoner", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Apply Raging condition
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    assert "Raging" in barbarian.active_conditions, "Should be raging"
    print("  Barbarian is raging")

    # Try to apply Poisoned - should succeed (not blocked)
    poisoned = Poisoned(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(poisoned)

    is_poisoned = "Poisoned" in barbarian.active_conditions
    print(f"  Poisoned applied: {is_poisoned}")

    if is_poisoned:
        print("  [PASS] Mindless Rage only blocks Charmed/Frightened, not other conditions")
    else:
        print("  [FAIL] Poisoned should apply (Mindless Rage doesn't block it)")

    EventQueue.reset()


def test_mindless_rage_after_rage_ends():
    """Test conditions apply normally after rage ends."""
    print("\n=== Test: Conditions Apply After Rage Ends ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Post-Rage Barbarian", position=(0, 0))
    caster = create_caster("Charmer", position=(5, 0))

    Entity.update_all_entities_senses()

    # Apply MindlessRage feature
    mindless = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless)

    # Apply Raging condition
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # Verify raging
    assert "Raging" in barbarian.active_conditions
    print("  Barbarian is raging")

    # End rage
    barbarian.remove_condition("Raging")
    assert "Raging" not in barbarian.active_conditions
    print("  Rage ended")

    # Now Charmed should apply
    charmed = Charmed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(charmed)

    is_charmed = "Charmed" in barbarian.active_conditions
    print(f"  Charmed applied after rage: {is_charmed}")

    if is_charmed:
        print("  [PASS] Conditions apply normally after rage ends")
    else:
        print("  [FAIL] Charmed should apply after rage ends")

    EventQueue.reset()


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN MINDLESS RAGE TESTS")
    print("=" * 60)

    test_mindless_rage_blocks_charmed_while_raging()
    test_mindless_rage_blocks_frightened_while_raging()
    test_mindless_rage_works_with_frenzied()
    test_mindless_rage_no_effect_when_not_raging()
    test_mindless_rage_only_blocks_specific_conditions()
    test_mindless_rage_after_rage_ends()

    print("\n" + "=" * 60)
    print("MINDLESS RAGE TESTS COMPLETE")
    print("=" * 60)
