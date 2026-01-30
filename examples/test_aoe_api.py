"""
Test AoE spells via API - verify server-side POSITION_AOE execution works.

This test starts its own server, creates a game with a spellcaster,
and tests Fireball execution via the API.
"""

import subprocess
import requests
import sys
import atexit

BASE_URL = "http://localhost:8766"  # Different port to avoid conflicts
server_process = None


def start_server():
    """Start the server in a subprocess."""
    global server_process
    print("Starting server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.event_server:app",
         "--port", "8766", "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    atexit.register(stop_server)

    import time
    for _ in range(50):
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
        _, stderr = server_process.communicate(timeout=5)
        if stderr:
            print("\n=== Server stderr ===")
            print(stderr.decode()[-2000:])  # Last 2000 chars
        server_process = None


def test_aoe_via_api():
    """Test AoE spell (Fireball) through the server API."""
    print("\n=== Test AoE via API ===")

    # 1. Start AoE test arena (clustered goblins for Fireball)
    print("Starting AoE test arena...")
    resp = requests.post(f"{BASE_URL}/simulation/start-aoe-test")

    if resp.status_code != 200:
        print(f"Failed to start arena: {resp.status_code} {resp.text}")
        return False

    arena_data = resp.json()
    hero_uuid = arena_data.get("hero_uuid")
    print(f"Sorcerer UUID: {hero_uuid}")
    print(f"Arena type: {arena_data.get('test_type')}")

    # 2. Create session and join
    print("\nCreating session...")
    resp = requests.post(f"{BASE_URL}/session/create", json={
        "player_type": "human", "name": "Test Player"
    })
    session_id = resp.json().get("session_id")
    print(f"Session ID: {session_id}")

    resp = requests.post(f"{BASE_URL}/game/join", json={
        "session_id": session_id, "entity_uuids": [hero_uuid]
    })
    print(f"Joined game: {resp.json()}")

    # 3. Get available actions
    print("\nFetching available actions...")
    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/available-actions")
    actions = resp.json()

    # Print all position actions for debugging
    print(f"Position actions available: {[a.get('template_name') for a in actions.get('position_actions', [])]}")

    # 4. Find Fireball in position_actions
    fireball_action = None
    for action in actions.get("position_actions", []):
        if action.get("template_name") == "Fireball":
            fireball_action = action
            break

    if not fireball_action:
        print("ERROR: Fireball not found in position_actions!")
        print("All position actions:")
        for a in actions.get("position_actions", []):
            print(f"  - {a.get('template_name')}: {len(a.get('valid_targets', []))} targets")
        return False

    print(f"\nFireball action found!")
    print(f"  Valid targets count: {len(fireball_action.get('valid_targets', []))}")
    print(f"  Can afford: {fireball_action.get('can_afford')}")

    # 5. Find best target position (most affected entities)
    valid_targets = fireball_action.get("valid_targets", [])
    if not valid_targets:
        print("ERROR: No valid fireball targets!")
        return False

    # Debug: show some targets with affected entities
    targets_with_affected = [t for t in valid_targets if t.get("affected_count", 0) > 0]
    print(f"\nTargets with affected_count > 0: {len(targets_with_affected)}")
    if targets_with_affected:
        for t in targets_with_affected[:5]:
            print(f"  {t.get('position')}: {t.get('affected_count')} - {t.get('affected_entity_names')}")

    # Find target with max affected entities
    best_target = max(valid_targets, key=lambda t: t.get("affected_count", 0))
    target_pos = tuple(best_target.get("position"))
    affected_count = best_target.get("affected_count", 0)
    affected_names = best_target.get("affected_entity_names", [])

    print(f"\nBest target position: {target_pos}")
    print(f"  Affected entities: {affected_count}")
    print(f"  Names: {affected_names}")

    # Verify we're hitting multiple targets (the whole point of this test!)
    if affected_count < 2:
        print(f"WARNING: Only {affected_count} targets affected. Expected 2-3 goblins clustered.")

    # 6. Execute Fireball via /action/position
    print("\n=== Casting Fireball ===")
    resp = requests.post(f"{BASE_URL}/action/position", json={
        "session_id": session_id,
        "entity_uuid": hero_uuid,
        "action_name": "Fireball",
        "position": list(target_pos)
    })

    if resp.status_code != 200:
        print(f"ERROR: Fireball execution failed: {resp.status_code} {resp.text}")
        return False

    result = resp.json()
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    # 7. Check combat log entries
    combat_log_entries = result.get("combat_log_entries", [])
    print(f"\n=== Combat Log Entries ({len(combat_log_entries)}) ===")

    for i, entry in enumerate(combat_log_entries):
        entry_type = entry.get("entry_type", "unknown")
        compact = entry.get("compact", "")
        print(f"  {i+1}. [{entry_type}] {compact}")

    # Verify we got aggregate log
    entry_types = [e.get("entry_type") for e in combat_log_entries]
    has_aggregate = "multi_entity_action" in entry_types

    if has_aggregate:
        print("\n SUCCESS: Got aggregate multi_entity_action log!")

        # Find and display the aggregate log details
        for entry in combat_log_entries:
            if entry.get("entry_type") == "multi_entity_action":
                print("\n--- Aggregate Log Details ---")
                print(f"Compact: {entry.get('compact')}")
                print(f"Verbose:\n{entry.get('verbose')}")
                data = entry.get("data", {})
                print(f"\nStructured data:")
                print(f"  Total targets: {data.get('total_targets')}")
                print(f"  Total damage: {data.get('total_damage')}")
                print(f"  Saves succeeded: {data.get('saves_succeeded')}")
                print(f"  Saves failed: {data.get('saves_failed')}")
                break
    else:
        print(f"\n FAIL: No multi_entity_action log found. Types: {entry_types}")

    # 8. Get full combat log from server
    print("\n=== Full Combat Log ===")
    resp = requests.get(f"{BASE_URL}/combat-log")
    log_data = resp.json()
    print(f"Total entries on server: {log_data.get('total')}")

    return result.get("success", False) and has_aggregate


if __name__ == "__main__":
    if not start_server():
        sys.exit(1)

    success = False
    try:
        success = test_aoe_via_api()
    finally:
        stop_server()

    print(f"\n{'='*50}")
    print(f"TEST {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
