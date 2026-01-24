#!/usr/bin/env python3
"""Debug script to check what the AI sees during its turn."""

import sys
sys.path.insert(0, '/mnt/c/Users/tommaso/Documents/Dev/dnd_engine')

from uuid import uuid4
from dnd.core.gridmap import get_map, reset_map
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.controller import Controller, TurnContext, HumanController
from dnd.actions_functional import get_available_actions


def setup_debug():
    """Setup a test scenario."""
    # Reset everything
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    EventQueue._all_events.clear()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create entities
    hero = create_goblin(name="Hero", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton", position=(12, 7))

    print(f"Hero position: {hero.position}")
    print(f"Skeleton position: {skeleton.position}")

    # Update senses
    Entity.update_all_entities_senses()

    print(f"\n=== Hero's senses ===")
    print(f"  senses.position: {hero.senses.position}")
    print(f"  senses.entities: {hero.senses.entities}")
    print(f"  senses.paths count: {len(hero.senses.paths)}")

    print(f"\n=== Skeleton's senses ===")
    print(f"  senses.position: {skeleton.senses.position}")
    print(f"  senses.entities: {skeleton.senses.entities}")
    print(f"  senses.paths count: {len(skeleton.senses.paths)}")

    # Check available actions for skeleton
    print(f"\n=== Skeleton's available actions ===")
    available = get_available_actions(skeleton)
    print(f"  remaining_movement: {available.remaining_movement}")
    print(f"  entity_actions: {len(available.entity_actions)}")
    for atk in available.entity_actions:
        print(f"    - {atk.display_name}: can_afford={atk.can_afford}, valid_targets={len(atk.valid_targets)}")
    print(f"  position_actions: {len(available.position_actions)}")
    for mov in available.position_actions:
        print(f"    - {mov.display_name}: can_afford={mov.can_afford}, valid_targets count={len(mov.valid_targets)}")
    print(f"  self_actions: {len(available.self_actions)}")
    for self_act in available.self_actions:
        print(f"    - {self_act.display_name}: can_afford={self_act.can_afford}")

    return hero, skeleton


def test_encounter_turn():
    """Test the encounter turn flow."""
    hero, skeleton = setup_debug()

    # Create encounter
    encounter = Encounter(name="Debug Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))

    # Test with the actual MeleeAIController logic
    from dnd.controller import Controller
    from dnd.actions import Attack, Move
    from dnd.blocks.equipment import WeaponSlot

    class DebugAI(Controller):
        name: str = "Debug AI"
        controller_type: str = "debug_ai"

        def get_next_action(self, entity, context):
            print(f"\n=== DebugAI.get_next_action called ===")
            print(f"  Entity: {entity.name} at {entity.position}")
            print(f"  context.visible_enemies: {context.visible_enemies}")
            print(f"  context.actions_remaining: {context.actions_remaining}")
            print(f"  context.movement_remaining: {context.movement_remaining}")

            available = get_available_actions(entity)
            print(f"  entity_actions: {len(available.entity_actions)}")
            print(f"  position_actions: {len(available.position_actions)}")

            # Priority 1: Attack if we can
            for attack_info in available.entity_actions:
                print(f"    Checking attack {attack_info.display_name}: can_afford={attack_info.can_afford}, valid_targets={len(attack_info.valid_targets)}")
                if attack_info.can_afford and attack_info.valid_targets:
                    print(f"    -> Would attack!")
                    return None  # Don't actually attack in debug

            # Priority 2: Move toward enemy
            can_still_attack = entity.action_economy.can_afford("actions", 1)
            print(f"  can_still_attack: {can_still_attack}")
            print(f"  position_actions: {len(available.position_actions)}")

            if can_still_attack and available.position_actions:
                move_info = available.position_actions[0]
                print(f"  move_info.valid_targets count: {len(move_info.valid_targets)}")

                # Find closest position to any enemy
                closest_pos = None
                closest_dist = float('inf')
                current_min_dist = float('inf')

                # Current distance to nearest enemy
                for enemy_uuid, enemy_pos in context.visible_enemies.items():
                    if enemy_uuid == entity.uuid:
                        print(f"    Skipping self: {enemy_uuid}")
                        continue
                    dist = abs(entity.position[0] - enemy_pos[0]) + abs(entity.position[1] - enemy_pos[1])
                    print(f"    Enemy {enemy_uuid} at {enemy_pos}, distance={dist}")
                    if dist < current_min_dist:
                        current_min_dist = dist

                print(f"  current_min_dist: {current_min_dist}")

                # Find position that gets us closer
                positions_checked = 0
                positions_closer = 0
                for enemy_uuid, enemy_pos in context.visible_enemies.items():
                    if enemy_uuid == entity.uuid:
                        continue
                    for target in move_info.valid_targets:
                        if target.position is None:
                            continue
                        pos = target.position
                        positions_checked += 1
                        dist = abs(pos[0] - enemy_pos[0]) + abs(pos[1] - enemy_pos[1])
                        if dist < closest_dist and dist < current_min_dist:
                            positions_closer += 1
                            closest_dist = dist
                            closest_pos = pos

                print(f"  Positions checked: {positions_checked}")
                print(f"  Positions closer: {positions_closer}")
                print(f"  closest_pos: {closest_pos}, closest_dist: {closest_dist}")

                if closest_pos and closest_pos != entity.position:
                    print(f"  -> Would move to {closest_pos}!")
                    template = entity.get_action_template(move_info.template_name)
                    if template:
                        return template.instantiate(end_position=closest_pos)
                else:
                    print(f"  -> No closer position found!")

            print("  -> Ending turn (no action)")
            return None

    encounter.add_combatant(skeleton, DebugAI(source_entity_uuid=skeleton.uuid))

    # Start encounter
    print(f"\n=== Starting encounter ===")
    encounter.roll_initiative()
    encounter.start_encounter()

    print(f"Initiative order: {encounter.initiative_order}")
    print(f"Current turn index: {encounter.current_turn_index}")

    current = encounter.get_current_entity()
    print(f"Current entity: {current.name if current else None}")

    # Run the turn for whoever is current
    if current and current.name == "Hero":
        print("\n=== Skipping Hero turn, simulating skeleton turn ===")
        # End hero turn
        encounter.turn_state = TurnState.IN_PROGRESS
        encounter.end_turn()
        encounter.current_turn_index += 1
        encounter.turn_state = TurnState.NOT_STARTED

        # Now run skeleton turn
        print(f"Current turn index: {encounter.current_turn_index}")
        current = encounter.get_current_entity()
        print(f"Current entity: {current.name if current else None}")

    if current and current.name == "Skeleton":
        print("\n=== Running skeleton turn ===")
        encounter.run_turn()
        print(f"\n=== After skeleton turn ===")
        skeleton_entity = [e for e in Entity.get_all_entities() if e.name == "Skeleton"][0]
        print(f"  Skeleton position: {skeleton_entity.position}")


if __name__ == "__main__":
    test_encounter_turn()
