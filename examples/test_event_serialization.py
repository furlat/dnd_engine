"""
Test that ALL events serialize to JSON without errors.

This is a regression test for the PydanticSerializationError caused by
Callable fields (score_normalizer, contextual modifier callables) embedded
in events via ModifiableValue objects.

The test creates a full arena combat, runs several turns to generate a wide
variety of event types (attacks, damage, saves, conditions, movement, spells),
then verifies every single event can be serialized with model_dump(mode='json').
"""

from dnd.utils import reset_combat_state
from dnd.core.events import EventQueue


def test_all_events_serialize(character_class: str):
    """Run arena combat and verify all events serialize.

    Returns (event_count, failures, event_types_seen).
    """
    reset_combat_state()

    from server.event_server import setup_arena_combat
    enc = setup_arena_combat(
        player_position=(2, 7), pvp_mode=False, character_class=character_class
    )
    enc.roll_initiative()
    enc.start_encounter()
    enc.start_turn()

    # Run several turns to generate diverse event types
    for _ in range(8):
        enc.end_turn()
        enc.check_deaths()
        if enc.state.value == 'ended':
            break
        enc.next_turn()

    # Test serialization of every event
    failed = []
    event_types_seen = set()
    for i, e in enumerate(EventQueue._all_events):
        event_types_seen.add(type(e).__name__)
        try:
            e.model_dump(mode='json')
        except Exception as ex:
            failed.append((i, type(e).__name__, str(ex)[:300]))

    return len(EventQueue._all_events), failed, event_types_seen


# =========================================================================
# Run tests
# =========================================================================

print("=" * 60)
print("EVENT SERIALIZATION REGRESSION TEST")
print("=" * 60)

all_types_seen = set()
total_events = 0
total_failed = []

for char_class in ["fighter", "barbarian", "sorcerer"]:
    print(f"\n--- Testing with {char_class} ---")
    count, failed, types_seen = test_all_events_serialize(char_class)
    total_events += count
    total_failed.extend(failed)
    all_types_seen |= types_seen

    if failed:
        print(f"  FAILED: {len(failed)} / {count} events")
        for idx, name, err in failed:
            print(f"    [{idx}] {name}: {err}")
    else:
        print(f"  OK: {count} events serialized")

print(f"\n--- Summary ---")
print(f"Total events tested: {total_events}")
print(f"Event types seen: {len(all_types_seen)}")
for t in sorted(all_types_seen):
    print(f"  - {t}")

if total_failed:
    print(f"\nFAILED: {len(total_failed)} events failed serialization!")
    for idx, name, err in total_failed:
        print(f"  [{idx}] {name}: {err}")
    assert False, f"{len(total_failed)} events failed serialization"
else:
    print(f"\nALL {total_events} EVENTS SERIALIZE OK")
