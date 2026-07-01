"""Engine book parity tests for encounters, controllers, and API surfaces."""

import asyncio
import json
import os
import tempfile
import warnings
from typing import Optional
from uuid import UUID, uuid4

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient
from pydantic import Field

from dnd.actions import Attack, Move
from dnd.controller import (
    CodexController,
    Controller,
    ExternalAIController,
    HumanController,
    PassController,
    TurnContext,
)
from dnd.core.base_actions import BaseAction
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue, EventType, SpatialChangeEvent, WeaponSlot
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.items import create_dagger
from dnd.items.test_items import create_healing_potion
from dnd.monsters.bestiary import create_caster, create_goblin, create_skeleton
from dnd.reactions import add_opportunity_attack_handler
from dnd.utils import (
    force_attack_hit,
    get_hp,
    remove_attack_modifier,
    reset_combat_state,
    set_hp,
)
from server.event_server import app, event_monitor, sim, _available_actions_cache
from server.event_stream import event_stream, format_sse, make_stream_id
from server.spell_catalog import build_spell_catalog


class RecordingController(Controller):
    """Controller that records lifecycle callbacks for parity examples."""

    name: str = Field(default="Recording Controller")
    controller_type: str = Field(default="recording")
    encounter_start_names: list[str] = Field(default_factory=list)
    encounter_end_names: list[str] = Field(default_factory=list)
    turn_start_contexts: list[TurnContext] = Field(default_factory=list)
    turn_end_contexts: list[TurnContext] = Field(default_factory=list)

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Record encounter-start notification entities."""
        self.encounter_start_names.extend(entity.name for entity in entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Record encounter-end notification entities."""
        self.encounter_end_names.extend(entity.name for entity in entities)

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record turn-start context."""
        self.turn_start_contexts.append(context)

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Record turn-end context."""
        self.turn_end_contexts.append(context)


class OneAttackController(Controller):
    """Controller that returns one melee attack, then stops."""

    name: str = Field(default="One Attack Controller")
    controller_type: str = Field(default="one_attack")
    target_uuid: UUID = Field(description="Target UUID for the one scripted attack")
    used: bool = Field(default=False)

    def get_next_action(self, entity: Entity, context: TurnContext) -> Optional[BaseAction]:
        """Return one attack action, then end the turn."""
        if self.used:
            return None
        self.used = True
        return Attack(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=self.target_uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        )

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Continue only until the scripted attack is used."""
        return not self.used


def reset_chapter_18_state(width: int = 16, height: int = 10) -> None:
    """Clear global state and create a rectangular encounter/API test grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    _available_actions_cache.clear()
    session_manager = sim.get_session_manager()
    session_manager.sessions.clear()
    session_manager.games.clear()
    session_manager.active_game = None
    sim.encounter = None
    sim._game_session = None
    sim.combat_task = None
    sim.paused = True
    get_map().create_rectangle(0, 0, width, height)


def create_book_pair() -> tuple[Entity, Entity]:
    """Create two opposing combatants for Chapter 18 examples."""
    hero = create_goblin(name="Book Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Book Skeleton", position=(2, 1), faction="monsters")
    Entity.update_all_entities_senses()
    return hero, monster


def create_melee_only_skeleton(
    name: str,
    position: tuple[int, int],
    faction: Optional[str],
) -> Entity:
    """Create a skeleton fixture whose controller choices are melee-only.

    Args:
        name: Entity name.
        position: Starting grid position.
        faction: Optional faction identifier.

    Returns:
        Skeleton with its ranged-main weapon removed.
    """
    skeleton = create_skeleton(name=name, position=position, faction=faction)
    removed = skeleton.equipment.unequip(WeaponSlot.RANGED_MAIN)

    assert removed is not None
    assert skeleton.get_action_template("Attack_RANGED_MAIN") is None
    return skeleton


def create_action_api_session() -> tuple[TestClient, str, Entity, Entity]:
    """Create a real API client session controlling the active Chapter 18 hero."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )
    encounter.start_turn()
    sim.encounter = encounter
    sim.create_game_session(encounter)
    client = TestClient(app)

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Book Player"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
    )
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [str(hero.uuid)]

    return client, session_id, hero, monster


async def drain_stream_subscription(subscription, limit: int = 32, timeout: float = 0.05) -> list[dict]:
    """Collect currently queued SSE envelopes from a stream subscription."""
    envelopes = []
    for _ in range(limit):
        try:
            envelopes.append(await asyncio.wait_for(subscription.get(), timeout=timeout))
        except asyncio.TimeoutError:
            break
    return envelopes


def start_ordered_encounter(
    hero: Entity,
    monster: Entity,
    hero_controller: Controller,
    monster_controller: Controller,
    first: Entity,
) -> Encounter:
    """Create an active encounter with deterministic initiative order."""
    encounter = Encounter(name="Book Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()
    second = monster if first.uuid == hero.uuid else hero
    encounter.initiative_order = [first.uuid, second.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter


def test_eb_18_001_encounter_start_sets_active_state_callbacks_and_round() -> None:
    """EB-18-001: encounter start wires active state, initiative, and callbacks."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)

    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

    assert encounter.state == EncounterState.ACTIVE
    assert Encounter.get_active() is encounter
    assert encounter.round_number == 1
    assert encounter.turn_state == TurnState.NOT_STARTED
    assert encounter.initiative_order == [hero.uuid, monster.uuid]
    assert hero_controller.encounter_start_names == ["Book Hero"]
    assert monster_controller.encounter_start_names == ["Book Skeleton"]
    assert EventQueue._combat_log_callback == encounter._on_event_combat_log
    assert EventQueue._perceiver_computer is not None
    assert EventQueue._revealed_computer is not None

    end_event = encounter.end_encounter("chapter test complete")

    assert end_event.reason == "chapter test complete"
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert hero_controller.encounter_end_names == ["Book Hero"]
    assert monster_controller.encounter_end_names == ["Book Skeleton"]
    assert EventQueue._combat_log_callback is None
    assert EventQueue._perceiver_computer is None
    assert EventQueue._revealed_computer is None


def test_eb_18_002_turn_lifecycle_builds_context_and_advances_rounds() -> None:
    """EB-18-002: start/end/next turn updates context, counters, and rounds."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

    start_event = encounter.start_turn()

    assert start_event is not None
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.get_current_entity() is hero
    assert hero_controller.turn_start_contexts
    start_context = hero_controller.turn_start_contexts[-1]
    assert start_context.entity_uuid == hero.uuid
    assert start_context.round_number == 1
    assert start_context.actions_remaining == 1
    assert monster.uuid in start_context.visible_enemies

    end_event = encounter.end_turn()

    assert end_event is not None
    assert encounter.turn_state == TurnState.ENDED
    assert encounter.combatants[hero.uuid].has_acted_this_round
    assert encounter.combatants[hero.uuid].turn_count == 1
    assert hero_controller.turn_end_contexts[-1].entity_uuid == hero.uuid

    next_event = encounter.next_turn()

    assert next_event is not None
    assert encounter.get_current_entity() is monster
    assert encounter.current_turn_index == 1
    assert encounter.round_number == 1

    encounter.end_turn()
    encounter.next_turn()

    assert encounter.get_current_entity() is hero
    assert encounter.current_turn_index == 0
    assert encounter.round_number == 2
    assert not encounter.combatants[hero.uuid].has_acted_this_round
    assert not encounter.combatants[monster.uuid].has_acted_this_round


def test_eb_18_003_run_turn_and_advance_until_player_respect_controller_types() -> None:
    """EB-18-003: controller types drive autonomous turns and player stops."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    human_controller = HumanController(source_entity_uuid=hero.uuid)
    pass_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, human_controller, pass_controller, monster)

    result = encounter.advance_until_player()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Book Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1


def test_eb_18_019_surprise_blocks_reactions_until_skipped_turn_ends() -> None:
    """EB-18-019: surprise prevents reactions until the skipped first turn ends."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    add_opportunity_attack_handler(monster)
    encounter = Encounter(name="Book Surprise Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid), surprised=True)
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()

    assert monster.action_economy.reactions.normalized_score == 0

    encounter.start_turn()
    initial_hero_hp = get_hp(hero)
    move_event = Move(source_entity_uuid=hero.uuid, end_position=(1, 3)).apply()

    assert move_event is not None
    assert not move_event.canceled
    assert get_hp(hero) == initial_hero_hp
    assert monster.action_economy.reactions.normalized_score == 0

    encounter.end_turn()
    encounter.next_turn()

    assert encounter.round_number == 2
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert monster.action_economy.reactions.normalized_score == 1


def test_eb_18_020_codex_controller_stops_as_external_input_turn() -> None:
    """EB-18-020: Codex-controlled turns stop for external input."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    codex_controller = CodexController(source_entity_uuid=hero.uuid)
    pass_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, codex_controller, pass_controller, monster)

    result = encounter.advance_until_player()
    context = encounter._build_turn_context(hero)

    assert result.status == "waiting_for_codex"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Book Hero"
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert not codex_controller.can_continue_turn(hero, context)
    assert codex_controller.get_next_action(hero, context) is None


def test_eb_18_021_external_ai_controller_waits_for_session_commands() -> None:
    """EB-18-021: ExternalAI waits while legal actions stay engine-derived."""
    reset_chapter_18_state()
    actor = create_melee_only_skeleton(name="Book External Skeleton", position=(1, 1), faction="monsters")
    target = create_goblin(name="Book Hero", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses()
    controller = ExternalAIController(source_entity_uuid=actor.uuid)
    encounter = start_ordered_encounter(
        target,
        actor,
        PassController(source_entity_uuid=target.uuid),
        controller,
        actor,
    )
    result = encounter.advance_until_player()
    context = TurnContext(
        source_entity_uuid=actor.uuid,
        entity_uuid=actor.uuid,
        visible_enemies=actor.get_visible_enemies(),
    )

    available = actor.get_available_actions()
    attack_info = next(action for action in available.entity_actions if action.template_name == "Attack_MELEE_MAIN")

    assert result.status == "waiting_for_ai"
    assert result.entity_uuid == actor.uuid
    assert encounter.get_current_entity() is actor
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert controller.controller_type == "external_ai"
    assert not controller.can_continue_turn(actor, context)
    assert controller.get_next_action(actor, context) is None
    assert target.uuid in context.visible_enemies
    assert attack_info.valid_targets[0].target_uuid == target.uuid
    assert attack_info.valid_targets[0].index == 0


def test_eb_18_034_available_move_paths_preserve_directional_blockers() -> None:
    """EB-18-034: Available Move rows carry legal paths around directional blockers."""
    reset_chapter_18_state(width=8, height=5)
    grid = get_map()
    melee_actor = create_melee_only_skeleton(name="Book AI Skeleton", position=(1, 1), faction="monsters")
    distant_target = create_goblin(name="Distant Hero", position=(5, 1), faction="heroes")

    changed = grid.set_tile_directional_border((1, 1), "movement", "east", False)
    Entity.update_all_entities_senses()

    assert changed
    assert not grid.can_transition((1, 1), (2, 1))

    assert distant_target.uuid in melee_actor.get_visible_enemies()

    move_info = next(
        action_info
        for action_info in melee_actor.get_available_actions().position_actions
        if action_info.template_name == "Move"
    )
    legal_move_targets = {
        target.position: target
        for target in move_info.valid_targets
        if target.position is not None
    }

    improving_targets = [
        target
        for target in legal_move_targets.values()
        if target.position is not None
        and abs(target.position[0] - distant_target.position[0])
        + abs(target.position[1] - distant_target.position[1])
        < abs(melee_actor.position[0] - distant_target.position[0])
        + abs(melee_actor.position[1] - distant_target.position[1])
    ]
    chosen_target = min(
        improving_targets,
        key=lambda target: len(target.path or []),
    )

    assert chosen_target.position is not None
    assert chosen_target.path is not None
    assert chosen_target.path[0] == melee_actor.position
    assert chosen_target.path[-1] == chosen_target.position
    assert ((1, 1), (2, 1)) not in zip(chosen_target.path, chosen_target.path[1:])

    for start, end in zip(chosen_target.path, chosen_target.path[1:]):
        assert grid.can_transition(start, end)

    current_distance = abs(melee_actor.position[0] - distant_target.position[0]) + abs(
        melee_actor.position[1] - distant_target.position[1]
    )
    moved_distance = abs(chosen_target.position[0] - distant_target.position[0]) + abs(
        chosen_target.position[1] - distant_target.position[1]
    )
    assert moved_distance < current_distance


def test_eb_18_004_execute_action_captures_combat_log_and_listener_payload() -> None:
    """EB-18-004: API-style action execution appends combat log entries."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    hero_controller = HumanController(source_entity_uuid=hero.uuid)
    monster_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)
    encounter.start_turn()

    listener_calls: list[tuple[int, str]] = []

    def listener(active: Encounter, index: int, entry, event) -> None:
        listener_calls.append((index, entry.entry_type.value))

    Encounter.add_combat_log_listener(listener)
    force_uuid = force_attack_hit(hero)
    initial_hp = get_hp(monster)
    try:
        event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
    finally:
        remove_attack_modifier(hero, force_uuid)
        Encounter.remove_combat_log_listener(listener)

    assert event is not None
    assert not event.canceled
    assert get_hp(monster) < initial_hp
    assert encounter.combat_log
    assert listener_calls
    assert listener_calls[-1][0] == len(encounter.combat_log) - 1
    assert encounter.get_combat_log(since=listener_calls[-1][0])[0] is encounter.combat_log[-1]


def test_eb_18_005_check_deaths_marks_dead_and_ends_single_faction_encounter() -> None:
    """EB-18-005: encounter death checks mark dead combatants and end combat."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )

    set_hp(monster, 0)
    death_events = encounter.check_deaths()

    assert death_events
    assert encounter.combatants[monster.uuid].is_dead
    assert "Dead" in monster.active_conditions
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert len(encounter.get_alive_combatants()) == 1
    assert encounter.get_dead_combatants()[0].entity_uuid == monster.uuid


def test_eb_18_006_serialization_and_spell_catalog_api_do_not_mutate_registry() -> None:
    """EB-18-006: serialization and catalog APIs produce JSON-safe payloads."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )

    entity_dump = hero.model_dump(mode="json")
    encounter_dump = encounter.model_dump(mode="json")
    json.dumps(entity_dump)
    json.dumps(encounter_dump)

    assert "registered_actions" in entity_dump
    assert "combatants" in encounter_dump
    assert "initiative_order" in encounter_dump

    before_registry_count = len(BaseObject._registry)
    catalog = build_spell_catalog()
    after_registry_count = len(BaseObject._registry)

    assert after_registry_count == before_registry_count
    assert catalog.version
    assert any(spell.id == "fire_bolt" and spell.attack_roll for spell in catalog.spells)

    response = TestClient(app).get("/catalog/spells")

    assert response.status_code == 200
    spell_ids = {spell["id"] for spell in response.json()["spells"]}
    assert {"fire_bolt", "magic_missile", "fireball"} <= spell_ids


def test_eb_18_030_health_endpoint_reports_scalar_listener_count() -> None:
    """EB-18-030: root health reports listener count as a scalar."""
    reset_chapter_18_state(width=2, height=2)

    response = TestClient(app).get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["listeners"] == event_monitor.listener_count
    assert isinstance(payload["listeners"], int)
    assert isinstance(payload["event_count"], int)
    assert payload["has_encounter"] is False
    assert payload["paused"] is True


def test_eb_18_031_simulation_reset_status_delay_and_step_are_stateful() -> None:
    """EB-18-031: simulation control endpoints expose stateful transitions."""
    reset_chapter_18_state(width=2, height=2)
    client = TestClient(app)

    empty_encounter = client.get("/encounter")
    assert empty_encounter.status_code == 200
    assert empty_encounter.json() == {"active": False, "encounter": None}

    empty_log = client.get("/combat-log")
    assert empty_log.status_code == 200
    assert empty_log.json() == {"entries": [], "count": 0, "total": 0}

    reset_response = client.post("/simulation/reset")
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["status"] == "reset"

    status_response = client.get("/simulation/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["has_encounter"] is True
    assert status_payload["paused"] is True
    assert status_payload["encounter_state"] == EncounterState.NOT_STARTED.value

    encounter_response = client.get("/encounter")
    assert encounter_response.status_code == 200
    encounter_payload = encounter_response.json()
    assert encounter_payload["active"] is True
    assert encounter_payload["encounter"]["uuid"] == reset_payload["encounter_uuid"]
    assert encounter_payload["encounter"]["state"] == EncounterState.NOT_STARTED.value

    delay_response = client.post("/simulation/set-delay", params={"delay": 0.25})
    assert delay_response.status_code == 200
    assert delay_response.json() == {"status": "delay_set", "turn_delay": 0.25}

    pause_response = client.post("/simulation/pause")
    assert pause_response.status_code == 200
    assert pause_response.json() == {"status": "paused"}

    step_response = client.post("/simulation/step")
    assert step_response.status_code == 200
    step_payload = step_response.json()
    assert step_payload["status"] == "stepped"
    assert isinstance(step_payload["round"], int)
    assert isinstance(step_payload["turn_index"], int)
    assert sim.encounter is not None
    assert sim.encounter.state != EncounterState.NOT_STARTED


def test_eb_18_007_event_history_and_sse_payloads_preserve_directional_spatial_fields() -> None:
    """EB-18-007: event API and SSE payloads serialize directional spatial metadata."""
    reset_chapter_18_state(width=4, height=4)
    cursor = EventQueue.event_cursor()
    changed = get_map().set_tile_directional_border((1, 1), "vision", "east", False)

    assert changed

    response = TestClient(app).get(f"/events?since={cursor}&limit=0")

    assert response.status_code == 200
    events = [
        event for event in response.json()["events"]
        if event["event_type"] == "spatial_tile_changed"
    ]
    assert events
    event_payload = events[-1]
    assert event_payload["directional_position"] == [1, 1]
    assert event_payload["directional_directions"] == ["east"]
    assert event_payload["directional_channels"] == ["vision"]
    assert event_payload["directional_blocks_vision"]["east"] is True

    event_stream.ensure_attached()
    payloads = [
        payload for payload in event_stream.iter_game_events_since(cursor, None)
        if isinstance(payload.event, SpatialChangeEvent)
        and payload.event.event_type == EventType.SPATIAL_TILE_CHANGED
    ]
    assert payloads

    frame = format_sse(
        "game_event",
        payloads[-1],
        make_stream_id(payloads[-1].event_cursor, payloads[-1].combat_log_cursor),
    )
    data_lines = [
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    ]
    sse_data = json.loads("\n".join(data_lines))

    assert "event: game_event" in frame
    assert sse_data["event"]["directional_position"] == [1, 1]
    assert sse_data["event"]["directional_directions"] == ["east"]
    assert sse_data["event"]["directional_channels"] == ["vision"]
    assert sse_data["event"]["directional_blocks_vision"]["east"] is True


def test_eb_18_008_mapeditor_api_saves_map_state_without_entities_or_encounter() -> None:
    """EB-18-008: mapeditor API saves only map/editor state."""
    reset_chapter_18_state(width=3, height=2)
    client = TestClient(app)

    response = client.post(
        "/mapeditor/maps",
        json={"source": "scratch", "width": 3, "height": 2, "origin": [0, 0], "default_light": 1},
    )
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1}
    assert len(snapshot["tiles"]) == 6

    response = client.post(
        "/mapeditor/map/tiles",
        json={"tiles": [{"x": 1, "y": 0, "type": "Wall", "light_level": 4}]},
    )
    assert response.status_code == 200
    wall = next(tile for tile in response.json()["tiles"] if tile["x"] == 1 and tile["y"] == 0)
    assert wall["name"] == "Wall"
    assert not wall["walkable"]
    assert wall["light_level"] == 4

    response = client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [2, 1]})
    assert response.status_code == 200
    assert response.json()["name"] == "Door"

    entities = client.get("/entities").json()["entities"]
    assert entities == []


def test_eb_18_022_mapeditor_save_load_roundtrip_restores_entity_free_state() -> None:
    """EB-18-022: mapeditor saves and loads map state without entities."""
    reset_chapter_18_state(width=3, height=2)
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as save_dir:
        old_save_dir = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
        os.environ["DND_MAPEDITOR_SAVE_DIR"] = save_dir
        try:
            create_response = client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 3, "height": 2, "origin": [0, 0], "default_light": 1},
            )
            assert create_response.status_code == 200

            tile_response = client.post(
                "/mapeditor/map/tiles",
                json={
                    "tiles": [
                        {"x": 1, "y": 0, "type": "Wall", "light_level": 4},
                        {
                            "x": 0,
                            "y": 0,
                            "directional_channel": "movement",
                            "direction": "east",
                            "passable": False,
                        },
                    ]
                },
            )
            assert tile_response.status_code == 200

            object_response = client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [2, 1]})
            assert object_response.status_code == 200
            placed_door_uuid = object_response.json()["uuid"]

            save_response = client.post("/mapeditor/saves", json={"id": "book_roundtrip", "name": "Book Roundtrip"})
            assert save_response.status_code == 200
            metadata = save_response.json()
            assert metadata["id"] == "book_roundtrip"
            assert metadata["revision"] == 1
            assert metadata["tile_count"] == 6
            assert metadata["floor_object_count"] == 1

            document_response = client.get("/mapeditor/saves/book_roundtrip")
            assert document_response.status_code == 200
            document = document_response.json()
            assert set(document["snapshot"]) == {"grid_bounds", "tiles", "floor_objects"}
            assert document["object_placements"][0]["catalog_id"] == "door"
            assert document["object_placements"][0]["position"] == [2, 1]
            assert all("entities" not in section for section in document)
            assert all("encounter" not in section for section in document)

            changed_response = client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 1, "height": 1, "origin": [9, 9], "default_light": 1},
            )
            assert changed_response.status_code == 200
            assert changed_response.json()["grid_bounds"] == {"min_x": 9, "min_y": 9, "max_x": 9, "max_y": 9}

            load_response = client.post("/mapeditor/saves/book_roundtrip/load")
            assert load_response.status_code == 200
            loaded = load_response.json()
            assert loaded["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1}
            loaded_tiles = {(tile["x"], tile["y"]): tile for tile in loaded["tiles"]}
            assert loaded_tiles[(1, 0)]["name"] == "Wall"
            assert loaded_tiles[(1, 0)]["light_level"] == 4
            assert loaded_tiles[(0, 0)]["directional_blocks_movement"]["east"] is True
            assert loaded["floor_objects"][0]["name"] == "Door"
            assert loaded["floor_objects"][0]["position"] == [2, 1]
            assert loaded["floor_objects"][0]["uuid"] != placed_door_uuid

            state_response = client.get("/state")
            assert state_response.status_code == 200
            state = state_response.json()
            assert state["entities"] == []
            assert state["encounter"] is None
            assert state["floor_objects"][0]["name"] == "Door"
        finally:
            if old_save_dir is None:
                os.environ.pop("DND_MAPEDITOR_SAVE_DIR", None)
            else:
                os.environ["DND_MAPEDITOR_SAVE_DIR"] = old_save_dir


def test_eb_18_024_tile_lookup_error_reports_grid_context() -> None:
    """EB-18-024: /tile missing-tile errors include grid correction context."""
    reset_chapter_18_state(width=2, height=2)
    client = TestClient(app)

    existing_response = client.get("/tile/1/1")
    assert existing_response.status_code == 200
    existing_tile = existing_response.json()
    assert existing_tile["position"] == [1, 1]
    assert existing_tile["name"] == "Floor"

    missing_response = client.get("/tile/9/9")
    assert missing_response.status_code == 404
    detail = missing_response.json()["detail"]
    assert detail["code"] == "tile_not_found"
    assert detail["message"] == "No tile at (9, 9)"
    assert detail["requested_position"] == [9, 9]
    assert detail["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}
    assert detail["tile_count"] == 4
    assert detail["entity_count"] == 0
    assert detail["object_count"] == 0


def test_eb_18_009_action_execute_error_payload_reports_available_corrections() -> None:
    """EB-18-009: action execution errors include correction context."""
    client, session_id, hero, _monster = create_action_api_session()

    available_response = client.get(f"/entity/{hero.uuid}/available-actions")
    assert available_response.status_code == 200
    available_payload = available_response.json()
    assert "Attack_MELEE_MAIN" in {
        action["template_name"] for action in available_payload["entity_actions"]
    }

    response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "template_name": "NotARealAction",
            "target_index": 0,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "unknown_action"
    assert detail["message"] == "Unknown action: NotARealAction"
    assert detail["entity_uuid"] == str(hero.uuid)
    assert detail["action_economy"]["actions"] == 1
    assert detail["action_economy"]["movement"] == hero.action_economy.movement.normalized_score
    assert "Attack_MELEE_MAIN" in detail["valid_action_names"]
    assert detail["available_actions"]["entity_uuid"] == str(hero.uuid)
    assert detail["available_actions"]["actions_remaining"] == 1

    bad_target_response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "template_name": "Attack_MELEE_MAIN",
            "target_index": 999,
        },
    )

    assert bad_target_response.status_code == 400
    bad_target_detail = bad_target_response.json()["detail"]
    assert bad_target_detail["code"] == "invalid_action_target"
    assert "Target index 999 not valid for Attack_MELEE_MAIN" in bad_target_detail["message"]
    assert "Attack_MELEE_MAIN" in bad_target_detail["valid_action_names"]


def test_eb_18_027_available_actions_serializes_spell_slot_variant_metadata() -> None:
    """EB-18-027: /available-actions serializes executable spell slot variants."""
    reset_chapter_18_state(width=12, height=8)
    client = TestClient(app)
    caster = create_caster(name="Book Caster", position=(1, 1), faction="heroes")
    target = create_skeleton(name="Book Target", position=(3, 1), faction="monsters")
    Entity.update_all_entities_senses()

    response = client.get(f"/entity/{caster.uuid}/available-actions")

    assert response.status_code == 200
    payload = response.json()
    missile_by_name = {
        action["template_name"]: action
        for action in payload["entity_actions"]
        if action.get("base_template_name") == "Magic Missile"
    }
    fireball_by_name = {
        action["template_name"]: action
        for action in payload["position_actions"]
        if action.get("base_template_name") == "Fireball"
    }

    assert payload["entity_uuid"] == str(caster.uuid)
    assert _available_actions_cache[str(caster.uuid)].entity_uuid == caster.uuid
    assert {"Magic Missile__slot_1", "Magic Missile__slot_3"} <= set(missile_by_name)
    assert "Fireball__slot_3" in fireball_by_name

    missile_level_1 = missile_by_name["Magic Missile__slot_1"]
    missile_level_3 = missile_by_name["Magic Missile__slot_3"]
    fireball_level_3 = fireball_by_name["Fireball__slot_3"]

    assert missile_level_1["display_name"] == "Magic Missile (Level 1)"
    assert missile_level_1["spell_level"] == 1
    assert missile_level_1["cast_at_level"] == 1
    assert missile_level_1["is_spell_variant"] is True
    assert missile_level_1["num_projectiles"] == 3
    assert missile_level_1["allow_same_target"] is True
    assert str(target.uuid) in {
        target_info["target_uuid"] for target_info in missile_level_1["valid_targets"]
    }

    assert missile_level_3["display_name"] == "Magic Missile (Level 3)"
    assert missile_level_3["cast_at_level"] == 3
    assert missile_level_3["num_projectiles"] == 5
    assert fireball_level_3["target_type"] == "position_aoe"
    assert fireball_level_3["spell_level"] == 3
    assert fireball_level_3["cast_at_level"] == 3
    assert fireball_level_3["is_spell_variant"] is True


def test_eb_18_010_named_action_endpoints_share_structured_error_payloads() -> None:
    """EB-18-010: named action endpoints return structured correction details."""
    client, session_id, hero, monster = create_action_api_session()
    available_response = client.get(f"/entity/{hero.uuid}/available-actions")
    assert available_response.status_code == 200

    unknown_self_response = client.post(
        "/action/self",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "NotARealAction",
        },
    )
    assert unknown_self_response.status_code == 400
    unknown_self = unknown_self_response.json()["detail"]
    assert unknown_self["code"] == "unknown_action"
    assert unknown_self["message"] == "Unknown action: NotARealAction"
    assert "Dash" in unknown_self["valid_action_names"]
    assert unknown_self["action_economy"]["actions"] == 1

    wrong_self_response = client.post(
        "/action/self",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Attack_MELEE_MAIN",
        },
    )
    assert wrong_self_response.status_code == 400
    wrong_self = wrong_self_response.json()["detail"]
    assert wrong_self["code"] == "invalid_action_type"
    assert "not a SELF action" in wrong_self["message"]
    assert "Attack_MELEE_MAIN" in wrong_self["valid_action_names"]

    wrong_entity_response = client.post(
        "/action/entity",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Dash",
            "target_uuid": str(monster.uuid),
        },
    )
    assert wrong_entity_response.status_code == 400
    wrong_entity = wrong_entity_response.json()["detail"]
    assert wrong_entity["code"] == "invalid_action_type"
    assert "not an ENTITY action" in wrong_entity["message"]
    assert wrong_entity["available_actions"]["entity_uuid"] == str(hero.uuid)

    wrong_position_response = client.post(
        "/action/position",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Dash",
            "position": [1, 2],
        },
    )
    assert wrong_position_response.status_code == 400
    wrong_position = wrong_position_response.json()["detail"]
    assert wrong_position["code"] == "invalid_action_type"
    assert "not a position action" in wrong_position["message"]
    assert wrong_position["action_economy"]["actions"] == 1


def test_eb_18_023_entity_action_target_errors_report_current_choices() -> None:
    """EB-18-023: /action/entity target errors include correction context."""
    client, session_id, hero, monster = create_action_api_session()
    available_response = client.get(f"/entity/{hero.uuid}/available-actions")
    assert available_response.status_code == 200

    invalid_target_response = client.post(
        "/action/entity",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Attack_MELEE_MAIN",
            "target_uuid": "not-a-uuid",
        },
    )
    assert invalid_target_response.status_code == 400
    invalid_target = invalid_target_response.json()["detail"]
    assert invalid_target["code"] == "invalid_target_uuid"
    assert invalid_target["target_uuid"] == "not-a-uuid"
    assert invalid_target["entity_uuid"] == str(hero.uuid)
    assert "Attack_MELEE_MAIN" in invalid_target["valid_action_names"]
    assert invalid_target["available_actions"]["entity_uuid"] == str(hero.uuid)
    assert {entity["uuid"] for entity in invalid_target["known_entities"]} >= {
        str(hero.uuid),
        str(monster.uuid),
    }

    missing_target_uuid = uuid4()
    missing_target_response = client.post(
        "/action/entity",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Attack_MELEE_MAIN",
            "target_uuid": str(missing_target_uuid),
        },
    )
    assert missing_target_response.status_code == 404
    missing_target = missing_target_response.json()["detail"]
    assert missing_target["code"] == "target_not_found"
    assert missing_target["target_uuid"] == str(missing_target_uuid)
    assert "Book Hero" in {entity["name"] for entity in missing_target["known_entities"]}
    assert missing_target["action_economy"]["actions"] == 1
    assert "Attack_MELEE_MAIN" in missing_target["valid_action_names"]


def test_eb_18_011_entity_and_handler_errors_report_current_choices() -> None:
    """EB-18-011: entity and handler errors expose correction context."""
    client, session_id, hero, monster = create_action_api_session()
    add_opportunity_attack_handler(hero)

    invalid_entity_response = client.get("/entity/not-a-uuid")
    assert invalid_entity_response.status_code == 400
    invalid_entity = invalid_entity_response.json()["detail"]
    assert invalid_entity["code"] == "invalid_entity_uuid"
    assert invalid_entity["entity_uuid"] == "not-a-uuid"
    assert {entity["uuid"] for entity in invalid_entity["known_entities"]} >= {
        str(hero.uuid),
        str(monster.uuid),
    }

    missing_uuid = uuid4()
    missing_entity_response = client.get(f"/entity/{missing_uuid}")
    assert missing_entity_response.status_code == 404
    missing_entity = missing_entity_response.json()["detail"]
    assert missing_entity["code"] == "entity_not_found"
    assert missing_entity["entity_uuid"] == str(missing_uuid)
    assert any(entity["name"] == "Book Hero" for entity in missing_entity["known_entities"])

    handlers_response = client.get(f"/entity/{hero.uuid}/handlers")
    assert handlers_response.status_code == 200
    handler_names = {handler["name"] for handler in handlers_response.json()["handlers"]}
    assert "Opportunity Attack Handler" in handler_names

    missing_handler_response = client.post(
        f"/entity/{hero.uuid}/handlers/NotAHandler/toggle",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid), "enabled": False},
    )
    assert missing_handler_response.status_code == 404
    missing_handler = missing_handler_response.json()["detail"]
    assert missing_handler["code"] == "handler_not_found"
    assert missing_handler["handler_name"] == "NotAHandler"
    assert "Opportunity Attack Handler" in missing_handler["valid_handler_names"]
    assert any(handler["enabled"] for handler in missing_handler["handlers"])

    mismatch_response = client.post(
        f"/entity/{monster.uuid}/handlers/Opportunity%20Attack%20Handler/toggle",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid), "enabled": False},
    )
    assert mismatch_response.status_code == 400
    mismatch = mismatch_response.json()["detail"]
    assert mismatch["code"] == "entity_uuid_mismatch"
    assert mismatch["entity_uuid"] == str(hero.uuid)
    assert mismatch["handler_name"] == "Opportunity Attack Handler"
    assert "Opportunity Attack Handler" in mismatch["valid_handler_names"]


def test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout() -> None:
    """EB-18-012: equipment errors expose slots, inventory, and loadout state."""
    client, session_id, hero, _monster = create_action_api_session()
    potion = create_healing_potion(hero.uuid)
    dagger = create_dagger(hero.uuid)
    assert hero.inventory.add_item(potion)
    assert hero.inventory.add_item(dagger)

    equipment_response = client.get(f"/entity/{hero.uuid}/equipment")
    assert equipment_response.status_code == 200
    assert {item["uuid"] for item in equipment_response.json()["inventory"]} == {
        str(potion.uuid),
        str(dagger.uuid),
    }

    missing_item_response = client.get(f"/entity/{hero.uuid}/equipment/item/{uuid4()}")
    assert missing_item_response.status_code == 404
    missing_item = missing_item_response.json()["detail"]
    assert missing_item["code"] == "item_not_found"
    assert "weapon_melee_main" in missing_item["valid_slots"]
    assert str(potion.uuid) in missing_item["inventory_item_uuids"]
    assert missing_item["equipment"]["ac"] == hero.ac_bonus().normalized_score

    invalid_slot_response = client.post(
        f"/entity/{hero.uuid}/equip",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "item_uuid": str(dagger.uuid),
            "slot": "not_a_slot",
        },
    )
    assert invalid_slot_response.status_code == 400
    invalid_slot = invalid_slot_response.json()["detail"]
    assert invalid_slot["code"] == "invalid_slot"
    assert invalid_slot["slot"] == "not_a_slot"
    assert str(dagger.uuid) in invalid_slot["inventory_item_uuids"]
    assert "ring_left" in invalid_slot["valid_slots"]

    potion_equip_response = client.post(
        f"/entity/{hero.uuid}/equip",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "item_uuid": str(potion.uuid),
        },
    )
    assert potion_equip_response.status_code == 400
    potion_equip = potion_equip_response.json()["detail"]
    assert potion_equip["code"] == "item_not_equippable"
    assert potion_equip["item_uuid"] == str(potion.uuid)
    assert str(potion.uuid) in potion_equip["inventory_item_uuids"]

    empty_slot_response = client.post(
        f"/entity/{hero.uuid}/unequip",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "slot": "weapon_ranged_off",
        },
    )
    assert empty_slot_response.status_code == 400
    empty_slot = empty_slot_response.json()["detail"]
    assert empty_slot["code"] == "empty_or_canceled_slot"
    assert empty_slot["slot"] == "weapon_ranged_off"
    assert "weapon_ranged_off" in empty_slot["valid_slots"]
    assert empty_slot["equipped_item_uuids"]


def test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities() -> None:
    """EB-18-013: session and game errors expose current session/game context."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    client = TestClient(app)

    invalid_player_response = client.post(
        "/session/create",
        json={"player_type": "dragon", "name": "Wrong Door"},
    )
    assert invalid_player_response.status_code == 400
    invalid_player = invalid_player_response.json()["detail"]
    assert invalid_player["code"] == "invalid_player_type"
    assert invalid_player["player_type"] == "dragon"
    assert {"human", "codex", "ai"} <= set(invalid_player["valid_player_types"])
    assert {entity["uuid"] for entity in invalid_player["known_entities"]} >= {
        str(hero.uuid),
        str(monster.uuid),
    }

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Book Player"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    no_game_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
    )
    assert no_game_response.status_code == 400
    no_game = no_game_response.json()["detail"]
    assert no_game["code"] == "no_active_game"
    assert no_game["session_id"] == session_id
    assert no_game["active_game_id"] is None
    assert no_game["requested_entity_uuids"] == [str(hero.uuid)]
    assert no_game["known_sessions"][0]["session_id"] == session_id

    missing_session_uuid = uuid4()
    ping_response = client.post(f"/session/{missing_session_uuid}/ping")
    assert ping_response.status_code == 404
    missing_ping = ping_response.json()["detail"]
    assert missing_ping["code"] == "session_not_found"
    assert missing_ping["session_id"] == str(missing_session_uuid)
    assert any(session["session_id"] == session_id for session in missing_ping["known_sessions"])

    bad_entities_response = client.get("/session/not-a-session/entities")
    assert bad_entities_response.status_code == 400
    bad_entities = bad_entities_response.json()["detail"]
    assert bad_entities["code"] == "invalid_session_uuid"
    assert bad_entities["session_id"] == "not-a-session"
    assert bad_entities["known_entities"]


def test_eb_18_032_session_create_ping_and_delete_are_stateful() -> None:
    """EB-18-032: session create, ping, and delete form a stateful lifecycle."""
    reset_chapter_18_state()
    client = TestClient(app)

    create_response = client.post(
        "/session/create",
        json={"player_type": "codex"},
    )

    assert create_response.status_code == 200
    created = create_response.json()
    session_id = created["session_id"]
    assert created["player_type"] == "codex"
    assert created["name"] == "Codex"

    ping_response = client.post(f"/session/{session_id}/ping")
    assert ping_response.status_code == 200
    pinged = ping_response.json()
    assert pinged["status"] == "ok"
    assert pinged["session_id"] == session_id
    assert pinged["connection_status"] == "connected"
    assert pinged["is_my_turn"] is False
    assert pinged["active_entity_uuid"] is None
    assert pinged["active_entity_name"] is None
    assert pinged["controlled_entities"] == []

    delete_response = client.delete(f"/session/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted", "session_id": session_id}

    deleted_ping_response = client.post(f"/session/{session_id}/ping")
    assert deleted_ping_response.status_code == 404
    deleted_ping = deleted_ping_response.json()["detail"]
    assert deleted_ping["code"] == "session_not_found"
    assert deleted_ping["session_id"] == session_id
    assert deleted_ping["known_sessions"] == []


def test_eb_18_033_game_join_status_and_session_entities_are_stateful() -> None:
    """EB-18-033: game join, game status, and session entities share ownership state."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )
    sim.encounter = encounter
    game = sim.create_game_session(encounter)
    client = TestClient(app)

    hero_session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Hero Player"},
    )
    assert hero_session_response.status_code == 200
    hero_session_id = hero_session_response.json()["session_id"]

    hero_join_response = client.post(
        "/game/join",
        json={"session_id": hero_session_id, "entity_uuids": [str(hero.uuid)]},
    )
    assert hero_join_response.status_code == 200
    hero_join = hero_join_response.json()
    assert hero_join["success"] is True
    assert hero_join["game_id"] == str(game.game_id)
    assert hero_join["controlled_entities"] == [str(hero.uuid)]

    monster_session_response = client.post(
        "/session/create",
        json={"player_type": "codex", "name": "Monster Player"},
    )
    assert monster_session_response.status_code == 200
    monster_session_id = monster_session_response.json()["session_id"]

    monster_join_response = client.post(
        "/game/join",
        json={"session_id": monster_session_id, "faction": "monsters"},
    )
    assert monster_join_response.status_code == 200
    monster_join = monster_join_response.json()
    assert monster_join["success"] is True
    assert monster_join["controlled_entities"] == [str(monster.uuid)]

    status_response = client.get("/game/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["active"] is True
    assert status["game_id"] == str(game.game_id)
    assert status["active_entity_uuid"] == str(hero.uuid)
    sessions_by_id = {session["session_id"]: session for session in status["sessions"]}
    assert sessions_by_id[hero_session_id]["controlled_entities"] == [str(hero.uuid)]
    assert sessions_by_id[hero_session_id]["is_their_turn"] is True
    assert sessions_by_id[monster_session_id]["controlled_entities"] == [str(monster.uuid)]
    assert sessions_by_id[monster_session_id]["is_their_turn"] is False

    entities_response = client.get(f"/session/{hero_session_id}/entities")
    assert entities_response.status_code == 200
    entities_payload = entities_response.json()
    assert entities_payload["session_id"] == hero_session_id
    assert entities_payload["controlled_entities"] == [
        {
            "uuid": str(hero.uuid),
            "name": hero.name,
            "faction": "heroes",
            "hp": hero.get_hp(),
            "position": list(hero.position),
        }
    ]


def test_eb_18_014_event_filter_and_simulation_errors_report_valid_ranges() -> None:
    """EB-18-014: event and simulation errors expose valid filters and ranges."""
    reset_chapter_18_state()
    client = TestClient(app)

    invalid_event_response = client.get("/events", params={"event_type": "not_an_event"})
    assert invalid_event_response.status_code == 400
    invalid_event = invalid_event_response.json()["detail"]
    assert invalid_event["code"] == "unknown_event_type"
    assert invalid_event["event_type"] == "not_an_event"
    assert "attack" in invalid_event["valid_event_types"]
    assert invalid_event["event_count"] == EventQueue.event_cursor()

    invalid_phase_response = client.get("/events", params={"phase": "not_a_phase"})
    assert invalid_phase_response.status_code == 400
    invalid_phase = invalid_phase_response.json()["detail"]
    assert invalid_phase["code"] == "unknown_event_phase"
    assert invalid_phase["phase"] == "not_a_phase"
    assert "completion" in invalid_phase["valid_phases"]

    bad_sse_session_response = client.get(
        "/events/subscribe",
        params={"session_id": "not-a-session"},
    )
    assert bad_sse_session_response.status_code == 400
    bad_sse_session = bad_sse_session_response.json()["detail"]
    assert bad_sse_session["code"] == "invalid_session_uuid"
    assert bad_sse_session["session_id"] == "not-a-session"

    resume_response = client.post("/simulation/resume")
    assert resume_response.status_code == 400
    resume_detail = resume_response.json()["detail"]
    assert resume_detail["code"] == "simulation_not_started"
    assert resume_detail["has_encounter"] is False
    assert resume_detail["min_delay"] == 0.1
    assert resume_detail["max_delay"] == 10.0

    low_delay_response = client.post("/simulation/set-delay", params={"delay": 0.05})
    assert low_delay_response.status_code == 400
    low_delay = low_delay_response.json()["detail"]
    assert low_delay["code"] == "delay_too_low"
    assert low_delay["requested_delay"] == 0.05
    assert low_delay["turn_delay"] == sim.turn_delay

    high_delay_response = client.post("/simulation/set-delay", params={"delay": 11})
    assert high_delay_response.status_code == 400
    high_delay = high_delay_response.json()["detail"]
    assert high_delay["code"] == "delay_too_high"
    assert high_delay["requested_delay"] == 11
    assert high_delay["max_delay"] == 10.0


def test_eb_18_025_end_turn_without_active_encounter_reports_state_context() -> None:
    """EB-18-025: /action/end-turn reports structured encounter-state drift."""
    client, session_id, hero, monster = create_action_api_session()
    active_game_id = str(sim.game.game_id) if sim.game else None
    sim.encounter = None

    response = client.post(
        "/action/end-turn",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid)},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "no_active_encounter"
    assert detail["session_id"] == session_id
    assert detail["entity_uuid"] == str(hero.uuid)
    assert detail["entity_name"] == "Book Hero"
    assert detail["active_game_id"] == active_game_id
    assert detail["active_entity_uuid"] == str(hero.uuid)
    assert detail["has_encounter"] is False
    assert detail["encounter_state"] is None
    assert {entity["uuid"] for entity in detail["known_entities"]} >= {
        str(hero.uuid),
        str(monster.uuid),
    }


def test_eb_18_026_session_authority_errors_report_action_context() -> None:
    """EB-18-026: session action validation errors expose authority context."""
    client, session_id, hero, monster = create_action_api_session()
    mgr = sim.get_session_manager()
    hero_session_uuid = UUID(session_id)
    hero_session = mgr.get_session(hero_session_uuid)
    assert hero_session is not None

    invalid_session_uuid = uuid4()
    invalid_session_response = client.post(
        "/action/self",
        json={"session_id": str(invalid_session_uuid), "entity_uuid": str(hero.uuid), "action_name": "Dash"},
    )
    assert invalid_session_response.status_code == 401
    invalid_session = invalid_session_response.json()["detail"]
    assert invalid_session["code"] == "invalid_session"
    assert invalid_session["session_id"] == str(invalid_session_uuid)
    assert invalid_session["entity_uuid"] == str(hero.uuid)
    assert session_id in invalid_session["known_session_ids"]
    assert invalid_session["active_entity_uuid"] == str(hero.uuid)

    unowned_response = client.post(
        "/action/self",
        json={"session_id": session_id, "entity_uuid": str(monster.uuid), "action_name": "Dash"},
    )
    assert unowned_response.status_code == 403
    unowned = unowned_response.json()["detail"]
    assert unowned["code"] == "entity_not_controlled"
    assert unowned["controlled_entities"] == [str(hero.uuid)]
    assert unowned["entity_owner_session_id"] is None

    monster_session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Monster Player"},
    )
    assert monster_session_response.status_code == 200
    monster_session_id = monster_session_response.json()["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": monster_session_id, "entity_uuids": [str(monster.uuid)]},
    )
    assert join_response.status_code == 200

    wrong_turn_response = client.post(
        "/action/self",
        json={"session_id": monster_session_id, "entity_uuid": str(monster.uuid), "action_name": "Dash"},
    )
    assert wrong_turn_response.status_code == 403
    wrong_turn = wrong_turn_response.json()["detail"]
    assert wrong_turn["code"] == "not_entity_turn"
    assert wrong_turn["active_entity_uuid"] == str(hero.uuid)
    assert wrong_turn["controlled_entities"] == [str(monster.uuid)]
    assert wrong_turn["entity_owner_session_id"] == monster_session_id

    assert sim.encounter is not None
    sim.encounter.turn_state = TurnState.NOT_STARTED
    stopped_turn_response = client.post(
        "/action/self",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid), "action_name": "Dash"},
    )
    assert stopped_turn_response.status_code == 400
    stopped_turn = stopped_turn_response.json()["detail"]
    assert stopped_turn["code"] == "turn_not_in_progress"
    assert stopped_turn["turn_state"] == TurnState.NOT_STARTED.value

    hero_session.disconnect()
    disconnected_response = client.post(
        "/action/self",
        json={"session_id": session_id, "entity_uuid": str(hero.uuid), "action_name": "Dash"},
    )
    assert disconnected_response.status_code == 401
    disconnected = disconnected_response.json()["detail"]
    assert disconnected["code"] == "session_disconnected"
    assert disconnected["connection_status"] == "disconnected"

    mgr.active_game = None
    sim._game_session = None
    no_game_response = client.post(
        "/action/self",
        json={"session_id": monster_session_id, "entity_uuid": str(monster.uuid), "action_name": "Dash"},
    )
    assert no_game_response.status_code == 400
    no_game = no_game_response.json()["detail"]
    assert no_game["code"] == "no_active_game"
    assert no_game["active_game_id"] is None
    assert no_game["active_entity_uuid"] is None
    assert monster_session_id in no_game["known_session_ids"]


def test_eb_18_015_mapeditor_errors_report_catalog_map_and_save_context() -> None:
    """EB-18-015: mapeditor failures expose catalog, map, and save context."""
    reset_chapter_18_state()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as save_dir:
        old_save_dir = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
        os.environ["DND_MAPEDITOR_SAVE_DIR"] = save_dir
        try:
            invalid_preset_response = client.post(
                "/mapeditor/maps",
                json={"source": "preset", "preset_id": "missing_preset"},
            )
            assert invalid_preset_response.status_code == 400
            invalid_preset = invalid_preset_response.json()["detail"]
            assert invalid_preset["code"] == "mapeditor_map_create_failed"
            assert invalid_preset["requested_preset_id"] == "missing_preset"
            assert "forgotten_crypt_arena" in invalid_preset["valid_presets"]

            scratch_response = client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 2, "height": 2, "origin": [0, 0]},
            )
            assert scratch_response.status_code == 200

            unknown_object_response = client.post(
                "/mapeditor/map/objects",
                json={"catalog_id": "unknown_object", "position": [0, 0]},
            )
            assert unknown_object_response.status_code == 400
            unknown_object = unknown_object_response.json()["detail"]
            assert unknown_object["code"] == "mapeditor_object_place_failed"
            assert unknown_object["requested_catalog_id"] == "unknown_object"
            assert unknown_object["requested_position"] == [0, 0]
            assert "door" in unknown_object["valid_objects"]
            assert "healing_potion" in unknown_object["valid_loot"]
            assert unknown_object["current_map"]["tile_count"] == 4

            bad_tile_response = client.post(
                "/mapeditor/map/tiles",
                json={"tiles": [{"x": 0, "y": 0, "directional_channel": "movement"}]},
            )
            assert bad_tile_response.status_code == 400
            bad_tile = bad_tile_response.json()["detail"]
            assert bad_tile["code"] == "mapeditor_tile_patch_failed"
            assert bad_tile["directional_patch_required_fields"] == [
                "directional_channel",
                "direction",
                "passable",
            ]
            assert bad_tile["requested_tiles"][0]["directional_channel"] == "movement"

            missing_delete_response = client.post("/mapeditor/map/objects/delete", json={})
            assert missing_delete_response.status_code == 400
            missing_delete = missing_delete_response.json()["detail"]
            assert missing_delete["code"] == "mapeditor_object_delete_failed"
            assert missing_delete["requested_object_uuid"] is None
            assert missing_delete["requested_position"] is None

            save_response = client.post(
                "/mapeditor/saves",
                json={"id": "book_map", "name": "Book Map"},
            )
            assert save_response.status_code == 200

            duplicate_response = client.post(
                "/mapeditor/saves",
                json={"id": "book_map", "name": "Book Map"},
            )
            assert duplicate_response.status_code == 400
            duplicate = duplicate_response.json()["detail"]
            assert duplicate["code"] == "mapeditor_save_failed"
            assert duplicate["requested_map_id"] == "book_map"
            assert "book_map" in duplicate["saved_map_ids"]

            missing_save_response = client.get("/mapeditor/saves/missing_map")
            assert missing_save_response.status_code == 404
            missing_save = missing_save_response.json()["detail"]
            assert missing_save["code"] == "mapeditor_save_not_found"
            assert missing_save["requested_map_id"] == "missing_map"
            assert "book_map" in missing_save["saved_map_ids"]
        finally:
            if old_save_dir is None:
                os.environ.pop("DND_MAPEDITOR_SAVE_DIR", None)
            else:
                os.environ["DND_MAPEDITOR_SAVE_DIR"] = old_save_dir


def test_eb_18_016_state_endpoint_serializes_editor_and_active_encounter_state() -> None:
    """EB-18-016: /state serializes grid, objects, entities, and encounter DTOs."""
    reset_chapter_18_state(width=2, height=2)
    client = TestClient(app)

    empty_response = client.get("/state")
    assert empty_response.status_code == 200
    empty_state = empty_response.json()
    assert empty_state["grid"]["min_x"] == 0
    assert empty_state["grid"]["max_x"] == 1
    assert len(empty_state["grid"]["tiles"]) == 4
    assert empty_state["entities"] == []
    assert empty_state["encounter"] is None
    assert empty_state["floor_objects"] == []

    object_response = client.post(
        "/mapeditor/map/objects",
        json={"catalog_id": "door", "position": [1, 1]},
    )
    assert object_response.status_code == 200

    editor_state = client.get("/state").json()
    assert editor_state["entities"] == []
    assert editor_state["encounter"] is None
    assert editor_state["floor_objects"][0]["name"] == "Door"
    assert editor_state["floor_objects"][0]["position"] == [1, 1]
    assert "is_open" in editor_state["floor_objects"][0]["state"]

    reset_chapter_18_state(width=4, height=4)
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )
    sim.encounter = encounter

    active_state = client.get("/state").json()
    assert {entity["uuid"] for entity in active_state["entities"]} == {
        str(hero.uuid),
        str(monster.uuid),
    }
    assert active_state["encounter"]["uuid"] == str(encounter.uuid)
    assert active_state["encounter"]["state"] == EncounterState.ACTIVE.value
    assert active_state["encounter"]["current_entity_uuid"] == str(hero.uuid)
    assert [combatant["uuid"] for combatant in active_state["encounter"]["initiative_order"]] == [
        str(hero.uuid),
        str(monster.uuid),
    ]


def test_eb_18_017_combat_log_endpoint_uses_since_cursor_without_duplication() -> None:
    """EB-18-017: /combat-log returns cursor-addressed combat log entries."""
    client, session_id, hero, _monster = create_action_api_session()

    before_response = client.get("/combat-log")
    assert before_response.status_code == 200
    before = before_response.json()
    before_total = before["total"]
    assert before["count"] == before_total
    assert client.get("/combat-log", params={"since": before_total}).json()["entries"] == []

    dash_response = client.post(
        "/action/self",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "action_name": "Dash",
        },
    )
    assert dash_response.status_code == 200
    assert dash_response.json()["combat_log_cursor_after"] == before_total + 1

    new_logs_response = client.get("/combat-log", params={"since": before_total})
    assert new_logs_response.status_code == 200
    new_logs = new_logs_response.json()
    assert new_logs["count"] == 1
    assert new_logs["total"] == before_total + 1
    assert new_logs["entries"][0]["entry_type"] == "action"
    assert new_logs["entries"][0]["data"]["action_name"] == "Dash"
    assert new_logs["entries"][0]["source_uuid"] == str(hero.uuid)

    repeated_response = client.get("/combat-log", params={"since": new_logs["total"]})
    assert repeated_response.status_code == 200
    repeated = repeated_response.json()
    assert repeated["entries"] == []
    assert repeated["count"] == 0
    assert repeated["total"] == new_logs["total"]

    replay_last_response = client.get("/combat-log", params={"since": new_logs["total"] - 1})
    assert replay_last_response.status_code == 200
    replay_last = replay_last_response.json()
    assert replay_last["count"] == 1
    assert replay_last["entries"][0]["data"]["action_name"] == "Dash"


def test_eb_18_018_combat_log_sse_follows_matching_completion_event() -> None:
    """EB-18-018: SSE emits an action combat log after its completion event."""
    client, session_id, hero, _monster = create_action_api_session()
    event_stream.ensure_attached()
    subscription = event_stream.subscribe()
    try:
        dash_response = client.post(
            "/action/self",
            json={
                "session_id": session_id,
                "entity_uuid": str(hero.uuid),
                "action_name": "Dash",
            },
        )
        envelopes = asyncio.run(drain_stream_subscription(subscription))
    finally:
        event_stream.unsubscribe(subscription)

    assert dash_response.status_code == 200
    dash_log_indexes = [
        index
        for index, envelope in enumerate(envelopes)
        if envelope["event"] == "combat_log"
        and envelope["data"].entry.data.get("action_name") == "Dash"
    ]
    assert len(dash_log_indexes) == 1

    dash_log_index = dash_log_indexes[0]
    assert dash_log_index > 0
    prior_envelope = envelopes[dash_log_index - 1]
    assert prior_envelope["event"] == "game_event"

    completion_payload = prior_envelope["data"]
    assert completion_payload.event.event_type == EventType.BASE_ACTION
    assert completion_payload.event.phase.value == "completion"
    assert completion_payload.event.name == "Dash"

    log_envelope = envelopes[dash_log_index]
    log_payload = log_envelope["data"]
    assert log_payload.entry.entry_type.value == "action"
    assert log_payload.entry.data["action_name"] == "Dash"
    assert log_payload.event_cursor == completion_payload.event_cursor
    assert log_payload.combat_log_cursor == dash_response.json()["combat_log_cursor_after"]
    assert log_envelope["id"] == make_stream_id(
        completion_payload.event_cursor,
        log_payload.combat_log_cursor,
    )


def run_all_tests() -> None:
    """Run all Chapter 18 parity examples as a script."""
    tests = [
        test_eb_18_001_encounter_start_sets_active_state_callbacks_and_round,
        test_eb_18_002_turn_lifecycle_builds_context_and_advances_rounds,
        test_eb_18_003_run_turn_and_advance_until_player_respect_controller_types,
        test_eb_18_019_surprise_blocks_reactions_until_skipped_turn_ends,
        test_eb_18_020_codex_controller_stops_as_external_input_turn,
        test_eb_18_021_external_ai_controller_waits_for_session_commands,
        test_eb_18_034_available_move_paths_preserve_directional_blockers,
        test_eb_18_004_execute_action_captures_combat_log_and_listener_payload,
        test_eb_18_005_check_deaths_marks_dead_and_ends_single_faction_encounter,
        test_eb_18_006_serialization_and_spell_catalog_api_do_not_mutate_registry,
        test_eb_18_030_health_endpoint_reports_scalar_listener_count,
        test_eb_18_031_simulation_reset_status_delay_and_step_are_stateful,
        test_eb_18_007_event_history_and_sse_payloads_preserve_directional_spatial_fields,
        test_eb_18_008_mapeditor_api_saves_map_state_without_entities_or_encounter,
        test_eb_18_022_mapeditor_save_load_roundtrip_restores_entity_free_state,
        test_eb_18_024_tile_lookup_error_reports_grid_context,
        test_eb_18_009_action_execute_error_payload_reports_available_corrections,
        test_eb_18_027_available_actions_serializes_spell_slot_variant_metadata,
        test_eb_18_010_named_action_endpoints_share_structured_error_payloads,
        test_eb_18_011_entity_and_handler_errors_report_current_choices,
        test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout,
        test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities,
        test_eb_18_032_session_create_ping_and_delete_are_stateful,
        test_eb_18_033_game_join_status_and_session_entities_are_stateful,
        test_eb_18_014_event_filter_and_simulation_errors_report_valid_ranges,
        test_eb_18_025_end_turn_without_active_encounter_reports_state_context,
        test_eb_18_026_session_authority_errors_report_action_context,
        test_eb_18_015_mapeditor_errors_report_catalog_map_and_save_context,
        test_eb_18_023_entity_action_target_errors_report_current_choices,
        test_eb_18_016_state_endpoint_serializes_editor_and_active_encounter_state,
        test_eb_18_017_combat_log_endpoint_uses_since_cursor_without_duplication,
        test_eb_18_018_combat_log_sse_follows_matching_completion_event,
    ]
    for test in tests:
        test()
    print("Chapter 18 encounter/API engine book examples passed.")


if __name__ == "__main__":
    run_all_tests()
