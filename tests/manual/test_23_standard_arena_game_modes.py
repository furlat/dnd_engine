"""Manual Chapter 23 checks for standard arena game modes."""

from dnd.core.events import WeaponSlot
from dnd.encounter import EncounterState, TurnState
from dnd.entity import Entity
from server.arena_mode import (
    ArenaApiClient,
    action_template_names,
    entity_by_name,
    equipped_item_name,
    floor_object_names,
    inventory_item_names,
    reset_standard_arena_runtime,
    start_joined_human_arena,
)
from server.event_server import setup_arena_combat, sim


def test_arena_mode_exposes_local_client_readers_and_joined_start(capsys) -> None:
    """The arena mode helper exposes the public local tooling surface."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()
    status = client.get("/game/status").json()

    assert status["active"] is False
    assert status["game"] is None
    assert status["sessions"] == []
    assert callable(setup_arena_combat)
    assert callable(entity_by_name)
    assert callable(floor_object_names)
    assert callable(action_template_names)
    assert callable(inventory_item_names)
    assert callable(equipped_item_name)
    assert callable(start_joined_human_arena)

    readout_lines = [
        f"status: active={status['active']}, game={status['game']}, sessions={len(status['sessions'])}",
        (
            "surfaces: "
            f"client={ArenaApiClient.__name__}, reset=yes, "
            f"setup={callable(setup_arena_combat)}, "
            f"joined={callable(start_joined_human_arena)}"
        ),
        (
            "readers: "
            f"entity={callable(entity_by_name)}, "
            f"objects={callable(floor_object_names)}, "
            f"actions={callable(action_template_names)}, "
            f"inventory={callable(inventory_item_names)}, "
            f"equipment={callable(equipped_item_name)}"
        ),
    ]
    expected_lines = [
        "status: active=False, game=None, sessions=0",
        "surfaces: client=ArenaApiClient, reset=yes, setup=True, joined=True",
        "readers: entity=True, objects=True, actions=True, inventory=True, equipment=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_standard_arena_composes_environment_actors_and_ai_controllers(capsys) -> None:
    """The arena fixture builds the product's default tactical scene."""
    reset_standard_arena_runtime()

    encounter = setup_arena_combat(pvp_mode=False, character_class="fighter")
    sim.encounter = encounter
    client = ArenaApiClient()
    hero = entity_by_name("Hero")
    warrior = entity_by_name("Skeleton Warrior")
    archer = entity_by_name("Skeleton Archer")
    warlock = entity_by_name("Skeleton Warlock")
    object_names = floor_object_names(client)

    assert encounter.name == "Arena Combat"
    assert encounter.state == EncounterState.NOT_STARTED
    assert len(encounter.combatants) == 4
    assert hero.faction == "heroes"
    assert {warrior.faction, archer.faction, warlock.faction} == {"monsters"}
    assert hero.position == (2, 7)
    assert warrior.position == (12, 5)
    assert archer.position == (12, 7)
    assert warlock.position == (12, 9)

    assert encounter.get_controller_for(hero.uuid).controller_type == "human"
    assert encounter.get_controller_for(warrior.uuid).controller_type == "external_ai"
    assert encounter.get_controller_for(archer.uuid).controller_type == "external_ai"
    assert encounter.get_controller_for(warlock.uuid).controller_type == "external_ai"

    assert object_names.count("Directional Wall") == 8
    assert object_names.count("Door") == 1
    assert object_names.count("Potion of Healing") == 2
    assert object_names.count("Wall Torch") == 2
    assert object_names.count("Trap Lever") == 1

    readout_lines = [
        (
            "encounter: "
            f"name={encounter.name}, state={encounter.state.value}, "
            f"combatants={len(encounter.combatants)}"
        ),
        (
            "actors: "
            f"hero={hero.name}/{hero.faction}@{hero.position}, "
            f"warrior={warrior.position}, archer={archer.position}, "
            f"warlock={warlock.position}"
        ),
        (
            "controllers: "
            f"hero={encounter.get_controller_for(hero.uuid).controller_type}, "
            f"warrior={encounter.get_controller_for(warrior.uuid).controller_type}, "
            f"archer={encounter.get_controller_for(archer.uuid).controller_type}, "
            f"warlock={encounter.get_controller_for(warlock.uuid).controller_type}"
        ),
        (
            "floor objects: "
            f"walls={object_names.count('Directional Wall')}, "
            f"doors={object_names.count('Door')}, "
            f"potions={object_names.count('Potion of Healing')}, "
            f"torches={object_names.count('Wall Torch')}, "
            f"levers={object_names.count('Trap Lever')}"
        ),
    ]
    expected_lines = [
        "encounter: name=Arena Combat, state=not_started, combatants=4",
        (
            "actors: hero=Hero/heroes@(2, 7), warrior=(12, 5), "
            "archer=(12, 7), warlock=(12, 9)"
        ),
        "controllers: hero=human, warrior=external_ai, archer=external_ai, warlock=external_ai",
        "floor objects: walls=8, doors=1, potions=2, torches=2, levers=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_arena_hero_class_presets_change_actions_equipment_and_inventory(capsys) -> None:
    """Character-class selection changes the hero kit in the same arena."""
    reset_standard_arena_runtime()
    setup_arena_combat(character_class="fighter")
    fighter = entity_by_name("Hero")
    fighter_actions = action_template_names(fighter)
    fighter_inventory = set(inventory_item_names(fighter))

    assert equipped_item_name(fighter, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(fighter, WeaponSlot.MELEE_OFF) == "Dagger"
    assert equipped_item_name(fighter, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert {"Action Surge", "Second Wind"} <= fighter_actions
    assert {"Torch", "Potion of Greater Invisibility"} <= fighter_inventory

    fighter_readout = [
        (
            "fighter kit: "
            f"melee={equipped_item_name(fighter, WeaponSlot.MELEE_MAIN)}+"
            f"{equipped_item_name(fighter, WeaponSlot.MELEE_OFF)}, "
            f"ranged={equipped_item_name(fighter, WeaponSlot.RANGED_MAIN)}, "
            f"features={sorted({'Action Surge', 'Second Wind'} & fighter_actions)}"
        ),
        (
            "fighter inventory: "
            f"torch={'Torch' in fighter_inventory}, "
            f"invis_potion={'Potion of Greater Invisibility' in fighter_inventory}"
        ),
    ]

    reset_standard_arena_runtime()
    setup_arena_combat(character_class="sorcerer")
    sorcerer = entity_by_name("Hero")
    sorcerer_actions = action_template_names(sorcerer)
    sorcerer_inventory = inventory_item_names(sorcerer)

    assert {"Fire Bolt", "Magic Missile", "Fireball"} <= sorcerer_actions
    assert {"Quickened Spell", "Twinned Spell"} <= sorcerer_actions
    assert sorcerer_inventory.count("Scroll of Fireball") == 2
    assert "Scroll of Magic Missile" in sorcerer_inventory

    sorcerer_readout = [
        (
            "sorcerer kit: "
            f"spells={sorted({'Fire Bolt', 'Magic Missile', 'Fireball'} & sorcerer_actions)}, "
            f"metamagic={sorted({'Quickened Spell', 'Twinned Spell'} & sorcerer_actions)}"
        ),
        (
            "sorcerer inventory: "
            f"fireball_scrolls={sorcerer_inventory.count('Scroll of Fireball')}, "
            f"magic_missile_scroll={'Scroll of Magic Missile' in sorcerer_inventory}"
        ),
    ]

    reset_standard_arena_runtime()
    setup_arena_combat(character_class="barbarian")
    barbarian = entity_by_name("Hero")
    barbarian_actions = action_template_names(barbarian)

    assert equipped_item_name(barbarian, WeaponSlot.MELEE_MAIN) == "Greataxe"
    assert {"Rage", "Frenzy"} <= barbarian_actions

    barbarian_readout = [
        (
            "barbarian kit: "
            f"melee={equipped_item_name(barbarian, WeaponSlot.MELEE_MAIN)}, "
            f"actions={sorted({'Rage', 'Frenzy'} & barbarian_actions)}"
        ),
    ]

    readout_lines = [*fighter_readout, *sorcerer_readout, *barbarian_readout]
    expected_lines = [
        "fighter kit: melee=Shortsword+Dagger, ranged=Longbow, features=['Action Surge', 'Second Wind']",
        "fighter inventory: torch=True, invis_potion=True",
        (
            "sorcerer kit: spells=['Fire Bolt', 'Fireball', 'Magic Missile'], "
            "metamagic=['Quickened Spell', 'Twinned Spell']"
        ),
        "sorcerer inventory: fireball_scrolls=2, magic_missile_scroll=True",
        "barbarian kit: melee=Greataxe, actions=['Frenzy', 'Rage']",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_pvp_arena_swaps_monster_side_to_codex_controllers(capsys) -> None:
    """PvP mode keeps the arena scene and changes monster-side ownership."""
    reset_standard_arena_runtime()

    encounter = setup_arena_combat(pvp_mode=True, character_class="fighter")
    hero = entity_by_name("Hero")
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]

    assert encounter.name == "PvP Arena"
    assert encounter.get_controller_for(hero.uuid).controller_type == "human"
    assert len(monsters) == 3
    assert {encounter.get_controller_for(monster.uuid).controller_type for monster in monsters} == {"codex"}

    readout_lines = [
        f"encounter: name={encounter.name}, monsters={len(monsters)}",
        (
            "controllers: "
            f"hero={encounter.get_controller_for(hero.uuid).controller_type}, "
            f"monsters={sorted({encounter.get_controller_for(monster.uuid).controller_type for monster in monsters})}"
        ),
        f"monster names: {sorted(monster.name for monster in monsters)}",
    ]
    expected_lines = [
        "encounter: name=PvP Arena, monsters=3",
        "controllers: hero=human, monsters=['codex']",
        "monster names: ['Skeleton Archer', 'Skeleton Warlock', 'Skeleton Warrior']",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_start_human_mode_creates_ai_session_and_waits_for_player_join(capsys) -> None:
    """The live human arena starts, assigns monsters to AI, and waits for the hero player."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()

    response = client.post("/simulation/start-human", params={"character_class": "fighter"})
    payload = response.json()
    hero_uuid = payload["hero_uuid"]
    game_status = client.get("/game/status").json()

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == hero_uuid
    assert payload["entity_name"] == "Hero"
    assert sim.encounter is not None
    assert sim.encounter.name == "Arena Combat"
    assert sim.encounter.state == EncounterState.ACTIVE
    assert sim.encounter.turn_state == TurnState.IN_PROGRESS

    assert game_status["active"] is True
    assert game_status["encounter_active"] is True
    assert game_status["active_entity_uuid"] == hero_uuid
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert len(ai_sessions[0]["controlled_entities"]) == 3

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Arena Player"},
    )
    session_id = session_response.json()["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    ping_response = client.post(f"/session/{session_id}/ping")

    assert session_response.status_code == 200
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [hero_uuid]
    assert ping_response.status_code == 200
    assert ping_response.json()["is_my_turn"] is True
    assert ping_response.json()["active_entity_name"] == "Hero"

    readout_lines = [
        (
            "start: "
            f"status_code={response.status_code}, status={payload['status']}, "
            f"entity={payload['entity_name']}, "
            f"encounter={sim.encounter.name if sim.encounter else None}/"
            f"{sim.encounter.state.value if sim.encounter else None}"
        ),
        (
            "game status: "
            f"active={game_status['active']}, "
            f"encounter_active={game_status['encounter_active']}, "
            f"active_matches={game_status['active_entity_uuid'] == hero_uuid}, "
            f"ai_sessions={len(ai_sessions)}, "
            f"ai_controls={len(ai_sessions[0]['controlled_entities']) if ai_sessions else 0}"
        ),
        (
            "join: "
            f"session_status={session_response.status_code}, "
            f"join_status={join_response.status_code}, "
            f"controls_hero={join_response.json()['controlled_entities'] == [hero_uuid]}"
        ),
        (
            "ping: "
            f"status={ping_response.status_code}, "
            f"is_my_turn={ping_response.json()['is_my_turn']}, "
            f"active_entity={ping_response.json()['active_entity_name']}"
        ),
    ]
    expected_lines = [
        "start: status_code=200, status=waiting_for_human, entity=Hero, encounter=Arena Combat/active",
        "game status: active=True, encounter_active=True, active_matches=True, ai_sessions=1, ai_controls=3",
        "join: session_status=200, join_status=200, controls_hero=True",
        "ping: status=200, is_my_turn=True, active_entity=Hero",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_live_arena_payloads_describe_grid_entities_visibility_and_hero_detail(capsys) -> None:
    """Client-facing payloads describe the running standard arena."""
    arena = start_joined_human_arena()
    client = arena.client
    session_id = arena.session_id
    hero_uuid = arena.hero_uuid

    state = client.get("/state").json()
    visibility = client.get("/visibility").json()
    controlled = client.get(f"/session/{session_id}/entities").json()
    hero_detail = client.get(f"/entity/{hero_uuid}").json()

    assert state["grid"]["min_x"] == 0
    assert state["grid"]["min_y"] == 0
    assert state["grid"]["max_x"] == 14
    assert state["grid"]["max_y"] == 14
    assert len(state["grid"]["tiles"]) == 225
    assert {entity["name"] for entity in state["entities"]} == {
        "Hero",
        "Skeleton Warrior",
        "Skeleton Archer",
        "Skeleton Warlock",
    }
    assert state["encounter"]["name"] == "Arena Combat"
    assert state["encounter"]["state"] == "active"
    assert {obj["name"] for obj in state["floor_objects"]} >= {"Door", "Trap Lever", "Potion of Healing"}

    assert hero_uuid in visibility
    assert visibility[hero_uuid]["name"] == "Hero"
    assert visibility[hero_uuid]["position"] == [2, 7]
    assert visibility[hero_uuid]["visible_cells"]
    assert isinstance(visibility[hero_uuid]["sense_modes"], list)

    assert controlled["controlled_entities"][0]["uuid"] == hero_uuid
    assert controlled["controlled_entities"][0]["name"] == "Hero"
    assert hero_detail["name"] == "Hero"
    assert hero_detail["equipment"]["ac"] == hero_detail["ac"]

    floor_names = {obj["name"] for obj in state["floor_objects"]}
    readout_lines = [
        (
            "grid: "
            f"bounds=({state['grid']['min_x']},{state['grid']['min_y']})-"
            f"({state['grid']['max_x']},{state['grid']['max_y']}), "
            f"tiles={len(state['grid']['tiles'])}"
        ),
        (
            "state: "
            f"encounter={state['encounter']['name']}/{state['encounter']['state']}, "
            f"entities={sorted(entity['name'] for entity in state['entities'])}"
        ),
        (
            "floor objects: "
            f"has_door={'Door' in floor_names}, "
            f"has_trap={'Trap Lever' in floor_names}, "
            f"has_potion={'Potion of Healing' in floor_names}"
        ),
        (
            "visibility: "
            f"hero_known={hero_uuid in visibility}, "
            f"position={visibility[hero_uuid]['position']}, "
            f"visible_cells={len(visibility[hero_uuid]['visible_cells'])}, "
            f"sense_modes={visibility[hero_uuid]['sense_modes']}"
        ),
        (
            "hero detail: "
            f"controlled={controlled['controlled_entities'][0]['name']}, "
            f"name={hero_detail['name']}, "
            f"ac_matches={hero_detail['equipment']['ac'] == hero_detail['ac']}"
        ),
    ]
    expected_lines = [
        "grid: bounds=(0,0)-(14,14), tiles=225",
        (
            "state: encounter=Arena Combat/active, entities=['Hero', "
            "'Skeleton Archer', 'Skeleton Warlock', 'Skeleton Warrior']"
        ),
        "floor objects: has_door=True, has_trap=True, has_potion=True",
        "visibility: hero_known=True, position=[2, 7], visible_cells=107, sense_modes=[]",
        "hero detail: controlled=Hero, name=Hero, ac_matches=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
