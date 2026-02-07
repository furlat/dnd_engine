"""
Live combat scenario with websocket event broadcasting.

This script:
1. Starts the event websocket server in a background thread
2. Runs a sophisticated combat scenario with movements and attacks
3. Events are broadcast in real-time to any connected websocket clients

Usage:
    # Run the scenario (server starts automatically)
    python -m examples.combat_scenario_live

    # In another terminal, connect a client to watch events:
    python -m server.test_client

    # Or connect any websocket client to ws://localhost:8000/ws
"""

import threading
import time
from uuid import uuid4
from typing import Tuple, Optional

import uvicorn

from dnd.core.gridmap import get_map, reset_map
from dnd.core.events import EventQueue, EventType, RangeType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import (
    EquipmentConfig, Weapon, BodyArmor, Shield,
    WeaponSlot, WeaponProperty, ArmorType, BodyPart, Range
)
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.modifiers import DamageType
from dnd.actions import Attack, AttackEvent, Move
from dnd.conditions import Poisoned, Prone, Dodging

# Use bestiary for goblin and skeleton
from dnd.monsters.bestiary import create_goblin, create_skeleton

from server.event_server import app, event_monitor


# Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
TURN_DELAY = 6.0  # seconds between turns
ACTION_DELAY = 1.5  # seconds between actions within a turn


def clear_state():
    """Clear all game state for fresh scenario."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    EventQueue._events_by_lineage.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_timestamp.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._all_events.clear()
    EventQueue._event_handlers.clear()
    EventQueue._event_handlers_by_trigger.clear()
    EventQueue._event_handlers_by_simple_trigger.clear()
    EventQueue._event_handlers_by_source_entity_uuid.clear()
    # Don't clear callbacks - we need the monitor


def create_arena():
    """Create a 20x20 arena with some obstacles."""
    grid = get_map()

    # Main floor
    grid.create_rectangle(0, 0, 20, 20, walkable=True, visible=True, name="Arena Floor")

    # Add some pillars (obstacles)
    pillars = [(5, 5), (5, 14), (14, 5), (14, 14), (10, 10)]
    for x, y in pillars:
        grid.set_tile(x, y, walkable=False, visible=False, name="Pillar")

    print(f"Arena created: {grid.size[0]}x{grid.size[1]} with {len(pillars)} pillars")
    return grid


def create_longsword(source_id) -> Weapon:
    """Creates a longsword - 1d8 slashing, versatile"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Longsword",
        description="A well-crafted knight's sword.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_plate_armor(source_id) -> BodyArmor:
    """Creates plate armor - AC 18, no dex bonus"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Plate Armor",
        description="Full plate armor providing excellent protection.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=18,
            value_name="Armor Class"
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,  # No dex bonus for heavy armor
            value_name="Max Dex Bonus"
        )
    )


def create_steel_shield(source_id) -> Shield:
    """Creates a steel shield - +2 AC"""
    return Shield(
        source_entity_uuid=source_id,
        name="Steel Shield",
        description="A sturdy steel shield.",
        ac_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=2,
            value_name="Shield AC Bonus"
        )
    )


def create_knight(name: str = "Knight", position: Tuple[int, int] = (0, 0)) -> Entity:
    """Create a human knight (CR 3)."""
    source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=16),
        dexterity=AbilityConfig(ability_score=11),
        constitution=AbilityConfig(ability_score=14),
        intelligence=AbilityConfig(ability_score=11),
        wisdom=AbilityConfig(ability_score=11),
        charisma=AbilityConfig(ability_score=15)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=10,
            hit_dice_count=8,
            mode="average",
            ignore_first_level=False
        )]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A noble knight in shining armor.",
        config=entity_config
    )

    # Equip gear
    longsword = create_longsword(entity.uuid)
    plate = create_plate_armor(entity.uuid)
    shield = create_steel_shield(entity.uuid)

    entity.equipment.equip(plate)
    entity.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    return entity


def log_action(message: str):
    """Print action with timestamp."""
    print(f"\n>>> {message}")


def log_result(message: str):
    """Print result."""
    print(f"    {message}")


def get_entity_status(entity: Entity) -> str:
    """Get entity status string."""
    current_hp = entity.get_hp()
    damage = entity.health.damage_taken
    conditions = list(entity.active_conditions.keys())
    cond_str = f" [{', '.join(conditions)}]" if conditions else ""
    return f"{entity.name}: {current_hp} HP (damage: {damage}){cond_str} at {entity.position}"


def perform_attack(attacker: Entity, target: Entity):
    """Perform an attack action."""
    log_action(f"{attacker.name} attacks {target.name}!")

    # Reset action economy if needed
    if not attacker.action_economy.can_afford("actions", 1):
        attacker.action_economy.reset_all_costs()

    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        name=f"{attacker.name}'s Attack"
    )
    event = attack.apply()

    if event is None:
        log_result(f"Attack returned no event")
    elif event.canceled:
        log_result(f"Attack failed: {event.status_message}")
    elif isinstance(event, AttackEvent):
        outcome = event.attack_outcome.value if event.attack_outcome else "unknown"
        log_result(f"Attack roll: {outcome}")
        if event.damage_rolls:
            total_damage = sum(r.total for r in event.damage_rolls)
            log_result(f"Damage dealt: {total_damage}")

    log_result(get_entity_status(target))


def perform_move(entity: Entity, new_position: tuple):
    """Move an entity to a new position."""
    old_pos = entity.position
    log_action(f"{entity.name} moves from {old_pos} to {new_position}")

    # Update senses first to get valid paths
    entity.update_entity_senses(max_distance=15)

    move = Move(
        source_entity_uuid=entity.uuid,
        end_position=new_position,
        name=f"{entity.name}'s Movement"
    )
    event = move.apply()

    if event is None:
        log_result(f"Move returned no event")
        Entity.update_entity_position(entity, new_position)
        log_result(f"(Teleported for demo purposes)")
    elif event.canceled:
        log_result(f"Move failed: {event.status_message}")
        # Fall back to direct position update for demo
        Entity.update_entity_position(entity, new_position)
        log_result(f"(Teleported for demo purposes)")
    else:
        log_result(f"Moved successfully")


def apply_condition(entity: Entity, condition_class, source: Optional[Entity] = None, **kwargs):
    """Apply a condition to an entity."""
    source_uuid = source.uuid if source else entity.uuid
    condition = condition_class(
        source_entity_uuid=source_uuid,
        target_entity_uuid=entity.uuid,
        **kwargs
    )
    log_action(f"{entity.name} becomes {condition.name}!")
    entity.add_condition(condition)
    log_result(get_entity_status(entity))


def run_combat_scenario():
    """Run the full combat scenario."""
    print("\n" + "=" * 60)
    print("COMBAT SCENARIO: Arena Battle")
    print("=" * 60)
    print(f"\nWebSocket server running at ws://localhost:{SERVER_PORT}/ws")
    print("Connect a client to watch events in real-time!\n")

    # Setup
    clear_state()
    create_arena()

    # Create combatants
    print("\n--- Combatants Enter the Arena ---")
    time.sleep(ACTION_DELAY)

    knight = create_knight(name="Sir Roland", position=(2, 10))
    log_result(get_entity_status(knight))
    time.sleep(ACTION_DELAY)

    goblin1 = create_goblin(name="Gruk", position=(17, 8))
    log_result(get_entity_status(goblin1))
    time.sleep(ACTION_DELAY)

    goblin2 = create_goblin(name="Snik", position=(17, 12))
    log_result(get_entity_status(goblin2))
    time.sleep(ACTION_DELAY)

    skeleton = create_skeleton(name="Bones", position=(10, 2))
    log_result(get_entity_status(skeleton))
    time.sleep(ACTION_DELAY)

    # Update all senses
    Entity.update_all_entities_senses(max_distance=15)

    print("\n" + "=" * 60)
    print("ROUND 1")
    print("=" * 60)
    time.sleep(TURN_DELAY)

    # Turn 1: Knight moves toward goblins
    print("\n--- Sir Roland's Turn ---")
    perform_move(knight, (6, 10))
    time.sleep(ACTION_DELAY)
    apply_condition(knight, Dodging)  # Takes dodge action
    time.sleep(TURN_DELAY)

    # Turn 2: Goblin 1 moves and attacks
    print("\n--- Gruk's Turn ---")
    perform_move(goblin1, (12, 9))
    time.sleep(ACTION_DELAY)
    # Can't reach knight yet, dashes
    perform_move(goblin1, (8, 9))
    time.sleep(TURN_DELAY)

    # Turn 3: Goblin 2 flanks
    print("\n--- Snik's Turn ---")
    perform_move(goblin2, (12, 11))
    time.sleep(ACTION_DELAY)
    perform_move(goblin2, (8, 11))
    time.sleep(TURN_DELAY)

    # Turn 4: Skeleton advances
    print("\n--- Bones' Turn ---")
    perform_move(skeleton, (10, 6))
    time.sleep(ACTION_DELAY)
    perform_move(skeleton, (10, 9))
    time.sleep(TURN_DELAY)

    print("\n" + "=" * 60)
    print("ROUND 2")
    print("=" * 60)
    time.sleep(TURN_DELAY)

    # Knight engages goblin 1
    print("\n--- Sir Roland's Turn ---")
    knight.remove_condition("Dodging")  # Dodge ends
    perform_move(knight, (7, 9))
    time.sleep(ACTION_DELAY)
    perform_attack(knight, goblin1)
    time.sleep(TURN_DELAY)

    # Goblin 1 is poisoned (from a previous trap, narrative)
    print("\n--- Gruk's Turn ---")
    apply_condition(goblin1, Poisoned)
    time.sleep(ACTION_DELAY)
    perform_attack(goblin1, knight)  # Disadvantage from poison
    time.sleep(TURN_DELAY)

    # Goblin 2 attacks from other side
    print("\n--- Snik's Turn ---")
    perform_move(goblin2, (7, 11))
    time.sleep(ACTION_DELAY)
    perform_move(goblin2, (7, 10))  # Adjacent to knight
    time.sleep(ACTION_DELAY)
    perform_attack(goblin2, knight)
    time.sleep(TURN_DELAY)

    # Skeleton joins the fray
    print("\n--- Bones' Turn ---")
    perform_move(skeleton, (8, 10))
    time.sleep(ACTION_DELAY)
    perform_attack(skeleton, knight)
    time.sleep(TURN_DELAY)

    print("\n" + "=" * 60)
    print("ROUND 3")
    print("=" * 60)
    time.sleep(TURN_DELAY)

    # Knight fights back
    print("\n--- Sir Roland's Turn ---")
    perform_attack(knight, goblin1)
    time.sleep(ACTION_DELAY)
    # Bonus action: knight knocks goblin 2 prone
    apply_condition(goblin2, Prone)
    time.sleep(TURN_DELAY)

    # Goblin 1 retreats (still poisoned)
    print("\n--- Gruk's Turn ---")
    perform_move(goblin1, (9, 8))
    time.sleep(ACTION_DELAY)
    # Uses action to recover (removes poison)
    goblin1.remove_condition("Poisoned")
    log_action(f"{goblin1.name} shakes off the poison!")
    log_result(get_entity_status(goblin1))
    time.sleep(TURN_DELAY)

    # Goblin 2 is prone, attacks with disadvantage
    print("\n--- Snik's Turn ---")
    perform_attack(goblin2, knight)  # Disadvantage from prone
    time.sleep(ACTION_DELAY)
    # Stands up (costs movement)
    goblin2.remove_condition("Prone")
    log_action(f"{goblin2.name} stands up!")
    time.sleep(TURN_DELAY)

    # Skeleton continues attacking
    print("\n--- Bones' Turn ---")
    perform_attack(skeleton, knight)
    time.sleep(TURN_DELAY)

    print("\n" + "=" * 60)
    print("ROUND 4 - FINALE")
    print("=" * 60)
    time.sleep(TURN_DELAY)

    # Knight goes all out
    print("\n--- Sir Roland's Turn ---")
    perform_attack(knight, skeleton)
    time.sleep(ACTION_DELAY)
    perform_attack(knight, goblin2)  # Extra attack
    time.sleep(TURN_DELAY)

    # Final status
    print("\n" + "=" * 60)
    print("BATTLE STATUS")
    print("=" * 60)
    for entity in Entity.get_all_entities():
        print(f"  {get_entity_status(entity)}")

    print("\n" + "=" * 60)
    print("EVENT SUMMARY")
    print("=" * 60)
    print(f"Total events generated: {len(EventQueue._all_events)}")
    print("Events by type:")
    for et in EventType:
        count = len(EventQueue.get_events_by_type(et))
        if count > 0:
            print(f"  {et.value}: {count}")

    print("\n" + "=" * 60)
    print("SCENARIO COMPLETE")
    print("=" * 60)


def run_server_in_background():
    """Run the FastAPI server in a background thread."""
    config = uvicorn.Config(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="warning"  # Reduce noise
    )
    server = uvicorn.Server(config)

    # Run in a thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Give server time to start
    time.sleep(1.0)

    return server, thread


def main():
    """Main entry point."""
    print("=" * 60)
    print("LIVE COMBAT SCENARIO")
    print("=" * 60)

    # Start the event monitor
    event_monitor.start()

    # Start server in background
    print(f"\nStarting websocket server on port {SERVER_PORT}...")
    _server, _thread = run_server_in_background()
    print(f"Server running at http://localhost:{SERVER_PORT}")
    print(f"WebSocket at ws://localhost:{SERVER_PORT}/ws")

    print("\n" + "-" * 60)
    print("TIP: In another terminal, run:")
    print("  python -m server.test_client")
    print("to watch events in real-time!")
    print("-" * 60)

    # Wait a moment for user to connect client
    print("\nStarting combat in 5 seconds...")
    time.sleep(5)

    try:
        # Run the scenario
        run_combat_scenario()

        # Keep server running for a bit after scenario ends
        print("\nServer will stay running for 30 more seconds...")
        print("Press Ctrl+C to exit early.")
        time.sleep(30)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        event_monitor.stop()
        print("Shutting down...")


if __name__ == "__main__":
    main()
