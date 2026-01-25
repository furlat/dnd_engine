"""
Test human control endpoints.

Run with: python -m server.test_human_control

Requires server running: python -m server.event_server
"""

import httpx

BASE_URL = "http://localhost:8000"


def test_human_control():
    """Test the human control flow."""
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    print("=" * 60)
    print("HUMAN CONTROL API TEST")
    print("=" * 60)

    # 1. Start human simulation
    print("\n1. Starting human simulation...")
    resp = client.post("/simulation/start-human")
    data = resp.json()
    print(f"   Status: {data.get('status')}")
    print(f"   Entity UUID: {data.get('entity_uuid')}")
    print(f"   Entity Name: {data.get('entity_name')}")

    if data.get("status") != "waiting_for_human":
        print("   ERROR: Expected waiting_for_human status")
        return False

    entity_uuid = data.get("entity_uuid")
    if not entity_uuid:
        print("   ERROR: No entity UUID returned")
        return False

    # 2. Get current turn info
    print("\n2. Getting current turn...")
    resp = client.get("/encounter/current-turn")
    turn = resp.json()
    print(f"   Round: {turn['round_number']}, Turn: {turn['turn_index']}")
    print(f"   Current entity: {turn['current_entity_name']}")
    print(f"   Is human turn: {turn['is_human_turn']}")
    print(f"   Waiting for input: {turn['waiting_for_input']}")
    print(f"   Actions: {turn['actions_remaining']}, Movement: {turn['movement_remaining']}ft")

    # 3. Get available actions
    print("\n3. Getting available actions...")
    resp = client.get(f"/entity/{entity_uuid}/available-actions")
    actions = resp.json()
    print(f"   Attacks: {len(actions['attacks'])}")
    for atk in actions['attacks']:
        print(f"      - {atk['name']}: {len(atk['valid_targets'])} targets")
    print(f"   Movement: {actions['can_move']}, {actions['remaining_movement']}ft")
    print(f"   Other actions: {[a['action_id'] for a in actions['other_actions']]}")

    # 4. Execute a move
    print("\n4. Executing move...")
    # Find a valid position
    if actions['movement'] and actions['movement'][0]['valid_positions']:
        target_pos = actions['movement'][0]['valid_positions'][0]
        print(f"   Moving to {target_pos}...")
        resp = client.post("/action/move", json={
            "entity_uuid": entity_uuid,
            "position": target_pos
        })
        result = resp.json()
        print(f"   Success: {result['success']}")
        print(f"   Message: {result['message']}")
    else:
        print("   No valid positions to move to")

    # 5. Get updated actions (movement should be reduced)
    print("\n5. Getting updated available actions...")
    resp = client.get(f"/entity/{entity_uuid}/available-actions")
    actions = resp.json()
    print(f"   Remaining movement: {actions['remaining_movement']}ft")

    # 6. Try an attack if we have targets
    attacks_with_targets = [a for a in actions['attacks'] if a['valid_targets']]
    if attacks_with_targets:
        print("\n6. Executing attack...")
        attack = attacks_with_targets[0]
        target = attack['valid_targets'][0]
        resp = client.post("/action/attack", json={
            "entity_uuid": entity_uuid,
            "target_uuid": target,
            "weapon_slot": "main_hand"
        })
        result = resp.json()
        print(f"   Success: {result['success']}")
        print(f"   Message: {result['message']}")
        if result.get('event_data'):
            print(f"   Outcome: {result['event_data'].get('outcome')}")
            print(f"   Roll: {result['event_data'].get('roll')}")
            print(f"   Damage: {result['event_data'].get('damage')}")
        print(f"   Target HP: {result.get('target_hp')}")
        if result.get('deaths'):
            print(f"   Deaths: {result['deaths']}")
    else:
        print("\n6. No targets in range for attack")

    # 7. End turn
    print("\n7. Ending turn...")
    resp = client.post("/action/end-turn", json={"entity_uuid": entity_uuid})
    result = resp.json()
    print(f"   Status: {result.get('status')}")

    # If AI took their turn, we might be waiting for human again
    if result.get("status") == "waiting_for_human":
        print(f"   Next turn: {result.get('entity_name')}")
    elif result.get("status") == "encounter_ended":
        print("   Encounter ended!")

    # 8. Check encounter state
    print("\n8. Final encounter state...")
    resp = client.get("/encounter/current-turn")
    turn = resp.json()
    print(f"   Round: {turn['round_number']}")
    print(f"   Active: {turn['encounter_active']}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_human_control()
        exit(0 if success else 1)
    except httpx.ConnectError:
        print("ERROR: Could not connect to server.")
        print("Make sure the server is running: python -m server.event_server")
        exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
