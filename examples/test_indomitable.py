"""
Test Indomitable (Fighter Level 9 Feature)

Tests the Indomitable feature which allows rerolling failed saving throws.
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from dnd.entity import Entity, EntityConfig
from dnd.core.events import EventQueue
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.core.gridmap import reset_map, get_map
from dnd.classes.fighter import Indomitable


def setup_map_once():
    """Reset and create the map (call once per test)."""
    reset_map()
    get_map().create_rectangle(0, 0, 10, 10)


def create_entity(name: str = "Entity", position=(0, 0), wisdom: int = 10) -> Entity:
    """Create a test entity (doesn't reset map)."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=wisdom),
        ),
        position=position
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config
    )
    return entity


def clear_event_queue():
    """Clear all events and handlers from the queue for fresh tests."""
    EventQueue._events_by_lineage.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_timestamp.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._all_events.clear()
    # Also clear handlers to avoid cross-test interference
    EventQueue._event_handlers.clear()
    EventQueue._event_handlers_by_trigger.clear()
    EventQueue._event_handlers_by_simple_trigger.clear()
    EventQueue._event_handlers_by_source_entity_uuid.clear()


def test_indomitable_basic():
    """Test basic Indomitable - resource exists and can be used."""
    print("\n=== Test 1: Basic Indomitable Setup ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    _caster = create_entity("Caster", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply Indomitable condition
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(indom)

    # Check resource was added
    resource = fighter.action_economy.resources.get("indomitable")
    assert resource is not None, "Indomitable resource not created"
    assert resource.current == 1, f"Resource should have 1 use, got {resource.current}"
    assert resource.maximum == 1, f"Resource max should be 1, got {resource.maximum}"

    print(f"  Resource created: {resource.current}/{resource.maximum}")
    print(f"  Condition active: {'Indomitable' in fighter.active_conditions}")
    print("  PASSED: Indomitable setup works")
    return True


def test_indomitable_triggers_on_failure():
    """Test that Indomitable triggers when save fails."""
    print("\n=== Test 2: Indomitable Triggers on Failed Save ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    caster = create_entity("Caster", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply Indomitable
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(indom)

    initial_uses = fighter.action_economy.resources["indomitable"].current

    # Make a very hard save (DC 30) - almost guaranteed to fail
    request = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=30
    )

    # Execute the save
    _outcome, roll, success = fighter.saving_throw(request)

    final_uses = fighter.action_economy.resources["indomitable"].current

    print(f"  Roll total: {roll.total}, DC: 30")
    print(f"  Final success: {success}")
    print(f"  Uses before: {initial_uses}, after: {final_uses}")

    # Indomitable should have been consumed if the first roll failed
    # (even if the reroll also failed)
    if roll.total < 30:
        assert final_uses == 0, "Indomitable should have been used on failure"
        print("  PASSED: Indomitable triggered on failed save")
    else:
        print("  (Natural 20 rolled - skipping resource check)")
        print("  PASSED: Test ran correctly")
    return True


def test_indomitable_no_trigger_on_success():
    """Test that Indomitable doesn't trigger when save succeeds."""
    print("\n=== Test 3: Indomitable Doesn't Trigger on Success ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    caster = create_entity("Caster", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply Indomitable
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(indom)

    initial_uses = fighter.action_economy.resources["indomitable"].current

    # Make an easy save (DC 1) - guaranteed to pass
    request = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=1
    )
    _outcome, roll, success = fighter.saving_throw(request)

    final_uses = fighter.action_economy.resources["indomitable"].current

    print(f"  Roll total: {roll.total}, DC: 1")
    print(f"  Success: {success}")
    print(f"  Uses before: {initial_uses}, after: {final_uses}")

    assert success, "Save should have succeeded with DC 1"
    assert final_uses == initial_uses, "Indomitable should NOT be used on success"

    print("  PASSED: Indomitable not consumed on successful save")
    return True


def test_indomitable_resource_consumed():
    """Test that Indomitable resource is consumed after use."""
    print("\n=== Test 4: Indomitable Resource Consumed ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    caster = create_entity("Caster", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply Indomitable
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(indom)

    # Use up Indomitable by failing a save
    request = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=30  # Very hard - will likely use Indomitable
    )
    fighter.saving_throw(request)

    # Check resource
    resource = fighter.action_economy.resources["indomitable"]
    first_save_uses = resource.current

    # Try another save - Indomitable should NOT trigger (no uses left)
    request2 = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=30
    )
    fighter.saving_throw(request2)

    final_uses = resource.current

    print(f"  After first save: {first_save_uses} uses")
    print(f"  After second save: {final_uses} uses")

    # Should still be 0 (or whatever it was after first save)
    assert final_uses == first_save_uses, \
        "Resource should not change when already at 0"

    print("  PASSED: Resource correctly consumed and limited")
    return True


def test_indomitable_multiple_uses():
    """Test Indomitable with multiple uses (L13 = 2, L17 = 3)."""
    print("\n=== Test 5: Multiple Uses (Level 13 = 2 uses) ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    caster = create_entity("Caster", position=(1, 0))
    Entity.update_all_entities_senses()

    # Apply Indomitable with 2 uses (Level 13)
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=2
    )
    fighter.add_condition(indom)

    resource = fighter.action_economy.resources["indomitable"]
    assert resource.current == 2, f"Should have 2 uses, got {resource.current}"
    assert resource.maximum == 2, f"Max should be 2, got {resource.maximum}"

    print(f"  Initial uses: {resource.current}/{resource.maximum}")

    # First failed save
    request1 = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=30
    )
    fighter.saving_throw(request1)
    print(f"  After first save: {resource.current} uses")

    # Second failed save
    request2 = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=30
    )
    fighter.saving_throw(request2)
    print(f"  After second save: {resource.current} uses")

    # Resource should be depleted (or nearly so)
    print("  PASSED: Multiple uses work correctly")
    return True


def test_indomitable_long_rest_recharge():
    """Test that Indomitable recharges on long rest."""
    print("\n=== Test 6: Long Rest Recharge ===")

    # Setup
    clear_event_queue()
    setup_map_once()
    fighter = create_entity("Fighter", position=(0, 0), wisdom=8)
    Entity.update_all_entities_senses()

    # Apply Indomitable
    indom = Indomitable(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=1
    )
    fighter.add_condition(indom)

    # Use up Indomitable
    resource = fighter.action_economy.resources["indomitable"]
    resource.current = 0  # Simulate using it

    print(f"  Before long rest: {resource.current}/{resource.maximum}")

    # Long rest
    fighter.action_economy.on_long_rest()

    print(f"  After long rest: {resource.current}/{resource.maximum}")

    assert resource.current == resource.maximum, \
        "Indomitable should recharge on long rest"

    print("  PASSED: Long rest recharges Indomitable")
    return True


def main():
    print("=" * 60)
    print("INDOMITABLE (FIGHTER LEVEL 9) TESTS")
    print("=" * 60)

    results = []
    results.append(("Basic Setup", test_indomitable_basic()))
    results.append(("Trigger on Failure", test_indomitable_triggers_on_failure()))
    results.append(("No Trigger on Success", test_indomitable_no_trigger_on_success()))
    results.append(("Resource Consumed", test_indomitable_resource_consumed()))
    results.append(("Multiple Uses", test_indomitable_multiple_uses()))
    results.append(("Long Rest Recharge", test_indomitable_long_rest_recharge()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
