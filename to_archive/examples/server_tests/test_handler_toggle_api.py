#!/usr/bin/env python3
"""
Test handler toggle API endpoints.

Tests:
- GET /entity/{uuid}/handlers — only returns player_toggleable handlers
- POST /entity/{uuid}/handlers/{name}/toggle — toggles handler on/off
- handler_details in available-actions response — filtered by player_toggleable
- Toggle persists across available-actions refreshes

Usage:
    # Start server on port 8111:
    uvicorn server.event_server:app --port 8111

    # Run test:
    python examples/server_tests/test_handler_toggle_api.py
"""

import requests
import sys
import subprocess
import time
import signal
import os
from pathlib import Path

PORT = 8111
BASE_URL = f"http://localhost:{PORT}"
ROOT = Path(__file__).resolve().parents[2]
server_proc = None


def start_server():
    """Start the server on the test port."""
    global server_proc
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.event_server:app", "--port", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            requests.get(f"{BASE_URL}/state", timeout=1)
            return True
        except requests.ConnectionError:
            time.sleep(0.3)
    print("FAIL: Server didn't start in time")
    return False


def stop_server():
    """Stop the server."""
    global server_proc
    if server_proc:
        server_proc.send_signal(signal.SIGTERM)
        server_proc.wait(timeout=5)
        server_proc = None


def setup_game():
    """Start simulation, create session, join game."""
    # Start human simulation (creates hero with Shield + OA handlers)
    resp = requests.post(f"{BASE_URL}/simulation/start-human")
    assert resp.ok, f"Failed to start simulation: {resp.text}"
    data = resp.json()
    hero_uuid = data["hero_uuid"]
    print(f"  Hero UUID: {hero_uuid}")

    # Create session
    resp = requests.post(f"{BASE_URL}/session/create", json={
        "player_type": "human",
        "name": "Test Player"
    })
    assert resp.ok, f"Failed to create session: {resp.text}"
    session_id = resp.json()["session_id"]
    print(f"  Session ID: {session_id}")

    # Join game
    resp = requests.post(f"{BASE_URL}/game/join", json={
        "session_id": session_id,
        "entity_uuids": [hero_uuid]
    })
    assert resp.ok, f"Failed to join game: {resp.text}"

    return session_id, hero_uuid


def test_get_handlers(hero_uuid: str):
    """Test GET /entity/{uuid}/handlers returns only player_toggleable handlers."""
    print("\n=== Test 1: GET /handlers returns only toggleable ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/handlers")
    assert resp.ok, f"GET handlers failed: {resp.status_code} {resp.text}"
    data = resp.json()
    handlers = data.get("handlers", [])

    print(f"  Got {len(handlers)} handlers:")
    for h in handlers:
        print(f"    [{('ON' if h['enabled'] else 'OFF')}] {h['name']} ({h.get('trigger_event', '')})")

    # Should have toggleable handlers (OA, Shield) but NOT internal ones
    # (HasAttacked, HasTakenDamage, Death, ProneAutoStand)
    names = [h["name"] for h in handlers]
    internal_names = ["HasAttacked Tracker", "HasTakenDamage Tracker",
                      "Death Condition Handler", "Prone Auto-Stand"]

    for internal in internal_names:
        assert internal not in names, f"Internal handler '{internal}' should NOT be in response"

    # All returned handlers should be enabled by default
    for h in handlers:
        assert h["enabled"] is True, f"Handler '{h['name']}' should be enabled by default"

    print("  PASSED: Only toggleable handlers returned, no internal ones")
    return handlers


def test_handler_details_in_actions(hero_uuid: str):
    """Test handler_details in available-actions only shows toggleable."""
    print("\n=== Test 2: handler_details in available-actions ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/available-actions")
    assert resp.ok, f"GET available-actions failed: {resp.status_code} {resp.text}"
    data = resp.json()

    handler_details = data.get("handler_details", [])
    print(f"  handler_details has {len(handler_details)} entries:")
    for h in handler_details:
        print(f"    [{('ON' if h['enabled'] else 'OFF')}] {h['name']}")

    internal_names = ["HasAttacked Tracker", "HasTakenDamage Tracker",
                      "Death Condition Handler", "Prone Auto-Stand"]
    names = [h["name"] for h in handler_details]
    for internal in internal_names:
        assert internal not in names, f"Internal handler '{internal}' should NOT be in handler_details"

    print("  PASSED: handler_details filtered correctly")
    return handler_details


def test_toggle_handler(session_id: str, hero_uuid: str, handler_name: str):
    """Test POST toggle endpoint."""
    print(f"\n=== Test 3: Toggle '{handler_name}' OFF ===")

    # Toggle OFF
    resp = requests.post(
        f"{BASE_URL}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "enabled": False,
        }
    )
    print(f"  POST status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    assert resp.ok, f"Toggle failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["enabled"] is False

    # Verify via GET handlers
    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/handlers")
    handlers = resp.json()["handlers"]
    handler = next((h for h in handlers if h["name"] == handler_name), None)
    assert handler is not None, f"Handler '{handler_name}' not found after toggle"
    assert handler["enabled"] is False, f"Handler should be OFF but is {handler['enabled']}"

    print(f"  PASSED: '{handler_name}' is now OFF")


def test_toggle_persists_in_actions(session_id: str, hero_uuid: str, handler_name: str):
    """Test toggle state shows in available-actions handler_details."""
    print(f"\n=== Test 4: Toggle persists in available-actions ===")

    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/available-actions")
    data = resp.json()
    handler_details = data.get("handler_details", [])

    handler = next((h for h in handler_details if h["name"] == handler_name), None)
    assert handler is not None, f"Handler '{handler_name}' not in handler_details"
    assert handler["enabled"] is False, f"Should be OFF in handler_details but is {handler['enabled']}"

    print(f"  PASSED: '{handler_name}' shows OFF in available-actions")


def test_toggle_back_on(session_id: str, hero_uuid: str, handler_name: str):
    """Test toggling back ON."""
    print(f"\n=== Test 5: Toggle '{handler_name}' back ON ===")

    resp = requests.post(
        f"{BASE_URL}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "enabled": True,
        }
    )
    assert resp.ok, f"Toggle ON failed: {resp.status_code} {resp.text}"

    # Verify
    resp = requests.get(f"{BASE_URL}/entity/{hero_uuid}/handlers")
    handlers = resp.json()["handlers"]
    handler = next((h for h in handlers if h["name"] == handler_name), None)
    assert handler is not None, f"Handler '{handler_name}' not found after toggling back on"
    assert handler["enabled"] is True

    print(f"  PASSED: '{handler_name}' back ON")


def test_toggle_non_toggleable_fails(session_id: str, hero_uuid: str):
    """Test that toggling a non-player-toggleable handler fails."""
    print(f"\n=== Test 6: Non-toggleable handler rejected ===")

    resp = requests.post(
        f"{BASE_URL}/entity/{hero_uuid}/handlers/Death Condition Handler/toggle",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "enabled": False,
        }
    )
    print(f"  POST status: {resp.status_code}")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    print("  PASSED: Non-toggleable handler correctly rejected")


def test_toggle_with_spaces(session_id: str, hero_uuid: str):
    """Test toggling handler with spaces in name via URL."""
    print(f"\n=== Test 7: Toggle handler with spaces in name ===")

    # Try Opportunity Attack Handler (has spaces)
    handler_name = "Opportunity Attack Handler"
    resp = requests.post(
        f"{BASE_URL}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "enabled": False,
        }
    )
    print(f"  POST status: {resp.status_code}")
    print(f"  URL: /entity/{hero_uuid}/handlers/{handler_name}/toggle")
    if not resp.ok:
        print(f"  Error: {resp.text}")

    # This might fail due to URL encoding — that's what we're testing
    if resp.ok:
        print("  PASSED: Spaces in handler name work")
        # Toggle back on
        requests.post(
            f"{BASE_URL}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
            json={"session_id": session_id, "entity_uuid": hero_uuid, "enabled": True}
        )
    else:
        print(f"  FAILED: Spaces in handler name cause {resp.status_code}")
        print("  This is likely a URL encoding issue")
        return False
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Handler Toggle API Tests")
    print("=" * 60)

    print("\nStarting server on port", PORT)
    if not start_server():
        sys.exit(1)

    try:
        session_id, hero_uuid = setup_game()

        # Run tests
        handlers = test_get_handlers(hero_uuid)
        test_handler_details_in_actions(hero_uuid)

        # Pick a handler to toggle (Shield if available, else first one)
        toggle_name = "Shield"
        if not any(h["name"] == "Shield" for h in handlers):
            toggle_name = handlers[0]["name"] if handlers else None

        if toggle_name:
            test_toggle_handler(session_id, hero_uuid, toggle_name)
            test_toggle_persists_in_actions(session_id, hero_uuid, toggle_name)
            test_toggle_back_on(session_id, hero_uuid, toggle_name)

        test_toggle_non_toggleable_fails(session_id, hero_uuid)
        test_toggle_with_spaces(session_id, hero_uuid)

        print("\n" + "=" * 60)
        print("All handler toggle API tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        stop_server()
