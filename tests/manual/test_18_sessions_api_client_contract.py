"""Manual Chapter 18 checks for sessions, API payloads, and client cursors."""

import asyncio
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx

from dnd.controller import Controller, HumanController, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.dice import fixed_dice_faces
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from server.event_server import app, sim
from server.player_replication_contract import SubjectiveReplicationBootstrap
from server.session import (
    ConnectionStatus,
    PlayerSession,
    PlayerType,
    SessionManager,
)


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


def replication_seed(client: ApiClient, session_id: str) -> dict:
    """Fetch the sole expectation-free player replication entry point."""
    response = client.get("/replication/bootstrap", params={"session_id": session_id})
    assert response.status_code == 200
    return response.json()


def replication_window(client: ApiClient, session_id: str, seed: dict) -> tuple[dict, dict]:
    """Fetch exact subjective reducer and combat-log windows after one seed."""
    identity = {
        "session_id": session_id,
        "expected_source_stream_id": seed["protocol"]["source_stream_id"],
        "expected_generation_id": seed["protocol"]["generation_id"],
        "expected_perspective_epoch_id": seed["perspective"]["perspective_epoch_id"],
    }
    frames = client.get(
        "/replication/frames",
        params={
            **identity,
            "from_observation_cursor": seed["watermarks"]["observation_cursor"],
        },
    )
    logs = client.get(
        "/replication/combat-log",
        params={
            **identity,
            "from_combat_log_cursor": seed["watermarks"]["combat_log_cursor"],
        },
    )
    assert frames.status_code == logs.status_code == 200
    return frames.json(), logs.json()


def test_session_manager_reset_preserves_the_shared_registry() -> None:
    """Arena resets clear session state without creating a split registry."""
    reset_client_api_state()
    manager = sim.get_session_manager()
    manager.create_session(PlayerType.HUMAN, "Reset Probe")

    SessionManager.reset()

    assert SessionManager.get() is manager
    assert manager.sessions == {}
    assert manager.games == {}
    assert manager.active_game is None


def test_player_session_activity_disconnect_and_ping_reconnect() -> None:
    """Ping advances activity exactly and reconnects a disconnected session."""
    session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.HUMAN,
        name="Lifecycle Probe",
        last_activity=100.0,
    )

    assert session.connection_status is ConnectionStatus.CONNECTED
    assert session.last_activity == 100.0

    with patch("server.session.time.time", return_value=101.25):
        session.ping()

    assert session.last_activity == 101.25
    session.disconnect()
    assert session.connection_status is ConnectionStatus.DISCONNECTED

    with patch("server.session.time.time", return_value=103.5):
        session.ping()

    assert session.last_activity == 103.5
    assert session.connection_status is ConnectionStatus.CONNECTED


def test_invalid_session_player_type_returns_structured_400() -> None:
    """Invalid session input remains a client error with correction metadata."""
    reset_client_api_state()
    response = ApiClient().post(
        "/session/create",
        json={"player_type": "dragon", "name": "Wrong Door"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert set(detail) == {
        "code",
        "message",
        "session_id",
        "player_type",
        "valid_player_types",
        "known_sessions",
        "active_game_id",
        "active_entity_uuid",
    }
    assert detail["code"] == "invalid_player_type"
    assert detail["player_type"] == "dragon"
    assert detail["session_id"] is None
    assert set(detail["valid_player_types"]) == {
        player_type.value for player_type in PlayerType
    }
    assert detail["known_sessions"] == []
    assert detail["active_game_id"] is None
    assert detail["active_entity_uuid"] is None


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
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
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
    game = sim.game
    assert game is not None
    assert join_payload["game_id"] == str(game.game_id)
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
    assert game.is_player_turn(UUID(session_id))

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
            f"game_matches={'yes' if join_payload['game_id'] == str(game.game_id) else 'no'}, "
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


def test_game_join_accepts_single_entity_uuid_alias() -> None:
    """A one-entity join can use the singular convenience field."""
    reset_client_api_state()
    hero, _monster = create_api_pair()
    start_api_game(hero, _monster)
    client = ApiClient()

    create_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Manual Player"},
    )
    session_id = create_response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid)},
    )
    join_payload = join_response.json()

    assert join_response.status_code == 200
    assert join_payload["success"]
    assert join_payload["controlled_entities"] == [str(hero.uuid)]

    ping_payload = client.post(f"/session/{session_id}/ping").json()

    assert ping_payload["is_my_turn"]
    assert ping_payload["controlled_entities"] == [str(hero.uuid)]


def test_subjective_state_and_available_actions_payloads(capsys) -> None:
    """Subjective bootstrap and command routes describe the joined scene."""
    client, session_id, hero, monster, _encounter = create_joined_client_game()

    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = SubjectiveReplicationBootstrap.model_validate(bootstrap_response.json())
    encounter = bootstrap.world.state.encounter
    assert encounter is not None
    entity_names = {entity.name for entity in bootstrap.world.state.entities}
    actions_payload = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    action_names = {
        action["template_name"]
        for action in actions_payload["entity_actions"]
    }

    assert {"Manual Hero", "Manual Skeleton"} <= entity_names
    assert bootstrap.perspective.controlled_entity_uuids == (str(hero.uuid),)
    assert encounter.current_entity_uuid == str(hero.uuid)
    assert actions_payload["entity_uuid"] == str(hero.uuid)
    assert "Attack_MELEE_MAIN" in action_names
    assert attack_target_index(actions_payload, monster.uuid) == 0
    assert actions_payload["actions_remaining"] == 1
    assert session_id in client.get("/game/status").text

    readout_lines = [
        f"subjective snapshot: entities={sorted(entity_names)}, current=Manual Hero",
        (
            "action menu: "
            "entity=Manual Hero, "
            f"actions={sorted(action_names)}, "
            f"target_index={attack_target_index(actions_payload, monster.uuid)}"
        ),
        (
            "status echo: "
            f"session_seen={'yes' if session_id in client.get('/game/status').text else 'no'}, "
            f"actions_remaining={actions_payload['actions_remaining']}"
        ),
    ]
    expected_lines = [
        "subjective snapshot: entities=['Manual Hero', 'Manual Skeleton'], current=Manual Hero",
        (
            "action menu: entity=Manual Hero, "
            "actions=['Attack_MELEE_MAIN', 'Attack_RANGED_MAIN', 'Shove'], target_index=0"
        ),
        "status echo: session_seen=yes, actions_remaining=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_execute_action_by_index_acknowledges_then_journals_state_and_logs(capsys) -> None:
    """Commands ack once; reducer facts and logs arrive through the player journal."""
    client, session_id, hero, monster, encounter = create_joined_client_game()
    initial_monster_hp = monster.get_hp()
    seed = replication_seed(client, session_id)

    with fixed_dice_faces(12, 4):
        result = execute_manual_attack(client, session_id, hero, monster)
    frames, logs = replication_window(client, session_id, seed)
    presentation = [
        cue
        for frame in frames["frames"]
        for cue in frame["presentation"]
    ]
    damage = next(
        cue
        for cue in presentation
        if cue["kind"] == "damage" and cue["target_uuid"] == str(monster.uuid)
    )

    assert result["success"]
    assert result["event_type"] == "attack_melee_main"
    assert damage["resulting_hp"] == monster.get_hp() < initial_monster_hp
    assert result["turn_continues"]
    assert not result["encounter_ended"]
    assert result["available_actions"]["actions_remaining"] == 0
    assert result["event_cursor_after"] == EventQueue.event_cursor()
    assert result["combat_log_cursor_after"] == len(encounter.combat_log)
    assert frames["through_watermarks"]["source_event_cursor"] == result["event_cursor_after"]
    assert logs["through_cursor"] == result["combat_log_cursor_after"]
    assert any(frame["entry"] is not None for frame in logs["frames"])
    assert {
        "state",
        "event_data",
        "entity_hp",
        "target_hp",
        "combat_log_entries",
    }.isdisjoint(result)

    readout_lines = [
        (
            "execute result: "
            f"success={'yes' if result['success'] else 'no'}, "
            f"event={result['event_type']}, "
            f"turn_continues={'yes' if result['turn_continues'] else 'no'}"
        ),
        f"journal damage: monster={initial_monster_hp}->{damage['resulting_hp']}",
        (
            "command ack: "
            f"actions_remaining={result['available_actions']['actions_remaining']}, "
            f"ended={'yes' if result['encounter_ended'] else 'no'}"
        ),
        (
            "cursors: "
            f"events={result['event_cursor_after']}, "
            f"logs={result['combat_log_cursor_after']}, "
            f"log_frames={len(logs['frames'])}"
        ),
    ]
    expected_lines = [
        "execute result: success=yes, event=attack_melee_main, turn_continues=yes",
        "journal damage: monster=17->11",
        "command ack: actions_remaining=0, ended=no",
        "cursors: events=72, logs=2, log_frames=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_execute_movement_delivers_typed_trajectory_through_replication() -> None:
    """Movement geometry belongs to presentation cues, not command responses."""
    client, session_id, hero, _monster, _encounter = create_joined_client_game()
    seed = replication_seed(client, session_id)
    actions = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    move = next(
        action
        for action in actions["position_actions"]
        if action["template_name"] == "Move"
    )
    target = next(
        row
        for row in move["valid_targets"]
        if row["position"] != list(hero.position)
    )

    response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "template_name": "Move",
            "target_index": target["index"],
            "return_available_actions": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    frames, _logs = replication_window(client, session_id, seed)
    movement = next(
        cue
        for frame in frames["frames"]
        for cue in frame["presentation"]
        if cue["kind"] == "movement"
    )
    assert payload["success"]
    assert "event_data" not in payload
    assert movement["trajectory"][0] == [1, 1]
    assert movement["trajectory"][-1] == target["position"]
    assert all(isinstance(position, list) for position in movement["trajectory"])


def test_replication_bootstrap_is_one_typed_cursor_aligned_base() -> None:
    """The canonical subjective world, logs, and cursors share one identity."""
    client, session_id, hero, _, encounter = create_joined_client_game()

    response = client.get("/replication/bootstrap", params={"session_id": session_id})

    assert response.status_code == 200
    bootstrap = SubjectiveReplicationBootstrap.model_validate(response.json())
    assert bootstrap.protocol.generation_id == str(EventQueue.generation_id())
    assert bootstrap.protocol.source_stream_id == str(encounter.uuid)
    assert bootstrap.watermarks.source_event_cursor == EventQueue.event_cursor()
    assert bootstrap.watermarks.combat_log_cursor == len(encounter.combat_log)
    assert bootstrap.combat_log_frames.total == len(encounter.combat_log)
    assert str(hero.uuid) in bootstrap.perspective.controlled_entity_uuids
    assert any(entity.uuid == str(hero.uuid) for entity in bootstrap.world.state.entities)
    assert str(hero.uuid) in bootstrap.world.visibility.root
    hero_visibility = bootstrap.world.visibility.root[str(hero.uuid)]
    assert hero_visibility.position == hero.position
    assert hero_visibility.effective_light_levels == (
        hero.senses.get_effective_light_levels(hero.uuid)
    )


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
