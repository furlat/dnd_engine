"""
Ranged Combat Example

Demonstrates ranged attack mechanics:
1. Normal range attacks (no disadvantage)
2. Long range attacks (disadvantage)
3. Ranged attacks while threatened (disadvantage)
4. Attacks beyond max range (blocked)

Run with: python examples/combat_ranged.py
"""

from dnd.monsters.bestiary import create_goblin_archer, create_skeleton, create_goblin
from dnd.entity import Entity
from dnd.core.gridmap import get_map, reset_map
from dnd.actions import Attack
from dnd.core.events import WeaponSlot


def setup_scenario():
    """Reset and create a fresh 30x30 grid."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    grid = get_map()
    grid.create_rectangle(0, 0, 40, 40)
    return grid


def print_attack_result(_name: str, event):
    """Print attack result in a readable format."""
    if event.canceled:
        print(f"  Result: CANCELED - {event.status_message}")
    else:
        outcome = event.attack_outcome.value if event.attack_outcome else "N/A"
        roll_total = event.dice_roll.total if event.dice_roll else "N/A"

        # Show dice roll details - this captures the advantage state at roll time
        if event.dice_roll:
            dr = event.dice_roll
            adv_status = dr.advantage_status.value
            print(f"  Result: {outcome}, Total: {roll_total} (d20 + {dr.bonus})")
            print(f"  Dice rolled: {dr.results}, Advantage: {adv_status}")

            # Show which die was selected for advantage/disadvantage
            if len(dr.results) == 2:
                selected = dr.total - dr.bonus
                if adv_status == "Disadvantage":
                    print(f"  -> Took LOWER of {dr.results} = {selected}")
                elif adv_status == "Advantage":
                    print(f"  -> Took HIGHER of {dr.results} = {selected}")
        else:
            print(f"  Result: {outcome}, Roll: {roll_total}")

        if event.is_long_range:
            print(f"  (Long range disadvantage applied)")
        if event.is_threatened:
            print(f"  (Threatened disadvantage applied)")


def main():
    print("=" * 60)
    print("RANGED COMBAT EXAMPLE")
    print("=" * 60)

    # =========================================================================
    # Scenario 1: Normal Range Attack (within 80ft for shortbow)
    # =========================================================================
    print("\n--- Scenario 1: Normal Range Attack ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(0, 0))
    target = create_skeleton(name="Skeleton", position=(10, 0))  # 50ft away

    Entity.update_all_entities_senses(max_distance=20)

    print(f"Archer at {archer.position}")
    print(f"Target at {target.position} (distance: {archer.senses.get_feet_distance(target.position)}ft)")
    print(f"Shortbow range: normal=80ft, long=320ft")
    print(f"Archer is_threatened: {archer.is_threatened()}")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Shortbow Attack"
    )
    event = attack.apply()
    print_attack_result("Normal Range", event)

    # =========================================================================
    # Scenario 2: Long Range Attack (beyond 80ft, within 320ft)
    # =========================================================================
    print("\n--- Scenario 2: Long Range Attack ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(0, 0))
    target = create_skeleton(name="Skeleton", position=(20, 0))  # 100ft away

    Entity.update_all_entities_senses(max_distance=25)

    print(f"Archer at {archer.position}")
    print(f"Target at {target.position} (distance: {archer.senses.get_feet_distance(target.position)}ft)")
    print(f"Shortbow range: normal=80ft, long=320ft")
    print(f"100ft > 80ft (normal) but <= 320ft (long) -> DISADVANTAGE")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Long Range Shot"
    )
    event = attack.apply()
    print_attack_result("Long Range", event)

    # =========================================================================
    # Scenario 3: Ranged Attack While Threatened
    # =========================================================================
    print("\n--- Scenario 3: Ranged Attack While Threatened ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(5, 5))
    melee_enemy = create_goblin(name="Enemy Goblin", position=(5, 6))  # Adjacent!
    distant_target = create_skeleton(name="Skeleton", position=(15, 5))  # 50ft away

    Entity.update_all_entities_senses(max_distance=20)

    print(f"Archer at {archer.position}")
    print(f"Melee enemy at {melee_enemy.position} (distance: {archer.senses.get_feet_distance(melee_enemy.position)}ft)")
    print(f"Distant target at {distant_target.position} (distance: {archer.senses.get_feet_distance(distant_target.position)}ft)")
    print(f"Archer is_threatened: {archer.is_threatened()}")
    print(f"Making ranged attack while threatened -> DISADVANTAGE")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=distant_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Threatened Ranged Attack"
    )
    event = attack.apply()
    print_attack_result("Threatened", event)

    # =========================================================================
    # Scenario 4: Attack Beyond Max Range (blocked)
    # =========================================================================
    print("\n--- Scenario 4: Beyond Max Range (Should Be Blocked) ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(0, 0))
    far_target = create_skeleton(name="Far Skeleton", position=(70, 0))  # 350ft away

    Entity.update_all_entities_senses(max_distance=80)

    print(f"Archer at {archer.position}")
    print(f"Target at {far_target.position} (distance: {archer.senses.get_feet_distance(far_target.position)}ft)")
    print(f"Shortbow range: normal=80ft, long=320ft")
    print(f"350ft > 320ft (long) -> ATTACK BLOCKED")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=far_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Impossible Shot"
    )
    event = attack.apply()
    print_attack_result("Beyond Range", event)

    # =========================================================================
    # Scenario 5: Melee Fallback When Threatened
    # =========================================================================
    print("\n--- Scenario 5: Melee Fallback (No Disadvantage) ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(5, 5))
    melee_enemy = create_goblin(name="Enemy Goblin", position=(5, 6))  # Adjacent

    Entity.update_all_entities_senses(max_distance=20)

    print(f"Archer at {archer.position}")
    print(f"Enemy at {melee_enemy.position} (adjacent)")
    print(f"Using MELEE_MAIN scimitar (melee) instead of bow")
    print(f"Melee attacks are NOT affected by being threatened")

    # Use the scimitar in off-hand for melee
    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=melee_enemy.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,  # Scimitar!
        name="Scimitar Strike"
    )
    event = attack.apply()
    print_attack_result("Melee Fallback", event)

    # =========================================================================
    # Scenario 6: Long Range AND Threatened (Double Disadvantage)
    # =========================================================================
    print("\n--- Scenario 6: Long Range AND Threatened ---")
    setup_scenario()

    archer = create_goblin_archer(name="Goblin Archer", position=(5, 5))
    melee_enemy = create_goblin(name="Enemy Goblin", position=(5, 6))  # Adjacent
    distant_target = create_skeleton(name="Far Skeleton", position=(25, 5))  # 100ft away

    Entity.update_all_entities_senses(max_distance=30)

    print(f"Archer at {archer.position}")
    print(f"Melee enemy at {melee_enemy.position} (adjacent - THREATENED)")
    print(f"Target at {distant_target.position} (distance: {archer.senses.get_feet_distance(distant_target.position)}ft - LONG RANGE)")
    print(f"Both long range AND threatened -> DISADVANTAGE (stacks but doesn't worsen)")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=distant_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Desperate Shot"
    )
    event = attack.apply()
    print_attack_result("Double Disadvantage", event)

    # =========================================================================
    # Scenario 7: Competing Advantage/Disadvantage (2 disadv vs 1 adv)
    # =========================================================================
    print("\n--- Scenario 7: Competing Modifiers (Target Blinded) ---")
    setup_scenario()

    from dnd.conditions import Blinded

    archer = create_goblin_archer(name="Goblin Archer", position=(5, 5))
    melee_enemy = create_goblin(name="Enemy Goblin", position=(5, 6))  # Adjacent = threatened
    blinded_target = create_skeleton(name="Blinded Skeleton", position=(25, 5))  # 100ft = long range

    # Apply Blinded to target - gives attackers ADVANTAGE
    blinded = Blinded(source_entity_uuid=archer.uuid, target_entity_uuid=blinded_target.uuid)
    blinded_target.add_condition(blinded)

    Entity.update_all_entities_senses(max_distance=30)

    print(f"Archer at {archer.position}")
    print(f"Melee enemy at {melee_enemy.position} (adjacent - THREATENED)")
    print(f"Target at {blinded_target.position} (distance: {archer.senses.get_feet_distance(blinded_target.position)}ft - LONG RANGE)")
    print(f"Target is BLINDED: {('Blinded' in blinded_target.active_conditions)}")
    print()
    print("Modifier math:")
    print("  - Long Range: DISADVANTAGE (-1)")
    print("  - Threatened: DISADVANTAGE (-1)")
    print("  - Target Blinded: ADVANTAGE (+1)")
    print("  - Net sum: -1 = DISADVANTAGE")
    print("  (In D&D terms: 2 sources of disadvantage vs 1 advantage = still disadvantage)")

    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=blinded_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
        name="Blinded Target Shot"
    )
    event = attack.apply()
    print_attack_result("Competing Modifiers", event)

    print("\n" + "=" * 60)
    print("RANGED COMBAT EXAMPLE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
