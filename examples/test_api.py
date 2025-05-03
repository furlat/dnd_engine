import requests
import json
from typing import Dict, List, Any, Optional
from uuid import UUID
import sys

# Base URL for the API
BASE_URL = "http://localhost:8000/api"

def list_modifiable_values(entity_uuid: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get a list of all ModifiableValue objects, optionally filtered by entity UUID.
    
    Args:
        entity_uuid (Optional[str]): UUID of the entity to filter by
        
    Returns:
        List[Dict[str, Any]]: List of ModifiableValue summaries
    """
    url = f"{BASE_URL}/values"
    if entity_uuid:
        url += f"?entity_uuid={entity_uuid}"
        
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []
    
    return response.json()

def get_modifiable_value(value_uuid: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific ModifiableValue.
    
    Args:
        value_uuid (str): UUID of the ModifiableValue
        
    Returns:
        Optional[Dict[str, Any]]: ModifiableValue details or None if not found
    """
    url = f"{BASE_URL}/values/{value_uuid}"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    
    return response.json()

def print_value_hierarchy(value_data: Dict[str, Any], indent: int = 0) -> None:
    """
    Print a hierarchical representation of a ModifiableValue.
    
    Args:
        value_data (Dict[str, Any]): ModifiableValue data
        indent (int): Current indentation level
    """
    indent_str = "  " * indent
    print(f"{indent_str}Name: {value_data['name']}")
    print(f"{indent_str}UUID: {value_data['uuid']}")
    print(f"{indent_str}Score: {value_data['score']} (Normalized: {value_data['normalized_score']})")
    print(f"{indent_str}Advantage: {value_data['advantage']}")
    print(f"{indent_str}Critical: {value_data['critical']}")
    print(f"{indent_str}Auto Hit: {value_data['auto_hit']}")
    
    # Print component summaries
    print(f"{indent_str}Components:")
    for name, component in value_data["components"].items():
        print(f"{indent_str}  {name} ({component['type']}): {component['score']} (Normalized: {component['normalized_score']})")

def analyze_modifiable_value(value_data: Dict[str, Any]) -> None:
    """
    Analyze a ModifiableValue, showing its key structure and properties.
    
    Args:
        value_data (Dict[str, Any]): ModifiableValue data
    """
    print("\n=== ModifiableValue Analysis ===")
    print_value_hierarchy(value_data)
    
    # Check for active modifiers
    print("\nActive Modifiers:")
    
    # Check self_static value modifiers
    value_modifiers = value_data["self_static"]["value_modifiers"]
    if value_modifiers:
        print(f"  Self Static Value Modifiers: {len(value_modifiers)}")
        for mod_id, modifier in value_modifiers.items():
            print(f"    - {modifier['name']}: {modifier['value']}")
    
    # Check if from_target components are present
    if value_data.get("from_target_static"):
        print("\nFrom Target Static Component Present")
    
    if value_data.get("from_target_contextual"):
        print("\nFrom Target Contextual Component Present")
    
    print("\n===============================\n")

def main() -> None:
    """Main function to test the API endpoints"""
    print("Retrieving list of ModifiableValue objects...")
    values_list = list_modifiable_values()
    
    if not values_list:
        print("No ModifiableValue objects found!")
        return
    
    print(f"Found {len(values_list)} ModifiableValue objects")
    
    # Get details for the first few values
    for i, value_summary in enumerate(values_list[:3]):  # Limit to first 3
        value_uuid = value_summary["uuid"]
        print(f"\nRetrieving details for ModifiableValue {i+1}/{min(3, len(values_list))}: {value_summary['name']} ({value_uuid})")
        
        value_details = get_modifiable_value(value_uuid)
        if value_details:
            analyze_modifiable_value(value_details)
        else:
            print(f"Failed to retrieve details for {value_uuid}")
    
    # Try to get values for a specific entity
    if len(values_list) > 0:
        entity_uuid = values_list[0]["source_entity_uuid"]
        print(f"\nFiltering ModifiableValues by entity: {entity_uuid}")
        entity_values = list_modifiable_values(entity_uuid)
        print(f"Found {len(entity_values)} ModifiableValue objects for entity {entity_uuid}")
    
    print("\nAPI test completed!")

if __name__ == "__main__":
    main()