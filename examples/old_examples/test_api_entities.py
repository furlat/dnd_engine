#!/usr/bin/env python3
"""
Test script to verify that locally created entities match API responses.
This script:
1. Creates entities locally
2. Fetches the same entities from the API
3. Compares the values to ensure they match
"""

import sys
import os
import json
import uuid
import requests
from typing import Dict, Any, Optional

# Add parent directory to sys.path to allow importing from dnd package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import entity and interface modules
from dnd.entity import Entity
from dnd.monsters.circus_fighter import create_warrior
from dnd.interfaces.entity import EntitySnapshot

# Configuration
API_BASE_URL = "http://localhost:8000/api"
HEADERS = {"Content-Type": "application/json"}
ENTITY_NAME = "Test Warrior"

def get_entity_from_api(entity_uuid: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Retrieve entity from API by UUID"""
    response = requests.get(
        f"{API_BASE_URL}/entities/{entity_uuid}",
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print(f"Error retrieving entity: {response.text}")
        return None
    
    return response.json()

def get_subblock_from_api(entity_uuid: uuid.UUID, subblock_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a specific subblock from API by entity UUID and subblock name"""
    response = requests.get(
        f"{API_BASE_URL}/entities/{entity_uuid}/{subblock_name}",
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print(f"Error retrieving subblock {subblock_name}: {response.text}")
        return None
    
    return response.json()

def compare_values(local_value: Any, api_value: Any, path: str = "") -> bool:
    """
    Compare local and API values recursively
    
    Args:
        local_value: Value from local entity
        api_value: Value from API response
        path: Current path in the object hierarchy for error reporting
        
    Returns:
        bool: True if values match, False otherwise
    """
    # Handle different types
    if type(local_value) != type(api_value):
        print(f"Type mismatch at {path}: local {type(local_value)} vs API {type(api_value)}")
        print(f"Values: local {local_value} vs API {api_value}")
        return False
        
    # Handle dictionaries
    if isinstance(local_value, dict) and isinstance(api_value, dict):
        for key in local_value:
            if key not in api_value:
                print(f"Key {key} missing in API response at {path}")
                return False
            if not compare_values(local_value[key], api_value[key], f"{path}.{key}"):
                return False
        return True
        
    # Handle lists
    elif isinstance(local_value, list) and isinstance(api_value, list):
        if len(local_value) != len(api_value):
            print(f"List length mismatch at {path}: local {len(local_value)} vs API {len(api_value)}")
            return False
        
        # For simple lists, compare by index
        for i, (local_item, api_item) in enumerate(zip(local_value, api_value)):
            if not compare_values(local_item, api_item, f"{path}[{i}]"):
                return False
        return True
        
    # Compare primitive values
    else:
        if local_value != api_value:
            print(f"Value mismatch at {path}: local {local_value} vs API {api_value}")
            return False
        return True

def test_entity_matches_api():
    """Test that a locally created entity matches the API response"""
    print("=== Testing Entity API Consistency ===")
    
    # Create a warrior locally with the same name as the one in the API
    warrior_uuid = uuid.uuid4()
    local_warrior = create_warrior(source_id=warrior_uuid, proficiency_bonus=2, name=ENTITY_NAME)
    
    # List entities from API to find the matching test entity
    response = requests.get(f"{API_BASE_URL}/entities/", headers=HEADERS)
    entities = response.json()
    
    if not entities:
        print("No entities found in API")
        return
    
    # Find the entity with matching name
    api_entity_uuid = None
    for entity in entities:
        if entity["name"] == ENTITY_NAME:
            api_entity_uuid = entity["uuid"]
            break
    
    if not api_entity_uuid:
        print(f"No entity with name '{ENTITY_NAME}' found in API")
        return
    
    print(f"Found entity {ENTITY_NAME} with UUID: {api_entity_uuid}")
    
    # Get entity from API
    api_entity = get_entity_from_api(api_entity_uuid)
    if not api_entity:
        return
    
    # Convert local entity to same format as API response
    local_snapshot = EntitySnapshot.from_engine(
        local_warrior,
        include_skill_calculations=True,
        include_attack_calculations=True,
        include_ac_calculation=True
    )
    local_entity_dict = {
        "uuid": str(local_warrior.uuid),
        "name": local_warrior.name,
        "entity": local_snapshot.model_dump()
    }
    
    # Compare
    print("\nComparing full entity...")
    entity_match = compare_values(local_entity_dict, api_entity)
    
    if entity_match:
        print("✓ Full entity values match!")
    else:
        print("✗ Full entity values do not match")
    
    # Test subblocks
    subblocks = ["health", "ability_scores", "skill_set", "equipment", "saving_throws"]
    
    for subblock in subblocks:
        print(f"\nTesting subblock: {subblock}")
        api_subblock = get_subblock_from_api(api_entity_uuid, subblock)
        
        if not api_subblock:
            continue
            
        # Get the local subblock in the same format as API
        local_subblock_obj = getattr(local_warrior, subblock)
        local_subblock_snapshot = None
        
        # Get appropriate snapshot based on subblock type
        if subblock == "health":
            from dnd.interfaces.health import HealthSnapshot
            local_subblock_snapshot = HealthSnapshot.from_engine(local_subblock_obj, local_warrior)
        elif subblock == "ability_scores":
            from dnd.interfaces.abilities import AbilityScoresSnapshot
            local_subblock_snapshot = AbilityScoresSnapshot.from_engine(local_subblock_obj)
        elif subblock == "skill_set":
            from dnd.interfaces.skills import SkillSetSnapshot
            local_subblock_snapshot = SkillSetSnapshot.from_engine(local_subblock_obj, local_warrior)
        elif subblock == "equipment":
            from dnd.interfaces.equipment import EquipmentSnapshot
            local_subblock_snapshot = EquipmentSnapshot.from_engine(local_subblock_obj)
        elif subblock == "saving_throws":
            from dnd.interfaces.saving_throws import SavingThrowSetSnapshot
            local_subblock_snapshot = SavingThrowSetSnapshot.from_engine(local_subblock_obj, local_warrior)
            
        if local_subblock_snapshot:
            local_subblock_dict = {
                "uuid": str(local_subblock_obj.uuid),
                "name": local_subblock_obj.name,
                "entity_uuid": str(local_warrior.uuid),
                "entity_name": local_warrior.name,
                "subblock": local_subblock_snapshot.model_dump()
            }
            
            match = compare_values(local_subblock_dict, api_subblock)
            if match:
                print(f"✓ {subblock} values match!")
            else:
                print(f"✗ {subblock} values do not match")
    
if __name__ == "__main__":
    print("Starting API entity test...")
    print("Note: Ensure the FastAPI server is running on http://localhost:8000")
    print()
    test_entity_matches_api() 