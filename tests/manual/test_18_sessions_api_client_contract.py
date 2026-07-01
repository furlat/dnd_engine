"""Manual Chapter 18 checks for sessions, API payloads, and client cursors."""

import asyncio
from uuid import UUID, uuid4

import httpx

from dnd.controller import Controller, HumanController, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.dice import fixed_dice_faces
from dnd.core.base_object import BaseObject
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from server.event_server import app, sim
from server.event_stream import event_stream, format_sse, make_stream_id
from server.session import PlayerType


class ApiClient:
    """Synchronous wrapper over the real ASGI app for client-contract examples."""

    def get(self, path, **kwargs):
        """Issue a GET request to the in-process app."""
        return asyncio.run(self._request("GET", path, **kwargs))

    def post(self, path, **kwargs):
        """Issue a POST request to the in-process app."""
        return asyncio.run(self._request("POST", path, **kwargs))

    async def _request(self, method, path, **kwargs):
        """Run one request through HTTPX's ASGI transport."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://neurodragon.local",
        ) as client:
            return await client.request(method, path, **kwargs)


def reset_client_api_state(width: int = 16, height: int = 10) -> None:
    """Clear engine and server state for one client/API tutorial scene."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)

    sim.reset()


def create_api_pair() -> tuple[Entity, Entity]:
    """Create a hero and an adjacent monster for client API examples."""
    hero = create_goblin(name="Manual Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Manual Skeleton", position=(2, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)
    return hero, monster


def start_api_game(hero: Entity, monster: Entity) -> Encounter:
    """Start a deterministic encounter and attach it to server game state."""
    encounter = Encounter(name="Manual API Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    sim.encounter = encounter
    sim.create_game_session(encounter)
    return encounter


def create_session_and_join_hero(client: ApiClient, hero: Entity) -> str:
    """Create a human session and assign the hero to it."""
    response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Manual Player"},
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
    )
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [str(hero.uuid)]
    return session_id


def create_joined_client_game() -> tuple[ApiClient, str, Entity, Entity, Encounter]:
    """Create an active API scene with one joined human-controlled hero."""
    reset_client_api_state()
    hero, monster = create_api_pair()
    encounter = start_api_game(hero, monster)
    client = ApiClient()
    session_id = create_session_and_join_hero(client, hero)
    return client, session_id, hero, monster, encounter


def make_melee_attack_auto_hit(entity: Entity) -> UUID:
    """Add an explicit auto-hit modifier to the entity's melee attack bonus."""
    modifier = AutoHitModifier(
        name="Manual API Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def clear_melee_attack_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove an explicit melee attack modifier from an entity."""
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)


def attack_target_index(actions_payload: dict, target_uuid: UUID) -> int:
    """Return the available-actions target index for a melee attack target."""
    for action in actions_payload["entity_actions"]:
        if action["template_name"] != "Attack_MELEE_MAIN":
            continue
        for target in action["valid_targets"]:
            if target.get("target_uuid") == str(target_uuid):
                return target["index"]
    raise AssertionError("Manual Skeleton was not an available melee target")


def execute_manual_attack(
    client: ApiClient,
    session_id: str,
    hero: Entity,
    monster: Entity,
) -> dict:
    """Execute the hero's indexed melee attack through the public API."""
    actions = client.get(f"/entity/{hero.uuid}/available-actions").json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = make_melee_attack_auto_hit(hero)
    try:
        response = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": str(hero.uuid),
                "template_name": "Attack_MELEE_MAIN",
                "target_index": target_index,
            },
        )
    finally:
        clear_melee_attack_modifier(hero, modifier_uuid)

    assert response.status_code == 200
    return response.json()


def test_session_create_join_ping_and_game_status(capsys) -> None:
    """A client session can join the active game and control the hero."""
    reset_client_api_state()
    hero, monster = create_api_pair()
    encounter = start_api_game(hero, monster)
    client = ApiClient()

    create_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Manual Player"},
    )
    create_payload = create_response.json()

    assert create_response.status_code == 200
    assert create_payload["player_type"] == PlayerType.HUMAN.value
    assert create_payload["name"] == "Manual Player"

    session_id = create_payload["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
    )
    join_payload = join_response.json()

    assert join_response.status_code == 200
    assert join_payload["success"]
    assert join_payload["game_id"] == str(sim.game.game_id)
    assert join_payload["controlled_entities"] == [str(hero.uuid)]

    ping_response = client.post(f"/session/{session_id}/ping")
    ping_payload = ping_response.json()

    assert ping_response.status_code == 200
    assert ping_payload["is_my_turn"]
    assert ping_payload["active_entity_uuid"] == str(hero.uuid)
    assert ping_payload["controlled_entities"] == [str(hero.uuid)]

    status_payload = client.get("/game/status").json()

    assert status_payload["active"]
    assert status_payload["active_entity_uuid"] == str(hero.uuid)
    assert status_payload["encounter_active"]
    assert status_payload["sessions"][0]["is_their_turn"]
    assert encounter.get_current_entity() is hero
    assert sim.game.is_player_turn(UUID(session_id))

    readout_lines = [
        (
            "session created: "
            f"status={create_response.status_code}, "
            f"type={create_payload['player_type']}, "
            f"name={create_payload['name']}"
        ),
        (
            "join result: "
            f"success={'yes' if join_payload['success'] else 'no'}, "
            f"game_matches={'yes' if join_payload['game_id'] == str(sim.game.game_id) else 'no'}, "
            f"controlled={len(join_payload['controlled_entities'])}"
        ),
        (
            "turn ping: "
            f"my_turn={'yes' if ping_payload['is_my_turn'] else 'no'}, "
            "active=Manual Hero, "
            f"controlled={len(ping_payload['controlled_entities'])}"
        ),
        (
            "game status: "
            f"active={'yes' if status_payload['active'] else 'no'}, "
            f"encounter={'yes' if status_payload['encounter_active'] else 'no'}, "
            f"session_turn={'yes' if status_payload['sessions'][0]['is_their_turn'] else 'no'}"
        ),
    ]
    expected_lines = [
        "session created: status=200, type=human, name=Manual Player",
        "join result: success=yes, game_matches=yes, controlled=1",
        "turn ping: my_turn=yes, active=Manual Hero, controlled=1",
        "game status: active=yes, encounter=yes, session_turn=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_state_current_turn_and_available_actions_payloads(capsys) -> None:
    """State, current-turn, and available-action routes describe the scene."""
    client, session_id, hero, monster, _encounter = create_joined_client_game()

    state_payload = client.get("/state").json()
    entity_names = {entity["name"] for entity in state_payload["entities"]}
    current_turn = client.get("/encounter/current-turn").json()
    actions_payload = client.get(f"/entity/{hero.uuid}/available-actions").json()
    attack_names = {
        action["template_name"]
        for action in actions_payload["entity_actions"]
    }

    assert {"Manual Hero", "Manual Skeleton"} <= entity_names
    assert state_payload["encounter"]["current_entity_uuid"] == str(hero.uuid)
    assert current_turn["current_entity_uuid"] == str(hero.uuid)
    assert current_turn["controller_type"] == "human"
    assert current_turn["waiting_for_input"]
    assert current_turn["actions_remaining"] == 1
    assert actions_payload["entity_uuid"] == str(hero.uuid)
    assert "Attack_MELEE_MAIN" in attack_names
    assert attack_target_index(actions_payload, monster.uuid) == 0
    assert actions_payload["actions_remaining"] == 1
    assert session_id in client.get("/game/status").text

    readout_lines = [
        f"state snapshot: entities={sorted(entity_names)}, current=Manual Hero",
        (
            "turn payload: "
            f"controller={current_turn['controller_type']}, "
            f"waiting={'yes' if current_turn['waiting_for_input'] else 'no'}, "
            f"actions={current_turn['actions_remaining']}"
        ),
        (
            "action menu: "
            "entity=Manual Hero, "
            f"attacks={sorted(attack_names)}, "
            f"target_index={attack_target_index(actions_payload, monster.uuid)}"
        ),
        (
            "status echo: "
            f"session_seen={'yes' if session_id in client.get('/game/status').text else 'no'}, "
            f"actions_remaining={actions_payload['actions_remaining']}"
        ),
    ]
    expected_lines = [
        "state snapshot: entities=['Manual Hero', 'Manual Skeleton'], current=Manual Hero",
        "turn payload: controller=human, waiting=yes, actions=1",
        (
            "action menu: entity=Manual Hero, "
            "attacks=['Attack_MELEE_MAIN', 'Attack_RANGED_MAIN'], target_index=0"
        ),
        "status echo: session_seen=yes, actions_remaining=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_execute_action_by_index_returns_state_logs_and_cursors(capsys) -> None:
    """The client can execute a discovered target index and receive deltas."""
    client, session_id, hero, monster, encounter = create_joined_client_game()
    initial_monster_hp = monster.get_hp()

    with fixed_dice_faces(12, 4):
        result = execute_manual_attack(client, session_id, hero, monster)

    assert result["success"]
    assert result["event_type"] == "attack_melee_main"
    assert result["target_hp"] < initial_monster_hp
    assert result["entity_hp"] == hero.get_hp()
    assert result["turn_continues"]
    assert not result["encounter_ended"]
    assert result["combat_log_entries"]
    assert result["available_actions"]["actions_remaining"] == 0
    assert result["state"]["encounter"]["current_entity_uuid"] == str(hero.uuid)
    assert result["event_cursor_after"] == EventQueue.event_cursor()
    assert result["combat_log_cursor_after"] == len(encounter.combat_log)

    readout_lines = [
        (
            "execute result: "
            f"success={'yes' if result['success'] else 'no'}, "
            f"event={result['event_type']}, "
            f"turn_continues={'yes' if result['turn_continues'] else 'no'}"
        ),
        f"hit points: monster={initial_monster_hp}->{result['target_hp']}, hero={result['entity_hp']}",
        (
            "returned state: "
            "current=Manual Hero, "
            f"actions_remaining={result['available_actions']['actions_remaining']}, "
            f"ended={'yes' if result['encounter_ended'] else 'no'}"
        ),
        (
            "cursors: "
            f"events={result['event_cursor_after']}, "
            f"logs={result['combat_log_cursor_after']}, "
            f"log_entries={len(result['combat_log_entries'])}"
        ),
    ]
    expected_lines = [
        "execute result: success=yes, event=attack_melee_main, turn_continues=yes",
        "hit points: monster=17->11, hero=10",
        "returned state: current=Manual Hero, actions_remaining=0, ended=no",
        "cursors: events=78, logs=2, log_entries=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_event_and_combat_log_history_are_cursor_addressed(capsys) -> None:
    """Clients can poll or stream event and combat-log deltas by cursor."""
    client, session_id, hero, monster, encounter = create_joined_client_game()

    with fixed_dice_faces(12, 4):
        execute_manual_attack(client, session_id, hero, monster)

    events_payload = client.get("/events", params={"since": 0, "limit": 0}).json()
    logs_payload = client.get("/combat-log", params={"since": 0}).json()
    game_events = event_stream.iter_game_events_since(0, encounter)
    combat_logs = event_stream.iter_combat_logs_since(encounter, 0)
    latest_log = combat_logs[-1]
    frame = format_sse(
        "combat_log",
        latest_log,
        make_stream_id(latest_log.event_cursor, latest_log.combat_log_cursor),
    )

    assert events_payload["count"] == events_payload["total"]
    assert events_payload["total"] == EventQueue.event_cursor()
    assert any(event["phase"] == EventPhase.COMPLETION.value for event in events_payload["events"])
    assert logs_payload["count"] == logs_payload["total"]
    assert logs_payload["total"] == len(encounter.combat_log)
    assert game_events[-1].event_cursor == EventQueue.event_cursor()
    assert combat_logs[-1].combat_log_cursor == len(encounter.combat_log)
    assert frame.startswith("id: e=")
    assert "\nevent: combat_log\n" in frame

    completion_count = sum(
        1
        for event in events_payload["events"]
        if event["phase"] == EventPhase.COMPLETION.value
    )
    readout_lines = [
        (
            "event history: "
            f"route_count={events_payload['count']}, "
            f"total={events_payload['total']}, "
            f"completions={completion_count}"
        ),
        (
            "combat log: "
            f"route_count={logs_payload['count']}, "
            f"total={logs_payload['total']}, "
            f"latest_type={latest_log.entry.entry_type.value}"
        ),
        (
            "stream cursors: "
            f"event={game_events[-1].event_cursor}, "
            f"combat={combat_logs[-1].combat_log_cursor}"
        ),
        (
            "sse frame: "
            f"id={frame.splitlines()[0]}, "
            f"event_line={frame.splitlines()[1]}"
        ),
    ]
    expected_lines = [
        "event history: route_count=78, total=78, completions=19",
        "combat log: route_count=2, total=2, latest_type=attack",
        "stream cursors: event=78, combat=2",
        "sse frame: id=id: e=78;l=2, event_line=event: combat_log",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_spell_catalog_route_exposes_design_time_spell_metadata(capsys) -> None:
    """The spell catalog gives clients stable metadata for spell UI and VFX."""
    reset_client_api_state()
    client = ApiClient()

    response = client.get("/catalog/spells")
    payload = response.json()
    spells = {spell["id"]: spell for spell in payload["spells"]}

    assert response.status_code == 200
    assert payload["version"]
    assert {"fire_bolt", "magic_missile", "fireball"} <= set(spells)
    assert spells["fire_bolt"]["action_category"] == "spell"
    assert spells["fire_bolt"]["attack_roll"]
    assert spells["fire_bolt"]["range_ft"] is not None
    assert spells["magic_missile"]["multi_target"] is not None
    assert spells["fireball"]["aoe_shape_type"] == "sphere"
    assert "Fire" in spells["fireball"]["damage_types"]

    readout_lines = [
        (
            "catalog response: "
            f"status={response.status_code}, "
            f"version={payload['version']}, "
            f"spells={len(spells)}"
        ),
        (
            "fire bolt: "
            f"category={spells['fire_bolt']['action_category']}, "
            f"attack_roll={'yes' if spells['fire_bolt']['attack_roll'] else 'no'}, "
            f"range={spells['fire_bolt']['range_ft']}"
        ),
        (
            "magic missile: "
            f"multi_target={'yes' if spells['magic_missile']['multi_target'] is not None else 'no'}"
        ),
        (
            "fireball: "
            f"aoe={spells['fireball']['aoe_shape_type']}, "
            f"damage_types={spells['fireball']['damage_types']}"
        ),
    ]
    expected_lines = [
        "catalog response: status=200, version=2026-05-03.1, spells=109",
        "fire bolt: category=spell, attack_roll=yes, range=120",
        "magic missile: multi_target=yes",
        "fireball: aoe=sphere, damage_types=['Fire']",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
