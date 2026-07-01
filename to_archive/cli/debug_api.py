"""
Debug script to dump raw API responses and understand the data structure.
Run with server running: uv run python -m cli.debug_api
"""

import httpx
import json

BASE_URL = "http://localhost:8000"


def dump_json(name: str, data: dict):
    """Pretty print JSON data with a header."""
    print(f"\n{'='*80}")
    print(f"  {name}")
    print('='*80)
    print(json.dumps(data, indent=2, default=str))


def main():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    try:

        print("\n[1] Starting human game...")
        resp = client.post("/simulation/start-human")
        resp.raise_for_status()
        start_data = resp.json()
        dump_json("POST /simulation/start-human", start_data)

        entity_uuid = start_data.get("entity_uuid")
        print(f"\nHuman entity UUID: {entity_uuid}")

        print("\n[2] Getting full state...")
        resp = client.get("/state")
        resp.raise_for_status()
        state_data = resp.json()
        dump_json("GET /state", state_data)

        print("\n[3] Getting current turn...")
        resp = client.get("/encounter/current-turn")
        resp.raise_for_status()
        turn_data = resp.json()
        dump_json("GET /encounter/current-turn", turn_data)

        print("\n[4] Getting available actions...")
        resp = client.get(f"/entity/{entity_uuid}/available-actions")
        resp.raise_for_status()
        actions_data = resp.json()
        dump_json(f"GET /entity/{entity_uuid}/available-actions", actions_data)

        movement = actions_data.get("movement", [])
        if movement:
            print(f"\n[5] Movement data analysis:")
            print(f"  - Number of movement entries: {len(movement)}")
            print(f"  - First entry keys: {list(movement[0].keys()) if movement else 'N/A'}")
            valid_positions = movement[0].get("valid_positions", []) if movement else []
            print(f"  - Number of valid positions: {len(valid_positions)}")
            if valid_positions[:5]:
                print(f"  - First 5 positions: {valid_positions[:5]}")

        attacks = actions_data.get("attacks", [])
        if attacks:
            print(f"\n[6] Attack data analysis:")
            for i, atk in enumerate(attacks):
                print(f"  Attack {i+1}:")
                print(f"    - name: {atk.get('name')}")
                print(f"    - action_id: {atk.get('action_id')}")
                print(f"    - can_afford: {atk.get('can_afford')}")
                print(f"    - valid_targets: {atk.get('valid_targets')}")
                print(f"    - weapon_slot: {atk.get('weapon_slot')}")

        target_uuid = None
        for atk in attacks:
            targets = atk.get("valid_targets", [])
            if targets:
                target_uuid = targets[0]
                break

        if target_uuid:
            print(f"\n[7] Testing attack on target {target_uuid}...")
            resp = client.post("/action/attack", json={
                "entity_uuid": entity_uuid,
                "target_uuid": target_uuid,
                "weapon_slot": "main_hand"
            })
            resp.raise_for_status()
            attack_result = resp.json()
            dump_json("POST /action/attack", attack_result)

            print(f"\n[8] Attack result analysis:")
            print(f"  - success: {attack_result.get('success')}")
            print(f"  - message: {attack_result.get('message')}")
            print(f"  - event_type: {attack_result.get('event_type')}")
            print(f"  - event_data keys: {list(attack_result.get('event_data', {}).keys())}")

            event_data = attack_result.get("event_data", {})
            print(f"  - outcome: {event_data.get('outcome')}")
            print(f"  - roll: {event_data.get('roll')}")
            print(f"  - damage: {event_data.get('damage')}")
            print(f"  - attack_outcome: {event_data.get('attack_outcome')}")
            print(f"  - dice_roll: {event_data.get('dice_roll')}")
        else:
            print("\n[7] No valid attack targets available (need to move closer)")

            if movement and valid_positions:

                entities = state_data.get("entities", [])
                enemy = next((e for e in entities if e["uuid"] != entity_uuid), None)
                if enemy:
                    enemy_pos = tuple(enemy["position"])
                    print(f"\n[7b] Enemy at {enemy_pos}, trying to move closer...")

                    def dist(p):
                        return abs(p[0] - enemy_pos[0]) + abs(p[1] - enemy_pos[1])

                    valid_tuples = [tuple(p) for p in valid_positions]
                    closest = min(valid_tuples, key=dist)
                    print(f"  Moving to {closest}...")

                    resp = client.post("/action/move", json={
                        "entity_uuid": entity_uuid,
                        "position": list(closest)
                    })
                    resp.raise_for_status()
                    move_result = resp.json()
                    dump_json("POST /action/move", move_result)

        print("\n[9] Ending turn to trigger AI...")
        resp = client.post("/action/end-turn", json={"entity_uuid": entity_uuid})
        resp.raise_for_status()
        end_result = resp.json()
        dump_json("POST /action/end-turn", end_result)

        print("\n[10] State after AI turn...")
        resp = client.get("/state")
        resp.raise_for_status()
        state_after = resp.json()
        dump_json("GET /state (after AI)", state_after)

    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    main()
