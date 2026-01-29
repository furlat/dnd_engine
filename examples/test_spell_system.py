"""
Test the generic spell system implementation (Phase 1, 2, and 2b).

Tests:
1. Spell slot ModifiableValues in ActionEconomy
2. SpellcastingBlock extra damage fields
3. Entity spell helper methods
4. Modifier stacking (general + spell-specific)
"""

from uuid import uuid4

# Reset state first
from dnd.utils import reset_combat_state, get_hp, set_hp
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig, SpellcastingBlock
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier, DamageType


def test_spell_slots_in_action_economy():
    """Test that spell slots exist as ModifiableValues in ActionEconomy."""
    print("\n=== Test 1: Spell Slots in ActionEconomy ===")

    # Create entity with spell slots (use spell_slots dict, not individual fields)
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=16),  # +3 modifier
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2},  # 4 L1, 3 L2, 2 L3 slots
        ),
        proficiency_bonus=2,
    )

    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Test Caster",
        config=config
    )

    # Check spell slots exist and have correct values
    assert hasattr(caster.action_economy, 'spell_slot_1'), "spell_slot_1 should exist"
    assert hasattr(caster.action_economy, 'spell_slot_2'), "spell_slot_2 should exist"
    assert hasattr(caster.action_economy, 'spell_slot_3'), "spell_slot_3 should exist"

    assert caster.action_economy.spell_slot_1.normalized_score == 4, f"Expected 4 L1 slots, got {caster.action_economy.spell_slot_1.normalized_score}"
    assert caster.action_economy.spell_slot_2.normalized_score == 3, f"Expected 3 L2 slots, got {caster.action_economy.spell_slot_2.normalized_score}"
    assert caster.action_economy.spell_slot_3.normalized_score == 2, f"Expected 2 L3 slots, got {caster.action_economy.spell_slot_3.normalized_score}"

    # Check has_spell_slot helper
    assert caster.has_spell_slot(1) == True, "Should have L1 slots"
    assert caster.has_spell_slot(2) == True, "Should have L2 slots"
    assert caster.has_spell_slot(3) == True, "Should have L3 slots"
    assert caster.has_spell_slot(4) == False, "Should NOT have L4 slots"

    # Check get_lowest_spell_slot
    assert caster.get_lowest_spell_slot(1) == 1, "Lowest slot from L1 should be 1"
    assert caster.get_lowest_spell_slot(3) == 3, "Lowest slot from L3 should be 3"
    assert caster.get_lowest_spell_slot(4) is None, "No slots at L4+"

    # Test spell slot consumption
    caster.action_economy.consume("spell_slot_1", 1)
    assert caster.action_economy.spell_slot_1.normalized_score == 3, "Should have 3 L1 slots after consuming 1"
    assert caster.has_spell_slot(1) == True, "Should still have L1 slots"

    # Consume more
    caster.action_economy.consume("spell_slot_1", 3)
    assert caster.action_economy.spell_slot_1.normalized_score == 0, "Should have 0 L1 slots"
    assert caster.has_spell_slot(1) == False, "Should NOT have L1 slots anymore"

    # Test reset_spell_slot_costs (long rest)
    caster.action_economy.reset_spell_slot_costs()
    assert caster.action_economy.spell_slot_1.normalized_score == 4, "Slots should be restored after long rest"
    assert caster.has_spell_slot(1) == True, "Should have L1 slots after long rest"

    print("✓ Spell slots work correctly in ActionEconomy")


def test_spellcasting_block_fields():
    """Test SpellcastingBlock has all required fields."""
    print("\n=== Test 2: SpellcastingBlock Fields ===")

    # Create with config
    config = SpellcastingConfig(
        spellcasting_ability="intelligence",
        spell_attack_modifiers=[("Wand of War Mage", 2)],
        spell_damage_modifiers=[("Elemental Affinity", 3)],
        spell_dc_modifiers=[("Robe of Archmagi", 2)],
        spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
        spell_crit_extra_dice_modifiers=[("Arcane Amplifier", 1)],
        extra_spell_damage_dices=[6],
        extra_spell_damage_dices_numbers=[1],
        extra_spell_damage_bonus_modifiers=[[("Holy", 2)]],
        extra_spell_damage_types=["Radiant"],  # Must match DamageType enum values
    )

    block = SpellcastingBlock.create(source_entity_uuid=uuid4(), config=config)

    # Check ability
    assert block.spellcasting_ability == "intelligence", "Should use INT"

    # Check modifiers
    assert block.spell_attack_bonus.normalized_score == 2, f"Expected +2 spell attack, got {block.spell_attack_bonus.normalized_score}"
    assert block.spell_damage_bonus.normalized_score == 3, f"Expected +3 spell damage, got {block.spell_damage_bonus.normalized_score}"
    assert block.spell_dc_bonus.normalized_score == 2, f"Expected +2 DC, got {block.spell_dc_bonus.normalized_score}"
    assert block.spell_crit_threshold.normalized_score == 1, f"Expected +1 crit threshold, got {block.spell_crit_threshold.normalized_score}"
    assert block.spell_crit_extra_dice.normalized_score == 1, f"Expected +1 crit extra dice, got {block.spell_crit_extra_dice.normalized_score}"

    # Check extra damage fields
    assert len(block.extra_spell_damage_dices) == 1, "Should have 1 extra damage"
    assert block.extra_spell_damage_dices[0] == 6, "Should be d6"
    assert block.extra_spell_damage_dices_numbers[0] == 1, "Should be 1d6"
    assert block.extra_spell_damage_type[0] == DamageType.RADIANT, "Should be radiant"
    assert block.extra_spell_damage_bonus[0].normalized_score == 2, "Should have +2 bonus"

    # Test get_extra_spell_damage()
    damages = block.get_extra_spell_damage()
    assert len(damages) == 1, "Should return 1 Damage object"
    assert damages[0].damage_dice == 6, "Damage should use d6"
    assert damages[0].damage_type == DamageType.RADIANT, "Damage should be radiant"

    print("✓ SpellcastingBlock has all required fields")


def test_entity_spell_methods():
    """Test Entity spell helper methods."""
    print("\n=== Test 3: Entity Spell Methods ===")

    # Create a Sorcerer-like entity (CHA caster, L5)
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=16),  # +3 modifier
            intelligence=AbilityConfig(ability_score=10),
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2},  # 4 L1, 3 L2, 2 L3 slots
        ),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(
            spellcasting_ability="charisma",
            spell_dc_modifiers=[("Focus", 1)],
        ),
    )

    sorcerer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Test Sorcerer",
        config=config
    )

    # Test spell_save_dc: 8 + prof(3) + CHA(3) + bonus(1) = 15
    dc = sorcerer.spell_save_dc()
    assert dc == 15, f"Expected DC 15, got {dc}"

    # Test spell_attack_bonus: prof(3) + CHA(3) = 6
    attack = sorcerer.spell_attack_bonus()
    assert attack.normalized_score == 6, f"Expected +6 spell attack, got {attack.normalized_score}"

    # Test spell crit threshold (no bonuses, should be 20)
    crit_thresh = sorcerer.get_spell_crit_threshold()
    assert crit_thresh == 20, f"Expected crit on 20, got {crit_thresh}"

    # Test is_spellcaster
    assert sorcerer.is_spellcaster == True, "Sorcerer should be a spellcaster"

    print("✓ Entity spell methods work correctly")


def test_modifier_stacking():
    """Test that general and spell-specific modifiers stack correctly."""
    print("\n=== Test 4: Modifier Stacking ===")

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=14),  # +2 modifier
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),  # 2 L1 slots
        proficiency_bonus=2,
        spellcasting=SpellcastingConfig(
            spellcasting_ability="charisma",
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],  # +1 to spell crit
        ),
    )

    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Test Caster",
        config=config
    )

    # Add general crit threshold (like Improved Critical on Equipment)
    caster.equipment.crit_threshold.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="Improved Critical",
            value=1  # Crit on 19-20 for all attacks
        )
    )

    # Weapon crit threshold: 20 - 1 (equipment) = 19
    weapon_crit = caster.get_crit_threshold()
    assert weapon_crit == 19, f"Weapon crit should be 19, got {weapon_crit}"

    # Spell crit threshold: 20 - (1 equipment + 1 spell) = 18
    spell_crit = caster.get_spell_crit_threshold()
    assert spell_crit == 18, f"Spell crit should be 18, got {spell_crit}"

    print("✓ General and spell-specific modifiers stack correctly")


def test_non_caster_defaults():
    """Test that non-casters have harmless SpellcastingBlock defaults."""
    print("\n=== Test 5: Non-Caster Defaults ===")

    # Create entity without spellcasting config
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
        ),
        proficiency_bonus=2,
        # No spellcasting config = non-caster
    )

    fighter = Entity.create(
        source_entity_uuid=uuid4(),
        name="Test Fighter",
        config=config
    )

    # Spellcasting block should exist with harmless defaults
    assert fighter.spellcasting is not None, "SpellcastingBlock should always exist"
    assert fighter.spellcasting.spellcasting_ability == "charisma", "Default ability should be charisma"
    assert fighter.spellcasting.spell_attack_bonus.normalized_score == 0, "No spell attack bonus"
    assert fighter.spellcasting.spell_dc_bonus.normalized_score == 0, "No DC bonus"

    # No spell slots
    assert fighter.has_spell_slot(1) == False, "Fighter should have no spell slots"
    assert fighter.is_spellcaster == False, "Fighter should not be a spellcaster"

    # Methods should still work (with charisma by default)
    dc = fighter.spell_save_dc()  # 8 + 2 + 0 (default CHA) + 0 = 10
    assert dc == 10, f"Non-caster DC should be 10, got {dc}"

    print("✓ Non-caster defaults are harmless")


def test_fire_bolt_cantrip_scaling():
    """Test Fire Bolt damage scales with caster level."""
    print("\n=== Test 6: Fire Bolt Cantrip Scaling ===")

    from dnd.spells import FireBolt

    # Create spell template
    spell = FireBolt(
        source_entity_uuid=uuid4(),
        template=True
    )

    # Test cantrip scaling
    assert spell._get_cantrip_dice_count(1) == 1, "L1 caster should deal 1d10"
    assert spell._get_cantrip_dice_count(4) == 1, "L4 caster should deal 1d10"
    assert spell._get_cantrip_dice_count(5) == 2, "L5 caster should deal 2d10"
    assert spell._get_cantrip_dice_count(10) == 2, "L10 caster should deal 2d10"
    assert spell._get_cantrip_dice_count(11) == 3, "L11 caster should deal 3d10"
    assert spell._get_cantrip_dice_count(16) == 3, "L16 caster should deal 3d10"
    assert spell._get_cantrip_dice_count(17) == 4, "L17 caster should deal 4d10"
    assert spell._get_cantrip_dice_count(20) == 4, "L20 caster should deal 4d10"

    print("✓ Fire Bolt scales correctly with caster level")


def test_magic_missile_dart_count():
    """Test Magic Missile creates correct number of darts."""
    print("\n=== Test 7: Magic Missile Dart Count ===")

    from dnd.spells import MagicMissile

    # Base L1 spell: 3 darts
    spell_l1 = MagicMissile(
        source_entity_uuid=uuid4(),
        spell_level=1,
        cast_at_level=1,
        template=False
    )
    assert spell_l1.get_upcast_bonus() == 0, "L1 at L1 = 0 upcast bonus"
    # Note: 3 + 0 = 3 darts

    # Upcast to L2: 4 darts
    spell_l2 = MagicMissile(
        source_entity_uuid=uuid4(),
        spell_level=1,
        cast_at_level=2,
        template=False
    )
    assert spell_l2.get_upcast_bonus() == 1, "L1 at L2 = 1 upcast bonus"
    # Note: 3 + 1 = 4 darts

    # Upcast to L5: 7 darts
    spell_l5 = MagicMissile(
        source_entity_uuid=uuid4(),
        spell_level=1,
        cast_at_level=5,
        template=False
    )
    assert spell_l5.get_upcast_bonus() == 4, "L1 at L5 = 4 upcast bonus"
    # Note: 3 + 4 = 7 darts

    print("✓ Magic Missile dart count scales with upcast level")


def test_cantrip_variant_generation():
    """Test cantrip generates exactly one variant with no slot cost."""
    print("\n=== Test 8: Cantrip Variant Generation ===")

    from dnd.spells import FireBolt

    # Create caster
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),
        proficiency_bonus=2,
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Wizard", config=config)

    # Create Fire Bolt template
    fire_bolt = FireBolt(
        source_entity_uuid=caster.uuid,
        template=True
    )

    # Generate variants
    variants = fire_bolt.generate_variants(caster)

    assert len(variants) == 1, f"Cantrip should generate exactly 1 variant, got {len(variants)}"
    assert variants[0].cast_at_level == 0, f"Cantrip cast_at_level should be 0, got {variants[0].cast_at_level}"
    assert variants[0].is_variant == True, "Should be marked as variant"
    assert variants[0].template == False, "Variant should not be a template"

    # Check costs - should be 1 action, no spell slot
    assert len(variants[0].costs) == 1, f"Cantrip should have 1 cost, got {len(variants[0].costs)}"
    assert variants[0].costs[0].cost_type == "actions", "Cost should be actions"
    assert variants[0].costs[0].cost == 1, "Should cost 1 action"

    print("✓ Cantrip variant generation works correctly")


def test_leveled_spell_variant_generation():
    """Test leveled spell generates variants for each available slot."""
    print("\n=== Test 9: Leveled Spell Variant Generation ===")

    from dnd.spells import MagicMissile

    # Create caster with L1, L2, L3 slots
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2, 2: 2, 3: 1}),
        proficiency_bonus=2,
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Wizard", config=config)

    # Create Magic Missile template
    mm = MagicMissile(
        source_entity_uuid=caster.uuid,
        template=True
    )

    # Generate variants
    variants = mm.generate_variants(caster)

    assert len(variants) == 3, f"Should generate 3 variants (L1, L2, L3), got {len(variants)}"

    # Check cast levels
    cast_levels = [v.cast_at_level for v in variants]
    assert cast_levels == [1, 2, 3], f"Cast levels should be [1, 2, 3], got {cast_levels}"

    # Check L2 variant costs
    l2_variant = [v for v in variants if v.cast_at_level == 2][0]
    assert len(l2_variant.costs) == 2, f"L2 variant should have 2 costs, got {len(l2_variant.costs)}"
    cost_types = [c.cost_type for c in l2_variant.costs]
    assert "actions" in cost_types, "Should include action cost"
    assert "spell_slot_2" in cost_types, f"Should include spell_slot_2 cost, got {cost_types}"

    print("✓ Leveled spell variant generation works correctly")


def test_include_self_targeting():
    """Test that include_self=True allows self-targeting in get_available_actions()."""
    print("\n=== Test 10: include_self Targeting ===")

    from dnd.spells import MageArmor

    # Reset state
    reset_combat_state()

    # Create caster with Mage Armor template
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),
        proficiency_bonus=2,
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Sorcerer", config=config)

    # Create an ally to also be a valid target
    ally_config = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=16)),
        proficiency_bonus=2,
        position=(1, 0),  # Adjacent
    )
    _ally = Entity.create(
        source_entity_uuid=uuid4(),
        name="Ally Fighter",
        config=ally_config,
    )

    # Update senses
    Entity.update_all_entities_senses()

    # Register Mage Armor template on caster
    mage_armor = MageArmor(
        source_entity_uuid=caster.uuid,
        template=True
    )
    caster.register_action(mage_armor)

    # Verify include_self is True
    assert mage_armor.include_self == True, "MageArmor should have include_self=True"

    # Get available actions (allies filter includes self when include_self=True)
    actions = caster.get_available_actions(target_filter="allies")

    # Find Mage Armor in results
    mage_armor_info = None
    for action in actions.entity_actions:
        if action.template_name == "Mage Armor":
            mage_armor_info = action
            break

    assert mage_armor_info is not None, "Mage Armor should appear in available actions"

    # Check valid targets include self
    target_uuids = [t.target_uuid for t in mage_armor_info.valid_targets]
    assert caster.uuid in target_uuids, f"Self (caster) should be in valid targets, got {target_uuids}"

    print("✓ include_self targeting works correctly")


def test_mage_armor_self_cast():
    """Test casting Mage Armor on self."""
    print("\n=== Test 11: Mage Armor Self-Cast ===")

    from dnd.spells import MageArmor

    # Reset state
    reset_combat_state()

    # Create unarmored caster with DEX 14 (+2)
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),  # +2 DEX
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),
        proficiency_bonus=2,
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Unarmored Mage", config=config)
    Entity.update_all_entities_senses()

    # Check initial AC (unarmored: 10 + DEX = 12)
    initial_ac = caster.ac_bonus().normalized_score
    assert initial_ac == 12, f"Initial AC should be 12 (10 + 2 DEX), got {initial_ac}"

    # Create Mage Armor targeting self
    caster_uuid = caster.uuid
    mage_armor = MageArmor(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=caster_uuid,
        cast_at_level=1,
        template=False,
        costs=MageArmor(source_entity_uuid=caster_uuid)._get_costs_for_level(1)
    )

    # Cast spell
    result = mage_armor.apply()
    assert result is not None, "Mage Armor should apply successfully"
    assert not result.canceled, f"Mage Armor should not be canceled: {result.status_message}"

    # Check condition applied
    assert "Mage Armor" in caster.active_conditions, f"Mage Armor condition should be active, got {list(caster.active_conditions.keys())}"

    # Check new AC (Mage Armor: 13 + DEX = 15)
    new_ac = caster.ac_bonus().normalized_score
    assert new_ac == 15, f"AC with Mage Armor should be 15 (13 + 2 DEX), got {new_ac}"

    print("✓ Mage Armor self-cast works correctly")


def test_mage_armor_ends_on_armor_equip():
    """Test that Mage Armor ends when armor is equipped."""
    print("\n=== Test 12: Mage Armor Ends on Armor Equip ===")

    from dnd.spells import MageArmor
    from dnd.items.armors import create_leather_armor

    # Reset state
    reset_combat_state()

    # Create unarmored caster
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),  # +2 DEX
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 2}),
        proficiency_bonus=2,
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Mage", config=config)
    Entity.update_all_entities_senses()

    # Cast Mage Armor on self
    caster_uuid = caster.uuid
    mage_armor = MageArmor(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=caster_uuid,
        cast_at_level=1,
        template=False,
        costs=MageArmor(source_entity_uuid=caster_uuid)._get_costs_for_level(1)
    )
    mage_armor.apply()

    # Verify condition is active
    assert "Mage Armor" in caster.active_conditions, "Mage Armor should be active"

    # Equip leather armor
    leather = create_leather_armor(caster.uuid)
    caster.equipment.equip(leather)

    # Condition should be removed
    assert "Mage Armor" not in caster.active_conditions, f"Mage Armor should be removed after equipping armor, got {list(caster.active_conditions.keys())}"

    # AC should now be leather armor (11 + DEX = 13)
    new_ac = caster.ac_bonus().normalized_score
    assert new_ac == 13, f"AC with leather should be 13 (11 + 2 DEX), got {new_ac}"

    print("✓ Mage Armor correctly ends when armor is equipped")


def test_fire_bolt_combat():
    """Test Fire Bolt in actual combat - spell attack vs AC."""
    print("\n=== Test 13: Fire Bolt Combat (Spell Attack vs AC) ===")

    from dnd.spells import FireBolt

    reset_combat_state()

    # Create caster with high INT for reliable hits
    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=18),  # +4
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Wizard", config=caster_config)

    # Create target with moderate AC (adjacent for LOS)
    target_config = EntityConfig(
        ability_scores=AbilityScoresConfig(dexterity=AbilityConfig(ability_score=10)),
        proficiency_bonus=2,
        position=(1, 0),
    )
    target = Entity.create(source_entity_uuid=uuid4(), name="Target", config=target_config)

    Entity.update_all_entities_senses()

    # Verify spell attack bonus: prof(3) + INT(4) = +7
    spell_attack = caster.spell_attack_bonus().normalized_score
    assert spell_attack == 7, f"Spell attack should be +7, got +{spell_attack}"

    # Cast Fire Bolt at caster level 5 (2d10)
    set_hp(target, 100)
    fire_bolt = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False
    )
    result = fire_bolt.apply()

    assert result is not None, "Fire Bolt should return an event"
    assert not result.canceled, f"Fire Bolt should not be canceled: {result.status_message}"

    # Check that attack outcome is recorded
    from dnd.core.dice import AttackOutcome
    assert result.attack_outcome is not None, "Attack outcome should be recorded"
    print(f"  Attack outcome: {result.attack_outcome.value}")

    # If hit, damage should be dealt
    if result.attack_outcome in [AttackOutcome.HIT, AttackOutcome.CRIT]:
        assert result.damage_rolls is not None, "Damage rolls should be recorded"
        total_damage = sum(r.total for r in result.damage_rolls)
        print(f"  Damage dealt: {total_damage} fire")
    else:
        print("  Attack missed (RNG)")

    print("✓ Fire Bolt combat mechanics work")


def test_sacred_flame_combat():
    """Test Sacred Flame in actual combat - spell DC vs DEX save."""
    print("\n=== Test 14: Sacred Flame Combat (Spell DC vs Save) ===")

    from dnd.spells import SacredFlame

    reset_combat_state()

    # Create caster with high WIS
    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=18),  # +4
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Cleric", config=caster_config)

    # Create target with low DEX for reliable failures (adjacent for LOS)
    target_config = EntityConfig(
        ability_scores=AbilityScoresConfig(dexterity=AbilityConfig(ability_score=6)),  # -2
        proficiency_bonus=2,
        position=(1, 0),
    )
    target = Entity.create(source_entity_uuid=uuid4(), name="Target", config=target_config)

    Entity.update_all_entities_senses()

    # Verify spell DC: 8 + prof(3) + WIS(4) = 15
    dc = caster.spell_save_dc()
    assert dc == 15, f"Spell DC should be 15, got {dc}"
    print(f"  Spell DC: {dc}")
    dex_save_bonus = target.saving_throw_bonus(None, "dexterity").normalized_score
    print(f"  Target DEX save: {dex_save_bonus}")

    # Cast Sacred Flame at caster level 5 (2d8)
    set_hp(target, 100)
    sacred_flame = SacredFlame(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False
    )
    result = sacred_flame.apply()

    assert result is not None, "Sacred Flame should return an event"
    assert not result.canceled, f"Sacred Flame should not be canceled: {result.status_message}"

    # Check save result is recorded
    assert result.save_dc == dc, "Save DC should be recorded in event"
    assert result.save_success is not None, "Save success should be recorded"

    if result.save_success:
        assert result.damage_rolls is None, "Successful save means no damage rolls"
        print("  Target saved (no damage)")
    else:
        assert result.damage_rolls is not None, "Damage rolls should be recorded"
        total_damage = sum(r.total for r in result.damage_rolls)
        assert total_damage > 0, "Failed save should deal damage"
        print(f"  Target failed save, took {total_damage} radiant damage")

    print("✓ Sacred Flame save mechanics work")


def test_magic_missile_combat():
    """Test Magic Missile - auto-hit and upcast scaling."""
    print("\n=== Test 15: Magic Missile Combat (Auto-hit + Upcast) ===")

    from dnd.spells import MagicMissile
    from dnd.core.gridmap import get_map

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 15, 15)  # Create floor tiles for LOS

    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=16)),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3, 3: 2}),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        position=(0, 0),
        faction="heroes",  # Set faction for target filtering
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Wizard", config=caster_config)

    target_config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        proficiency_bonus=2,
        position=(1, 0),
        faction="enemies",  # Target must be enemy
    )
    target = Entity.create(source_entity_uuid=uuid4(), name="Target", config=target_config)

    Entity.update_all_entities_senses()

    # Cast at L1 (3 darts, 3d4+3 = 6-15 damage)
    mm_l1 = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        spell_level=1,
        cast_at_level=1,
        template=False,
        costs=MagicMissile(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    result_l1 = mm_l1.apply()

    assert result_l1 is not None, "Should get result event"
    assert not result_l1.canceled, "Magic Missile should not be canceled"
    # MULTI_ENTITY returns target_results list and total_damage
    assert result_l1.total_targets == 3, f"Should have 3 dart results, got {result_l1.total_targets}"
    damage_l1 = result_l1.total_damage
    assert damage_l1 >= 6, f"L1 MM (3 darts) should deal at least 6 damage, got {damage_l1}"
    assert damage_l1 <= 15, f"L1 MM (3 darts) should deal at most 15 damage, got {damage_l1}"
    print(f"  L1 (3 darts): {damage_l1} force damage")

    # Reset action economy for second cast
    caster.action_economy.reset_all_costs()

    # Cast at L3 (5 darts, 5d4+5 = 10-25 damage)
    mm_l3 = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        spell_level=1,
        cast_at_level=3,
        template=False,
        costs=MagicMissile(source_entity_uuid=caster.uuid)._get_costs_for_level(3)
    )
    result_l3 = mm_l3.apply()

    assert result_l3 is not None, "Should get result event"
    assert not result_l3.canceled, "Magic Missile should not be canceled"
    assert result_l3.total_targets == 5, f"Should have 5 dart results, got {result_l3.total_targets}"
    damage_l3 = result_l3.total_damage
    assert damage_l3 >= 10, f"L3 MM (5 darts) should deal at least 10 damage, got {damage_l3}"
    assert damage_l3 <= 25, f"L3 MM (5 darts) should deal at most 25 damage, got {damage_l3}"
    print(f"  L3 (5 darts): {damage_l3} force damage")

    print("✓ Magic Missile auto-hit and upcast work")


def test_spell_slot_consumption():
    """Test that casting leveled spells consumes spell slots."""
    print("\n=== Test 16: Spell Slot Consumption ===")

    from dnd.spells import MagicMissile

    reset_combat_state()

    caster_config = EntityConfig(
        ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=16)),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3}),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        position=(0, 0),
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name="Wizard", config=caster_config)

    target_config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        position=(1, 0),
    )
    target = Entity.create(source_entity_uuid=uuid4(), name="Target", config=target_config)

    Entity.update_all_entities_senses()

    # Check initial slots
    initial_l1 = caster.action_economy.spell_slot_1.normalized_score
    initial_l2 = caster.action_economy.spell_slot_2.normalized_score
    assert initial_l1 == 4, f"Should start with 4 L1 slots, got {initial_l1}"
    assert initial_l2 == 3, f"Should start with 3 L2 slots, got {initial_l2}"
    print(f"  Initial slots: L1={initial_l1}, L2={initial_l2}")

    # Cast Magic Missile at L1
    mm_l1 = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        spell_level=1,
        cast_at_level=1,
        template=False,
        costs=MagicMissile(source_entity_uuid=caster.uuid)._get_costs_for_level(1)
    )
    mm_l1.apply()

    after_l1_cast = caster.action_economy.spell_slot_1.normalized_score
    assert after_l1_cast == 3, f"Should have 3 L1 slots after casting, got {after_l1_cast}"
    print(f"  After L1 cast: L1={after_l1_cast}")

    # Reset actions (but NOT spell slots) for second cast
    caster.action_economy.reset_all_costs()

    # Cast Magic Missile at L2 (upcast)
    mm_l2 = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        spell_level=1,
        cast_at_level=2,
        template=False,
        costs=MagicMissile(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    mm_l2.apply()

    after_l2_cast = caster.action_economy.spell_slot_2.normalized_score
    assert after_l2_cast == 2, f"Should have 2 L2 slots after casting, got {after_l2_cast}"
    print(f"  After L2 cast: L2={after_l2_cast}")

    # Long rest restores slots
    caster.action_economy.reset_spell_slot_costs()
    restored_l1 = caster.action_economy.spell_slot_1.normalized_score
    restored_l2 = caster.action_economy.spell_slot_2.normalized_score
    assert restored_l1 == 4, f"L1 slots should be restored to 4, got {restored_l1}"
    assert restored_l2 == 3, f"L2 slots should be restored to 3, got {restored_l2}"
    print(f"  After long rest: L1={restored_l1}, L2={restored_l2}")

    print("✓ Spell slot consumption and restoration work")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("GENERIC SPELL SYSTEM TESTS (Phase 1, 2, 2b, 3)")
    print("=" * 60)

    # Phase 1, 2, 2b tests
    test_spell_slots_in_action_economy()
    test_spellcasting_block_fields()
    test_entity_spell_methods()
    test_modifier_stacking()
    test_non_caster_defaults()

    # Phase 3 tests - unit tests
    test_fire_bolt_cantrip_scaling()
    test_magic_missile_dart_count()
    test_cantrip_variant_generation()
    test_leveled_spell_variant_generation()
    test_include_self_targeting()
    test_mage_armor_self_cast()
    test_mage_armor_ends_on_armor_equip()

    # Phase 3 tests - combat integration
    test_fire_bolt_combat()
    test_sacred_flame_combat()
    test_magic_missile_combat()
    test_spell_slot_consumption()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
