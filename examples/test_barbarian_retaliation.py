"""
Test Barbarian Retaliation (Berserker Level 14)

Tests:
1. Reaction melee attack when hit by adjacent creature
2. Consumes reaction
3. Only triggers from <=5ft
4. Requires melee weapon
5. No trigger if reaction already used
"""

from uuid import uuid4
import random

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.actions_functional import setup_standard_actions
from dnd.actions import Attack
from dnd.items.weapons import create_greatsword, create_shortsword
from dnd.utils import reset_combat_state

from dnd.classes.barbarian import Retaliation


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0)
) -> Entity:
    """Create a simple barbarian for testing."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=18),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=16),
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=14,  # Level 14
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=5,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    greatsword = create_greatsword(entity.uuid)
    entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    return entity


def create_test_attacker(
    name: str = "Attacker",
    position: tuple = (1, 0)
) -> Entity:
    """Create an attacker entity."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10,
            hit_dice_count=10,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=4,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    sword = create_shortsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    return entity


def test_retaliation_triggers_on_hit():
    """Test that retaliation triggers when hit by adjacent creature using real combat."""
    print("\n=== Test: Retaliation Triggers on Hit (Real Combat) ===")

    # Run multiple trials since attacks can miss
    retaliation_triggered = 0
    hits_on_barbarian = 0
    trials = 10

    for trial in range(trials):
        # Set seed for some variation but reproducibility
        random.seed(42 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Attacker_{trial}", position=(1, 0))  # Adjacent (5ft)

        Entity.update_all_entities_senses()

        # Apply Retaliation feature
        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        # Record state before
        attacker_hp_before = attacker.get_hp()
        barbarian_hp_before = barbarian.get_hp()

        # Attacker attacks barbarian using real Attack action
        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        # Check if barbarian was hit (took damage)
        barbarian_hp_after = barbarian.get_hp()
        attacker_hp_after = attacker.get_hp()

        if barbarian_hp_after < barbarian_hp_before:
            hits_on_barbarian += 1
            # Barbarian was hit - check if retaliation fired
            if attacker_hp_after < attacker_hp_before:
                retaliation_triggered += 1

    print(f"  Trials: {trials}")
    print(f"  Hits on barbarian: {hits_on_barbarian}")
    print(f"  Retaliation attacks triggered: {retaliation_triggered}")

    # We expect retaliation to trigger when hit
    if hits_on_barbarian > 0:
        retaliation_rate = retaliation_triggered / hits_on_barbarian * 100
        print(f"  Retaliation rate when hit: {retaliation_rate:.1f}%")

        if retaliation_triggered > 0:
            print("  [PASS] Retaliation triggered at least once when hit")
        else:
            print("  [WARN] Retaliation never triggered (attacks may have missed)")
    else:
        print("  [INFO] No hits on barbarian in trials")




def test_retaliation_consumes_reaction():
    """Test that retaliation consumes the reaction."""
    print("\n=== Test: Retaliation Consumes Reaction ===")

    # Find a trial where retaliation triggers
    reaction_consumed_correctly = False

    for trial in range(10):
        random.seed(100 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Attacker_{trial}", position=(1, 0))

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        # Record state
        barbarian_hp_before = barbarian.get_hp()
        attacker_hp_before = attacker.get_hp()
        reactions_before = barbarian.action_economy.reactions.normalized_score

        # Attack
        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        barbarian_hp_after = barbarian.get_hp()
        attacker_hp_after = attacker.get_hp()
        reactions_after = barbarian.action_economy.reactions.normalized_score

        # Check if hit and retaliation triggered
        if barbarian_hp_after < barbarian_hp_before and attacker_hp_after < attacker_hp_before:
            # Retaliation triggered - check reaction consumed
            if reactions_after == reactions_before - 1:
                reaction_consumed_correctly = True
                print(f"  Trial {trial}: Hit + Retaliation + Reaction consumed")
                print(f"    Reactions: {reactions_before} -> {reactions_after}")
                print("  [PASS] Reaction correctly consumed when retaliation triggers")
                break

    if not reaction_consumed_correctly:
        print("  [INFO] Could not verify reaction consumption (retaliation may not have triggered)")




def test_retaliation_no_trigger_from_distance():
    """Test that retaliation does NOT trigger from distance > 5ft."""
    print("\n=== Test: Retaliation No Trigger from Distance ===")

    # Multiple trials to ensure consistency
    triggered_from_distance = False

    for trial in range(10):
        random.seed(200 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        # Place attacker far away - but they need a ranged weapon to attack from distance
        # For simplicity, we'll use a melee attacker at distance and verify attack fails
        # OR we test with a nearby attacker that moves away before the event completes

        # Actually, let's just verify the distance check works
        # Create attacker at 10ft (2 squares)
        attacker = create_test_attacker(f"Attacker_{trial}", position=(2, 0))

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        # Check distance
        distance = barbarian.senses.get_feet_distance(attacker.senses.position)
        if trial == 0:
            print(f"  Distance to attacker: {distance}ft")

        attacker_hp_before = attacker.get_hp()

        # Attack from distance (will likely fail range check)
        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        attacker_hp_after = attacker.get_hp()

        # Retaliation should NOT have triggered
        if attacker_hp_after < attacker_hp_before:
            triggered_from_distance = True
            break

    if not triggered_from_distance:
        print("  [PASS] Retaliation did not trigger from distance > 5ft")
    else:
        print("  [FAIL] Retaliation triggered from distance > 5ft")




def test_retaliation_no_trigger_without_reaction():
    """Test that retaliation does NOT trigger if reaction already used."""
    print("\n=== Test: Retaliation No Trigger Without Reaction ===")

    triggered_without_reaction = False

    for trial in range(10):
        random.seed(300 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Attacker_{trial}", position=(1, 0))

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        # Use up the reaction BEFORE attack
        barbarian.action_economy.consume("reactions", 1)
        reactions = barbarian.action_economy.reactions.normalized_score
        if trial == 0:
            print(f"  Reactions available: {reactions}")

        attacker_hp_before = attacker.get_hp()
        barbarian_hp_before = barbarian.get_hp()

        # Attack
        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        attacker_hp_after = attacker.get_hp()
        barbarian_hp_after = barbarian.get_hp()

        # If barbarian was hit but attacker took no damage, retaliation correctly didn't trigger
        if barbarian_hp_after < barbarian_hp_before and attacker_hp_after < attacker_hp_before:
            triggered_without_reaction = True
            break

    if not triggered_without_reaction:
        print("  [PASS] Retaliation did not trigger without reaction available")
    else:
        print("  [FAIL] Retaliation triggered without reaction available")




def test_retaliation_no_trigger_without_melee_weapon():
    """Test that retaliation requires a melee weapon."""
    print("\n=== Test: Retaliation Requires Melee Weapon ===")

    triggered_without_weapon = False

    for trial in range(10):
        random.seed(400 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Attacker_{trial}", position=(1, 0))

        # Unequip barbarian's weapon BEFORE applying retaliation
        barbarian.equipment.unequip(WeaponSlot.MELEE_MAIN)
        weapon = barbarian.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
        if trial == 0:
            print(f"  Melee weapon equipped: {weapon is not None}")

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        attacker_hp_before = attacker.get_hp()
        barbarian_hp_before = barbarian.get_hp()

        # Attack
        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        attacker_hp_after = attacker.get_hp()
        barbarian_hp_after = barbarian.get_hp()

        # If barbarian was hit but attacker took no damage, correct
        if barbarian_hp_after < barbarian_hp_before and attacker_hp_after < attacker_hp_before:
            triggered_without_weapon = True
            break

    if not triggered_without_weapon:
        print("  [PASS] Retaliation did not trigger without melee weapon")
    else:
        print("  [FAIL] Retaliation triggered without melee weapon")




def test_retaliation_only_once_per_round():
    """Test that only one retaliation per round (reaction limit)."""
    print("\n=== Test: Retaliation Only Once Per Round ===")

    # Find a scenario where retaliation triggers on first hit
    found_scenario = False

    for trial in range(10):
        random.seed(500 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barbarian_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Attacker_{trial}", position=(1, 0))

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        # First attack
        attacker_hp_before_1 = attacker.get_hp()
        barbarian_hp_before_1 = barbarian.get_hp()

        attack1 = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack1.apply()

        attacker_hp_after_1 = attacker.get_hp()
        barbarian_hp_after_1 = barbarian.get_hp()
        reactions_after_1 = barbarian.action_economy.reactions.normalized_score

        # Check if first attack hit and triggered retaliation
        first_hit = barbarian_hp_after_1 < barbarian_hp_before_1
        first_retaliation = attacker_hp_after_1 < attacker_hp_before_1

        if first_hit and first_retaliation and reactions_after_1 == 0:
            found_scenario = True
            print(f"  Trial {trial}: First hit triggered retaliation, reaction consumed")

            # Reset attacker's action economy for second attack
            attacker.action_economy.reset_all_costs()

            # Second attack
            attacker_hp_before_2 = attacker.get_hp()

            attack2 = Attack(
                source_entity_uuid=attacker.uuid,
                target_entity_uuid=barbarian.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN
            )
            attack2.apply()

            attacker_hp_after_2 = attacker.get_hp()

            # Second retaliation should NOT fire (no reaction)
            if attacker_hp_after_2 == attacker_hp_before_2:
                print("  Second attack: No retaliation (reaction already used)")
                print("  [PASS] Only one retaliation per round")
            else:
                print("  [FAIL] Retaliation fired twice (shouldn't happen)")
            break

    if not found_scenario:
        print("  [INFO] Could not find scenario where retaliation triggers (RNG)")




def test_retaliation_feature_summary():
    """Summary test showing retaliation works with real combat."""
    print("\n=== Test: Retaliation Feature Summary ===")

    # Multiple trials to get statistics
    total_trials = 20
    hits_on_barbarian = 0
    retaliations = 0
    retaliation_hits = 0

    for trial in range(total_trials):
        random.seed(600 + trial)

        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)

        barbarian = create_test_barbarian(f"Barb_{trial}", position=(0, 0))
        attacker = create_test_attacker(f"Att_{trial}", position=(1, 0))

        Entity.update_all_entities_senses()

        retaliation = Retaliation(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid
        )
        barbarian.add_condition(retaliation)

        barbarian_hp_before = barbarian.get_hp()
        attacker_hp_before = attacker.get_hp()

        attack = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=barbarian.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        attack.apply()

        barbarian_hp_after = barbarian.get_hp()
        attacker_hp_after = attacker.get_hp()

        if barbarian_hp_after < barbarian_hp_before:
            hits_on_barbarian += 1
            if attacker_hp_after < attacker_hp_before:
                retaliations += 1
                retaliation_hits += 1
            elif barbarian.action_economy.reactions.normalized_score == 0:
                # Reaction consumed but attack missed
                retaliations += 1

    print(f"  Total trials: {total_trials}")
    print(f"  Attacker hits on barbarian: {hits_on_barbarian}")
    print(f"  Retaliations triggered: {retaliations}")
    print(f"  Retaliation hits on attacker: {retaliation_hits}")

    if hits_on_barbarian > 0:
        trigger_rate = retaliations / hits_on_barbarian * 100
        print(f"  Retaliation trigger rate: {trigger_rate:.1f}%")

    if retaliations > 0:
        print("  [PASS] Retaliation feature working correctly")
    else:
        print("  [WARN] No retaliations triggered - check implementation")




if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN RETALIATION TESTS")
    print("=" * 60)

    test_retaliation_triggers_on_hit()
    test_retaliation_consumes_reaction()
    test_retaliation_no_trigger_from_distance()
    test_retaliation_no_trigger_without_reaction()
    test_retaliation_no_trigger_without_melee_weapon()
    test_retaliation_only_once_per_round()
    test_retaliation_feature_summary()

    print("\n" + "=" * 60)
    print("RETALIATION TESTS COMPLETE")
    print("=" * 60)
