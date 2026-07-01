"""
Test Jump via API - verify server-side execution works.

This test starts its own server, creates a game, and tests Jump execution.
"""

import subprocess
import requests
import sys
import atexit

BASE_URL = "http://localhost:8765"  # Different port to avoid conflicts
server_process = None


def start_server():
    """Start the server in a subprocess."""
    global server_process
    print("Starting server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.event_server:app",
         "--port", "8765", "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    atexit.register(stop_server)

    # Wait for server to be ready
    import time
    for _ in range(50):  # 5 seconds max
        try:
            resp = requests.get(f"{BASE_URL}/", timeout=1)
            if resp.status_code == 200:
                print("Server ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.1)

    print("ERROR: Server failed to start")
    return False


def stop_server():
    """Stop the server subprocess."""
    global server_process
    if server_process:
        server_process.terminate()
        _stdout, stderr = server_process.communicate(timeout=5)
        if stderr:
            print("\n=== Server stderr ===")
            print(stderr.decode()[-2000:])  # Last 2000 chars
        server_process = None


def test_jump_via_api():
    """Test Jump action through the server API."""
    print("\n=== Test Jump via API ===")

    # 1. Start arena combat (human vs AI mode)
    print("Starting arena combat...")
    resp = requests.post(f"{BASE_URL}/simulation/start-human?character_class=fighter")

    if resp.status_code != 200:
        print(f"Failed to start arena: {resp.status_code} {resp.text}")
        return False

    arena_data = resp.json()
    hero_uuid = arena_data.get("hero_uuid")
    print(f"Hero UUID: {hero_uuid}")

    if not hero_uuid:
        print("ERROR: No hero_uuid in response")
        return False

    # 2. Create a session
    print("\nCreating session...")
    resp = requests.post(f"{BASE_URL}/session/create", json={
        "player_type": "human",
        "name": "Test Player"
    })
    if resp.status_code != 200:
        print(f"Failed to create session: {resp.text}")
        return False

    session_data = resp.json()
    session_id = session_data.get("session_id")
    print(f"Session ID: {session_id}")

    # 3. Join game
    print("\nJoining game...")
    resp = requests.post(f"{BASE_URL}/game/join", json={
        "session_id": session_id,
        "entity_uuids": [hero_uuid]
    })
    if resp.status_code != 200:
        print(f"Failed to join game: {resp.text}")
        return False

    print(f"Joined game: {resp.json()}")

    # 4. Get state to see current position
    print("\nGetting state...")
    resp = requests.get(f"{BASE_URL}/state")
    if resp.status_code != 200:
        print(f"Failed to get state: {resp.text}")
        return False

    state = resp.json()
    hero_entity = None
    for entity in state.get("entities", []):
        if entity.get("uuid") == hero_uuid:
            hero_entity = entity
            break

    if not hero_entity:
        print("ERROR: Hero not found in state")
        return False

    initial_pos = tuple(hero_entity.get("position", [0, 0]))
    print(f"Hero position: {initial_pos}")

    # 5. Get available actions
    print("\nFetching available actions...")
    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/available-actions")
    if resp.status_code != 200:
        print(f"Failed to get actions: {resp.text}")
        return False

    actions = resp.json()

    # Print all position actions
    print(f"Position actions: {[a.get('template_name') for a in actions.get('position_actions', [])]}")

    # 6. Find Jump action
    jump_action = None
    for action in actions.get("position_actions", []):
        if action.get("template_name") == "Jump":
            jump_action = action
            break

    if not jump_action:
        print("ERROR: Jump action not found in position_actions!")
        print("Available position_actions:")
        for a in actions.get("position_actions", []):
            print(f"  - {a.get('template_name')}: {len(a.get('valid_targets', []))} targets")
        return False

    print(f"Jump action found!")
    print(f"  Valid targets count: {len(jump_action.get('valid_targets', []))}")
    print(f"  Can afford: {jump_action.get('can_afford')}")
    print(f"  Cost type: {jump_action.get('cost_type')}")

    valid_targets = jump_action.get("valid_targets", [])
    if not valid_targets:
        print("ERROR: No valid jump targets!")
        return False

    # Pick a target that's different from current position
    target = None
    for t in valid_targets:
        pos = t.get("position")
        if pos and tuple(pos) != initial_pos:
            target = t
            break

    if not target:
        print("ERROR: Could not find a valid jump target different from current position")
        return False

    target_pos = tuple(target.get("position"))
    print(f"\nJumping from {initial_pos} to {target_pos}")

    # 7. Execute the jump via /action/position
    resp = requests.post(f"{BASE_URL}/action/position", json={
        "session_id": session_id,
        "entity_uuid": hero_uuid,
        "action_name": "Jump",
        "position": list(target_pos)
    })

    print(f"Response status: {resp.status_code}")
    print(f"Response text: {resp.text[:500] if resp.text else 'empty'}")
    try:
        result = resp.json()
        print(f"Response: {result}")
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return False

    if resp.status_code != 200:
        print(f"ERROR: Jump execution failed!")
        return False

    if not result.get("success"):
        print(f"ERROR: Jump not successful: {result.get('message')}")
        return False

    # 8. Verify position changed
    print("\nVerifying position changed...")
    resp = requests.get(f"{BASE_URL}/state")
    state = resp.json()

    hero_entity = None
    for entity in state.get("entities", []):
        if entity.get("uuid") == hero_uuid:
            hero_entity = entity
            break

    if not hero_entity:
        print("ERROR: Could not find hero in state!")
        return False

    final_pos = tuple(hero_entity.get("position"))
    print(f"Final position: {final_pos}")

    if final_pos == target_pos:
        print("\nSUCCESS: Jump moved entity to correct position!")
        return True
    else:
        print(f"\nFAILED: Expected {target_pos}, got {final_pos}")
        return False


if __name__ == "__main__":
    if not start_server():
        sys.exit(1)

    try:
        success = test_jump_via_api()
    finally:
        stop_server()

    sys.exit(0 if success else 1)
