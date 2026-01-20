"""
Basic Combat Example

Demonstrates a simple attack exchange between a Goblin and a Skeleton.
Both creatures are placed adjacent to each other (5ft apart).

This example verifies:
- Attack bonus calculation
- AC calculation
- Damage application
- HP tracking
"""

from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.actions import Attack
from dnd.blocks.equipment import WeaponSlot
from dnd.entity import Entity


def print_separator(title: str = "") -> None:
    """Print a visual separator with optional title."""
    if title:
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    else:
        print("-" * 60)


def print_entity_status(entity: Entity) -> None:
    """Print the current status of an entity."""
    hp = entity.get_hp()
    ac = entity.ac_bonus().normalized_score
    attack_bonus = entity.attack_bonus(WeaponSlot.MAIN_HAND).normalized_score

    print(f"  {entity.name}:")
    print(f"    HP: {hp}")
    print(f"    AC: {ac}")
    print(f"    Attack Bonus: +{attack_bonus}")
    print(f"    Position: {entity.position}")
    print(f"    Damage Taken: {entity.health.damage_taken}")


def print_attack_result(event) -> None:
    """Print the result of an attack event."""
    if event is None:
        print("  Attack failed - no event returned")
        return

    if event.canceled:
        print(f"  Attack canceled: {event.status_message}")
        return

    print(f"  Attack Roll: {event.dice_roll.total if event.dice_roll else 'N/A'}")
    print(f"    Natural Roll: {event.dice_roll.results if event.dice_roll else 'N/A'}")
    print(f"    Bonus: +{event.attack_bonus.normalized_score if event.attack_bonus else 'N/A'}")
    print(f"  Target AC: {event.ac.normalized_score if event.ac else 'N/A'}")
    print(f"  Outcome: {event.attack_outcome}")

    if event.damage_rolls:
        total_damage = sum(roll.total for roll in event.damage_rolls)
        print(f"  Damage Dealt: {total_damage}")
        for i, roll in enumerate(event.damage_rolls):
            damage_type = event.damages[i].damage_type if event.damages else "Unknown"
            print(f"    - {roll.total} {damage_type.value}")


def main():
    print_separator("BASIC COMBAT EXAMPLE")
    print("Creating combatants...")

    # Clear any existing entities (in case of multiple runs)
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Create combatants at adjacent positions (0,0) and (1,0) = 5ft apart
    goblin = create_goblin(name="Goblin Scout", position=(0, 0))
    skeleton = create_skeleton(name="Skeleton Warrior", position=(1, 0))

    # Update senses so they can see each other
    Entity.update_all_entities_senses()

    print_separator("INITIAL STATE")
    print_entity_status(goblin)
    print_entity_status(skeleton)

    # Verify they can see each other
    print_separator("LINE OF SIGHT")
    print(f"  {goblin.name} can see {skeleton.name}: {skeleton.uuid in goblin.senses.entities}")
    print(f"  {skeleton.name} can see {goblin.name}: {goblin.uuid in skeleton.senses.entities}")
    print(f"  Distance: {goblin.senses.get_feet_distance(skeleton.position)} feet")

    # ROUND 1: Goblin attacks Skeleton
    print_separator("ROUND 1: GOBLIN ATTACKS SKELETON")

    goblin_attack = Attack(
        source_entity_uuid=goblin.uuid,
        target_entity_uuid=skeleton.uuid,
        weapon_slot=WeaponSlot.MAIN_HAND,
        name="Scimitar Attack"
    )

    print(f"  {goblin.name} swings their scimitar at {skeleton.name}!")
    attack_event = goblin_attack.apply()
    print_attack_result(attack_event)

    print_separator("AFTER GOBLIN'S ATTACK")
    print_entity_status(skeleton)

    # ROUND 1: Skeleton attacks Goblin
    print_separator("ROUND 1: SKELETON ATTACKS GOBLIN")

    skeleton_attack = Attack(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=goblin.uuid,
        weapon_slot=WeaponSlot.MAIN_HAND,
        name="Shortsword Attack"
    )

    print(f"  {skeleton.name} thrusts their shortsword at {goblin.name}!")
    attack_event = skeleton_attack.apply()
    print_attack_result(attack_event)

    print_separator("AFTER SKELETON'S ATTACK")
    print_entity_status(goblin)

    # ROUND 2: Continue combat
    print_separator("ROUND 2: CONTINUED COMBAT")

    # Reset action economy for round 2
    goblin.action_economy.reset_all_costs()
    skeleton.action_economy.reset_all_costs()

    # Goblin attacks again
    print(f"\n  {goblin.name} attacks again!")
    goblin_attack2 = Attack(
        source_entity_uuid=goblin.uuid,
        target_entity_uuid=skeleton.uuid,
        weapon_slot=WeaponSlot.MAIN_HAND,
        name="Scimitar Attack"
    )
    attack_event = goblin_attack2.apply()
    print_attack_result(attack_event)

    # Skeleton attacks again
    print(f"\n  {skeleton.name} retaliates!")
    skeleton_attack2 = Attack(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=goblin.uuid,
        weapon_slot=WeaponSlot.MAIN_HAND,
        name="Shortsword Attack"
    )
    attack_event = skeleton_attack2.apply()
    print_attack_result(attack_event)

    print_separator("FINAL STATE")
    print_entity_status(goblin)
    print_entity_status(skeleton)

    # Summary
    print_separator("COMBAT SUMMARY")
    goblin_hp = goblin.get_hp()
    skeleton_hp = skeleton.get_hp()

    print(f"  {goblin.name}: {goblin_hp} HP remaining")
    print(f"  {skeleton.name}: {skeleton_hp} HP remaining")

    if goblin_hp <= 0:
        print(f"\n  {goblin.name} has fallen!")
    if skeleton_hp <= 0:
        print(f"\n  {skeleton.name} has been destroyed!")
    if goblin_hp > 0 and skeleton_hp > 0:
        print(f"\n  Both combatants still standing!")

    print_separator()
    print("Combat example completed successfully!")


if __name__ == "__main__":
    main()
