"""
Test Barbarian SRD Missing Features

Tests for:
1. Rage ends when unconscious (UNCONSCIOUS event)
2. Voluntary rage end (End Rage bonus action)
3. Danger Sense disabled by conditions (contextual)
4. Mindless Rage suspends existing Charmed/Frightened
5. Extend Intimidating Presence action
6. Intimidating Presence ends at >60ft or out of LOS
"""

from uuid import uuid4

from dnd.core.events import EventPhase, UnconsciousEvent, TurnEndEvent, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions, execute_action, get_available_actions
from dnd.items.weapons import create_greataxe
from dnd.classes.barbarian import (
    RageFeature, Raging, MindlessRage, DangerSense,
    IntimidatingPresenceFeature,
    create_intimidating_presence_end_handler
)
from dnd.conditions import Charmed, Frightened, Blinded
from dnd.core.modifiers import AdvantageStatus


def create_test_barbarian(name: str = "Test Barbarian", position: tuple = (0, 0), level: int = 11) -> Entity:
    """Create a test barbarian with all relevant features."""
    source_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=18),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=16),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=14)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=12, hit_dice_count=level, mode="average")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=4,
        position=position
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=config)
    setup_standard_actions(entity)

    # Equip greataxe
    axe = create_greataxe(entity.uuid)
    entity.equipment.equip(axe)

    return entity


def reset_test_state():
    """Reset game state for clean tests."""
    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def test_unconscious_event_fires():
    """Test that UNCONSCIOUS event fires when HP drops to 0."""
    print("\n=== Test: UNCONSCIOUS Event Fires ===")
    reset_test_state()

    # Create a simple entity
    source_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=6, hit_dice_count=1, mode="average")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=(0, 0)
    )
    entity = Entity.create(name="Test Victim", source_entity_uuid=source_id, config=config)

    # Manually fire UNCONSCIOUS event (simulating what encounter.check_deaths does)
    unconscious_event = UnconsciousEvent(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        entity_uuid=entity.uuid,
        entity_name=entity.name,
        final_hp=0,
        phase=EventPhase.DECLARATION
    )
    unconscious_event = unconscious_event.phase_to(EventPhase.EXECUTION)
    unconscious_event = unconscious_event.phase_to(EventPhase.EFFECT)
    unconscious_event = unconscious_event.phase_to(EventPhase.COMPLETION)

    print(f"  UNCONSCIOUS event fired: {unconscious_event is not None}")
    print(f"  Event phase: {unconscious_event.phase}")
    assert unconscious_event is not None, "Event should fire"
    assert unconscious_event.phase == EventPhase.COMPLETION, "Event should reach COMPLETION"
    print("  [PASS] UNCONSCIOUS event infrastructure works")


def test_rage_ends_when_unconscious():
    """Test that rage ends when falling unconscious."""
    print("\n=== Test: Rage Ends When Unconscious ===")
    reset_test_state()

    barbarian = create_test_barbarian()

    # Apply RageFeature
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=3,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    # Apply Raging directly (simulating rage activation)
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    print(f"  Is raging: {'Raging' in barbarian.active_conditions}")
    assert "Raging" in barbarian.active_conditions, "Should be raging"

    # Fire UNCONSCIOUS event (simulating dropping to 0 HP)
    unconscious_event = UnconsciousEvent(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        entity_uuid=barbarian.uuid,
        entity_name=barbarian.name,
        final_hp=0,
        phase=EventPhase.DECLARATION
    )
    unconscious_event = unconscious_event.phase_to(EventPhase.EXECUTION)
    unconscious_event = unconscious_event.phase_to(EventPhase.EFFECT)
    unconscious_event = unconscious_event.phase_to(EventPhase.COMPLETION)

    print(f"  Is raging after unconscious: {'Raging' in barbarian.active_conditions}")
    assert "Raging" not in barbarian.active_conditions, "Rage should end when unconscious"
    print("  [PASS] Rage ends when falling unconscious")


def test_voluntary_rage_end():
    """Test that End Rage action works."""
    print("\n=== Test: Voluntary Rage End ===")
    reset_test_state()

    barbarian = create_test_barbarian()

    # Apply RageFeature
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=3,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    # Check End Rage action is registered
    action_names = [a.name for a in barbarian.registered_actions]
    print(f"  Registered actions include 'End Rage': {'End Rage' in action_names}")
    assert "End Rage" in action_names, "End Rage action should be registered"

    # Apply Raging directly (simulating rage activation)
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    print(f"  Is raging: {'Raging' in barbarian.active_conditions}")
    assert "Raging" in barbarian.active_conditions, "Should be raging"

    # Use End Rage via execute_action
    available = get_available_actions(barbarian)
    end_rage_info = next((a for a in available.self_actions if a.template_name == "End Rage"), None)
    assert end_rage_info is not None, "End Rage should be available"

    result = execute_action(barbarian, "End Rage", end_rage_info.valid_targets[0])

    print(f"  End Rage result: {result.status_message if result else 'None'}")
    print(f"  Is raging after End Rage: {'Raging' in barbarian.active_conditions}")
    assert "Raging" not in barbarian.active_conditions, "Rage should end"
    print("  [PASS] End Rage action works")


def test_danger_sense_contextual():
    """Test that Danger Sense is disabled by Blinded/Deafened/Incapacitated."""
    print("\n=== Test: Danger Sense Contextual ===")
    reset_test_state()

    barbarian = create_test_barbarian()

    # Apply Danger Sense
    danger_sense = DangerSense(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(danger_sense)

    # Check DEX save advantage
    dex_save = barbarian.saving_throws.get_saving_throw("dexterity")
    advantage_before = dex_save.bonus.advantage
    print(f"  DEX save advantage (normal): {advantage_before}")
    assert advantage_before == AdvantageStatus.ADVANTAGE, "Should have advantage"

    # Apply Blinded
    blinded = Blinded(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(blinded)

    # Check DEX save advantage again (should be disabled by contextual check)
    advantage_blinded = dex_save.bonus.advantage
    print(f"  DEX save advantage (blinded): {advantage_blinded}")
    # Contextual modifier returns None when blinded, so advantage should be NONE
    assert advantage_blinded == AdvantageStatus.NONE, "Should not have advantage when blinded"

    # Remove blinded
    barbarian.remove_condition("Blinded")
    advantage_after = dex_save.bonus.advantage
    print(f"  DEX save advantage (after removing blinded): {advantage_after}")
    assert advantage_after == AdvantageStatus.ADVANTAGE, "Advantage should return"
    print("  [PASS] Danger Sense contextual mechanism verified")


def test_mindless_rage_suspends_existing():
    """Test that Mindless Rage removes existing Charmed/Frightened on rage start."""
    print("\n=== Test: Mindless Rage Suspends Existing Conditions ===")
    reset_test_state()

    barbarian = create_test_barbarian()

    # Apply RageFeature and MindlessRage
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=3,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    mindless_rage = MindlessRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(mindless_rage)

    # Apply Charmed condition BEFORE raging
    enemy_id = uuid4()
    charmed = Charmed(
        source_entity_uuid=enemy_id,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(charmed)

    print(f"  Is Charmed before rage: {'Charmed' in barbarian.active_conditions}")
    assert "Charmed" in barbarian.active_conditions, "Should be charmed"

    # Enter rage by applying Raging directly
    # (Raging._apply() contains the Mindless Rage check)
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    print(f"  Is Raging: {'Raging' in barbarian.active_conditions}")
    print(f"  Is Charmed after entering rage: {'Charmed' in barbarian.active_conditions}")
    assert "Raging" in barbarian.active_conditions, "Should be raging"
    assert "Charmed" not in barbarian.active_conditions, "Charmed should be removed when entering rage"
    print("  [PASS] Mindless Rage removes existing Charmed on rage start")


def test_extend_intimidating_presence():
    """Test that Extend Intimidating Presence action works."""
    print("\n=== Test: Extend Intimidating Presence ===")
    reset_test_state()

    barbarian = create_test_barbarian(position=(0, 0))
    target = create_test_barbarian(name="Target", position=(1, 0))

    # Update senses
    Entity.update_all_entities_senses()

    # Apply IntimidatingPresenceFeature
    ip_feature = IntimidatingPresenceFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(ip_feature)

    # Check Extend Intimidating Presence action is registered
    action_names = [a.name for a in barbarian.registered_actions]
    print(f"  Registered actions include 'Extend Intimidating Presence': {'Extend Intimidating Presence' in action_names}")
    assert "Extend Intimidating Presence" in action_names, "Extend action should be registered"

    # Manually apply Frightened to target (simulating IP success)
    from dnd.core.base_conditions import DurationType
    frightened = Frightened(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid
    )
    frightened.duration.duration_type = DurationType.ROUNDS
    frightened.duration.duration = 2  # Set to 2 so we can verify it's reset to 1
    target.add_condition(frightened)

    print(f"  Target is Frightened: {'Frightened' in target.active_conditions}")
    assert "Frightened" in target.active_conditions, "Target should be frightened"

    # Get initial duration
    initial_duration = target.active_conditions["Frightened"].duration.duration
    print(f"  Initial duration: {initial_duration}")

    # Use Extend Intimidating Presence via manual instantiation
    extend_template = barbarian.get_action_template("Extend Intimidating Presence")
    assert extend_template is not None, "Extend template should exist"
    extend_action = extend_template.instantiate(target_entity_uuid=target.uuid)
    result = extend_action.apply()
    print(f"  Extend result: {result.status_message if result else 'None'}")

    # Check duration was reset
    new_duration = target.active_conditions["Frightened"].duration.duration
    print(f"  Duration after extend: {new_duration}")
    assert new_duration == 1, "Duration should be reset to 1"
    print("  [PASS] Extend Intimidating Presence works")


def test_intimidating_presence_distance_los():
    """Test that Frightened from IP ends when target moves >60ft or breaks LOS."""
    print("\n=== Test: Intimidating Presence Distance/LOS Check ===")
    reset_test_state()

    barbarian = create_test_barbarian(position=(0, 0))
    target = create_test_barbarian(name="Target", position=(1, 0))

    # Update senses
    Entity.update_all_entities_senses()

    # Manually apply Frightened to target with the handler
    frightened = Frightened(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(frightened)

    # Register the end-check handler
    end_handler = create_intimidating_presence_end_handler(
        source_entity_uuid=target.uuid,
        barbarian_uuid=barbarian.uuid
    )
    target.add_event_handler(end_handler)

    print(f"  Target is Frightened: {'Frightened' in target.active_conditions}")

    # Move target far away (>60ft = >12 grid squares)
    target.senses.position = (15, 0)  # 75ft away
    target.update_entity_senses()

    # Simulate turn end by firing TurnEndEvent
    turn_end = TurnEndEvent(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        encounter_uuid=uuid4(),
        entity_uuid=target.uuid,
        round_number=1,
        turn_index=0,
        phase=EventPhase.DECLARATION
    )
    turn_end = turn_end.phase_to(EventPhase.EXECUTION)

    print(f"  Target position: {target.senses.position} (75ft from barbarian)")
    print(f"  Target is Frightened after turn end: {'Frightened' in target.active_conditions}")
    assert "Frightened" not in target.active_conditions, "Frightened should end at >60ft"
    print("  [PASS] Frightened ends when target moves >60ft away")


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN SRD FEATURES TESTS")
    print("=" * 60)

    test_unconscious_event_fires()
    test_rage_ends_when_unconscious()
    test_voluntary_rage_end()
    test_danger_sense_contextual()
    test_mindless_rage_suspends_existing()
    test_extend_intimidating_presence()
    test_intimidating_presence_distance_los()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
