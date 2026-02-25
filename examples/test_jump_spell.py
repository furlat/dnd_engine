"""Test Jump spell and jump distance ModifiableValue system.

Tests:
1. Base jump distance formula: (15 + max(0, STR_mod)*5 + additive) * multiplier
2. Additive modifier channel (flat bonuses from spells/conditions)
3. Multiplicative modifier channel (Jump spell sets 3x)
4. Stacking: additive + multiplicative together
5. Jump spell full lifecycle with concentration
6. Jump spell on ally
7. get_available_actions shows expanded jump targets after spell
"""
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.actions_functional import setup_standard_actions, get_available_actions, register_spell
from dnd.actions import Jump
from dnd.spells.transmutation import JumpSpell
from dnd.core.modifiers import NumericalModifier
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.encounter import Encounter
from dnd.controller import HumanController


def create_arena(size: int = 30):
    """Create a floor grid for jump testing."""
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)


def test_base_formula():
    """Test base jump distance formula with different STR values."""
    print("\n=== Test 1: Base jump distance formula ===")
    reset_combat_state()
    create_arena()

    # STR 10 (mod +0) → 15ft
    config_10 = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=10)),
        position=(10, 10)
    )
    ent_10 = Entity.create(name="STR10", source_entity_uuid=uuid4(), config=config_10)
    setup_standard_actions(ent_10)

    # STR 14 (mod +2) → 25ft
    config_14 = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=14)),
        position=(15, 10)
    )
    ent_14 = Entity.create(name="STR14", source_entity_uuid=uuid4(), config=config_14)
    setup_standard_actions(ent_14)

    # STR 20 (mod +5) → 40ft
    config_20 = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=20)),
        position=(20, 10)
    )
    ent_20 = Entity.create(name="STR20", source_entity_uuid=uuid4(), config=config_20)
    setup_standard_actions(ent_20)

    Entity.update_all_entities_senses()

    for ent, expected_str_mod, expected_range in [
        (ent_10, 0, 15), (ent_14, 2, 25), (ent_20, 5, 40)
    ]:
        jump = ent.get_action_template("Jump")
        assert isinstance(jump, Jump)
        actual = jump.get_range()
        assert actual is not None
        assert actual.normal == expected_range, f"{ent.name}: expected {expected_range}, got {actual.normal}"
        # Verify the additive and multiplier channels are at defaults
        assert ent.jump_distance_additive.normalized_score == 0
        assert ent.jump_distance_multiplier.normalized_score == 1
        print(f"  {ent.name} (STR mod +{expected_str_mod}): range={actual.normal}ft ✓")

    print("  PASSED")


def test_additive_modifier():
    """Test adding flat bonuses to jump distance via additive ModifiableValue."""
    print("\n=== Test 2: Additive modifier channel ===")
    reset_combat_state()
    create_arena()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=10)),
        position=(10, 10)
    )
    entity = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    jump = entity.get_action_template("Jump")
    assert isinstance(jump, Jump)
    base_range = jump.get_range()
    assert base_range is not None
    assert base_range.normal == 15  # STR 10 → 15ft
    print(f"  Base: {base_range.normal}ft")

    # Add +10ft flat bonus
    mod1 = NumericalModifier(name="Boots of Springing", value=10,
                             source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    mod1_uuid = entity.jump_distance_additive.self_static.add_value_modifier(mod1)

    r = jump.get_range()
    assert r is not None and r.normal == 25  # 15 + 10
    print(f"  +10ft bonus → {r.normal}ft ✓")

    # Stack another +5ft
    mod2 = NumericalModifier(name="Ring of Jumping", value=5,
                             source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    mod2_uuid = entity.jump_distance_additive.self_static.add_value_modifier(mod2)

    r = jump.get_range()
    assert r is not None and r.normal == 30  # 15 + 10 + 5
    print(f"  +10 +5 stacked → {r.normal}ft ✓")

    # Remove first
    entity.jump_distance_additive.self_static.remove_modifier(mod1_uuid)
    r = jump.get_range()
    assert r is not None and r.normal == 20  # 15 + 5
    print(f"  Remove +10 → {r.normal}ft ✓")

    # Remove second → back to base
    entity.jump_distance_additive.self_static.remove_modifier(mod2_uuid)
    r = jump.get_range()
    assert r is not None and r.normal == 15
    print(f"  Remove +5 → {r.normal}ft (base) ✓")

    print("  PASSED")


def test_multiplicative_modifier():
    """Test multiplier channel via direct modifier (not spell)."""
    print("\n=== Test 3: Multiplicative modifier channel ===")
    reset_combat_state()
    create_arena()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=14)),
        position=(10, 10)
    )
    entity = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    jump = entity.get_action_template("Jump")
    assert isinstance(jump, Jump)
    base = jump.get_range()
    assert base is not None and base.normal == 25  # STR 14 → 25ft
    print(f"  Base: {base.normal}ft (multiplier=1)")

    # +2 multiplier → 3x
    mod = NumericalModifier(name="Jump Spell", value=2,
                            source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    mod_uuid = entity.jump_distance_multiplier.self_static.add_value_modifier(mod)

    assert entity.jump_distance_multiplier.normalized_score == 3
    r = jump.get_range()
    assert r is not None and r.normal == 75  # 25 * 3
    print(f"  Multiplier=3 → {r.normal}ft (3x) ✓")

    # Stack another +1 → 4x
    mod2 = NumericalModifier(name="Extra Boost", value=1,
                             source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    mod2_uuid = entity.jump_distance_multiplier.self_static.add_value_modifier(mod2)

    assert entity.jump_distance_multiplier.normalized_score == 4
    r = jump.get_range()
    assert r is not None and r.normal == 100  # 25 * 4
    print(f"  Multiplier=4 → {r.normal}ft (4x) ✓")

    # Remove both
    entity.jump_distance_multiplier.self_static.remove_modifier(mod_uuid)
    entity.jump_distance_multiplier.self_static.remove_modifier(mod2_uuid)
    assert entity.jump_distance_multiplier.normalized_score == 1
    r = jump.get_range()
    assert r is not None and r.normal == 25
    print(f"  All removed → {r.normal}ft (1x) ✓")

    print("  PASSED")


def test_additive_and_multiplicative_combined():
    """Test both modifiers stacking: (base + additive) * multiplier."""
    print("\n=== Test 4: Additive + Multiplicative combined ===")
    reset_combat_state()
    create_arena()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=10)),
        position=(10, 10)
    )
    entity = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    jump = entity.get_action_template("Jump")
    assert isinstance(jump, Jump)
    # STR 10 → base 15ft
    print(f"  Base: 15ft = (15 + 0) * 1")

    # Add +10 flat
    add_mod = NumericalModifier(name="Boots", value=10,
                                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    add_uuid = entity.jump_distance_additive.self_static.add_value_modifier(add_mod)

    # Add +2 multiplier → 3x
    mul_mod = NumericalModifier(name="Jump", value=2,
                                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    mul_uuid = entity.jump_distance_multiplier.self_static.add_value_modifier(mul_mod)

    # (15 + 10) * 3 = 75
    r = jump.get_range()
    assert r is not None and r.normal == 75, f"Expected 75, got {r.normal if r else None}"
    print(f"  (15 + 10) * 3 = {r.normal}ft ✓")

    # Remove additive: (15 + 0) * 3 = 45
    entity.jump_distance_additive.self_static.remove_modifier(add_uuid)
    r = jump.get_range()
    assert r is not None and r.normal == 45, f"Expected 45, got {r.normal if r else None}"
    print(f"  Remove additive → (15 + 0) * 3 = {r.normal}ft ✓")

    # Remove multiplier: (15 + 0) * 1 = 15
    entity.jump_distance_multiplier.self_static.remove_modifier(mul_uuid)
    r = jump.get_range()
    assert r is not None and r.normal == 15
    print(f"  Remove multiplier → (15 + 0) * 1 = {r.normal}ft ✓")

    print("  PASSED")


def test_jump_spell_lifecycle():
    """Test Jump spell: cast → triple → concentration break → revert."""
    print("\n=== Test 5: Jump spell full lifecycle ===")
    reset_combat_state()
    create_arena()

    caster = create_sorcerer(level=5, name="Wizard", position=(10, 10))
    register_spell(caster, JumpSpell, caster_level=5)

    # Dummy enemy far away to keep encounter alive
    enemy = create_goblin(name="Enemy", position=(25, 25))

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    jump = caster.get_action_template("Jump")
    assert isinstance(jump, Jump)
    base = jump.get_range()
    assert base is not None
    base_range = base.normal
    str_mod = caster.ability_scores.strength.modifier
    expected = (15 + max(0, str_mod) * 5) * 1
    assert base_range == expected, f"Base expected {expected}, got {base_range}"
    print(f"  Base range: {base_range}ft (STR mod {str_mod})")

    # Cast Jump on self
    spell = JumpSpell(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, cast_at_level=1)
    result = spell.apply()
    assert result is not None and not result.canceled, f"Spell failed: {result}"
    print(f"  Cast Jump: {result.status_message}")

    assert "Jump" in caster.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert caster.jump_distance_multiplier.normalized_score == 3

    r = jump.get_range()
    assert r is not None and r.normal == base_range * 3
    print(f"  Range tripled: {r.normal}ft ✓")

    # Break concentration
    caster.remove_condition("Concentrating")
    assert "Jump" not in caster.active_conditions
    assert caster.jump_distance_multiplier.normalized_score == 1
    r = jump.get_range()
    assert r is not None and r.normal == base_range
    print(f"  Concentration broken → reverted: {r.normal}ft ✓")

    print("  PASSED")


def test_jump_spell_on_ally():
    """Test casting Jump on another creature (touch range)."""
    print("\n=== Test 6: Jump spell on ally ===")
    reset_combat_state()
    create_arena()

    caster = create_sorcerer(level=5, name="Wizard", position=(10, 10), faction="heroes")
    register_spell(caster, JumpSpell, caster_level=5)

    # Goblin has STR 8 (mod -1), so base jump = 15ft
    ally = create_goblin(name="Fighter", position=(11, 10), faction="heroes")

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(ally, HumanController(source_entity_uuid=ally.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    ally_jump = ally.get_action_template("Jump")
    assert isinstance(ally_jump, Jump)
    ally_base = ally_jump.get_range()
    assert ally_base is not None
    ally_base_range = ally_base.normal
    str_mod = ally.ability_scores.strength.modifier
    print(f"  Ally base: {ally_base_range}ft (STR mod {str_mod})")

    # Cast Jump on ally
    spell = JumpSpell(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, cast_at_level=1)
    result = spell.apply()
    assert result is not None and not result.canceled
    print(f"  Cast Jump on ally: {result.status_message}")

    assert "Jump" in ally.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert "Jump" not in caster.active_conditions  # effect on ally, not caster
    assert ally.jump_distance_multiplier.normalized_score == 3

    r = ally_jump.get_range()
    assert r is not None and r.normal == ally_base_range * 3
    print(f"  Ally range tripled: {r.normal}ft ✓")

    # Caster concentration break → ally loses effect
    caster.remove_condition("Concentrating")
    assert "Jump" not in ally.active_conditions
    assert ally.jump_distance_multiplier.normalized_score == 1
    r = ally_jump.get_range()
    assert r is not None and r.normal == ally_base_range
    print(f"  Concentration broken → ally reverted: {r.normal}ft ✓")

    print("  PASSED")


def test_available_actions_expanded_targets():
    """Test that get_available_actions shows more jump targets after Jump spell."""
    print("\n=== Test 7: get_available_actions expanded jump targets ===")
    reset_combat_state()
    create_arena(size=30)

    entity = create_sorcerer(level=5, name="Jumper", position=(15, 15))
    register_spell(entity, JumpSpell, caster_level=5)

    enemy = create_goblin(name="Enemy", position=(25, 25))

    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Get available actions BEFORE Jump spell
    actions_before = get_available_actions(entity)
    jump_before = None
    for a in actions_before.position_actions:
        if a.template_name == "Jump":
            jump_before = a
            break
    assert jump_before is not None, "Jump action should be in position_actions"
    targets_before = len(jump_before.valid_targets)
    print(f"  Jump targets before spell: {targets_before}")

    # Cast Jump on self
    spell = JumpSpell(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid, cast_at_level=1)
    result = spell.apply()
    assert result is not None and not result.canceled

    # Update senses after spell (concentration changes may affect things)
    entity.update_entity_senses()

    # Get available actions AFTER Jump spell
    actions_after = get_available_actions(entity)
    jump_after = None
    for a in actions_after.position_actions:
        if a.template_name == "Jump":
            jump_after = a
            break
    assert jump_after is not None, "Jump action should still be in position_actions"
    targets_after = len(jump_after.valid_targets)
    print(f"  Jump targets after spell: {targets_after}")

    assert targets_after > targets_before, \
        f"Should have more jump targets after spell ({targets_after} > {targets_before})"
    print(f"  Expanded targets: {targets_before} → {targets_after} ✓")

    # Check that the farthest targets are within tripled range
    jump_template = entity.get_action_template("Jump")
    assert isinstance(jump_template, Jump)
    max_range = jump_template.get_range()
    assert max_range is not None
    print(f"  Max jump range: {max_range.normal}ft (3x)")

    max_dist = 0
    for target in jump_after.valid_targets:
        assert target.position is not None
        dist = entity.senses.get_feet_distance(target.position)
        if dist > max_dist:
            max_dist = dist
    print(f"  Farthest valid target: {max_dist}ft")
    assert max_dist <= max_range.normal, f"Farthest target {max_dist}ft exceeds range {max_range.normal}ft"
    assert max_dist > 15, f"Should have targets beyond base 15ft range, farthest is {max_dist}ft"
    print(f"  Targets within range and beyond base ✓")

    print("  PASSED")


if __name__ == "__main__":
    test_base_formula()
    test_additive_modifier()
    test_multiplicative_modifier()
    test_additive_and_multiplicative_combined()
    test_jump_spell_lifecycle()
    test_jump_spell_on_ally()
    test_available_actions_expanded_targets()
    print("\n=== ALL JUMP DISTANCE TESTS PASSED ===")
