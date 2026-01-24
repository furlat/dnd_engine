"""
Full combat encounter example with turn-based combat and event streaming.

This demonstrates:
1. Setting up an encounter with two combatants
2. Using a simple AI controller that picks actions from available_actions
3. Running the combat loop with run_turn()
4. All events being fired (can be streamed via websocket)

Usage:
    python examples/combat_encounter_live.py

To also see events via websocket:
    1. In terminal 1: python -m server.event_server
    2. In terminal 2: python examples/combat_encounter_live.py
    3. Connect a websocket client to ws://localhost:8000/ws
"""

from uuid import uuid4
from typing import Optional

from dnd.core.gridmap import reset_map, get_map
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.encounter import Encounter, EncounterState
from dnd.controller import Controller, TurnContext
from dnd.actions_functional import get_available_actions
from dnd.actions import Attack, Move, Dodge
from dnd.blocks.equipment import WeaponSlot
from dnd.core.base_actions import BaseAction


class AggressiveAIController(Controller):
    """
    Simple AI that:
    1. If enemy in weapon range -> Attack
    2. If enemy visible but not in range -> Move closer, then Attack if possible
    3. If no enemies visible -> End turn
    """

    name: str = "Aggressive AI"
    controller_type: str = "aggressive_ai"

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional[BaseAction]:
        """Pick the next action based on available options."""

        # Get all available actions using functional API
        available = get_available_actions(entity)

        # Debug output
        print(f"    [{entity.name}] Actions: {context.actions_remaining}, "
              f"Movement: {context.movement_remaining}ft")

        # Priority 1: Attack if we can
        for attack_info in available.entity_actions:
            if attack_info.can_afford and attack_info.valid_targets:
                target = attack_info.valid_targets[0]  # Pick first target
                if target.target_uuid is None:
                    continue
                target_entity = Entity.get(target.target_uuid)
                target_name = target_entity.name if target_entity else "Unknown"
                print(f"    [{entity.name}] Attacking {target_name}!")

                # Use template to create instance
                template = entity.get_action_template(attack_info.template_name)
                if template:
                    return template.instantiate(target_entity_uuid=target.target_uuid)

        # Priority 2: Move toward enemy if we can't attack AND have action remaining
        # (Don't waste movement after attacking - stay in position)
        can_still_attack = entity.action_economy.can_afford("actions", 1)
        if can_still_attack and available.position_actions:
            move_info = available.position_actions[0]  # Get the move action descriptor

            # Find closest enemy position we can move to
            closest_pos = None
            closest_dist = float('inf')
            current_min_dist = float('inf')

            # First, find current distance to nearest enemy
            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue
                dist = abs(entity.position[0] - enemy_pos[0]) + abs(entity.position[1] - enemy_pos[1])
                if dist < current_min_dist:
                    current_min_dist = dist

            # Only move if we can get closer
            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue

                # Find valid position closest to this enemy
                for target in move_info.valid_targets:
                    if target.position is None:
                        continue
                    pos = target.position
                    # Manhattan distance to enemy
                    dist = abs(pos[0] - enemy_pos[0]) + abs(pos[1] - enemy_pos[1])
                    if dist < closest_dist and dist < current_min_dist:
                        closest_dist = dist
                        closest_pos = pos

            if closest_pos and closest_pos != entity.position:
                print(f"    [{entity.name}] Moving from {entity.position} to {closest_pos}")
                template = entity.get_action_template(move_info.template_name)
                if template:
                    return template.instantiate(end_position=closest_pos)

        # Priority 3: If we have action but nothing to attack, Dodge
        can_afford_action = entity.action_economy.can_afford("actions", 1)
        if can_afford_action:
            # Check if we have enemies nearby (within 10ft)
            has_nearby_enemy = False
            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid != entity.uuid:
                    dist = entity.senses.get_feet_distance(enemy_pos)
                    if dist <= 10:
                        has_nearby_enemy = True
                        break

            if has_nearby_enemy:
                print(f"    [{entity.name}] Taking Dodge action (defensive)")
                return Dodge(source_entity_uuid=entity.uuid)

        # No good action available, end turn
        print(f"    [{entity.name}] Ending turn (no actions available)")
        return None


def setup_combat():
    """Set up a combat encounter."""
    # Clear state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller._controller_registry.clear()
    Encounter._encounter_registry.clear()

    # Clear event queue
    EventQueue._events_by_lineage.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_timestamp.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._all_events.clear()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create combatants at opposite ends
    goblin = create_goblin(name="Goblin Scout", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton Warrior", position=(12, 7))

    # Update senses so they can see each other
    Entity.update_all_entities_senses()

    print(f"Created {goblin.name} at {goblin.position} (HP: {goblin.get_hp()})")
    print(f"Created {skeleton.name} at {skeleton.position} (HP: {skeleton.get_hp()})")
    print(f"Distance: {goblin.senses.get_feet_distance(skeleton.position)}ft")
    print()

    return goblin, skeleton


def run_combat(goblin: Entity, skeleton: Entity, max_rounds: int = 10):
    """Run the combat encounter."""

    # Create controllers
    goblin_controller = AggressiveAIController(source_entity_uuid=goblin.uuid)
    skeleton_controller = AggressiveAIController(source_entity_uuid=skeleton.uuid)

    # Create encounter
    encounter = Encounter(
        name="Test Combat",
        source_entity_uuid=uuid4()
    )

    encounter.add_combatant(goblin, goblin_controller)
    encounter.add_combatant(skeleton, skeleton_controller)

    # Roll initiative and start
    encounter.roll_initiative()
    encounter.start_encounter()

    print("=" * 60)
    print("COMBAT STARTED")
    print("=" * 60)
    initiative_names = [e.name for uuid in encounter.initiative_order if (e := Entity.get(uuid))]
    print(f"Initiative order: {initiative_names}")
    print()

    # Combat loop
    while encounter.state == EncounterState.ACTIVE and encounter.round_number <= max_rounds:
        print(f"--- Round {encounter.round_number} ---")

        # Run turns for all combatants in this round
        for _ in range(len(encounter.initiative_order)):
            if encounter.state != EncounterState.ACTIVE:
                break

            current = encounter.get_current_entity()
            if not current:
                break

            # Skip dead combatants
            combatant = encounter.get_current_combatant()
            if combatant and combatant.is_dead:
                encounter.run_turn()  # Will skip automatically
                continue

            print(f"\n  {current.name}'s turn:")

            # Run the turn (controller decides actions, encounter handles deaths)
            encounter.run_turn()

        # Check for deaths this round
        dead = encounter.get_dead_combatants()
        for d in dead:
            entity = d.entity
            if entity:
                print(f"\n*** {entity.name} has been defeated! ***")

        if encounter.state != EncounterState.ACTIVE:
            break

        print()

        # Status update
        alive = encounter.get_alive_combatants()
        for c in alive:
            e = c.entity
            if e:
                print(f"  Status: {e.name} HP={e.get_hp()} at {e.position}")

    return encounter


def print_combat_summary(encounter: Encounter, goblin: Entity, skeleton: Entity):
    """Print final combat summary."""
    print()
    print("=" * 60)
    print("COMBAT SUMMARY")
    print("=" * 60)

    print(f"  {goblin.name}: {goblin.get_hp()} HP remaining at {goblin.position}")
    print(f"  {skeleton.name}: {skeleton.get_hp()} HP remaining at {skeleton.position}")

    # Count events
    attack_events = EventQueue.get_events_by_type(EventType.ATTACK)
    movement_events = EventQueue.get_events_by_type(EventType.MOVEMENT)
    turn_events = EventQueue.get_events_by_type(EventType.TURN_START)
    death_events = EventQueue.get_events_by_type(EventType.DEATH)

    print()
    print(f"  Total events fired: {len(EventQueue._all_events)}")
    print(f"    - Attack events: {len(attack_events)}")
    print(f"    - Movement events: {len(movement_events)}")
    print(f"    - Turn start events: {len(turn_events)}")
    print(f"    - Death events: {len(death_events)}")

    # Determine winner
    alive = encounter.get_alive_combatants()
    if len(alive) == 1:
        winner = alive[0].entity
        if winner:
            print(f"\n  Winner: {winner.name}!")
    elif len(alive) == 0:
        print("\n  No survivors!")
    else:
        print("\n  Combat ended (max rounds reached)")


def main():
    """Run the full combat example."""
    print("=" * 60)
    print("COMBAT ENCOUNTER EXAMPLE")
    print("=" * 60)
    print()

    # Setup
    goblin, skeleton = setup_combat()

    # Run combat
    encounter = run_combat(goblin, skeleton, max_rounds=10)

    # Summary
    print_combat_summary(encounter, goblin, skeleton)

    print()
    print("=" * 60)
    print("Combat example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
