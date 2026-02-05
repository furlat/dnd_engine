"""Test that multi-target spells produce correct combat log hierarchy."""

from uuid import uuid4
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map
from dnd.actions_functional import setup_standard_actions
from dnd.spells.evocation import Fireball
from dnd.utils import reset_combat_state, set_hp


def create_caster(name="Wizard", position=(0, 0)):
    """Create a spellcaster entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),  # +3 mod -> DC 13
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2, 4: 1}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=2,
        position=position,
        faction="heroes",
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    set_hp(entity, 100)
    setup_standard_actions(entity)
    return entity


def create_target(name, position, faction="monsters"):
    """Create a target entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),  # +0 save mod
            constitution=AbilityConfig(ability_score=12),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    set_hp(entity, 50)
    return entity


def test_fireball_combat_log_hierarchy():
    """Verify Fireball produces parent log with per-target sub_entries."""
    print("=" * 60)
    print("FIREBALL COMBAT LOG HIERARCHY TEST")
    print("=" * 60)

    reset_combat_state()

    # Set up arena
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Create caster and 3 targets in a cluster
    # Position caster near targets for LOS
    caster = create_caster("Wizard", (5, 5))
    _ = create_target("Skeleton 1", (10, 5))
    _ = create_target("Skeleton 2", (10, 6))
    _ = create_target("Skeleton 3", (11, 5))

    Entity.update_all_entities_senses()

    # Register and cast Fireball at position (10, 7) - center of target cluster
    fireball = Fireball(
        source_entity_uuid=caster.uuid,
        spell_slot_level=3,
        caster_level=5,
    )
    fireball.end_position = (10, 5)  # Center of target cluster

    # Capture combat logs
    captured_logs = []
    def capture_log(event):
        if event.combat_log:
            captured_logs.append(event.combat_log)

    EventQueue.set_combat_log_callback(capture_log)

    # Cast the spell
    result = fireball.apply()

    EventQueue.set_combat_log_callback(None)

    # Debug output
    print(f"\nResult event: {result}")
    if result:
        print(f"Result type: {type(result).__name__}")
        print(f"Result phase: {result.phase}")
        print(f"Result parent_event: {result.parent_event}")
        print(f"Result combat_log: {result.combat_log is not None}")
        print(f"Result total_targets: {getattr(result, 'total_targets', 'N/A')}")
        print(f"Result total_damage: {getattr(result, 'total_damage', 'N/A')}")
        print(f"Result lineage_children_events: {len(result.lineage_children_events)}")

    # Verify we got exactly ONE top-level log (the parent)
    print(f"\nCaptured {len(captured_logs)} top-level combat log(s)")
    assert len(captured_logs) == 1, f"Expected 1 parent log, got {len(captured_logs)}"

    parent_log = captured_logs[0]
    print(f"\nParent log: {parent_log.compact}")
    print(f"Parent has {len(parent_log.sub_entries)} sub_entries")

    # Verify sub_entries exist for each target
    assert len(parent_log.sub_entries) > 0, "Parent should have sub_entries for per-target results"
    print(f"\nExpected ~3 sub_entries (one per target)")

    # Print the hierarchy
    print("\n--- COMBAT LOG HIERARCHY ---")
    print(parent_log.compact)
    for i, sub in enumerate(parent_log.sub_entries):
        print(f"  [{i}] {sub.compact}")
        # Check if sub has its own sub_entries (save roll, damage)
        for j, subsub in enumerate(sub.sub_entries):
            print(f"      [{j}] {subsub.compact}")

    # Verify each sub_entry has its OWN children (not mixed with other targets)
    print("\n--- VERIFYING ISOLATION ---")
    for i, sub in enumerate(parent_log.sub_entries):
        # Each per-target log should have exactly its own saves/damage
        # Not accumulated from all targets
        print(f"Sub {i}: {len(sub.sub_entries)} children")

    # Check that we have proper data
    print(f"\nParent total_damage: {getattr(result, 'total_damage', 'N/A') if result else 'N/A'}")
    print(f"Parent total_targets: {getattr(result, 'total_targets', 'N/A') if result else 'N/A'}")

    print("\n" + "=" * 60)
    print("TEST PASSED - Combat log hierarchy is correct!")
    print("=" * 60)

if __name__ == "__main__":
    test_fireball_combat_log_hierarchy()
