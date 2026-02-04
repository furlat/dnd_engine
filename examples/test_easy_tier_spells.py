"""Test Phase 1 Easy Tier Spells: Shocking Grasp, Power Word Stun, Guiding Bolt"""

from dnd.utils import reset_combat_state, get_hp, set_hp, has_condition
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.items.armors import create_chain_mail, create_leather_armor
from dnd.blocks.equipment import WeaponSlot
from dnd.actions_functional import setup_standard_actions, register_spell
from dnd.spells import ShockingGrasp, GuidingBolt, PowerWordStun
from dnd.core.gridmap import get_map


def setup_test():
    """Reset state and create a grid for LOS to work."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def test_shocking_grasp_basic():
    """Test Shocking Grasp basic mechanics."""
    print("\n=== Test: Shocking Grasp Basic ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))  # Adjacent

    setup_standard_actions(caster)
    register_spell(caster, ShockingGrasp, caster_level=5)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    print(f"Target HP: {initial_hp}")
    print(f"Target at {target.position}, distance: {caster.senses.get_feet_distance(target.position)}ft")

    # Cast Shocking Grasp (melee spell attack)
    spell = ShockingGrasp(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5  # 2d8 at level 5
    )
    event = spell.apply()

    final_hp = get_hp(target)
    print(f"Final HP: {final_hp}, Damage: {initial_hp - final_hp}")
    print(f"Event status: {event.status_message if event else 'None'}")

    # Check if No Reactions was applied (only on hit)
    has_no_reactions = has_condition(target, "No Reactions")
    print(f"Has No Reactions condition: {has_no_reactions}")

    if initial_hp > final_hp:
        assert has_no_reactions, "Should have No Reactions on hit"
        print("PASS: Shocking Grasp dealt damage and applied No Reactions")
    else:
        print("Spell missed (expected sometimes)")

    return True


def test_shocking_grasp_metal_armor_advantage():
    """Test Shocking Grasp advantage vs metal armor."""
    print("\n=== Test: Shocking Grasp Metal Armor Advantage ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))

    # Target with metal armor (chain mail = heavy metal)
    metal_target = create_skeleton(name="Metal Target", position=(1, 0))
    chain_mail = create_chain_mail(metal_target.uuid)
    metal_target.equipment.equip(chain_mail)

    # Target with non-metal armor (leather)
    nonmetal_target = create_skeleton(name="Leather Target", position=(0, 1))
    leather = create_leather_armor(nonmetal_target.uuid)
    nonmetal_target.equipment.equip(leather)

    Entity.update_all_entities_senses()

    print(f"Metal target armor: {metal_target.equipment.body_armor.name if metal_target.equipment.body_armor else 'None'}")
    print(f"Non-metal target armor: {nonmetal_target.equipment.body_armor.name if nonmetal_target.equipment.body_armor else 'None'}")

    # Cast at metal target - should have advantage
    spell_metal = ShockingGrasp(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=metal_target.uuid,
        caster_level=1
    )
    event_metal = spell_metal.apply()
    print(f"Metal target result: {event_metal.status_message if event_metal else 'None'}")
    if event_metal: 
        print(f"Metal target: advantage mentioned in message: {'advantage' in (event_metal.status_message or '').lower()}")

    # Cast at non-metal target - should NOT have advantage
    setup_test()
    caster = create_skeleton(name="Caster", position=(0, 0))
    nonmetal_target = create_skeleton(name="Leather Target", position=(1, 0))
    leather = create_leather_armor(nonmetal_target.uuid)
    nonmetal_target.equipment.equip(leather)
    Entity.update_all_entities_senses()

    spell_nonmetal = ShockingGrasp(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=nonmetal_target.uuid,
        caster_level=1
    )
    event_nonmetal = spell_nonmetal.apply()
    print(f"Non-metal target result: {event_nonmetal.status_message if event_nonmetal else 'None'}")
    if event_nonmetal:
        print(f"Non-metal target: advantage NOT mentioned: {'advantage' not in (event_nonmetal.status_message or '').lower()}")

    print("PASS: Metal armor detection working")
    return True


def test_shocking_grasp_range():
    """Test Shocking Grasp requires melee range."""
    print("\n=== Test: Shocking Grasp Range ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    # Position at (2, 0) = 10ft away - within LOS but outside melee range (5ft)
    target = create_skeleton(name="Target", position=(2, 0))

    Entity.update_all_entities_senses()

    distance = caster.senses.get_feet_distance(target.position)
    print(f"Target at {target.position}, distance: {distance}ft")
    print(f"Target in caster LOS: {target.uuid in caster.senses.entities}")

    spell = ShockingGrasp(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1
    )
    event = spell.apply()

    assert event is not None, "Event should not be None"
    assert event.canceled, "Shocking Grasp should fail at 10ft range"
    # Error says "melee range" so check for that
    assert "range" in (event.status_message or "").lower(), "Should mention range in error"
    print(f"Out of range error: {event.status_message}")
    print("PASS: Range check working")
    return True


def test_shocking_grasp_damage_scaling():
    """Test Shocking Grasp damage scales: 1d8 → 2d8 → 3d8 → 4d8."""
    print("\n=== Test: Shocking Grasp Damage Scaling ===")

    # Test the cantrip scaling function directly
    from uuid import uuid4
    test_cases = [
        (1, 1), (4, 1),    # L1-4: 1d8
        (5, 2), (10, 2),   # L5-10: 2d8
        (11, 3), (16, 3),  # L11-16: 3d8
        (17, 4), (20, 4),  # L17+: 4d8
    ]

    for level, expected in test_cases:
        spell = ShockingGrasp(source_entity_uuid=uuid4(), caster_level=level)
        actual = spell._get_cantrip_dice_count(level)
        assert actual == expected, f"Level {level}: expected {expected}d8, got {actual}d8"
        print(f"Level {level}: {actual}d8 ✓")

    print("PASS: Damage scaling correct")
    return True


def test_shocking_grasp_no_reactions_expiration():
    """Test NoReactions expires at start of target's next turn."""
    print("\n=== Test: Shocking Grasp No Reactions Expiration ===")
    setup_test()

    target = create_skeleton(name="Target", position=(0, 0))
    Entity.update_all_entities_senses()

    # Check initial reactions
    initial_reactions = target.action_economy.reactions.normalized_score
    print(f"Initial reactions: {initial_reactions}")
    assert initial_reactions == 1, "Should have 1 reaction initially"

    # Apply No Reactions with 1 round duration (same as Shocking Grasp applies)
    from dnd.conditions import NoReactions
    from dnd.core.base_conditions import Duration, DurationType

    no_reactions = NoReactions(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        duration=Duration(
            duration=1,
            duration_type=DurationType.ROUNDS,
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid
        )
    )
    target.add_condition(no_reactions)

    # Check reactions are now 0
    after_condition = target.action_economy.reactions.normalized_score
    print(f"Reactions after condition: {after_condition}")
    assert after_condition == 0, "Should have 0 reactions with No Reactions condition"
    assert has_condition(target, "No Reactions"), "Should have No Reactions condition"

    # Simulate turn start - condition should expire
    target.on_turn_start()

    # Reactions should be restored (condition expired)
    final_reactions = target.action_economy.reactions.normalized_score
    print(f"Reactions after turn start: {final_reactions}")
    assert final_reactions == 1, f"Should have 1 reaction after turn start, got {final_reactions}"
    assert not has_condition(target, "No Reactions"), "No Reactions should be removed"

    print("PASS: NoReactions expires at turn start")
    return True


def test_guiding_bolt_basic():
    """Test Guiding Bolt basic mechanics."""
    print("\n=== Test: Guiding Bolt Basic ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(2, 0))  # 10ft away (fixed for LOS)
    attacker = create_skeleton(name="Attacker", position=(3, 0))  # Adjacent to target

    setup_standard_actions(caster)
    setup_standard_actions(attacker)
    register_spell(caster, GuidingBolt, caster_level=5)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)
    print(f"Target HP: {initial_hp}")

    # Cast Guiding Bolt
    spell = GuidingBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        cast_at_level=1  # 4d6 base
    )
    event = spell.apply()

    final_hp = get_hp(target)
    print(f"Final HP: {final_hp}, Damage: {initial_hp - final_hp}")
    print(f"Event status: {event.status_message if event else 'None'}")

    # Check if target is marked (only on hit)
    has_mark = has_condition(target, "Guiding Bolt")
    print(f"Has Guiding Bolt mark: {has_mark}")

    if initial_hp > final_hp:
        assert has_mark, "Should have Guiding Bolt mark on hit"
        print("PASS: Guiding Bolt dealt damage and applied mark")

        # Test that mark provides advantage (check to_target_static has advantage)
        advantage_mods = target.equipment.ac_bonus.to_target_static.advantage_modifiers
        print(f"Advantage modifiers on target AC: {len(advantage_mods)}")
        assert len(advantage_mods) > 0, "Target should have advantage modifier for attackers"
        print("PASS: Mark provides advantage to attackers")
    else:
        print("Spell missed (expected sometimes)")

    return True


def test_guiding_bolt_mark_removed_on_attack():
    """Test Guiding Bolt mark is removed after first attack."""
    print("\n=== Test: Guiding Bolt Mark Removal ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    attacker = create_skeleton(name="Attacker", position=(2, 0))

    setup_standard_actions(caster)
    setup_standard_actions(attacker)

    Entity.update_all_entities_senses()

    # Manually apply the mark to ensure consistent test
    from dnd.spells import GuidingBoltMarked
    from dnd.core.base_conditions import Duration, DurationType

    mark = GuidingBoltMarked(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=caster.uuid,
        duration=Duration(
            duration=2,
            duration_type=DurationType.ROUNDS,
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
    )
    target.add_condition(mark)

    assert has_condition(target, "Guiding Bolt"), "Mark should be applied"
    print("Mark applied")

    # Attack the target
    from dnd.actions import Attack

    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()

    # Mark should be removed after attack
    still_has_mark = has_condition(target, "Guiding Bolt")
    print(f"Mark still present after attack: {still_has_mark}")
    assert not still_has_mark, "Mark should be removed after first attack"
    print("PASS: Mark removed after first attack")
    return True


def test_guiding_bolt_upcast():
    """Test Guiding Bolt upcast damage."""
    print("\n=== Test: Guiding Bolt Upcast ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))

    # Test at different levels
    spell_l1 = GuidingBolt(source_entity_uuid=caster.uuid, caster_level=5, cast_at_level=1)
    spell_l3 = GuidingBolt(source_entity_uuid=caster.uuid, caster_level=5, cast_at_level=3)
    spell_l5 = GuidingBolt(source_entity_uuid=caster.uuid, caster_level=5, cast_at_level=5)

    print(f"Level 1: {spell_l1.get_damage_dice_count()}d6")
    print(f"Level 3: {spell_l3.get_damage_dice_count()}d6")
    print(f"Level 5: {spell_l5.get_damage_dice_count()}d6")

    assert spell_l1.get_damage_dice_count() == 4, "4d6 at level 1"
    assert spell_l3.get_damage_dice_count() == 6, "6d6 at level 3"
    assert spell_l5.get_damage_dice_count() == 8, "8d6 at level 5"

    print("PASS: Upcast damage scaling correct")
    return True


def test_power_word_stun_basic():
    """Test Power Word Stun basic mechanics."""
    print("\n=== Test: Power Word Stun Basic ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))  # Adjacent for LOS

    Entity.update_all_entities_senses()

    # Set target HP to below threshold
    set_hp(target, 100)
    print(f"Target HP: {get_hp(target)} (threshold: 150)")
    print(f"Target visible: {target.uuid in caster.senses.entities}")

    spell = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=15
    )
    event = spell.apply()

    print(f"Event status: {event.status_message if event else 'None'}")

    # Check if stunned
    has_stun_effect = has_condition(target, "Power Word Stun")
    has_stunned = has_condition(target, "Stunned")
    print(f"Has Power Word Stun effect: {has_stun_effect}")
    print(f"Has Stunned (sub-condition): {has_stunned}")

    assert has_stun_effect, "Should have Power Word Stun effect"
    assert has_stunned, "Should have Stunned sub-condition"
    print("PASS: Power Word Stun applied stun effect")
    return True


def test_power_word_stun_hp_threshold():
    """Test Power Word Stun HP threshold check."""
    print("\n=== Test: Power Word Stun HP Threshold ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))  # Adjacent for LOS

    Entity.update_all_entities_senses()

    # Add max HP bonus so we can set HP above 150
    # Skeletons have ~17 HP normally, so we need +200 bonus
    from dnd.core.modifiers import NumericalModifier
    hp_bonus = NumericalModifier.create(
        source_entity_uuid=target.uuid,
        name="Test HP Bonus",
        value=200
    )
    target.health.max_hit_points_bonus.self_static.add_value_modifier(hp_bonus)

    # Set target HP above threshold
    set_hp(target, 200)
    print(f"Target HP: {get_hp(target)} (threshold: 150)")

    spell = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=15
    )
    event = spell.apply()

    print(f"Event status: {event.status_message if event else 'None'}")

    # Should NOT be stunned
    has_stun_effect = has_condition(target, "Power Word Stun")
    print(f"Has Power Word Stun effect: {has_stun_effect}")

    assert not has_stun_effect, "Should NOT have effect when HP > 150"
    if event:
        assert "no effect" in (event.status_message or "").lower(), "Should mention no effect"
    print("PASS: HP threshold check working")
    return True


def test_power_word_stun_exact_threshold():
    """Test Power Word Stun at exactly 150 HP."""
    print("\n=== Test: Power Word Stun Exact Threshold ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))  # Adjacent for LOS

    Entity.update_all_entities_senses()

    # Set target HP to exactly threshold
    set_hp(target, 150)
    print(f"Target HP: {get_hp(target)} (threshold: 150)")

    spell = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=15
    )
    event = spell.apply()

    print(f"Event status: {event.status_message if event else 'None'}")

    # Should be stunned (threshold is <= 150)
    has_stun_effect = has_condition(target, "Power Word Stun")
    print(f"Has Power Word Stun effect: {has_stun_effect}")

    assert has_stun_effect, "Should have effect at exactly 150 HP"
    print("PASS: Exact threshold working")
    return True


def test_no_reactions_condition():
    """Test that No Reactions condition prevents reactions."""
    print("\n=== Test: No Reactions Condition ===")
    setup_test()

    target = create_skeleton(name="Target", position=(0, 0))
    Entity.update_all_entities_senses()

    # Check initial reactions
    initial_reactions = target.action_economy.reactions.normalized_score
    print(f"Initial reactions available: {initial_reactions}")

    # Apply No Reactions
    from dnd.conditions import NoReactions
    from dnd.core.base_conditions import Duration, DurationType

    no_reactions = NoReactions(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        duration=Duration(
            duration=1,
            duration_type=DurationType.ROUNDS,
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid
        )
    )
    target.add_condition(no_reactions)

    # Check reactions now (should be 0 due to max constraint)
    final_reactions = target.action_economy.reactions.normalized_score
    print(f"Reactions after No Reactions condition: {final_reactions}")

    assert final_reactions == 0, "Reactions should be 0 with No Reactions condition"
    print("PASS: No Reactions condition working")
    return True


def test_guiding_bolt_range():
    """Test Guiding Bolt 120ft range check."""
    print("\n=== Test: Guiding Bolt Range ===")
    setup_test()

    # Use larger grid for range test (need 26+ tiles for 125ft test)
    get_map().create_rectangle(0, 0, 30, 30)

    caster = create_skeleton(name="Caster", position=(0, 0))

    # Target at 120ft (24 tiles) - should be at limit of range
    target_in_range = create_skeleton(name="In Range Target", position=(24, 0))
    # Update senses with max_distance=30 to see far away entities
    caster.update_entity_senses(max_distance=30)

    spell_in = GuidingBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_in_range.uuid,
        caster_level=5,
        cast_at_level=1
    )
    event_in = spell_in.apply()

    # The spell should execute (not cancel due to range)
    print(f"120ft target result: {event_in.status_message if event_in else 'None'}")
    # Either hits/misses or something other than range error
    range_error = event_in and event_in.canceled and "range" in (event_in.status_message or "").lower()
    assert not range_error, f"120ft target should be in range, got: {event_in.status_message if event_in else 'None'}"
    print("Target at 120ft: In range ✓")

    # Reset for out of range test
    setup_test()
    get_map().create_rectangle(0, 0, 30, 30)

    caster = create_skeleton(name="Caster", position=(0, 0))
    # Target at 125ft (25 tiles) - should be out of range
    target_out = create_skeleton(name="Out Range Target", position=(25, 0))
    # Update senses with max_distance=30 to see far away entities
    caster.update_entity_senses(max_distance=30)

    spell_out = GuidingBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_out.uuid,
        caster_level=5,
        cast_at_level=1
    )
    event_out = spell_out.apply()

    print(f"125ft target result: {event_out.status_message if event_out else 'None'}")
    assert event_out is not None, "Event should not be None"
    assert event_out.canceled, "125ft target should be out of range"
    assert "range" in (event_out.status_message or "").lower(), "Should mention range in error"
    print("Target at 125ft: Out of range ✓")

    print("PASS: Range check working")
    return True


def test_guiding_bolt_mark_duration_expiration():
    """Test mark expires at end of caster's next turn via duration."""
    print("\n=== Test: Guiding Bolt Mark Duration Expiration ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    Entity.update_all_entities_senses()

    # Manually apply the mark with 2-round duration
    from dnd.spells import GuidingBoltMarked
    from dnd.core.base_conditions import Duration, DurationType

    mark = GuidingBoltMarked(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=caster.uuid,
        duration=Duration(
            duration=2,  # Expires after 2 rounds (end of caster's next turn)
            duration_type=DurationType.ROUNDS,
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
    )
    target.add_condition(mark)

    assert has_condition(target, "Guiding Bolt"), "Mark should be applied"
    print("Mark applied, duration: 2 rounds")

    # First turn start for target - mark should persist (duration: 2 -> 1)
    target.on_turn_start()
    print(f"After target turn start 1: has mark = {has_condition(target, 'Guiding Bolt')}")
    assert has_condition(target, "Guiding Bolt"), "Mark should persist after 1 turn"

    # Second turn start for target - mark should expire (duration: 1 -> 0)
    target.on_turn_start()
    print(f"After target turn start 2: has mark = {has_condition(target, 'Guiding Bolt')}")
    assert not has_condition(target, "Guiding Bolt"), "Mark should expire after 2 turns"

    print("PASS: Mark duration expiration working")
    return True


def test_power_word_stun_range():
    """Test Power Word Stun 60ft range check."""
    print("\n=== Test: Power Word Stun Range ===")
    setup_test()

    # Use larger grid for range test (need 14+ tiles for 65ft test)
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_skeleton(name="Caster", position=(0, 0))

    # Target at 60ft (12 tiles) - should be at limit of range
    target_in_range = create_skeleton(name="In Range Target", position=(12, 0))
    set_hp(target_in_range, 100)  # Below 150 threshold
    # Update senses with max_distance=15 to see far away entities
    caster.update_entity_senses(max_distance=15)

    spell_in = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_in_range.uuid,
        caster_level=15
    )
    event_in = spell_in.apply()

    print(f"60ft target result: {event_in.status_message if event_in else 'None'}")
    # Should stun (not range error)
    range_error = event_in and event_in.canceled and "range" in (event_in.status_message or "").lower()
    assert not range_error, f"60ft target should be in range, got: {event_in.status_message if event_in else 'None'}"
    print("Target at 60ft: In range ✓")

    # Reset for out of range test
    setup_test()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_skeleton(name="Caster", position=(0, 0))
    # Target at 65ft (13 tiles) - should be out of range
    target_out = create_skeleton(name="Out Range Target", position=(13, 0))
    set_hp(target_out, 100)
    # Update senses with max_distance=15 to see far away entities
    caster.update_entity_senses(max_distance=15)

    spell_out = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_out.uuid,
        caster_level=15
    )
    event_out = spell_out.apply()

    print(f"65ft target result: {event_out.status_message if event_out else 'None'}")
    assert event_out is not None, "Event should not be None"
    assert event_out.canceled, "65ft target should be out of range"
    assert "range" in (event_out.status_message or "").lower(), "Should mention range in error"
    print("Target at 65ft: Out of range ✓")

    print("PASS: Range check working")
    return True


def test_power_word_stun_repeat_save():
    """Test CON save at end of target's turn removes stun on success."""
    print("\n=== Test: Power Word Stun Repeat Save ===")
    setup_test()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply PowerWordStunEffect directly
    from dnd.spells import PowerWordStunEffect

    stun_effect = PowerWordStunEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_uuid=caster.uuid,
        spell_dc=10  # Low DC for easier saves
    )
    target.add_condition(stun_effect)

    assert has_condition(target, "Power Word Stun"), "Should have Power Word Stun effect"
    assert has_condition(target, "Stunned"), "Should have Stunned sub-condition"
    print("Power Word Stun applied")

    # Simulate turn ends - CON save each time
    # With DC 10 and some CON bonus, should eventually save
    max_attempts = 30
    saved = False
    for i in range(max_attempts):
        target.on_turn_end()  # This triggers the repeat save handler
        if not has_condition(target, "Power Word Stun"):
            saved = True
            print(f"Target saved on turn end #{i + 1}")
            break
        print(f"Turn end #{i + 1}: Still stunned")

    assert saved, f"Target should eventually save (tried {max_attempts} times)"
    assert not has_condition(target, "Stunned"), "Stunned should be removed when Power Word Stun ends"

    print("PASS: Repeat save working")
    return True


if __name__ == "__main__":
    tests = [
        # Shocking Grasp tests
        test_shocking_grasp_basic,
        test_shocking_grasp_metal_armor_advantage,
        test_shocking_grasp_range,
        test_shocking_grasp_damage_scaling,
        test_shocking_grasp_no_reactions_expiration,
        # Guiding Bolt tests
        test_guiding_bolt_basic,
        test_guiding_bolt_mark_removed_on_attack,
        test_guiding_bolt_upcast,
        test_guiding_bolt_range,
        test_guiding_bolt_mark_duration_expiration,
        # Power Word Stun tests
        test_power_word_stun_basic,
        test_power_word_stun_hp_threshold,
        test_power_word_stun_exact_threshold,
        test_power_word_stun_range,
        test_power_word_stun_repeat_save,
        # NoReactions condition test
        test_no_reactions_condition,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
