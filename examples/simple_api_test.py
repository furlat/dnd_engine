#!/usr/bin/env python3
"""
Simple test script to demonstrate API functionality.
Gets entities from API and displays key information.
"""

import sys
import os
import json
import requests
from uuid import UUID

# Configuration
API_BASE_URL = "http://localhost:8000/api"
HEADERS = {"Content-Type": "application/json"}

def print_section(title):
    """Print a section header"""
    print(f"\n{'=' * 10} {title} {'=' * 10}")

def print_json(data, indent=2):
    """Print JSON data nicely formatted"""
    print(json.dumps(data, indent=indent))

def list_entities():
    """List all entities from the API"""
    print_section("Listing All Entities")
    
    response = requests.get(f"{API_BASE_URL}/entities/", headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []
    
    entities = response.json()
    print_json(entities)
    return entities

def get_entity_details(entity_uuid):
    """Get details of a specific entity"""
    print_section(f"Entity Details: {entity_uuid}")
    
    response = requests.get(
        f"{API_BASE_URL}/entities/{entity_uuid}",
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    
    entity = response.json()
    
    # Print basic info
    print(f"Name: {entity['name']}")
    print(f"UUID: {entity['uuid']}")
    
    # Print some key stats
    try:
        ability_scores = entity['entity']['ability_scores']['abilities']
        print("\nAbility Scores:")
        for ability in ability_scores:
            print(f"  {ability['name']}: {ability['ability_score']['base_value']} (Modifier: {ability['modifier']})")
    except (KeyError, TypeError):
        print("Unable to extract ability scores")
    
    try:
        health_data = entity['entity']['health']
        print("\nHealth:")
        print(f"  Hit Points Max: {health_data.get('max_hit_points', 'N/A')}")
        print(f"  Current HP: {health_data.get('current_hit_points', 'N/A')}")
        print(f"  Damage Taken: {health_data.get('damage_taken', 'N/A')}")
        print(f"  Temporary HP: {health_data.get('temporary_hit_points', {}).get('score', 'N/A')}")
    except (KeyError, TypeError):
        print("Unable to extract health data")
    
    return entity

def get_subblock(entity_uuid, subblock_name):
    """Get a specific subblock of an entity"""
    print_section(f"Subblock: {subblock_name}")
    
    response = requests.get(
        f"{API_BASE_URL}/entities/{entity_uuid}/{subblock_name}",
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    
    subblock = response.json()
    
    # Just print some basic info based on subblock type
    print(f"Name: {subblock['name']}")
    print(f"UUID: {subblock['uuid']}")
    print(f"Entity: {subblock['entity_name']} ({subblock['entity_uuid']})")
    
    if subblock_name == 'health':
        try:
            health = subblock['subblock']
            print(f"\nHit Dice Count: {health.get('total_hit_dices_number', 'N/A')}")
            print(f"Hit Points: {health.get('current_hit_points', 'N/A')}")
            print(f"Max Hit Points: {health.get('max_hit_points', 'N/A')}")
            
            # Print resistances if any
            if 'resistances' in health and health['resistances']:
                print("\nResistances:")
                for resistance in health['resistances']:
                    print(f"  {resistance['damage_type']}: {resistance['status']}")
                    
        except (KeyError, TypeError):
            print("Unable to extract health details")
    
    elif subblock_name == 'ability_scores':
        try:
            abilities = subblock['subblock']['abilities']
            print("\nAbility Scores:")
            for ability in abilities:
                print(f"  {ability['name']}: {ability['ability_score']['base_value']} (Modifier: {ability['modifier']})")
        except (KeyError, TypeError):
            print("Unable to extract ability scores details")
    
    return subblock

def main():
    print("Simple API Test - D&D Engine")
    print("Note: Make sure the API server is running at", API_BASE_URL)
    
    # Get all entities
    entities = list_entities()
    
    if not entities:
        print("No entities found. Make sure the API server is running.")
        return
    
    # Get details of the first entity
    first_entity_uuid = entities[0]['uuid']
    entity = get_entity_details(first_entity_uuid)
    
    if not entity:
        return
        
    # Test subblocks
    subblocks = ["health", "ability_scores", "skill_set", "equipment", "saving_throws"]
    
    for subblock in subblocks:
        get_subblock(first_entity_uuid, subblock)

if __name__ == "__main__":
    main() 