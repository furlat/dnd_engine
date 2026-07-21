"""Manual checks for server-side AI validation arena starts."""

from dnd.entity import Entity
from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime


def test_ai_validation_arena_list_endpoint_exposes_catalog_metadata() -> None:
    """The server exposes validation arena ids and pressure tags."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()

    response = client.get("/simulation/ai-validation-arenas")
    payload = response.json()
    arena_ids = [arena["arena_id"] for arena in payload["arenas"]]
    all_tags = {tag for arena in payload["arenas"] for tag in arena["tags"]}

    assert response.status_code == 200
    assert arena_ids == [
        "standard_skeleton_doors",
        "goblin_water_skirmish",
        "skeleton_anti_aoe_split",
        "caster_crossfire",
        "item_resource_gauntlet",
        "double_door_dark_hunt",
        "arcane_device_control",
        "skeleton_mark_focus_fire",
        "buff_consumable_ambush",
        "forced_movement_hazard_bridge",
        "line_aoe_corridor",
        "zone_control_web_gauntlet",
        "support_attrition_cache",
        "high_level_spell_resource_duel",
        "sorcerer_barbarian_duel",
        "class_party_mirror_scramble",
        "ranged_loadout_kiting_ring",
        "concentration_control_crossroads",
        "teleport_escape_skirmish",
        "darkness_reveal_labyrinth",
        "guardian_zone_shrine",
        "trap_lever_killzone",
        "condition_lock_sanctum",
        "necrotic_anti_healing_duel",
        "damage_affinity_weapon_lab",
        "resistance_weapon_counterplay",
        "field_cache_loot_race",
        "cleanse_support_triage",
        "multi_target_missile_allocation",
        "multi_projectile_no_aoe_lab",
        "reaction_counterspell_lab",
        "guardian_choke_body_block",
        "multi_object_control_room",
    ]
    assert {
        "door",
        "water",
        "anti-aoe",
        "caster",
        "items",
        "environment-object",
        "support",
        "buffs",
        "forced-movement",
        "line-aoe",
        "zone-control",
        "healing",
        "high-level-spells",
        "class-party",
        "gear-loadout",
        "concentration",
        "teleport",
        "vision",
        "guardian-of-faith",
        "summon-object",
        "trap-lever",
        "object-interaction",
        "conditions",
        "anti-healing",
        "necromancy",
        "damage-affinity",
        "resistance",
        "vulnerability",
        "weapon-choice",
        "chest",
        "loot",
        "restoration",
        "poisoned",
        "blinded",
        "multi-target",
        "magic-missile",
        "target-allocation",
        "no-aoe",
        "wounded-targets",
        "reaction",
        "counterspell",
        "spell-interrupt",
        "body-block",
        "multi-object",
        "torch",
        "fireball-cannon",
    } <= all_tags


def test_start_ai_validation_human_hero_mode_spawns_external_monsters(monkeypatch) -> None:
    """Human-hero validation mode mirrors the player-vs-external-AI flow."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        fake_start_external_agent,
    )

    client = ArenaApiClient()
    response = client.post(
        "/simulation/start-ai-validation",
        params={"arena_id": "goblin_water_skirmish", "mode": "human_hero"},
    )
    payload = response.json()
    game_status = client.get("/game/status").json()
    encounter = event_server.sim.encounter
    assert encounter is not None

    heroes = [entity for entity in Entity.get_all_entities() if entity.faction == "heroes"]
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    hero_controller = encounter.get_controller_for(heroes[0].uuid)
    monster_controller_types: set[str] = set()
    for monster in monsters:
        controller = encounter.get_controller_for(monster.uuid)
        assert controller is not None
        monster_controller_types.add(controller.controller_type)
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["arena_id"] == "goblin_water_skirmish"
    assert payload["mode"] == "human_hero"
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == payload["hero_uuid"]
    assert payload["ai_session_id"] == starts[0][0]
    assert starts == [(payload["ai_session_id"], "http://testserver")]
    assert hero_controller is not None
    assert hero_controller.controller_type == "human"
    assert monster_controller_types == {"external_ai"}
    assert len(payload["monsters"]) == 3
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert set(ai_sessions[0]["controlled_entities"]) == {str(monster.uuid) for monster in monsters}


def test_start_ai_validation_codex_monsters_mode_spawns_external_hero(monkeypatch) -> None:
    """Codex-monsters validation mode gives the hero to the external AI."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        fake_start_external_agent,
    )

    client = ArenaApiClient()
    response = client.post(
        "/simulation/start-ai-validation",
        params={"arena_id": "caster_crossfire", "mode": "codex_monsters"},
    )
    payload = response.json()
    game_status = client.get("/game/status").json()
    encounter = event_server.sim.encounter
    assert encounter is not None

    hero = next(entity for entity in Entity.get_all_entities() if entity.faction == "heroes")
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    hero_controller = encounter.get_controller_for(hero.uuid)
    monster_controller_types: set[str] = set()
    for monster in monsters:
        controller = encounter.get_controller_for(monster.uuid)
        assert controller is not None
        monster_controller_types.add(controller.controller_type)
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]
    codex_sessions = [session for session in game_status["sessions"] if session["player_type"] == "codex"]

    assert response.status_code == 200
    assert payload["arena_id"] == "caster_crossfire"
    assert payload["mode"] == "codex_monsters"
    assert payload["status"] == "waiting_for_ai"
    assert payload["entity_uuid"] == str(hero.uuid)
    assert payload["ai_session_id"] == starts[0][0]
    assert payload["codex_session_id"] == codex_sessions[0]["session_id"]
    assert payload["takeover_claim_id"]
    assert starts == [(payload["ai_session_id"], "http://testserver")]
    assert hero_controller is not None
    assert hero_controller.controller_type == "external_ai"
    assert monster_controller_types == {"codex"}
    assert len(payload["monsters"]) == 3
    assert len(ai_sessions) == 1
    assert len(codex_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Hero"
    assert ai_sessions[0]["controlled_entities"] == [str(hero.uuid)]
    assert codex_sessions[0]["name"] == "Codex Validation Monsters"
    assert set(codex_sessions[0]["controlled_entities"]) == {str(monster.uuid) for monster in monsters}

    snapshot = client.get(f"/ai/sessions/{payload['codex_session_id']}/observation/snapshot").json()
    assert set(snapshot["session"]["controlled_entity_uuids"]) == {str(monster.uuid) for monster in monsters}
    assert snapshot["session"]["is_my_turn"] is False

    claim_id = payload["takeover_claim_id"]
    heartbeat = client.post(f"/ai/takeover/{claim_id}/heartbeat")
    claims = client.get("/ai/takeover").json()["claims"]

    assert heartbeat.status_code == 200
    assert heartbeat.json()["claim"]["claim_id"] == claim_id
    assert heartbeat.json()["claim"]["session_id"] == payload["codex_session_id"]
    assert [claim["claim_id"] for claim in claims] == [claim_id]
    assert set(heartbeat.json()["claim"]["claimed_entities"][index]["entity_uuid"] for index in range(3)) == {
        str(monster.uuid) for monster in monsters
    }


def test_start_ai_validation_rejects_invalid_mode_and_arena() -> None:
    """Validation startup returns structured errors for bad selectors."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()

    invalid_mode = client.post(
        "/simulation/start-ai-validation",
        params={"arena_id": "standard_skeleton_doors", "mode": "legacy"},
    )
    invalid_arena = client.post(
        "/simulation/start-ai-validation",
        params={"arena_id": "missing", "mode": "human_hero"},
    )

    assert invalid_mode.status_code == 400
    assert invalid_mode.json()["detail"]["code"] == "invalid_validation_mode"
    assert invalid_mode.json()["detail"]["valid_modes"] == ["human_hero", "codex_monsters"]
    assert invalid_arena.status_code == 400
    assert invalid_arena.json()["detail"]["code"] == "invalid_validation_arena"
    assert "standard_skeleton_doors" in invalid_arena.json()["detail"]["valid_arena_ids"]
