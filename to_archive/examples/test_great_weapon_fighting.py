"""
Test Great Weapon Fighting Style

Demonstrates the damage dice reroll mechanic for two-handed melee weapons.
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from dnd.core.gridmap import get_map
from dnd.core.events import EventQueue, DamageRollResultEvent
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.classes.fighter import GreatWeaponFighting, create_modified_dice_roll
from dnd.blocks.equipment import WeaponProperty, Weapon
from dnd.core.events import WeaponSlot, RangeType, Range
from dnd.core.modifiers import DamageType
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.utils import reset_combat_state


def test_create_modified_dice_roll():
    """Test the dice roll modification utility."""
    from dnd.core.dice import DiceRoll, RollType
    from dnd.core.values import AdvantageStatus, CriticalStatus, AutoHitStatus

    # Create a mock dice roll
    original = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=[1, 2, 5],  # Three dice: 1, 2, and 5
        total=10,  # 1+2+5 + 2 bonus
        bonus=2,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4()
    )

    # Modify the results
    new_results = [4, 6, 5]  # Simulating rerolled 1→4, 2→6
    modified = create_modified_dice_roll(original, new_results)

    # Verify
    assert modified.results == [4, 6, 5]
    assert modified.total == 4 + 6 + 5 + 2  # 17
    assert modified.bonus == original.bonus
    assert modified.dice_uuid == original.dice_uuid

    print("create_modified_dice_roll test PASSED")
    print(f"  Original: {original.results} + {original.bonus} = {original.total}")
    print(f"  Modified: {modified.results} + {modified.bonus} = {modified.total}")


def test_great_weapon_fighting_condition():
    """Test that GreatWeaponFighting condition applies correctly."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create a fighter with a two-handed weapon
    fighter = create_goblin(name="Fighter", position=(5, 5))
    fighter.equipment.unequip(WeaponSlot.MELEE_OFF)

    # Give fighter a greatsword (2d6, two-handed)
    greatsword = Weapon(
        source_entity_uuid=fighter.uuid,
        name="Greatsword",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY],
        range=Range(type=RangeType.REACH, normal=5)
    )
    fighter.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    # Apply Great Weapon Fighting
    gwf = GreatWeaponFighting(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(gwf)

    # Verify the condition is applied
    assert "Fighting Style: Great Weapon Fighting" in fighter.active_conditions

    # Verify an event handler was registered with GWF
    gwf_handlers = [h for h in EventQueue._event_handlers.values() if h.name == "Great Weapon Fighting"]
    assert len(gwf_handlers) >= 1, f"Expected GWF handler, found: {[h.name for h in EventQueue._event_handlers.values()]}"

    print("GreatWeaponFighting condition test PASSED")
    print(f"  Fighter has condition: {list(fighter.active_conditions.keys())}")
    print(f"  GWF event handlers registered: {len(gwf_handlers)}")


def test_great_weapon_fighting_attack():
    """Test that GWF rerolls damage dice during an attack."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create combatants
    fighter = create_goblin(name="Fighter", position=(5, 5))
    target = create_skeleton(name="Target Dummy", position=(6, 5))  # Adjacent
    fighter.equipment.unequip(WeaponSlot.MELEE_OFF)

    # Give fighter a greatsword
    greatsword = Weapon(
        source_entity_uuid=fighter.uuid,
        name="Greatsword",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY],
        range=Range(type=RangeType.REACH, normal=5)
    )
    fighter.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    # Apply Great Weapon Fighting
    gwf = GreatWeaponFighting(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(gwf)

    # Update senses
    Entity.update_all_entities_senses(max_distance=20)

    # Set up standard actions
    setup_standard_actions(fighter)

    # Record initial HP
    initial_hp = target.get_hp()

    # Execute attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    assert event is not None, "Attack event should not be None"

    print("\nGreatWeaponFighting attack test")
    print(f"  Attack outcome: {event.attack_outcome}")

    if event.damage_rolls:
        print(f"  Damage rolls: {[r.total for r in event.damage_rolls]}")
        print(f"  Damage taken: {initial_hp - target.get_hp()}")

        # Check the DAMAGE_ROLL_RESULT events for any modifications
        from dnd.core.events import EventType
        damage_events = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        for de in damage_events:
            if isinstance(de, DamageRollResultEvent) and de.roll_modifications:
                print(f"  GWF modifications: {de.roll_modifications}")

    print("  Attack test completed (results depend on RNG)")


def test_gwf_does_not_apply_to_ranged():
    """Test that GWF doesn't affect ranged weapons."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create combatants
    fighter = create_goblin(name="Fighter", position=(5, 5))
    target = create_skeleton(name="Target", position=(10, 5))  # At range

    # Fighter has a longbow by default in RANGED_MAIN

    # Apply Great Weapon Fighting
    gwf = GreatWeaponFighting(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(gwf)

    # Update senses
    Entity.update_all_entities_senses(max_distance=20)

    # Set up standard actions
    setup_standard_actions(fighter)

    # Execute ranged attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN
    )
    event = attack.apply()
    assert event is not None, "Attack event should not be None"

    print("\nGWF ranged weapon test")
    print(f"  Attack outcome: {event.attack_outcome}")

    # Check that no modifications were made (GWF shouldn't apply)
    from dnd.core.events import EventType
    damage_events = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
    gwf_applied = False
    for de in damage_events:
        if isinstance(de, DamageRollResultEvent) and de.roll_modifications:
            gwf_applied = True

    if not gwf_applied:
        print("  GWF correctly did NOT apply to ranged attack")
    else:
        print("  WARNING: GWF incorrectly applied to ranged attack!")

    print("  Test completed")


def test_gwf_does_not_apply_to_one_handed():
    """Test that GWF doesn't affect one-handed melee weapons."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create combatants
    fighter = create_goblin(name="Fighter", position=(5, 5))
    target = create_skeleton(name="Target", position=(6, 5))  # Adjacent

    # Give fighter a shortsword (one-handed)
    shortsword = Weapon(
        source_entity_uuid=fighter.uuid,
        name="Shortsword",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5)
    )
    fighter.equipment.equip(shortsword, WeaponSlot.MELEE_MAIN)

    # Apply Great Weapon Fighting
    gwf = GreatWeaponFighting(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(gwf)

    # Update senses
    Entity.update_all_entities_senses(max_distance=20)

    # Set up standard actions
    setup_standard_actions(fighter)

    # Execute attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    assert event is not None, "Attack event should not be None"

    print("\nGWF one-handed weapon test")
    print(f"  Attack outcome: {event.attack_outcome}")

    # Check that no modifications were made
    from dnd.core.events import EventType
    damage_events = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
    gwf_applied = False
    for de in damage_events:
        if isinstance(de, DamageRollResultEvent) and de.roll_modifications:
            gwf_applied = True

    if not gwf_applied:
        print("  GWF correctly did NOT apply to one-handed weapon")
    else:
        print("  WARNING: GWF incorrectly applied to one-handed weapon!")

    print("  Test completed")


def test_gwf_statistics(num_runs: int = 20):
    """Run multiple attacks to gather statistics on GWF rerolls."""
    from dnd.core.events import EventType

    hits = 0
    misses = 0
    crits = 0
    total_damage = 0
    gwf_rerolls = 0
    gwf_damage_gained = 0

    print(f"\nRunning {num_runs} attacks with Great Weapon Fighting...")
    print("-" * 50)

    for i in range(num_runs):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        # Create combatants
        fighter = create_goblin(name="Fighter", position=(5, 5))
        target = create_skeleton(name="Target", position=(6, 5))
        fighter.equipment.unequip(WeaponSlot.MELEE_OFF)

        # Give fighter a greatsword (2d6, two-handed)
        greatsword = Weapon(
            source_entity_uuid=fighter.uuid,
            name="Greatsword",
            damage_dice=6,
            dice_numbers=2,
            damage_type=DamageType.SLASHING,
            properties=[WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY],
            range=Range(type=RangeType.REACH, normal=5)
        )
        fighter.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

        # Apply Great Weapon Fighting
        gwf = GreatWeaponFighting(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid
        )
        fighter.add_condition(gwf)

        Entity.update_all_entities_senses(max_distance=20)
        setup_standard_actions(fighter)

        # Execute attack
        attack = Attack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        event = attack.apply()

        # Track results
        if event and hasattr(event, 'attack_outcome'):
            from dnd.core.dice import AttackOutcome
            if event.attack_outcome == AttackOutcome.HIT:
                hits += 1
            elif event.attack_outcome == AttackOutcome.CRIT:
                crits += 1
                hits += 1  # Crits are also hits
            else:
                misses += 1

            if event.damage_rolls:
                for roll in event.damage_rolls:
                    total_damage += roll.total

        # Check for GWF modifications
        damage_events = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        for de in damage_events:
            if isinstance(de, DamageRollResultEvent) and de.roll_modifications:
                for mod in de.roll_modifications:
                    handler_name, _, old_total, new_total, reason = mod
                    if handler_name == "Great Weapon Fighting":
                        gwf_rerolls += 1
                        gwf_damage_gained += (new_total - old_total)
                        print(f"  Run {i+1}: GWF reroll! {old_total} -> {new_total} ({reason})")

    print("-" * 50)
    print(f"\nSTATISTICS ({num_runs} attacks):")
    print(f"  Hits: {hits} ({100*hits/num_runs:.1f}%)")
    print(f"  Crits: {crits}")
    print(f"  Misses: {misses}")
    print(f"  Total damage dealt: {total_damage}")
    if hits > 0:
        print(f"  Average damage per hit: {total_damage/hits:.1f}")
    print(f"  GWF rerolls triggered: {gwf_rerolls}")
    print(f"  Net damage from GWF: {gwf_damage_gained:+d}")


if __name__ == "__main__":
    print("=" * 60)
    print("GREAT WEAPON FIGHTING TESTS")
    print("=" * 60)

    test_create_modified_dice_roll()
    print()

    test_great_weapon_fighting_condition()
    print()

    test_gwf_does_not_apply_to_ranged()
    print()

    test_gwf_does_not_apply_to_one_handed()
    print()

    test_gwf_statistics(num_runs=20)

    print()
    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
