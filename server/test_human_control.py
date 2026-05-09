"""
Test human control endpoints.

Run with: python -m server.test_human_control

Requires server running: python -m server.event_server
"""

import traceback

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

    session_resp = client.post("/session/create", json={"player_type": "human", "name": "Human Control Test"})
    session_data = session_resp.json()
    session_id = session_data.get("session_id")
    if not session_id:
        print(f"   ERROR: No session ID returned: {session_data}")
        return False
    join_resp = client.post("/game/join", json={"session_id": session_id, "entity_uuid": entity_uuid})
    if not join_resp.is_success:
        print(f"   ERROR: Could not join game: {join_resp.text}")
        return False
    print(f"   Session ID: {session_id}")

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
    entity_actions = actions.get("entity_actions", [])
    position_actions = actions.get("position_actions", [])
    self_actions = actions.get("self_actions", [])
    print(f"   Entity actions: {len(entity_actions)}")
    for action in entity_actions:
        print(f"      - {action['template_name']}: {len(action['valid_targets'])} targets")
    print(f"   Position actions: {[a['template_name'] for a in position_actions]}")
    print(f"   Self actions: {[a['template_name'] for a in self_actions]}")
    print(f"   Movement: {actions.get('remaining_movement', 0)}ft")

    # 4. Execute a move
    print("\n4. Executing move...")
    # Find a valid position
    move_action = next((action for action in position_actions if action["template_name"] == "Move"), None)
    if move_action and move_action["valid_targets"]:
        target_pos = move_action["valid_targets"][0]["position"]
        print(f"   Moving to {target_pos}...")
        resp = client.post("/action/position", json={
            "session_id": session_id,
            "entity_uuid": entity_uuid,
            "action_name": "Move",
            "position": target_pos,
        })
        result = resp.json()
        if "success" not in result:
            print(f"   ERROR: Move returned unexpected payload: {result}")
            return False
        print(f"   Success: {result['success']}")
        print(f"   Message: {result['message']}")
    else:
        print("   No valid positions to move to")

    # 5. Get updated actions (movement should be reduced)
    print("\n5. Getting updated available actions...")
    resp = client.get(f"/entity/{entity_uuid}/available-actions")
    actions = resp.json()
    print(f"   Remaining movement: {actions.get('remaining_movement', 0)}ft")

    # 6. Try an attack if we have targets
    attacks_with_targets = [a for a in actions.get("entity_actions", []) if a["valid_targets"]]
    if attacks_with_targets:
        print("\n6. Executing attack...")
        attack = attacks_with_targets[0]
        target = attack['valid_targets'][0]["entity_uuid"]
        resp = client.post("/action/entity", json={
            "session_id": session_id,
            "entity_uuid": entity_uuid,
            "action_name": attack["template_name"],
            "target_uuid": target,
        })
        result = resp.json()
        if "success" not in result:
            print(f"   ERROR: Attack returned unexpected payload: {result}")
            return False
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
    resp = client.post("/action/end-turn", json={"session_id": session_id, "entity_uuid": entity_uuid})
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
        traceback.print_exc()
        exit(1)
