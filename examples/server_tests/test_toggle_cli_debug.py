#!/usr/bin/env python3
"""
Debug test: simulates exactly what the human CLI does for toggle command.
Starts server, creates session, then traces the full command path.

Usage:
    python examples/server_tests/test_toggle_cli_debug.py
"""
import subprocess, time, signal, sys, requests
import os
from pathlib import Path

PORT = 8222
BASE = f"http://localhost:{PORT}"
ROOT = Path(__file__).resolve().parents[2]

# Start server
env = os.environ.copy()
env["PYTHONPATH"] = str(ROOT)
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server.event_server:app", "--port", str(PORT)],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    env=env,
)
for _ in range(30):
    try:
        requests.get(f"{BASE}/state", timeout=1)
        break
    except requests.ConnectionError:
        time.sleep(0.3)
else:
    print("Server didn't start"); sys.exit(1)

try:
    # Setup game
    r = requests.post(f"{BASE}/simulation/start-human", params={"character_class": "sorcerer"})
    r.raise_for_status()
    hero_uuid = r.json()["hero_uuid"]
    print(f"Hero: {hero_uuid}")

    r = requests.post(f"{BASE}/session/create", json={"player_type": "human", "name": "Test"})
    r.raise_for_status()
    session_id = r.json()["session_id"]
    print(f"Session: {session_id}")

    r = requests.post(f"{BASE}/game/join", json={"session_id": session_id, "entity_uuids": [hero_uuid]})
    r.raise_for_status()
    print(f"Joined: {r.json()}")

    # Step 1: Check what handlers exist
    print("\n--- GET /handlers ---")
    r = requests.get(f"{BASE}/entity/{hero_uuid}/handlers")
    print(f"Status: {r.status_code}")
    handlers = r.json().get("handlers", [])
    for h in handlers:
        print(f"  {h['name']} enabled={h['enabled']}")

    # Step 2: Check handler_details in available-actions
    print("\n--- handler_details in available-actions ---")
    r = requests.get(f"{BASE}/entity/{hero_uuid}/available-actions")
    details = r.json().get("handler_details", [])
    for h in details:
        print(f"  {h['name']} enabled={h['enabled']}")

    # Step 3: Now simulate what CLI does
    # parse_command("toggle shield off") -> cmd="toggle", args=["shield", "off"]
    # handle_toggle extracts: handler_name="shield", enabled=False
    # client.toggle_handler("shield", False, hero_uuid)
    handler_name = "shield"
    print(f"\n--- POST toggle '{handler_name}' OFF ---")
    print(f"URL: {BASE}/entity/{hero_uuid}/handlers/{handler_name}/toggle")
    r = requests.post(
        f"{BASE}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={"session_id": session_id, "entity_uuid": hero_uuid, "enabled": False}
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text}")

    # Also try with full name
    handler_name = "Shield"
    print(f"\n--- POST toggle '{handler_name}' OFF (capitalized) ---")
    r = requests.post(
        f"{BASE}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={"session_id": session_id, "entity_uuid": hero_uuid, "enabled": False}
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text}")

    # Try OA handler
    handler_name = "opportunity attack handler"
    print(f"\n--- POST toggle '{handler_name}' OFF (lowercase) ---")
    r = requests.post(
        f"{BASE}/entity/{hero_uuid}/handlers/{handler_name}/toggle",
        json={"session_id": session_id, "entity_uuid": hero_uuid, "enabled": False}
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text}")

    # Verify final state
    print("\n--- Final handler state ---")
    r = requests.get(f"{BASE}/entity/{hero_uuid}/handlers")
    for h in r.json().get("handlers", []):
        print(f"  {h['name']} enabled={h['enabled']}")

    print("\n--- Final handler_details ---")
    r = requests.get(f"{BASE}/entity/{hero_uuid}/available-actions")
    for h in r.json().get("handler_details", []):
        print(f"  {h['name']} enabled={h['enabled']}")

finally:
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)
