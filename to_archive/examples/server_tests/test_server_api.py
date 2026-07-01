#!/usr/bin/env python3
"""
Test script for the new generic action API endpoints.

Tests the new functional API endpoints:
- POST /action/self - Self-targeting actions (Dash, Dodge, Disengage, StandUp)
- POST /action/entity - Entity-targeting actions (Attack)
- POST /action/position - Position-targeting actions (Move)
- POST /action/execute - Generic by index

Usage:
    # Start server first:
    uvicorn server.event_server:app --reload

    # Run test:
    python -m examples.test_server_api

Note: This is a manual integration test, not a unit test.
"""

import requests
import sys
import os
import subprocess
import time
import atexit
from pathlib import Path

PORT = int(os.environ.get("DND_TEST_SERVER_API_PORT", "8769"))
BASE_URL = f"http://localhost:{PORT}"
ROOT = Path(__file__).resolve().parents[2]
server_process = None


def start_server() -> bool:
    """Start a local uvicorn server for this integration test."""
    global server_process
    print(f"[INFO] Starting server on port {PORT}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.event_server:app",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    atexit.register(stop_server)
    for _ in range(60):
        try:
            resp = requests.get(f"{BASE_URL}/", timeout=1)
            if resp.status_code == 200:
                print("[PASS] Server ready")
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return False


def stop_server() -> None:
    """Stop the local uvicorn server if this test started one."""
    global server_process
    if server_process:
        server_process.terminate()
        try:
            _stdout, stderr = server_process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            server_process.kill()
            _stdout, stderr = server_process.communicate(timeout=5)
        if stderr:
            print("\n=== Server stderr ===")
            print(stderr.decode(errors="replace")[-2000:])
        server_process = None


def print_result(name: str, response: requests.Response) -> dict:
    """Print test result and return JSON."""
    status = "PASS" if response.ok else "FAIL"
    print(f"\n[{status}] {name}")
    print(f"  Status: {response.status_code}")
    if response.ok:
        data = response.json()
        if isinstance(data, dict):
            for key, value in data.items():
                if key not in ("event_data",):  # Skip verbose data
                    print(f"  {key}: {value}")
        return data
    else:
        print(f"  Error: {response.text}")
        return {}


def test_session_flow():
    """Test creating a session and joining a game."""
    print("\n" + "=" * 60)
    print("Testing Session Flow")
    print("=" * 60)

    # Start human simulation
    resp = requests.post(f"{BASE_URL}/simulation/start-human")
    if not resp.ok:
        print(f"[FAIL] Failed to start simulation: {resp.text}")
        return None, None, None

    data = resp.json()
    print(f"\n[PASS] Started simulation")
    print(f"  Hero UUID: {data.get('hero_uuid')}")
    print(f"  Skeleton UUID: {data.get('skeleton_uuid')}")

    hero_uuid = data.get("hero_uuid")
    skeleton_uuid = data.get("skeleton_uuid")

    # Create a human session
    resp = requests.post(f"{BASE_URL}/session/create", json={
        "player_type": "human",
        "name": "Test Player"
    })
    session_data = print_result("Create Session", resp)
    session_id = session_data.get("session_id")

    if not session_id:
        print("[FAIL] No session ID returned")
        return None, None, None

    # Join game with hero
    resp = requests.post(f"{BASE_URL}/game/join", json={
        "session_id": session_id,
        "entity_uuids": [hero_uuid]
    })
    _ = print_result("Join Game", resp)

    return session_id, hero_uuid, skeleton_uuid


def test_available_actions(entity_uuid: str):
    """Test getting available actions."""
    print("\n" + "=" * 60)
    print("Testing Available Actions")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/entity/{entity_uuid}/available-actions")
    data = print_result("Get Available Actions", resp)

    if data:
        print(f"\n  Entity Actions ({len(data.get('entity_actions', []))}):")
        for action in data.get("entity_actions", []):
            print(f"    - {action.get('template_name')}: {len(action.get('valid_targets', []))} targets")

        print(f"\n  Position Actions ({len(data.get('position_actions', []))}):")
        for action in data.get("position_actions", []):
            print(f"    - {action.get('template_name')}: {len(action.get('valid_targets', []))} positions")

        print(f"\n  Self Actions ({len(data.get('self_actions', []))}):")
        for action in data.get("self_actions", []):
            print(f"    - {action.get('template_name')}")

    return data


def test_self_action(session_id: str, entity_uuid: str, action_name: str):
    """Test executing a self-targeting action."""
    print("\n" + "-" * 40)
    print(f"Testing /action/self: {action_name}")
    print("-" * 40)

    resp = requests.post(f"{BASE_URL}/action/self", json={
        "session_id": session_id,
        "entity_uuid": entity_uuid,
        "action_name": action_name
    })
    return print_result(f"Execute {action_name}", resp)


def test_entity_action(session_id: str, entity_uuid: str, action_name: str, target_uuid: str):
    """Test executing an entity-targeting action."""
    print("\n" + "-" * 40)
    print(f"Testing /action/entity: {action_name}")
    print("-" * 40)

    resp = requests.post(f"{BASE_URL}/action/entity", json={
        "session_id": session_id,
        "entity_uuid": entity_uuid,
        "action_name": action_name,
        "target_uuid": target_uuid
    })
    return print_result(f"Execute {action_name}", resp)


def test_position_action(session_id: str, entity_uuid: str, action_name: str, position: tuple):
    """Test executing a position-targeting action."""
    print("\n" + "-" * 40)
    print(f"Testing /action/position: {action_name} to {position}")
    print("-" * 40)

    resp = requests.post(f"{BASE_URL}/action/position", json={
        "session_id": session_id,
        "entity_uuid": entity_uuid,
        "action_name": action_name,
        "position": list(position)
    })
    return print_result(f"Execute {action_name}", resp)


def test_execute_by_index(session_id: str, entity_uuid: str, template_name: str, target_index: int):
    """Test executing action by index."""
    print("\n" + "-" * 40)
    print(f"Testing /action/execute: {template_name} index={target_index}")
    print("-" * 40)

    resp = requests.post(f"{BASE_URL}/action/execute", json={
        "session_id": session_id,
        "entity_uuid": entity_uuid,
        "template_name": template_name,
        "target_index": target_index
    })
    return print_result(f"Execute {template_name} by index", resp)


def test_end_turn(session_id: str, entity_uuid: str):
    """Test ending turn."""
    print("\n" + "-" * 40)
    print("Testing /action/end-turn")
    print("-" * 40)

    resp = requests.post(f"{BASE_URL}/action/end-turn", json={
        "session_id": session_id,
        "entity_uuid": entity_uuid
    })
    return print_result("End Turn", resp)


def main():
    """Run all tests."""
    print("=" * 60)
    print("D&D Engine - New Server API Test")
    print("=" * 60)

    # Check server is running; start one if needed.
    try:
        resp = requests.get(f"{BASE_URL}/state", timeout=2)
        if not resp.ok:
            print(f"[FAIL] Server returned {resp.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        if not start_server():
            print("[FAIL] Cannot start local server")
            sys.exit(1)

    print("[PASS] Server is running")

    # Test session flow
    session_id, hero_uuid, _ = test_session_flow()
    if not session_id or not hero_uuid:
        print("\n[FAIL] Session setup failed")
        sys.exit(1)

    # Type narrow: we know these are now valid strings
    assert isinstance(session_id, str) and isinstance(hero_uuid, str)

    # Test available actions
    actions_data = test_available_actions(hero_uuid)
    if not actions_data:
        print("\n[FAIL] Available actions query failed")
        sys.exit(1)

    # Test self action (Dash)
    test_self_action(session_id, hero_uuid, "Dash")

    # Check available actions again to verify action consumed
    actions_data = test_available_actions(hero_uuid)

    # Test position action (Move) - find a valid position
    move_action = None
    for action in actions_data.get("position_actions", []):
        if action.get("template_name") == "Move":
            move_action = action
            break

    if move_action and move_action.get("valid_targets"):
        # Find a position near the skeleton for combat
        target_pos = move_action["valid_targets"][0].get("position")
        if target_pos:
            test_position_action(session_id, hero_uuid, "Move", tuple(target_pos))

    # End turn
    test_end_turn(session_id, hero_uuid)

    # Wait for AI turn to complete, then test attack
    print("\n[INFO] Waiting for AI turn...")
    import time
    time.sleep(1)

    # Check whose turn it is
    resp = requests.get(f"{BASE_URL}/pvp/status")
    if resp.ok:
        pvp_data = resp.json()
        print(f"  Current entity: {pvp_data.get('current_entity')}")
        print(f"  Is human turn: {pvp_data.get('is_human_turn')}")

        if pvp_data.get("is_human_turn"):
            # Get fresh actions
            actions_data = test_available_actions(hero_uuid)

            # Test entity action (Attack) if target in range
            attack_action = None
            for action in actions_data.get("entity_actions", []):
                if action.get("template_name", "").startswith("Attack_"):
                    attack_action = action
                    break

            if attack_action and attack_action.get("valid_targets"):
                target = attack_action["valid_targets"][0]
                test_entity_action(
                    session_id, hero_uuid,
                    attack_action["template_name"],
                    target.get("target_uuid")
                )

            # Test execute by index if we have targets
            if attack_action and attack_action.get("valid_targets"):
                test_execute_by_index(
                    session_id, hero_uuid,
                    attack_action["template_name"],
                    0  # First target
                )

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
