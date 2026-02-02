"""
Test Extra Attack in PvP-like scenario where turns alternate between entities.

This test simulates the server's turn management to debug why Extra Attack
stops working after the first use.
"""
from uuid import uuid4
from dnd.entity import Entity
from dnd.core.gridmap import get_map, reset_map
from dnd.core.events import EventQueue
from dnd.actions_functional import setup_standard_actions, execute_by_index, get_available_actions
from dnd.monsters.bestiary import create_skeleton
from dnd.classes.fighter import ExtraAttackFeature
from dnd.encounter import Encounter, TurnState
from dnd.controller import HumanController


def reset_state() -> None:
    """Reset all state between tests."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    EventQueue._all_events.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._event_handlers.clear()
    EventQueue._event_handlers_by_trigger.clear()
    EventQueue._event_handlers_by_simple_trigger.clear()
    EventQueue._event_handlers_by_source_entity_uuid.clear()
    reset_map()

    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


def advance_to_next_turn(encounter: Encounter) -> None:
    """Simulate server's turn advancement logic."""
    encounter.current_turn_index += 1
    if encounter.current_turn_index >= len(encounter.initiative_order):
        encounter._advance_round()
    encounter.turn_state = TurnState.NOT_STARTED


def test_pvp_extra_attack() -> None:
    """Test Extra Attack works across multiple turns."""
    print("=" * 60)
    print("Testing Extra Attack in PvP-like scenario")
    print("=" * 60)
    print()

    reset_state()

    # Create a skeleton with Extra Attack (simulating a Level 5 Fighter)
    hero = create_skeleton(name="Hero", position=(0, 0))
    setup_standard_actions(hero)
    hero.add_condition(ExtraAttackFeature(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        extra_attacks=1
    ))

    # Create target
    target = create_skeleton(name="Target", position=(1, 0))
    setup_standard_actions(target)

    # Setup encounter
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))

    Entity.update_all_entities_senses(max_distance=20)

    # Roll initiative and start
    encounter.roll_initiative()
    encounter.start_encounter()

    # Force Hero to go first by finding their position
    hero_index = None
    for i, entity_uuid in enumerate(encounter.initiative_order):
        if entity_uuid == hero.uuid:
            hero_index = i
            break

    assert hero_index is not None, "Hero should be found in initiative order"
    if hero_index != 0:
        # Swap to put hero first
        encounter.initiative_order[0], encounter.initiative_order[hero_index] = \
            encounter.initiative_order[hero_index], encounter.initiative_order[0]

    entity_names = [e.name for uid in encounter.initiative_order if (e := Entity.get(uid)) is not None]
    print(f"Initiative order: {entity_names}")
    print()

    # === TURN 1 (Hero) ===
    print("=" * 40)
    print("TURN 1 (Hero)")
    print("=" * 40)
    encounter.start_turn()

    # Check conditions before attack
    print(f"HasAttacked before attack: {'HasAttacked' in hero.active_conditions}")
    extra_attacks = hero.action_economy.resources.get("extra_attacks")
    print(f"extra_attacks resource: {extra_attacks.current if extra_attacks else 'N/A'}")

    # Attack
    actions = get_available_actions(hero)
    attack_actions = [a for a in actions.entity_actions
                      if "Attack" in a.template_name and "Extra" not in a.template_name]

    if attack_actions:
        print(f"\nExecuting: {attack_actions[0].template_name}")
        result = execute_by_index(hero, attack_actions[0].template_name, 0)
        print(f"Result: {result.status_message if result else 'None'}")

    # Check after attack
    print(f"\nHasAttacked after attack: {'HasAttacked' in hero.active_conditions}")
    extra_attacks = hero.action_economy.resources.get("extra_attacks")
    print(f"extra_attacks after attack: {extra_attacks.current if extra_attacks else 'N/A'}")

    # Check for Extra Attack availability
    actions = get_available_actions(hero)
    extra_attack_actions = [a for a in actions.entity_actions if "Extra Attack" in a.template_name]
    print(f"Extra Attack available: {len(extra_attack_actions) > 0}")

    if extra_attack_actions:
        # Use Extra Attack
        print(f"\nExecuting: {extra_attack_actions[0].template_name}")
        result = execute_by_index(hero, extra_attack_actions[0].template_name, 0)
        print(f"Result: {result.status_message if result else 'None'}")
        extra_attacks = hero.action_economy.resources.get("extra_attacks")
        print(f"extra_attacks after Extra Attack: {extra_attacks.current if extra_attacks else 'N/A'}")

    # End Hero's turn
    encounter.end_turn()
    print()

    # === TURN 2 (Target) ===
    print("=" * 40)
    print("TURN 2 (Target)")
    print("=" * 40)
    advance_to_next_turn(encounter)
    encounter.start_turn()  # Target's turn
    print(f"Hero's HasAttacked during target's turn: {'HasAttacked' in hero.active_conditions}")
    encounter.end_turn()
    print()

    # === TURN 3 (Hero again) ===
    print("=" * 40)
    print("TURN 3 (Hero)")
    print("=" * 40)
    advance_to_next_turn(encounter)
    encounter.start_turn()  # Hero's turn again

    # Check conditions at turn start
    print(f"HasAttacked at turn start: {'HasAttacked' in hero.active_conditions}")
    extra_attacks = hero.action_economy.resources.get("extra_attacks")
    print(f"extra_attacks at turn start: {extra_attacks.current if extra_attacks else 'N/A'}")

    # Attack again
    actions = get_available_actions(hero)
    attack_actions = [a for a in actions.entity_actions
                      if "Attack" in a.template_name and "Extra" not in a.template_name]

    if attack_actions:
        print(f"\nExecuting: {attack_actions[0].template_name}")
        result = execute_by_index(hero, attack_actions[0].template_name, 0)
        print(f"Result: {result.status_message if result else 'None'}")

    # Check after attack
    print(f"\nHasAttacked after attack: {'HasAttacked' in hero.active_conditions}")
    extra_attacks = hero.action_economy.resources.get("extra_attacks")
    print(f"extra_attacks after attack: {extra_attacks.current if extra_attacks else 'N/A'}")

    # Check for Extra Attack availability
    actions = get_available_actions(hero)
    extra_attack_actions = [a for a in actions.entity_actions if "Extra Attack" in a.template_name]
    print(f"Extra Attack available: {len(extra_attack_actions) > 0}")

    print()
    print("=" * 60)
    if extra_attack_actions:
        print("SUCCESS: Extra Attack is available on turn 3!")
    else:
        print("FAILURE: Extra Attack NOT available on turn 3!")
        # Debug info
        print()
        print("Debug info:")
        print(f"  EventQueue handlers: {len(EventQueue._event_handlers)}")
        for _, handler in EventQueue._event_handlers.items():
            print(f"    Handler: {handler.name}, source: {handler.source_entity_uuid}")
        print(f"  Hero active conditions: {list(hero.active_conditions.keys())}")
        print(f"  Hero resources: {list(hero.action_economy.resources.keys())}")
    print("=" * 60)


if __name__ == "__main__":
    test_pvp_extra_attack()
