#!/usr/bin/env python
"""
Debug script for testing entity creation and serialization without the API.

This script creates a test warrior entity directly and tries to convert it to a snapshot
to diagnose any issues with the entity modeling and serialization.
"""

import sys
import os
from uuid import uuid4
import json
from pprint import pprint

# Add the parent directory to sys.path to allow importing from dnd package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import entity creation and snapshot functionality
from dnd.monsters.circus_fighter import create_warrior
from dnd.interfaces.entity import EntitySnapshot
from dnd.core.modifiers import NumericalModifier, AdvantageStatus, CriticalStatus, AutoHitStatus

# Function to inspect attributes of an object
def inspect_object(obj, name="object", max_depth=2, current_depth=0):
    """Recursively inspect an object's attributes."""
    if current_depth > max_depth:
        return f"[Max depth reached for {type(obj).__name__}]"
    
    if hasattr(obj, "__dict__"):
        result = {
            "type": type(obj).__name__,
            "attributes": {}
        }
        for attr_name, attr_val in obj.__dict__.items():
            if current_depth < max_depth:
                if hasattr(attr_val, "__dict__"):
                    result["attributes"][attr_name] = inspect_object(
                        attr_val, attr_name, max_depth, current_depth + 1
                    )
                else:
                    result["attributes"][attr_name] = f"{type(attr_val).__name__}: {str(attr_val)[:100]}"
            else:
                result["attributes"][attr_name] = f"{type(attr_val).__name__} [truncated]"
        return result
    else:
        return f"{type(obj).__name__}: {str(obj)[:100]}"

def main():
    # Create a warrior from circus_fighter.py with a known UUID
    warrior_uuid = uuid4()
    print(f"Creating test warrior with UUID: {warrior_uuid}")
    warrior = create_warrior(source_id=warrior_uuid, proficiency_bonus=2, name="Test Warrior")
    
    print("\n=== Testing basic entity properties ===")
    print(f"Name: {warrior.name}")
    print(f"UUID: {warrior.uuid}")
    
    print("\n=== Testing ability scores ===")
    for ability_name in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        ability = getattr(warrior.ability_scores, ability_name)
        # Use the correct attributes based on the Ability class definition
        score = ability.ability_score.score
        modifier = ability.modifier  # This is a computed property
        print(f"{ability_name.capitalize()}: Score={score}, Modifier={modifier}")
    
    # Try to create a snapshot manually, without using the API
    print("\n=== Attempting to create EntitySnapshot ===")
  
    # Check the ability scores modifiers
    print("\n=== Checking ability score structure ===")
    strength = warrior.ability_scores.strength
    print(f"Strength object type: {type(strength).__name__}")
    print(f"Strength ability properties:")
    print(f"  name: {strength.name}")
    print(f"  modifier (computed): {strength.modifier}")
    
    # Examine the ability_score property (ModifiableValue)
    ability_score = strength.ability_score
    print(f"\nAbility score object type: {type(ability_score).__name__}")
    print(f"  score: {ability_score.score}")
    print(f"  normalized_score: {ability_score.normalized_score}")
    
    # Examine the self_static and base modifier structure
    print("\nExamining ModifiableValue.self_static structure:")
    if hasattr(ability_score, 'self_static'):
        static_value = ability_score.self_static
        print(f"  self_static type: {type(static_value).__name__}")
        
        # Try to access value_modifiers
        if hasattr(static_value, 'value_modifiers'):
            modifiers = static_value.value_modifiers
            print(f"  Found value_modifiers, count: {len(modifiers)}")
            
            for mod_id, mod in modifiers.items():
                print(f"  Modifier {mod_id}:")
                print(f"    type: {type(mod).__name__}")
                print(f"    name: {getattr(mod, 'name', 'Unknown')}")
                if hasattr(mod, 'value'):
                    print(f"    value: {mod.value}")
                else:
                    print(f"    value: Unknown")
                if hasattr(mod, 'normalized_value'):
                    print(f"    normalized_value: {mod.normalized_value}")
                else:
                    print(f"    normalized_value: Not available")
    
    # Create a test NumericalModifier to examine its actual structure
    print("\n=== Creating test NumericalModifier for inspection ===")
    test_mod = NumericalModifier(
        source_entity_uuid=warrior_uuid,
        target_entity_uuid=warrior_uuid,
        name="Test Modifier",
        value=5
    )
    print(f"NumericalModifier attributes:")
    print(f"  uuid: {test_mod.uuid}")
    print(f"  name: {getattr(test_mod, 'name', 'Unknown')}")
    print(f"  value: {getattr(test_mod, 'value', 'Unknown')}")
    # The normalized_value is a computed property that might be accessed differently
    if hasattr(test_mod, 'normalized_value'):
        print(f"  normalized_value: {test_mod.normalized_value}")
    else:
        print(f"  normalized_value: Not directly accessible")
    
    snapshot = EntitySnapshot.from_engine(warrior)
    print("✅ Successfully created snapshot")
    
    
    # Try to create a snapshot with more details
    print("\n=== Attempting to create detailed EntitySnapshot ===")
    detailed_snapshot = EntitySnapshot.from_engine(
        warrior, 
        include_skill_calculations=True,
        include_attack_calculations=True,
        include_ac_calculation=True
    )
    print("✅ Successfully created detailed snapshot")

    
    # Inspect a numerical modifier to see if it has the required attributes
    print("\n=== Creating and inspecting test NumericalModifier ===")
    test_modifier = NumericalModifier(
        source_entity_uuid=warrior_uuid,
        target_entity_uuid=warrior_uuid,
        name="Test Modifier",
        value=5
    )
    print(f"NumericalModifier.value: {test_modifier.value}")
    if hasattr(test_modifier, 'normalized_value'):
        print(f"NumericalModifier.normalized_value: {test_modifier.normalized_value}")
    else:
        print("NumericalModifier.normalized_value is MISSING!")
    
    # If we made it this far without errors, try to serialize the snapshot to JSON
    if 'snapshot' in locals():
        print("\n=== Attempting to serialize snapshot to JSON ===")
        try:
            json_data = snapshot.model_dump_json(indent=2)
            print("✅ Successfully serialized snapshot to JSON")
            
            # Save the JSON to a file
            with open("entity_snapshot.json", "w") as f:
                f.write(json_data)
            print("✅ Saved snapshot to entity_snapshot.json")
        except Exception as e:
            print(f"❌ Failed to serialize snapshot to JSON: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main() 