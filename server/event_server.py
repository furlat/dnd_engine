"""
WebSocket server for broadcasting game events + REST API for game state.

This server:
1. Hooks into EventQueue to capture all events
2. Broadcasts events to connected WebSocket clients
3. Provides REST endpoints for game state queries
4. Controls simulation (start/pause/resume/step)

Usage:
    # Start server
    uv run python -m server.event_server

    # Or import and run programmatically
    from server.event_server import run_server
    run_server(host="0.0.0.0", port=8000)
"""

import asyncio
import logging
import time
import traceback
from typing import Any, Dict, Set, Optional
from uuid import UUID, uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("dnd_server")

from dnd.core.events import BodyPart, Event, EventQueue, EventType, EventPhase, RingSlot
from dnd.core.gridmap import get_map, reset_map
from dnd.entity import Entity
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.monsters.bestiary import (
    create_goblin, create_skeleton,
    create_skeleton_warrior, create_skeleton_archer, create_skeleton_warlock,
)
from dnd.classes.sorcerer_factory import create_sorcerer as create_sorcerer_class, SorcererConfig
from dnd.classes.fighter_factory import create_fighter, FighterConfig
from dnd.classes.barbarian_factory import create_barbarian, BarbarianConfig, PrimalPathChoice
from dnd.items import create_shortsword, create_dagger, create_longbow
from dnd.items.test_items import (
    create_scroll_of_magic_missile, create_scroll_of_fireball,
    create_potion_of_greater_invisibility,
    create_torch,
)
from dnd.maps.arena_layout import build_standard_arena_environment
from dnd.blocks.equipment import WeaponSlot
from dnd.controller import Controller, HumanController, CodexController, MeleeAIController
from dnd.actions_functional import get_available_actions, execute_action, execute_by_index, execute_use_action
from dnd.actions import MovementEvent, JumpEvent
from dnd.core.base_actions import TargetType, AvailableTarget, AvailableActionsResult
from dnd.core.base_block import BaseBlock
from dnd.reactions import add_opportunity_attack_handler

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter, APIFloorObject,
    APIGameState, APISimulationStatus,
    APICurrentTurn, SimpleActionRequest, ActionResult, AoEPreviewResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    EventHistoryResponse, CombatLogHistoryResponse,
    SelfActionRequest, EntityActionRequest, PositionActionRequest, ExecuteByIndexRequest,
    ToggleHandlerRequest,
    APIEquipmentOverview, APIItemSummary, EquipRequest, UnequipRequest, EquipmentMutationResult,
    AdvanceEncounterResult,
    SpellCatalogResponse,
    MapEditorCatalog, MapEditorCreateMapRequest, MapEditorLightResponse, MapEditorMapSnapshot,
    MapEditorObjectDeleteRequest, MapEditorObjectPlaceRequest, MapEditorTilePatchRequest, MapEditorVisibilityResponse,
    MapEditorWalkabilityResponse, MapEditorSaveMapRequest, MapEditorSavedMapDocument,
    MapEditorSavedMapList, MapEditorSavedMapMetadata,
)
from server.mapeditor_support import (
    apply_tile_patches,
    build_catalog,
    create_editor_map,
    delete_catalog_object,
    delete_saved_editor_map,
    get_editor_snapshot,
    get_objective_light,
    get_saved_editor_map,
    get_visibility_blockers,
    get_walkability,
    list_saved_editor_maps,
    load_saved_editor_map,
    place_catalog_object,
    save_current_editor_map,
)
from server.spell_catalog import build_spell_catalog
from server.event_stream import (
    HeartbeatPayload,
    StreamSyncPayload,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.session import (
    SessionManager, GameSession,
    PlayerType, ConnectionStatus, get_session_manager
)

_available_actions_cache: Dict[str, AvailableActionsResult] = {}


class EventMonitor:
    """Monitor EventQueue and broadcast serialized events to listeners.

    Attributes:
        _listeners: Listener queues that receive serialized event payloads.
        _running: Whether the monitor callback is registered with EventQueue.
    """

    def __init__(self) -> None:
        self._listeners: Set[asyncio.Queue] = set()
        self._running = False

    def add_listener(self, queue: asyncio.Queue) -> None:
        """Add a listener queue that will receive events."""
        self._listeners.add(queue)

    def remove_listener(self, queue: asyncio.Queue) -> None:
        """Remove a listener queue."""
        self._listeners.discard(queue)

    @property
    def listener_count(self) -> int:
        """Number of active listeners."""
        return len(self._listeners)

    def _on_event(self, event: Event) -> None:
        """Callback invoked for every event in EventQueue."""
        if not self._listeners:
            return

        if event.event_type.value == "attack":
            attack_outcome = getattr(event, 'attack_outcome', None)
            dice_roll = getattr(event, 'dice_roll', None)
            logger.debug(
                "Broadcasting attack event phase=%s outcome=%s dice=%s",
                event.phase.value,
                attack_outcome,
                dice_roll,
            )

        try:
            event_data = event.model_dump(mode="json")

            for queue in self._listeners:
                try:
                    queue.put_nowait(event_data)
                except asyncio.QueueFull:
                    continue
        except Exception:
            logger.exception("Error serializing event for websocket broadcast")

    def start(self) -> None:
        """Start monitoring events."""
        if self._running:
            return

        EventQueue.add_on_event_callback(self._on_event)
        self._running = True
        logger.info("EventMonitor started")

    def stop(self) -> None:
        """Stop monitoring events."""
        if not self._running:
            return

        EventQueue.remove_on_event_callback(self._on_event)
        self._running = False
        logger.info("EventMonitor stopped")

event_monitor = EventMonitor()


class SimulationState:
    """Hold mutable server simulation state.

    Attributes:
        encounter: Active encounter, if one has been created.
        combat_task: Background task advancing AI combat, if running.
        paused: Whether automatic simulation advancement is paused.
        turn_delay: Delay in seconds between automatic turns.
        auto_run_ai: Whether AI turns should advance automatically.
        _session_manager: Session registry backing game/player sessions.
        _game_session: Active game session for the current encounter.
    """

    def __init__(self) -> None:
        self.encounter: Optional[Encounter] = None
        self.combat_task: Optional[asyncio.Task] = None
        self.paused: bool = True
        self.turn_delay: float = 1.5
        self.auto_run_ai: bool = True
        self._session_manager = get_session_manager()
        self._game_session: Optional[GameSession] = None

    @property
    def game(self) -> Optional[GameSession]:
        """Get the active game session."""
        return self._game_session

    @property
    def waiting_for_human(self) -> bool:
        """Check if waiting for a human/codex player (derived from session state)."""
        if not self._game_session or not self.encounter:
            return False
        active_player = self._game_session.active_player
        if not active_player:
            return False
        return active_player.player_type in (PlayerType.HUMAN, PlayerType.CODEX)

    @property
    def human_entity_uuid(self) -> Optional[UUID]:
        """Get the active entity UUID if it's a human/codex turn."""
        if not self._game_session:
            return None
        return self._game_session.active_entity_uuid

    def create_game_session(self, encounter: Encounter) -> GameSession:
        """Create a new game session for the encounter."""
        self._game_session = self._session_manager.create_game(encounter)
        return self._game_session

    def get_session_manager(self) -> SessionManager:
        """Get the session manager."""
        return self._session_manager

    def reset(self) -> None:
        """Reset mutable server session state for a fresh game scene."""
        self.encounter = None
        self._game_session = None
        self.combat_task = None
        self.paused = True
        self._session_manager.sessions.clear()
        self._session_manager.games.clear()
        self._session_manager.active_game = None
        _available_actions_cache.clear()
        event_stream.ensure_attached()

sim = SimulationState()


def setup_combat() -> Encounter:
    """Initialize the default two-combatant demo encounter.

    Returns:
        Encounter containing one goblin and one skeleton with melee AI controllers.
    """
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    EventQueue.reset()
    event_stream.ensure_attached()

    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    goblin = create_goblin(name="Goblin Scout", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton Warrior", position=(12, 7))
    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(goblin, MeleeAIController(source_entity_uuid=goblin.uuid))
    encounter.add_combatant(skeleton, MeleeAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def setup_arena_combat(
    player_position: tuple = (2, 7),
    pvp_mode: bool = False,
    character_class: str = "fighter"
) -> Encounter:
    """Initialize arena combat with one hero against three skeletons.

    Args:
        player_position: Starting position for the hero.
        pvp_mode: Whether skeletons use Codex controllers instead of melee AI.
        character_class: Hero class fixture to create.

    Returns:
        Encounter configured with the hero and skeleton combatants.
    """
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()
    EventQueue.reset()
    event_stream.ensure_attached()

    grid = get_map()
    build_standard_arena_environment(grid)

    if character_class == "barbarian":
        player = create_barbarian_hero(name="Hero", position=player_position, faction="heroes")
    elif character_class == "sorcerer":
        config = SorcererConfig(
            name="Hero",
            position=player_position,
            faction="heroes",
            level=5,
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt", "Ray of Frost",
                "Magic Missile", "Burning Hands", "Thunderwave",
                "Scorching Ray", "Hold Person", "Shatter", "Invisibility",
                "Fireball", "Lightning Bolt",
            ],
        )
        player = create_sorcerer_class(config)
    else:
        player = create_dex_fighter(name="Hero", position=player_position, faction="heroes")

    torch = create_torch(player.uuid)
    player.loot_item(torch)
    torch.ignite(player.uuid)

    potion = create_potion_of_greater_invisibility(player.uuid)
    player.loot_item(potion)

    if character_class == "sorcerer":
        scroll_mm1 = create_scroll_of_magic_missile(player.uuid, cast_level=1)
        scroll_mm2 = create_scroll_of_magic_missile(player.uuid, cast_level=1)
        scroll_fb3 = create_scroll_of_fireball(player.uuid, cast_level=3)
        scroll_fb5 = create_scroll_of_fireball(player.uuid, cast_level=5)
        player.loot_item(scroll_mm1)
        player.loot_item(scroll_mm2)
        player.loot_item(scroll_fb3)
        player.loot_item(scroll_fb5)

    warrior = create_skeleton_warrior(
        name="Skeleton Warrior", position=(12, 5), faction="monsters", darkvision=True
    )
    archer = create_skeleton_archer(
        name="Skeleton Archer", position=(12, 7), faction="monsters", darkvision=True
    )
    warlock = create_skeleton_warlock(
        name="Skeleton Warlock", position=(12, 9), faction="monsters", darkvision=True
    )
    skeletons = [warrior, archer, warlock]

    add_opportunity_attack_handler(player)
    for skeleton in skeletons:
        add_opportunity_attack_handler(skeleton)

    Entity.update_all_entities_senses(max_distance=20)

    encounter_name = "PvP Arena" if pvp_mode else "Arena Combat"
    encounter = Encounter(name=encounter_name, source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))

    for skeleton in skeletons:
        if pvp_mode:
            encounter.add_combatant(skeleton, CodexController(source_entity_uuid=skeleton.uuid))
        else:
            encounter.add_combatant(skeleton, MeleeAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def setup_aoe_test_arena(
    player_position: tuple = (2, 7),
    character_class: str = "sorcerer"
) -> Encounter:
    """Initialize an open arena for area-of-effect spell testing.

    Args:
        player_position: Starting position for the hero.
        character_class: Hero class fixture to create.

    Returns:
        Encounter with an open grid and three clustered goblins.
    """
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()
    EventQueue.reset()
    event_stream.ensure_attached()

    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    if character_class == "sorcerer":
        config = SorcererConfig(
            name="Hero",
            position=player_position,
            faction="heroes",
            level=5,
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt", "Ray of Frost",
                "Magic Missile", "Burning Hands", "Thunderwave",
                "Scorching Ray", "Hold Person", "Shatter", "Invisibility",
                "Fireball", "Lightning Bolt",
            ],
        )
        player = create_sorcerer_class(config)
    elif character_class == "barbarian":
        player = create_barbarian_hero(name="Hero", position=player_position, faction="heroes")
    else:
        player = create_dex_fighter(name="Hero", position=player_position, faction="heroes")

    goblin_positions = [(12, 4), (12, 5), (12, 6)]
    goblins = []
    for i, pos in enumerate(goblin_positions):
        goblin = create_goblin(
            name=f"Goblin {i+1}",
            position=pos,
            faction="monsters"
        )
        goblins.append(goblin)

    add_opportunity_attack_handler(player)
    for goblin in goblins:
        add_opportunity_attack_handler(goblin)

    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="AoE Test Arena", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))

    for goblin in goblins:
        encounter.add_combatant(goblin, MeleeAIController(source_entity_uuid=goblin.uuid))

    return encounter


def create_dex_fighter(name: str = "Hero", position: tuple = (0, 0), faction: Optional[str] = None) -> Entity:
    """Create a level 5 Dexterity fighter fixture.

    The fixture uses two-weapon fighting, a shortsword, a dagger, and a
    longbow, with Dexterity and Constitution racial bonuses plus a level 4
    Dexterity ability-score increase.

    Args:
        name: Entity display name.
        position: Starting grid position.
        faction: Optional faction identifier.

    Returns:
        Configured fighter entity.
    """
    config = FighterConfig(
        level=5,
        name=name,
        position=position,
        faction=faction,
        base_strength=12,
        base_dexterity=15,
        base_constitution=14,
        base_intelligence=10,
        base_wisdom=10,
        base_charisma=8,
        bonus_plus_2="dexterity",
        bonus_plus_1="constitution",
        fighting_style="two_weapon",
        equipment_preset="archery",
        asi_4=[("dexterity", 2)],
    )

    fighter = create_fighter(config)

    fighter.equipment.unequip(WeaponSlot.MELEE_MAIN)
    fighter.equipment.unequip(WeaponSlot.RANGED_MAIN)

    shortsword = create_shortsword(fighter.uuid)
    dagger = create_dagger(fighter.uuid)
    longbow = create_longbow(fighter.uuid)

    fighter.equipment.equip(shortsword, WeaponSlot.MELEE_MAIN)
    fighter.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    fighter.equipment.equip(longbow, WeaponSlot.RANGED_MAIN)

    return fighter


def create_barbarian_hero(name: str = "Hero", position: tuple = (0, 0), faction: Optional[str] = None) -> Entity:
    """Create a level 5 Berserker barbarian fixture.

    The fixture has Strength 19 after racial and level 4 bonuses, Constitution
    15, and the greataxe equipment preset.

    Args:
        name: Entity display name.
        position: Starting grid position.
        faction: Optional faction identifier.

    Returns:
        Configured barbarian entity.
    """
    config = BarbarianConfig(
        level=5,
        name=name,
        position=position,
        faction=faction,
        base_strength=15,
        base_dexterity=13,
        base_constitution=14,
        base_intelligence=8,
        base_wisdom=12,
        base_charisma=10,
        bonus_plus_2="strength",
        bonus_plus_1="constitution",
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],
        equipment_preset="greataxe",
    )
    return create_barbarian(config)


async def advance_encounter() -> AdvanceEncounterResult:
    """Advance the encounter until a player-controlled turn or terminal state.

    Returns:
        Structured advancement result with AI combat-log entries and replication
        cursors.
    """
    if sim.encounter is None:
        return AdvanceEncounterResult(status="no_encounter")

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.roll_initiative()
        sim.encounter.start_encounter()

    if sim.encounter.state == EncounterState.ENDED:
        return AdvanceEncounterResult(
            status="encounter_ended",
            **action_cursor_fields(),
        )

    log_start = len(sim.encounter.combat_log)

    result = sim.encounter.advance_until_player()

    new_entries = sim.encounter.get_combat_log(log_start)
    ai_actions = [e.to_dict() for e in new_entries]

    return AdvanceEncounterResult(
        status=result.status,
        entity_uuid=str(result.entity_uuid) if result.entity_uuid else None,
        entity_name=result.entity_name,
        round=result.round_number,
        turn_index=result.turn_index,
        ai_actions=ai_actions,
        new_log_since=log_start,
        **action_cursor_fields(),
    )


def action_cursor_fields() -> dict:
    """Return replication cursors after a state mutation.

    Returns:
        Event and combat-log cursor positions for clients that need deltas.
    """
    return {
        "event_cursor_after": EventQueue.event_cursor(),
        "combat_log_cursor_after": len(sim.encounter.combat_log) if sim.encounter else 0,
    }


def _api_http_exception(
    status_code: int,
    code: str,
    message: str,
    **context: Any,
) -> HTTPException:
    """Create a structured HTTP exception detail payload.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with a structured detail body.
    """
    detail = {"code": code, "message": message}
    detail.update(context)
    return HTTPException(status_code=status_code, detail=detail)


def _known_entity_summaries() -> list[dict]:
    """Return compact correction context for currently registered entities.

    Returns:
        Serialized summaries for all entities in the global registry.
    """
    return [
        APIEntitySummary.create(entity).model_dump(mode="json")
        for entity in Entity.get_all_entities()
    ]


def _grid_state_context() -> dict[str, Any]:
    """Return compact correction context for the current grid.

    Returns:
        Grid bounds and object/entity counts for structured API errors.
    """
    grid = get_map()
    min_x, min_y, max_x, max_y = grid.bounds
    return {
        "grid_bounds": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        },
        "tile_count": grid.tile_count(),
        "entity_count": grid.entity_count(),
        "object_count": len(grid._object_positions),
    }


def _entity_lookup_exception(entity_uuid: str, status_code: int, code: str, message: str) -> HTTPException:
    """Create a structured entity lookup error.

    Args:
        entity_uuid: Entity UUID string that failed validation or lookup.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.

    Returns:
        HTTP exception with known-entity correction context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        entity_uuid=entity_uuid,
        known_entities=_known_entity_summaries(),
    )


def _resolve_entity_or_raise(entity_uuid: str) -> Entity:
    """Resolve an entity UUID string or raise a structured API error.

    Args:
        entity_uuid: Entity UUID string from a route path or request body.

    Returns:
        Resolved entity.

    Raises:
        HTTPException: If the UUID is malformed or no entity exists.
    """
    try:
        uuid_obj = UUID(entity_uuid)
    except ValueError:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid,
            status_code=400,
            code="invalid_entity_uuid",
            message="Invalid entity UUID format",
        )

    entity = Entity.get(uuid_obj)
    if not entity:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid,
            status_code=404,
            code="entity_not_found",
            message="Entity not found",
        )
    return entity


def _serialize_entity_handlers(entity: Entity) -> list[dict]:
    """Serialize player-toggleable handlers for one entity.

    Args:
        entity: Entity whose player-toggleable event handlers should be exposed.

    Returns:
        Handler summaries with name, UUID, enabled state, and trigger event.
    """
    handlers = []
    for handler in entity.event_handlers.values():
        if not handler.player_toggleable:
            continue
        trigger_event = ""
        if handler.trigger_conditions:
            trigger_event = handler.trigger_conditions[0].event_type.value
        handlers.append({
            "name": handler.name,
            "uuid": str(handler.uuid),
            "enabled": handler.enabled,
            "trigger_event": trigger_event,
        })
    return handlers


def _handler_http_exception(
    entity: Entity,
    status_code: int,
    code: str,
    message: str,
    handler_name: Optional[str] = None,
) -> HTTPException:
    """Create a structured handler API error.

    Args:
        entity: Entity whose handler mutation failed.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        handler_name: Optional handler name supplied by the client.

    Returns:
        HTTP exception with valid handler names and handler summaries.
    """
    handlers = _serialize_entity_handlers(entity)
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        entity_uuid=str(entity.uuid),
        entity_name=entity.name,
        handler_name=handler_name,
        valid_handler_names=[handler["name"] for handler in handlers],
        handlers=handlers,
    )


def _equipment_slot_map() -> dict[str, Any]:
    """Return API slot names mapped to engine equipment-slot enums.

    Returns:
        Mapping from request slot names to weapon, body-part, and ring slots.
    """
    return {
        "weapon_melee_main": WeaponSlot.MELEE_MAIN,
        "weapon_melee_off": WeaponSlot.MELEE_OFF,
        "weapon_ranged_main": WeaponSlot.RANGED_MAIN,
        "weapon_ranged_off": WeaponSlot.RANGED_OFF,
        "helmet": BodyPart.HEAD,
        "body_armor": BodyPart.BODY,
        "gauntlets": BodyPart.HANDS,
        "greaves": BodyPart.LEGS,
        "boots": BodyPart.FEET,
        "amulet": BodyPart.AMULET,
        "cloak": BodyPart.CLOAK,
        "ring_left": RingSlot.LEFT,
        "ring_right": RingSlot.RIGHT,
    }


def _equipment_context(entity: Entity) -> dict:
    """Build correction context for equipment and inventory endpoints.

    Args:
        entity: Entity whose inventory and equipment state should be exposed.

    Returns:
        Structured equipment context for mutation error responses.
    """
    equipped_items = entity.equipment.get_all_equipped_items()
    return {
        "entity_uuid": str(entity.uuid),
        "entity_name": entity.name,
        "valid_slots": list(_equipment_slot_map().keys()),
        "inventory_item_uuids": [str(uuid) for uuid in entity.inventory.items.keys()],
        "equipped_item_uuids": [str(item.uuid) for item in equipped_items],
        "equipment": APIEquipmentOverview.create(entity).model_dump(mode="json"),
    }


def _equipment_http_exception(
    entity: Entity,
    status_code: int,
    code: str,
    message: str,
    item_uuid: Optional[str] = None,
    slot: Optional[str] = None,
) -> HTTPException:
    """Create a structured equipment API error.

    Args:
        entity: Entity whose equipment mutation failed.
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        item_uuid: Optional item UUID supplied by the client.
        slot: Optional equipment slot supplied by the client.

    Returns:
        HTTP exception with equipment correction context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        item_uuid=item_uuid,
        slot=slot,
        **_equipment_context(entity),
    )


def _session_context() -> dict:
    """Build correction context for session and game endpoints.

    Returns:
        Known session, player type, active game, and entity context.
    """
    mgr = sim.get_session_manager()
    game = sim.game
    return {
        "valid_player_types": [player_type.value for player_type in PlayerType],
        "known_sessions": [
            session.to_dict()
            for session in mgr.sessions.values()
        ],
        "active_game_id": str(game.game_id) if game else None,
        "active_entity_uuid": str(game.active_entity_uuid) if game and game.active_entity_uuid else None,
        "known_entities": _known_entity_summaries(),
    }


def _session_http_exception(
    status_code: int,
    code: str,
    message: str,
    session_id: Optional[str] = None,
    **context: Any,
) -> HTTPException:
    """Create a structured session or game API error.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        session_id: Optional session ID supplied by the client.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with session and active-game context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        session_id=session_id,
        **_session_context(),
        **context,
    )


def _event_filter_http_exception(
    code: str,
    message: str,
    event_type: Optional[str] = None,
    phase: Optional[str] = None,
) -> HTTPException:
    """Create a structured event-history filter error.

    Args:
        code: Machine-readable error code.
        message: Human-readable error message.
        event_type: Optional event-type filter supplied by the client.
        phase: Optional event-phase filter supplied by the client.

    Returns:
        HTTP exception with valid event types, phases, and cursor context.
    """
    return _api_http_exception(
        status_code=400,
        code=code,
        message=message,
        event_type=event_type,
        phase=phase,
        valid_event_types=[event_type.value for event_type in EventType],
        valid_phases=[phase.value for phase in EventPhase],
        event_cursor=EventQueue.event_cursor(),
        event_count=len(EventQueue._all_events),
    )


def _simulation_context() -> dict:
    """Build correction context for simulation-control endpoints.

    Returns:
        Simulation status fields used by structured control errors.
    """
    return {
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused,
        "encounter_state": sim.encounter.state.value if sim.encounter else None,
        "round_number": sim.encounter.round_number if sim.encounter else None,
        "turn_delay": sim.turn_delay,
        "min_delay": 0.1,
        "max_delay": 10.0,
    }


def _simulation_http_exception(code: str, message: str, **context: Any) -> HTTPException:
    """Create a structured simulation-control API error.

    Args:
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with current simulation-control context.
    """
    return _api_http_exception(
        status_code=400,
        code=code,
        message=message,
        **_simulation_context(),
        **context,
    )


def _mapeditor_context() -> dict:
    """Build correction context for mapeditor endpoint failures.

    Returns:
        Catalog, saved-map, and current-map context for map-editor errors.
    """
    catalog = build_catalog()
    saved_maps = list_saved_editor_maps().maps
    current_map = None
    try:
        snapshot = get_editor_snapshot()
        current_map = {
            "grid_bounds": snapshot.grid_bounds.model_dump(mode="json"),
            "tile_count": len(snapshot.tiles),
            "floor_object_count": len(snapshot.floor_objects),
        }
    except Exception:
        current_map = None

    return {
        "valid_presets": [entry.id for entry in catalog.presets],
        "valid_tiles": [entry.id for entry in catalog.tiles],
        "valid_objects": [entry.id for entry in catalog.objects],
        "valid_loot": [entry.id for entry in catalog.loot],
        "saved_map_ids": [metadata.id for metadata in saved_maps],
        "current_map": current_map,
        "directional_patch_required_fields": ["directional_channel", "direction", "passable"],
    }


def _mapeditor_http_exception(
    status_code: int,
    code: str,
    message: str,
    **context: Any,
) -> HTTPException:
    """Create a structured mapeditor API error.

    Args:
        status_code: HTTP status code for the response.
        code: Machine-readable error code.
        message: Human-readable error message.
        **context: Additional JSON-serializable correction context.

    Returns:
        HTTP exception with map-editor correction context.
    """
    return _api_http_exception(
        status_code=status_code,
        code=code,
        message=message,
        **_mapeditor_context(),
        **context,
    )


def validate_session_action(session_id_str: str, entity_uuid_str: str) -> Entity:
    """Validate that a session can perform an action with an entity.

    Args:
        session_id_str: UUID string for the acting session.
        entity_uuid_str: UUID string for the entity trying to act.

    Returns:
        Entity that passed session ownership and turn validation.

    Raises:
        HTTPException: If either UUID is malformed, the entity is missing, or
            the session manager rejects the action.
    """
    try:
        session_id = UUID(session_id_str)
    except ValueError:
        raise _api_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id_str,
        )

    try:
        entity_uuid = UUID(entity_uuid_str)
    except ValueError:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid_str,
            status_code=400,
            code="invalid_entity_uuid",
            message="Invalid entity UUID format",
        )

    mgr = sim.get_session_manager()
    _, _ = mgr.validate_action(session_id, entity_uuid)

    entity = Entity.get(entity_uuid)
    if not entity:
        raise _entity_lookup_exception(
            entity_uuid=entity_uuid_str,
            status_code=404,
            code="entity_not_found",
            message="Entity not found",
        )

    return entity


async def run_combat_loop():
    """Run automated encounter turns while the simulation is active.

    Returns:
        None.
    """
    if sim.encounter is None:
        return

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.start_encounter()

    while sim.encounter.state == EncounterState.ACTIVE:
        if sim.paused:
            await asyncio.sleep(0.1)
            continue

        sim.encounter.run_turn()
        await asyncio.sleep(sim.turn_delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage event-stream resources for the FastAPI application lifespan.

    Args:
        app: FastAPI application using the lifespan hook.

    Yields:
        None while the application is running.
    """
    event_monitor.start()
    event_stream.start()
    yield
    event_stream.stop()
    event_monitor.stop()
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()

app = FastAPI(
    title="D&D Engine Event Server",
    description="WebSocket server for real-time game events + REST API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Log request duration for every endpoint.

    Args:
        request: Incoming HTTP request.
        call_next: FastAPI middleware continuation callable.

    Returns:
        Response returned by the next middleware or route handler.
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.debug(
        "TIMING: %s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Log structured HTTP errors and return their detail payload.

    Args:
        request: Incoming HTTP request.
        exc: HTTP exception raised by route logic.

    Returns:
        JSON response containing the exception detail.
    """
    logger.error(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions and return a generic JSON response.

    Args:
        request: Incoming HTTP request.
        exc: Unhandled exception raised by route logic.

    Returns:
        JSON response with a 500 status code and exception detail string.
    """
    logger.error(f"Unhandled error on {request.method} {request.url.path}:\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
async def root():
    """Return a compact server health payload.

    Returns:
        Server status, listener count, event count, encounter presence, and
        pause state.
    """
    return {
        "status": "running",
        "listeners": event_monitor.listener_count,
        "event_count": len(EventQueue._all_events),
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused
    }

_BASE_BLOCK_INTERNAL_FIELDS = set(BaseBlock.model_fields.keys()) | {
    'use_register', 'blocks_dict_name_uuid', 'blocks_dict_uuid_name',
    'values_dict_name_uuid', 'values_dict_uuid_name',
}
_FLOOR_OBJECT_TOP_LEVEL_FIELDS = {'uuid', 'name', 'map_char'}


def _get_floor_object_state(obj: BaseBlock) -> dict:
    """Extract object-specific state fields for API serialization.

    Args:
        obj: Floor object block being serialized.

    Returns:
        JSON-compatible state fields not already represented by APIFloorObject
        top-level fields.
    """
    all_fields = set(type(obj).model_fields.keys())
    state_fields = all_fields - _BASE_BLOCK_INTERNAL_FIELDS - _FLOOR_OBJECT_TOP_LEVEL_FIELDS
    return obj.model_dump(mode='json', include=state_fields)


@app.get("/state", response_model=APIGameState)
async def get_state():
    """Return the public game-state DTO.

    Returns:
        Grid, entity summaries, optional encounter state, and floor-object
        summaries.
    """
    grid = get_map()

    encounter_data = None
    if sim.encounter:
        encounter_data = APIEncounter.create(sim.encounter)

    floor_objects = []
    for obj_uuid, obj_pos in grid._object_positions.items():
        obj = BaseBlock.get(obj_uuid)
        if obj:
            map_char = getattr(obj, 'map_char', '\u03c6')
            floor_objects.append(APIFloorObject(
                uuid=str(obj_uuid),
                name=obj.name or "Object",
                position=list(obj_pos),
                map_char=map_char,
                state=_get_floor_object_state(obj),
            ))

    return APIGameState(
        grid=APIGrid.create(grid),
        entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
        encounter=encounter_data,
        floor_objects=floor_objects,
    )


@app.get("/mapeditor/catalog", response_model=MapEditorCatalog)
async def get_mapeditor_catalog():
    """Return map-editor presets, terrain, objects, and loot catalog data.

    Returns:
        Catalog DTO for map-editor clients.
    """
    return build_catalog()


@app.get("/catalog/spells", response_model=SpellCatalogResponse)
async def get_spell_catalog():
    """Return spell templates and design-time VFX/rules metadata.

    Returns:
        Spell catalog DTO for clients.
    """
    return build_spell_catalog()


@app.post("/mapeditor/maps", response_model=MapEditorMapSnapshot)
async def create_mapeditor_map(request: MapEditorCreateMapRequest):
    """Create or reset an entity-free map-editor map.

    Args:
        request: Map creation request describing source, preset, and size.

    Returns:
        Snapshot for the newly active editor map.

    Raises:
        HTTPException: If the requested map source, preset, or size is invalid.
    """
    try:
        sim.encounter = None
        sim.combat_task = None
        return create_editor_map(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_map_create_failed",
            message=str(exc),
            requested_source=request.source,
            requested_preset_id=request.preset_id,
            include_entities=request.include_entities,
            requested_size={"width": request.width, "height": request.height},
        )


@app.get("/mapeditor/map", response_model=MapEditorMapSnapshot)
async def get_mapeditor_map():
    """Return the current entity-free map-editor snapshot.

    Returns:
        Current editor map snapshot.
    """
    return get_editor_snapshot()


@app.get("/mapeditor/saves", response_model=MapEditorSavedMapList)
async def list_mapeditor_saves():
    """Return file-backed map-editor map saves.

    Returns:
        Saved map metadata list.
    """
    return list_saved_editor_maps()


@app.post("/mapeditor/saves", response_model=MapEditorSavedMapMetadata)
async def save_mapeditor_map(request: MapEditorSaveMapRequest):
    """Save the current entity-free editor map state.

    Args:
        request: Save request containing map ID, display name, and overwrite
            policy.

    Returns:
        Metadata for the saved map.

    Raises:
        HTTPException: If the save ID is invalid or overwrite is not allowed.
    """
    try:
        return save_current_editor_map(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_save_failed",
            message=str(exc),
            requested_map_id=request.id,
            requested_name=request.name,
            overwrite=request.overwrite,
        )


@app.get("/mapeditor/saves/{map_id}", response_model=MapEditorSavedMapDocument)
async def get_mapeditor_save(map_id: str):
    """Read a saved editor map document without loading it.

    Args:
        map_id: Saved map identifier.

    Returns:
        Saved map document.

    Raises:
        HTTPException: If the saved map cannot be found.
    """
    try:
        return get_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_not_found",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.post("/mapeditor/saves/{map_id}/load", response_model=MapEditorMapSnapshot)
async def load_mapeditor_save(map_id: str):
    """Load a saved editor map into the entity-free editor world.

    Args:
        map_id: Saved map identifier.

    Returns:
        Snapshot for the loaded editor map.

    Raises:
        HTTPException: If the saved map cannot be loaded.
    """
    try:
        return load_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_load_failed",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.delete("/mapeditor/saves/{map_id}", status_code=204)
async def delete_mapeditor_save(map_id: str):
    """Delete a saved editor map document.

    Args:
        map_id: Saved map identifier.

    Returns:
        None.

    Raises:
        HTTPException: If the saved map cannot be deleted.
    """
    try:
        delete_saved_editor_map(map_id)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=404,
            code="mapeditor_save_delete_failed",
            message=str(exc),
            requested_map_id=map_id,
        )


@app.post("/mapeditor/map/tiles", response_model=MapEditorMapSnapshot)
async def patch_mapeditor_tiles(request: MapEditorTilePatchRequest):
    """Patch editor tiles through GridMap and terrain factories.

    Args:
        request: Tile patch request with terrain and directional-border edits.

    Returns:
        Updated editor map snapshot.

    Raises:
        HTTPException: If any requested tile patch is invalid.
    """
    try:
        return apply_tile_patches(request.tiles)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_tile_patch_failed",
            message=str(exc),
            requested_tiles=[tile.model_dump(mode="json") for tile in request.tiles],
        )


@app.post("/mapeditor/map/objects", response_model=APIFloorObject)
async def place_mapeditor_object(request: MapEditorObjectPlaceRequest):
    """Place a catalog object or loot item on the editor map.

    Args:
        request: Object placement request with catalog ID, position, and
            options.

    Returns:
        Serialized floor object that was placed.

    Raises:
        HTTPException: If the catalog ID, position, or options are invalid.
    """
    try:
        return place_catalog_object(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_object_place_failed",
            message=str(exc),
            requested_catalog_id=request.catalog_id,
            requested_position=list(request.position),
            requested_options=request.options,
        )


@app.post("/mapeditor/map/objects/delete", response_model=MapEditorMapSnapshot)
async def delete_mapeditor_object(request: MapEditorObjectDeleteRequest):
    """Delete editor objects by UUID or tile position.

    Args:
        request: Object deletion request with object UUID or tile position.

    Returns:
        Updated editor map snapshot.

    Raises:
        HTTPException: If the requested object deletion is invalid.
    """
    try:
        return delete_catalog_object(request)
    except ValueError as exc:
        raise _mapeditor_http_exception(
            status_code=400,
            code="mapeditor_object_delete_failed",
            message=str(exc),
            requested_object_uuid=request.object_uuid,
            requested_position=list(request.position) if request.position is not None else None,
        )


@app.get("/mapeditor/map/walkability", response_model=MapEditorWalkabilityResponse)
async def get_mapeditor_walkability():
    """Return objective walkability without entities.

    Returns:
        Walkability layer DTO.
    """
    return get_walkability()


@app.get("/mapeditor/map/visibility", response_model=MapEditorVisibilityResponse)
async def get_mapeditor_visibility():
    """Return objective line-of-sight blockers without observer visibility.

    Returns:
        Visibility-blocker layer DTO.
    """
    return get_visibility_blockers()


@app.get("/mapeditor/map/light", response_model=MapEditorLightResponse)
async def get_mapeditor_light():
    """Return objective resolved tile light levels.

    Returns:
        Objective light layer DTO.
    """
    return get_objective_light()


@app.get("/entities")
async def get_entities():
    """Return lightweight summaries for all registered entities.

    Returns:
        Mapping with serialized entity summaries.
    """
    return {
        "entities": [APIEntitySummary.create(e).model_dump(mode='json') for e in Entity.get_all_entities()]
    }


@app.get("/visibility")
async def get_visibility():
    """Return visibility data for all registered entities.

    Returns:
        Mapping from entity UUID to visible cells, seen cells, visible objects,
        visible entities, and active sense modes.
    """
    result = {}
    for entity in Entity.get_all_entities():
        visible_positions = [
            list(pos) for pos, is_visible in entity.senses.visible.items()
            if is_visible
        ]
        result[str(entity.uuid)] = {
            "name": entity.name,
            "position": list(entity.position),
            "visible_cells": visible_positions,
            "visible_entities": [str(uuid) for uuid in entity.senses.entities.keys()],
            "visible_objects": [str(uuid) for uuid in entity.senses.objects.keys()],
            "seen_cells": [list(pos) for pos in entity.senses.seen],
            "sense_modes": [
                {"sense_type": sm.sense_type.value, "range_feet": sm.range_feet}
                for sm in entity.senses.get_sense_modes()
            ],
        }
    return result


@app.get("/entity/{entity_uuid}", response_model=APIEntityFull)
async def get_entity(entity_uuid: str):
    """Return full details for one entity.

    Args:
        entity_uuid: Entity UUID string from the route path.

    Returns:
        Full entity DTO.

    Raises:
        HTTPException: If the entity UUID is malformed or unknown.
    """
    entity = _resolve_entity_or_raise(entity_uuid)
    return APIEntityFull.create(entity)


@app.get("/grid", response_model=APIGrid)
async def get_grid():
    """Return public grid/map data.

    Returns:
        Grid DTO for the active map.
    """
    return APIGrid.create(get_map())


@app.get("/tile/{x}/{y}")
async def get_tile_info(x: int, y: int):
    """Return detailed information for one tile.

    Args:
        x: Tile x-coordinate.
        y: Tile y-coordinate.

    Returns:
        Tile state, co-located entities and objects, handlers, and light data.

    Raises:
        HTTPException: If the requested tile does not exist.
    """
    grid = get_map()
    tile = grid.get_tile(x, y)

    if not tile:
        raise _api_http_exception(
            status_code=404,
            code="tile_not_found",
            message=f"No tile at ({x}, {y})",
            requested_position=[x, y],
            **_grid_state_context(),
        )

    entity_uuids = grid.get_entities_at((x, y))
    entities_at = []
    for uuid in entity_uuids:
        entity = Entity.get(uuid)
        if entity:
            entities_at.append({
                "uuid": str(entity.uuid),
                "name": entity.name,
                "hp": entity.get_hp(),
                "is_dead": not entity.has_hp
            })

    object_uuids = grid.get_objects_at((x, y))
    objects_at = []
    for obj_uuid in object_uuids:
        obj = BaseBlock.get(obj_uuid)
        if obj:
            objects_at.append({
                "uuid": str(obj.uuid),
                "name": obj.name,
                "is_pickable": getattr(obj, 'is_pickable', False),
                "is_usable": getattr(obj, 'is_usable', False),
                "map_char": getattr(obj, 'map_char', '\u03c6'),
            })

    handler_names = [h.name for h in tile.event_handlers.values()]

    light_level = tile.resolved_light_level
    light_level_names = {0: "Magical Darkness", 1: "Darkness", 2: "Dim Light", 3: "Bright Light", 4: "Very Bright"}

    return {
        "position": (x, y),
        "name": tile.name,
        "walkable": tile.walkable,
        "visible": tile.visible,
        "walking_cost": int(tile.walking_cost.normalized_score),
        "conditions": list(tile.active_conditions.keys()),
        "handlers": handler_names,
        "entities": entities_at,
        "objects": objects_at,
        "height": tile.height,
        "light_level": light_level.value,
        "light_level_name": light_level_names.get(light_level.value, "Unknown"),
        "default_light": tile.default_light.value,
        "illumination_count": len(tile._illuminations),
    }


@app.get("/encounter")
async def get_encounter():
    """Return the current encounter wrapper payload.

    Returns:
        Active flag plus the serialized encounter DTO when one exists.
    """
    if not sim.encounter:
        return {"active": False, "encounter": None}
    return {
        "active": True,
        "encounter": APIEncounter.create(sim.encounter).model_dump(mode='json')
    }


@app.get("/combat-log", response_model=CombatLogHistoryResponse)
async def get_combat_log(since: int = 0):
    """Return combat-log entries from the current encounter.

    Args:
        since: Only return entries with index greater than or equal to this
            cursor.

    Returns:
        Combat-log history response with entries, delta count, and total count.
    """
    if not sim.encounter:
        return CombatLogHistoryResponse(entries=[], count=0, total=0)

    entries = sim.encounter.get_combat_log(since)
    return CombatLogHistoryResponse(
        entries=entries,
        count=len(entries),
        total=len(sim.encounter.combat_log),
    )


@app.post("/simulation/start")
async def start_simulation():
    """Reset the demo encounter and start the continuous combat loop.

    Returns:
        Status payload with the new encounter UUID.
    """
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_combat()
    sim.paused = False
    sim.combat_task = asyncio.create_task(run_combat_loop())

    return {
        "status": "started",
        "encounter_uuid": str(sim.encounter.uuid)
    }


@app.post("/simulation/reset")
async def reset_simulation():
    """Stop current combat and reset to a paused demo encounter.

    Returns:
        Status payload with the reset encounter UUID.
    """
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_combat()
    sim.paused = True

    return {
        "status": "reset",
        "encounter_uuid": str(sim.encounter.uuid)
    }


@app.post("/simulation/pause")
async def pause_simulation():
    """Pause the combat loop.

    Returns:
        Status payload confirming the paused state.
    """
    sim.paused = True
    return {"status": "paused"}


@app.post("/simulation/resume")
async def resume_simulation():
    """Resume the combat loop for an existing simulation.

    Returns:
        Status payload confirming the resumed state.

    Raises:
        HTTPException: If no simulation exists.
    """
    if sim.encounter is None:
        raise _simulation_http_exception(
            code="simulation_not_started",
            message="No simulation to resume. Call /simulation/reset first.",
        )

    sim.paused = False

    if sim.combat_task is None or sim.combat_task.done():
        sim.combat_task = asyncio.create_task(run_combat_loop())

    return {"status": "resumed"}


@app.post("/simulation/step")
async def step_simulation():
    """Execute a single encounter turn.

    Returns:
        Status payload describing the stepped turn or terminal encounter state.

    Raises:
        HTTPException: If no simulation exists.
    """
    if sim.encounter is None:
        raise _simulation_http_exception(
            code="simulation_not_started",
            message="No simulation. Call /simulation/reset first.",
        )

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.start_encounter()

    if sim.encounter.state != EncounterState.ACTIVE:
        return {
            "status": "encounter_ended",
            "state": sim.encounter.state.value
        }

    sim.encounter.run_turn()

    return {
        "status": "stepped",
        "round": sim.encounter.round_number,
        "turn_index": sim.encounter.current_turn_index
    }


@app.get("/simulation/status", response_model=APISimulationStatus)
async def get_simulation_status():
    """Return current simulation status.

    Returns:
        Simulation status DTO.
    """
    return APISimulationStatus(
        has_encounter=sim.encounter is not None,
        paused=sim.paused,
        encounter_state=sim.encounter.state.value if sim.encounter else None,
        round_number=sim.encounter.round_number if sim.encounter else None,
        turn_delay=sim.turn_delay
    )


@app.post("/simulation/set-delay")
async def set_turn_delay(delay: float):
    """Set the delay between automated turns.

    Args:
        delay: Delay in seconds.

    Returns:
        Status payload with the effective turn delay.

    Raises:
        HTTPException: If the delay is outside supported bounds.
    """
    if delay < 0.1:
        raise _simulation_http_exception(
            code="delay_too_low",
            message="Delay must be at least 0.1 seconds",
            requested_delay=delay,
        )
    if delay > 10:
        raise _simulation_http_exception(
            code="delay_too_high",
            message="Delay cannot exceed 10 seconds",
            requested_delay=delay,
        )

    sim.turn_delay = delay
    return {"status": "delay_set", "turn_delay": sim.turn_delay}


@app.post("/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new player session.

    Args:
        request: Session creation request with player type and optional display
            name.

    Returns:
        Created session identifier, player type, and display name.

    Raises:
        HTTPException: If the requested player type is invalid.
    """
    try:
        ptype = PlayerType(request.player_type.lower())
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_player_type",
            message=f"Invalid player_type: {request.player_type}. Must be 'human' or 'codex'",
            player_type=request.player_type,
        )

    mgr = sim.get_session_manager()
    session = mgr.create_session(ptype, request.name)

    return CreateSessionResponse(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name
    )


def build_session_status(sid: UUID, ping: bool = False) -> SessionPingResponse:
    """Build the shared session status payload.

    Args:
        sid: Session UUID to report.
        ping: Whether to update the session activity timestamp first.

    Returns:
        Session ping/status response with active-turn and controlled-entity
        context.

    Raises:
        HTTPException: If the session does not exist.
    """
    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=str(sid),
        )

    if ping:
        session.ping()

    game = sim.game
    is_my_turn = False
    active_entity_uuid = None
    active_entity_name = None

    if game:
        active_entity_uuid = game.active_entity_uuid
        if active_entity_uuid:
            entity = Entity.get(active_entity_uuid)
            active_entity_name = entity.name if entity else None
            is_my_turn = game.is_player_turn(session.session_id)

    return SessionPingResponse(
        status="ok",
        session_id=str(session.session_id),
        connection_status=session.connection_status.value,
        is_my_turn=is_my_turn,
        active_entity_uuid=str(active_entity_uuid) if active_entity_uuid else None,
        active_entity_name=active_entity_name,
        controlled_entities=[str(e) for e in session.controlled_entities]
    )


@app.post("/session/{session_id}/ping", response_model=SessionPingResponse)
async def ping_session(session_id: str):
    """Ping a session and return its current status.

    Args:
        session_id: Session UUID string from the route path.

    Returns:
        Session status response after refreshing session activity.

    Raises:
        HTTPException: If the session UUID is malformed or unknown.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    return build_session_status(sid, ping=True)


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and remove its game associations.

    Args:
        session_id: Session UUID string from the route path.

    Returns:
        Deletion status payload.

    Raises:
        HTTPException: If the session UUID is malformed or unknown.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )

    mgr.remove_session(sid)

    return {"status": "deleted", "session_id": session_id}


@app.post("/game/join", response_model=JoinGameResponse)
async def join_game(request: JoinGameRequest):
    """Join the active game with a session.

    Entity assignment priority is explicit UUIDs, then faction, then the demo
    convention where human players receive Hero and Codex players receive
    non-Hero entities.

    Args:
        request: Join request with session ID and optional entity or faction
            selection.

    Returns:
        Join result with controlled entity UUIDs.

    Raises:
        HTTPException: If the session UUID is malformed, the session is missing,
            or no active game exists.
    """
    try:
        sid = UUID(request.session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=request.session_id,
            requested_entity_uuids=request.entity_uuids,
            requested_faction=request.faction,
        )

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=request.session_id,
            requested_entity_uuids=request.entity_uuids,
            requested_faction=request.faction,
        )

    game = sim.game
    if not game:
        raise _session_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game to join",
            session_id=request.session_id,
            requested_entity_uuids=request.entity_uuids,
            requested_faction=request.faction,
        )

    if session.session_id not in game.players:
        game.add_player(session)

    assigned = []
    if request.entity_uuids:
        for uuid_str in request.entity_uuids:
            try:
                entity_uuid = UUID(uuid_str)
                if game.assign_entity(entity_uuid, session.session_id):
                    assigned.append(str(entity_uuid))
            except ValueError:
                continue
    elif request.faction:
        for entity in Entity.get_all_entities():
            if entity.faction == request.faction:
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
    else:
        for entity in Entity.get_all_entities():
            if session.player_type == PlayerType.HUMAN and entity.name == "Hero":
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
            elif session.player_type == PlayerType.CODEX and entity.name != "Hero":
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))

    return JoinGameResponse(
        success=len(assigned) > 0,
        game_id=str(game.game_id),
        session_id=str(session.session_id),
        controlled_entities=assigned,
        message=f"Joined game, controlling {len(assigned)} entities"
    )


@app.get("/game/status")
async def get_game_status():
    """Return current game status including all joined sessions.

    Returns:
        Game status payload with active entity, encounter activity, and session
        summaries.
    """
    game = sim.game

    if not game:
        return {
            "active": False,
            "game": None,
            "sessions": []
        }

    sessions_info = []
    for session in game.players.values():
        sessions_info.append({
            "session_id": str(session.session_id),
            "player_type": session.player_type.value,
            "name": session.name,
            "connection_status": session.connection_status.value,
            "controlled_entities": [str(e) for e in session.controlled_entities],
            "is_their_turn": game.is_player_turn(session.session_id)
        })

    return {
        "active": True,
        "game_id": str(game.game_id),
        "encounter_active": game.encounter is not None and game.encounter.state.value == "active",
        "active_entity_uuid": str(game.active_entity_uuid) if game.active_entity_uuid else None,
        "sessions": sessions_info
    }


@app.get("/session/{session_id}/entities")
async def get_session_entities(session_id: str):
    """Return entity details controlled by a session.

    Args:
        session_id: Session UUID string from the route path.

    Returns:
        Session ID plus controlled entity summaries.

    Raises:
        HTTPException: If the session UUID is malformed or unknown.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=session_id,
        )

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise _session_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )

    entities_info = []
    for entity_uuid in session.controlled_entities:
        entity = Entity.get(entity_uuid)
        if entity:
            entities_info.append({
                "uuid": str(entity.uuid),
                "name": entity.name,
                "faction": entity.faction,
                "hp": entity.get_hp(),
                "position": entity.position
            })

    return {
        "session_id": str(session.session_id),
        "controlled_entities": entities_info
    }


@app.get("/events", response_model=EventHistoryResponse)
async def get_events(
    since: int = 0,
    limit: int = 50,
    event_type: Optional[str] = None,
    phase: Optional[str] = None
):
    """
    Get events with cursor-based pagination.

    Args:
        since: Return events starting from this index (0-based). Use the
               total from a previous response or WebSocket handshake event_count.
               Default 0 returns the last `limit` events (backwards-compatible).
        limit: Max events to return (0 = unlimited, default 50).
        event_type: Filter by event type (e.g. "attack", "movement").
        phase: Filter by event phase (e.g. "completion").
    """
    all_events = EventQueue._all_events

    if since > 0:
        events = all_events[since:]
    else:
        events = all_events[-limit:] if limit > 0 else all_events

    if since > 0 and limit > 0:
        events = events[:limit]

    if event_type:
        try:
            et = EventType(event_type)
            events = [e for e in events if e.event_type == et]
        except ValueError:
            raise _event_filter_http_exception(
                code="unknown_event_type",
                message=f"Unknown event_type: {event_type}",
                event_type=event_type,
                phase=phase,
            )

    if phase:
        try:
            ep = EventPhase(phase)
            events = [e for e in events if e.phase == ep]
        except ValueError:
            raise _event_filter_http_exception(
                code="unknown_event_phase",
                message=f"Unknown phase: {phase}",
                event_type=event_type,
                phase=phase,
            )

    return EventHistoryResponse(
        events=events,
        count=len(events),
        total=len(all_events),
    )


@app.get("/events/subscribe")
async def subscribe_events(
    request: Request,
    session_id: Optional[str] = None,
    since_event: int = 0,
    since_log: int = 0,
):
    """Resumable SSE stream for game events, combat log, and session status."""
    event_stream.ensure_attached()

    sid: Optional[UUID] = None
    if session_id:
        try:
            sid = UUID(session_id)
        except ValueError:
            raise _session_http_exception(
                status_code=400,
                code="invalid_session_uuid",
                message="Invalid session ID format",
                session_id=session_id,
            )

    subscription = event_stream.subscribe()
    heartbeat_seconds = 10.0

    def session_status_payload() -> Optional[dict]:
        if sid is None:
            return None
        return build_session_status(sid, ping=True).model_dump(mode="json")

    def should_emit_session_after_game_event(payload) -> bool:
        event_type = payload.event.event_type
        event_type_value = event_type.value if hasattr(event_type, "value") else str(event_type)
        return event_type_value in {
            "encounter_start",
            "encounter_end",
            "round_start",
            "round_end",
            "turn_start",
            "turn_end",
        }

    async def event_generator():
        try:
            sync_payload = StreamSyncPayload(
                event_cursor=event_stream.current_event_cursor(),
                combat_log_cursor=event_stream.current_combat_log_cursor(sim.encounter),
                session=session_status_payload(),
            )
            yield format_sse(
                "sync",
                sync_payload,
                event_stream.current_stream_id(sim.encounter),
            )

            for payload in event_stream.iter_game_events_since(since_event, sim.encounter):
                yield format_sse(
                    "game_event",
                    payload,
                    make_stream_id(payload.event_cursor, payload.combat_log_cursor),
                )
                if sid is not None and should_emit_session_after_game_event(payload):
                    yield format_sse(
                        "session",
                        session_status_payload() or {},
                        event_stream.current_stream_id(sim.encounter),
                    )

            for payload in event_stream.iter_combat_logs_since(sim.encounter, since_log):
                yield format_sse(
                    "combat_log",
                    payload,
                    make_stream_id(payload.event_cursor, payload.combat_log_cursor),
                )

            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(
                        subscription.get(),
                        timeout=heartbeat_seconds,
                    )
                except asyncio.TimeoutError:
                    heartbeat = HeartbeatPayload(
                        server_time=time.time(),
                        event_cursor=event_stream.current_event_cursor(),
                        combat_log_cursor=event_stream.current_combat_log_cursor(sim.encounter),
                        session=session_status_payload(),
                    )
                    yield format_sse(
                        "heartbeat",
                        heartbeat,
                        event_stream.current_stream_id(sim.encounter),
                    )
                    continue

                yield format_sse(
                    envelope["event"],
                    envelope["data"],
                    envelope.get("id"),
                )
                if envelope["event"] == "evicted":
                    break
                if (
                    sid is not None
                    and envelope["event"] == "game_event"
                    and should_emit_session_after_game_event(envelope["data"])
                ):
                    yield format_sse(
                        "session",
                        session_status_payload() or {},
                        event_stream.current_stream_id(sim.encounter),
                    )
        finally:
            event_stream.unsubscribe(subscription)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/event-types")
async def get_event_types():
    """List all available event types."""
    return {
        "event_types": [et.value for et in EventType],
        "phases": [ep.value for ep in EventPhase]
    }


@app.get("/encounter/current-turn", response_model=APICurrentTurn)
async def get_current_turn():
    """Get current turn information - who's turn is it, is it human?"""
    if sim.encounter is None:
        return APICurrentTurn(
            encounter_active=False,
            round_number=0,
            turn_index=0,
            current_entity_uuid=None,
            current_entity_name=None,
            is_human_turn=False,
            waiting_for_input=False,
            controller_type=None
        )

    entity = sim.encounter.get_current_entity()
    controller = sim.encounter.get_current_controller()

    actions = bonus = reactions = movement = 0
    if entity:
        ae = entity.action_economy
        actions = ae.actions.normalized_score
        bonus = ae.bonus_actions.normalized_score
        reactions = ae.reactions.normalized_score
        movement = ae.movement.normalized_score

    needs_input = controller.controller_type in ("human", "codex") if controller else False

    return APICurrentTurn(
        encounter_active=sim.encounter.state == EncounterState.ACTIVE,
        round_number=sim.encounter.round_number,
        turn_index=sim.encounter.current_turn_index,
        current_entity_uuid=str(entity.uuid) if entity else None,
        current_entity_name=entity.name if entity else None,
        is_human_turn=needs_input,
        waiting_for_input=sim.waiting_for_human,
        controller_type=controller.controller_type if controller else None,
        actions_remaining=actions,
        bonus_actions_remaining=bonus,
        reactions_remaining=reactions,
        movement_remaining=movement
    )


def _serialize_target(t: AvailableTarget) -> dict:
    """Serialize an AvailableTarget to JSON-compatible dict."""
    result: dict = {"index": t.index}
    if t.target_uuid:
        result["target_uuid"] = str(t.target_uuid)
    if t.position:
        result["position"] = list(t.position)
    if t.target_name:
        result["target_name"] = t.target_name
    if t.distance is not None:
        result["distance"] = t.distance
    if t.path_cost is not None:
        result["path_cost"] = t.path_cost

    if t.affected_entity_uuids:
        result["affected_entity_uuids"] = [str(uuid) for uuid in t.affected_entity_uuids]
    if t.affected_entity_names:
        result["affected_entity_names"] = t.affected_entity_names
    if t.affected_count is not None:
        result["affected_count"] = t.affected_count
    if t.affected_positions:
        result["affected_positions"] = [list(p) for p in t.affected_positions]

    result["is_path_hazardous"] = t.is_path_hazardous
    if t.path:
        result["path"] = [list(p) for p in t.path]
    if t.safe_path:
        result["safe_path"] = [list(p) for p in t.safe_path]
    if t.safe_path_cost is not None:
        result["safe_path_cost"] = t.safe_path_cost
    if t.extra_target_uuids:
        result["extra_target_uuids"] = [str(uuid) for uuid in t.extra_target_uuids]
    return result


def _serialize_action(a) -> dict:
    """Serialize an AvailableActionInfo to JSON-compatible dict."""
    result = {
        "template_name": a.template_name,
        "target_type": a.target_type.value,
        "valid_targets": [_serialize_target(t) for t in a.valid_targets],
        "can_afford": a.can_afford,
        "display_name": a.display_name,
        "description": a.description,
        "cost_type": a.cost_type,
        "cost_amount": a.cost_amount,
        "weapon_slot": a.weapon_slot,
        "weapon_name": a.weapon_name,
        "action_category": a.action_category.value
    }
    if a.base_template_name is not None:
        result["base_template_name"] = a.base_template_name
    if a.spell_level is not None:
        result["spell_level"] = a.spell_level
    if a.cast_at_level is not None:
        result["cast_at_level"] = a.cast_at_level
    if a.is_spell_variant:
        result["is_spell_variant"] = True
    if a.num_projectiles is not None:
        result["num_projectiles"] = a.num_projectiles
    if a.allow_same_target is not None:
        result["allow_same_target"] = a.allow_same_target
    if a.is_item_use:
        result["is_item_use"] = True
        result["source_item_uuid"] = str(a.source_item_uuid) if a.source_item_uuid else None
        result["item_stack_count"] = a.item_stack_count
    return result


def _serialize_available_actions(entity: Entity, actions: AvailableActionsResult) -> dict:
    """Serialize full available actions result for an entity."""
    ae = entity.action_economy
    result: dict = {
        "entity_uuid": str(actions.entity_uuid),
        "entity_actions": [_serialize_action(a) for a in actions.entity_actions],
        "position_actions": [_serialize_action(a) for a in actions.position_actions],
        "self_actions": [_serialize_action(a) for a in actions.self_actions],
        "object_actions": [_serialize_action(a) for a in actions.object_actions],
        "remaining_movement": actions.remaining_movement,
        "actions_remaining": ae.actions.normalized_score,
        "bonus_actions_remaining": ae.bonus_actions.normalized_score,
        "reactions_remaining": ae.reactions.normalized_score,
        "extra_attacks_remaining": ae.get_resource_current("extra_attacks"),
    }

    if actions.handler_details:
        result["handler_details"] = actions.handler_details

    if entity.is_spellcaster:
        spell_slots = {}
        for level in range(1, 10):
            slot_attr = getattr(ae, f"spell_slot_{level}", None)
            if slot_attr is not None:
                base_mod = slot_attr.get_base_modifier()
                max_val = base_mod.value if base_mod else 0
                if max_val > 0:
                    spell_slots[str(level)] = {
                        "current": slot_attr.normalized_score,
                        "max": max_val,
                    }
        if spell_slots:
            result["spell_slots"] = spell_slots

    if ae.resources:
        custom_resources = {}
        for res_name, resource in ae.resources.items():
            if res_name == "extra_attacks":
                continue
            custom_resources[res_name] = {
                "current": resource.current,
                "max": resource.maximum,
            }
        if custom_resources:
            result["resources"] = custom_resources

    return result


def _action_error_detail(
    entity: Entity,
    available: AvailableActionsResult,
    code: str,
    message: str,
    **context: Any,
) -> dict:
    """Build structured action-error detail for API clients."""
    detail = {
        "code": code,
        "message": message,
        "entity_uuid": str(entity.uuid),
        "entity_name": entity.name,
        "action_economy": {
            "actions": entity.action_economy.actions.normalized_score,
            "bonus_actions": entity.action_economy.bonus_actions.normalized_score,
            "reactions": entity.action_economy.reactions.normalized_score,
            "movement": entity.action_economy.movement.normalized_score,
            "extra_attacks": entity.action_economy.get_resource_current("extra_attacks"),
        },
        "valid_action_names": [
            action.template_name for action in available.all_actions
        ],
        "available_actions": _serialize_available_actions(entity, available),
    }
    detail.update(context)
    return detail


def _action_http_exception(
    entity: Entity,
    entity_uuid: str,
    code: str,
    message: str,
    status_code: int = 400,
    **context: Any,
) -> HTTPException:
    """Create an action error with available correction context."""
    available = _available_actions_cache.get(entity_uuid)
    if available is None:
        available = get_available_actions(entity)
    return HTTPException(
        status_code=status_code,
        detail=_action_error_detail(
            entity=entity,
            available=available,
            code=code,
            message=message,
            **context,
        ),
    )


@app.get("/entity/{entity_uuid}/available-actions")
async def get_entity_available_actions(entity_uuid: str):
    """Get all available actions for an entity."""
    entity = _resolve_entity_or_raise(entity_uuid)

    actions = get_available_actions(entity)

    _available_actions_cache[entity_uuid] = actions

    return _serialize_available_actions(entity, actions)


@app.get("/entity/{entity_uuid}/handlers")
async def get_entity_handlers(entity_uuid: str):
    """Get all event handlers for an entity with their enabled state."""
    entity = _resolve_entity_or_raise(entity_uuid)
    handlers = _serialize_entity_handlers(entity)
    return {"entity_uuid": entity_uuid, "handlers": handlers}


@app.post("/entity/{entity_uuid}/handlers/{handler_name}/toggle")
async def toggle_entity_handler(entity_uuid: str, handler_name: str, request: ToggleHandlerRequest):
    """Toggle a handler's enabled state by name.

    Validates that the session owns the entity and it's their turn.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    if entity_uuid != request.entity_uuid:
        raise _handler_http_exception(
            entity=entity,
            status_code=400,
            code="entity_uuid_mismatch",
            message="Entity UUID mismatch",
            handler_name=handler_name,
        )

    found = entity.set_handler_enabled(handler_name, request.enabled)
    if not found:
        raise _handler_http_exception(
            entity=entity,
            status_code=404,
            code="handler_not_found",
            message=f"Handler '{handler_name}' not found",
            handler_name=handler_name,
        )

    return {
        "success": True,
        "handler_name": handler_name,
        "enabled": request.enabled,
    }


@app.get("/entity/{entity_uuid}/equipment", response_model=APIEquipmentOverview)
async def get_entity_equipment(entity_uuid: str):
    """Get full equipment and inventory state for an entity."""
    entity = _resolve_entity_or_raise(entity_uuid)
    return APIEquipmentOverview.create(entity)


@app.get("/entity/{entity_uuid}/equipment/item/{item_uuid}")
async def get_entity_item_detail(entity_uuid: str, item_uuid: str):
    """Get full detail for a single item (equipped or in inventory)."""
    entity = _resolve_entity_or_raise(entity_uuid)
    try:
        item_uuid_obj = UUID(item_uuid)
    except ValueError:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="invalid_item_uuid",
            message="Invalid item UUID format",
            item_uuid=item_uuid,
        )

    for equipped_item in entity.equipment.get_all_equipped_items():
        if equipped_item.uuid == item_uuid_obj:
            return APIItemSummary.create(equipped_item).model_dump()

    if entity.inventory.has_item(item_uuid_obj):
        item = entity.inventory.items[item_uuid_obj]
        return APIItemSummary.create(item).model_dump()

    raise _equipment_http_exception(
        entity=entity,
        status_code=404,
        code="item_not_found",
        message="Item not found on entity",
        item_uuid=item_uuid,
    )


@app.get("/entity/{entity_uuid}/equippable-items")
async def get_equippable_items(entity_uuid: str):
    """Get inventory items that can be equipped, grouped by valid slots."""
    entity = _resolve_entity_or_raise(entity_uuid)
    return {"entity_uuid": entity_uuid, "equippable": entity.get_equippable_items()}


@app.post("/entity/{entity_uuid}/equip", response_model=EquipmentMutationResult)
async def equip_item(entity_uuid: str, request: EquipRequest):
    """Equip an item from inventory to a slot.

    Removes item from inventory, equips it. If slot is occupied, the old item
    goes to inventory (swap). Validates session ownership and turn.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    if entity_uuid != request.entity_uuid:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="entity_uuid_mismatch",
            message="Entity UUID mismatch",
        )

    try:
        item_uuid_obj = UUID(request.item_uuid)
    except ValueError:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="invalid_item_uuid",
            message="Invalid item UUID format",
            item_uuid=request.item_uuid,
        )

    if not entity.inventory.has_item(item_uuid_obj):
        raise _equipment_http_exception(
            entity=entity,
            status_code=404,
            code="inventory_item_not_found",
            message="Item not found in inventory",
            item_uuid=request.item_uuid,
        )

    item = entity.inventory.items[item_uuid_obj]

    from dnd.blocks.base_item import EquippableItem
    if not isinstance(item, EquippableItem):
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="item_not_equippable",
            message="Item is not equippable",
            item_uuid=request.item_uuid,
        )

    from dnd.blocks.equipment import Armor, Weapon, Shield, Ring, WeaponProperty

    parsed_slot = None
    if request.slot is not None:
        slot_str_map = _equipment_slot_map()
        parsed_slot = slot_str_map.get(request.slot)
        if parsed_slot is None:
            raise _equipment_http_exception(
                entity=entity,
                status_code=400,
                code="invalid_slot",
                message=f"Invalid slot: {request.slot}",
                item_uuid=request.item_uuid,
                slot=request.slot,
            )

    effective_slot = parsed_slot
    if effective_slot is None:
        if isinstance(item, Weapon):
            is_ranged = WeaponProperty.RANGED in item.properties
            effective_slot = WeaponSlot.RANGED_MAIN if is_ranged else WeaponSlot.MELEE_MAIN
        elif isinstance(item, Shield):
            effective_slot = WeaponSlot.MELEE_OFF
        elif isinstance(item, Ring):
            raise _equipment_http_exception(
                entity=entity,
                status_code=400,
                code="missing_slot",
                message="Rings require an explicit slot",
                item_uuid=request.item_uuid,
            )
        elif isinstance(item, Armor):
            effective_slot = item.body_part

    try:
        if effective_slot is None or not entity.equip_item(item_uuid_obj, effective_slot):
            raise ValueError("Item could not be equipped")
    except ValueError as e:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="equipment_operation_failed",
            message=str(e),
            item_uuid=request.item_uuid,
            slot=request.slot,
        )

    return EquipmentMutationResult(
        success=True,
        message=f"Equipped {item.name}",
        equipment=APIEquipmentOverview.create(entity),
        **action_cursor_fields(),
    )


@app.post("/entity/{entity_uuid}/unequip", response_model=EquipmentMutationResult)
async def unequip_item(entity_uuid: str, request: UnequipRequest):
    """Unequip an item from a slot to inventory.

    Validates session ownership and turn.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    if entity_uuid != request.entity_uuid:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="entity_uuid_mismatch",
            message="Entity UUID mismatch",
            slot=request.slot,
        )

    slot_str_map = _equipment_slot_map()
    parsed_slot = slot_str_map.get(request.slot)
    if parsed_slot is None:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="invalid_slot",
            message=f"Invalid slot: {request.slot}",
            slot=request.slot,
        )

    unequipped = entity.equipment.unequip(parsed_slot)
    if unequipped is None:
        raise _equipment_http_exception(
            entity=entity,
            status_code=400,
            code="empty_or_canceled_slot",
            message="Slot is empty or unequip was canceled",
            slot=request.slot,
        )

    unequipped.owner_uuid = entity.uuid
    unequipped.stored_in_uuid = entity.inventory.uuid
    entity.inventory.add_item(unequipped)

    return EquipmentMutationResult(
        success=True,
        message=f"Unequipped {unequipped.name}",
        equipment=APIEquipmentOverview.create(entity),
        **action_cursor_fields(),
    )


@app.post("/action/end-turn", response_model=AdvanceEncounterResult)
async def end_human_turn(request: SimpleActionRequest):
    """End the session's entity turn and advance through AI turns."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    if sim.encounter is None:
        raise _api_http_exception(
            status_code=400,
            code="no_active_encounter",
            message="No active encounter",
            session_id=request.session_id,
            entity_uuid=request.entity_uuid,
            entity_name=entity.name,
            **_session_context(),
            **_simulation_context(),
        )

    _available_actions_cache.clear()

    sim.encounter.end_turn()

    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED

    result = await advance_encounter()

    return result


@app.post("/action/self", response_model=ActionResult)
async def execute_self_action(request: SelfActionRequest):
    """Execute a self-targeting action (Dash, Dodge, Disengage, StandUp).

    Uses the new functional action API.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    template = entity.get_action_template(request.action_name)
    if template is None:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="unknown_action",
            message=f"Unknown action: {request.action_name}",
        )

    if template.target_type != TargetType.SELF:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_type",
            message=f"Action {request.action_name} is not a SELF action (is {template.target_type.value})",
        )

    target = AvailableTarget(index=0)
    try:
        event = execute_action(entity, request.action_name, target)
    except ValueError as e:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_target",
            message=str(e),
        )

    action_log_entries: list = []
    if event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or f"{request.action_name} executed",
        event_type=request.action_name.lower(),
        entity_hp=entity.get_hp(),
        turn_continues=True,
        encounter_ended=False,
        combat_log_entries=action_log_entries,
        **action_cursor_fields(),
    )


@app.post("/action/entity", response_model=ActionResult)
async def execute_entity_action(request: EntityActionRequest):
    """Execute an entity-targeting action (Attack).

    Uses the new functional action API. Captures opportunity attacks.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    try:
        target_uuid = UUID(request.target_uuid)
    except ValueError:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_target_uuid",
            message="Invalid target UUID format",
            target_uuid=request.target_uuid,
            known_entities=_known_entity_summaries(),
        )

    target = Entity.get(target_uuid)
    if not target:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            status_code=404,
            code="target_not_found",
            message="Target not found",
            target_uuid=str(target_uuid),
            known_entities=_known_entity_summaries(),
        )

    template = entity.get_action_template(request.action_name)
    if template is None:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="unknown_action",
            message=f"Unknown action: {request.action_name}",
        )

    if template.target_type != TargetType.ENTITY:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_type",
            message=f"Action {request.action_name} is not an ENTITY action (is {template.target_type.value})",
        )

    action_target = AvailableTarget(index=0, target_uuid=target_uuid, target_name=target.name)
    try:
        event = execute_action(entity, request.action_name, action_target)
    except ValueError as e:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_target",
            message=str(e),
        )

    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    action_log_entries: list = []

    event_data = None
    if event and hasattr(event, 'attack_outcome') and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

        event_data = dict(event.combat_log.data)

        event_data["target_hp"] = target.get_hp()

    for death_event in deaths:
        if death_event.combat_log:
            action_log_entries.append(death_event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Action executed",
        event_type=request.action_name.lower().replace("_", " "),
        event_data=event_data,
        entity_hp=entity.get_hp(),
        target_hp=target.get_hp(),
        deaths=death_names,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries,
        **action_cursor_fields(),
    )


@app.post("/action/position", response_model=ActionResult)
async def execute_position_action(request: PositionActionRequest):
    """Execute a position-targeting action (Move).

    Uses the new functional action API. Captures opportunity attacks.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    template = entity.get_action_template(request.action_name)
    if template is None:

        if "__item_" in request.action_name:
            item_uuid_str = request.action_name.split("__item_")[1]
            item_uuid = UUID(item_uuid_str)
            action_name = request.action_name.split("__item_")[0]
            pos = (request.position[0], request.position[1])
            action_target = AvailableTarget(index=0, position=pos)

            log_start_index = len(sim.encounter.combat_log) if sim.encounter else 0

            try:
                event = execute_use_action(entity, item_uuid, action_name, action_target)
            except ValueError as e:
                raise _action_http_exception(
                    entity=entity,
                    entity_uuid=request.entity_uuid,
                    code="invalid_action_target",
                    message=str(e),
                )

            _available_actions_cache.pop(request.entity_uuid, None)

            deaths = sim.encounter.check_deaths() if sim.encounter else []
            death_names = [d.entity_name for d in deaths]
            encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

            event_data = None
            if event and event.combat_log:
                event_data = dict(event.combat_log.data)

            action_log_entries: list = []
            if sim.encounter:
                for entry in sim.encounter.combat_log[log_start_index:]:
                    action_log_entries.append(entry.to_dict())
            if not action_log_entries and event and event.combat_log:
                action_log_entries.append(event.combat_log.to_dict())

            return ActionResult(
                success=not event.canceled if event else False,
                message=(event.status_message if event else None) or "Action executed",
                event_type=action_name.lower().replace("_", " "),
                event_data=event_data,
                entity_hp=entity.get_hp(),
                deaths=death_names,
                turn_continues=not encounter_ended and entity.has_hp,
                encounter_ended=encounter_ended,
                combat_log_entries=action_log_entries,
                **action_cursor_fields(),
            )
        else:
            raise _action_http_exception(
                entity=entity,
                entity_uuid=request.entity_uuid,
                code="unknown_action",
                message=f"Unknown action: {request.action_name}",
            )

    if template.target_type not in (TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_type",
            message=f"Action {request.action_name} is not a position action (is {template.target_type.value})",
        )

    log_start_index = len(sim.encounter.combat_log) if sim.encounter else 0

    try:

        pos = (request.position[0], request.position[1])
        action_target = AvailableTarget(index=0, position=pos)
        event = execute_action(entity, request.action_name, action_target)
    except ValueError as e:
        raise _action_http_exception(
            entity=entity,
            entity_uuid=request.entity_uuid,
            code="invalid_action_target",
            message=str(e),
        )

    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    event_data = None
    if isinstance(event, (MovementEvent, JumpEvent)):
        if event.combat_log:
            event_data = dict(event.combat_log.data)
        else:

            event_data = {
                "entity_name": entity.name,
                "start_position": list(event.start_position),
                "end_position": list(event.end_position),
                "path": [list(p) for p in event.path] if event.path else []
            }
    elif template.target_type == TargetType.POSITION_AOE and event:

        if event.combat_log:
            event_data = dict(event.combat_log.data)

    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)

            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = dict(entry.data)
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    if not action_log_entries and event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or ("Moved successfully" if event and not event.canceled else "Move failed"),
        event_type="movement",
        event_data=event_data,
        entity_hp=entity.get_hp(),
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries,
        **action_cursor_fields(),
    )


@app.post("/action/execute", response_model=ActionResult)
async def execute_action_by_index(request: ExecuteByIndexRequest):
    """Execute action by template name and target index.

    Enables 'attack 0', 'move 3' style commands from the available actions list.
    Uses cached available actions from the display call to avoid recomputing.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    available = _available_actions_cache.get(request.entity_uuid)
    if available is None:
        available = get_available_actions(entity)

    action_info = next(
        (a for a in available.all_actions if a.template_name == request.template_name),
        None
    )
    if action_info is None:
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="unknown_action",
                message=f"Unknown action: {request.template_name}",
            ),
        )

    target_type = action_info.target_type

    log_start_index = len(sim.encounter.combat_log) if sim.encounter else 0

    try:
        event = execute_by_index(
            entity,
            request.template_name,
            request.target_index,
            extra_target_uuids=request.extra_target_uuids,
            available=available,
            prefer_safe=request.prefer_safe,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="invalid_action_target",
                message=str(e),
            ),
        )

    _available_actions_cache.pop(request.entity_uuid, None)

    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    updated_actions = None
    if not encounter_ended and entity.has_hp:
        new_available = get_available_actions(entity)
        _available_actions_cache[request.entity_uuid] = new_available
        updated_actions = _serialize_available_actions(entity, new_available)

    event_data = None
    target_hp = None

    if target_type == TargetType.ENTITY and event and event.combat_log:

        event_data = dict(event.combat_log.data)

        if hasattr(event, 'attack_outcome'):
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            target_hp = target.get_hp() if target else None
            event_data["target_hp"] = target_hp

    elif target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):

        if event and isinstance(event, (MovementEvent, JumpEvent)):
            if event.combat_log:
                event_data = dict(event.combat_log.data)
            else:
                event_data = {
                    "entity_name": entity.name,
                    "start_position": list(event.start_position),
                    "end_position": list(event.end_position),
                    "path": [list(p) for p in event.path] if event.path else []
                }

    elif target_type == TargetType.POSITION_AOE:

        if event and event.combat_log:
            event_data = dict(event.combat_log.data)

    elif target_type == TargetType.MULTI_ENTITY:

        if event and event.combat_log:
            event_data = dict(event.combat_log.data)

    elif target_type == TargetType.SELF:

        if event and event.combat_log:
            event_data = dict(event.combat_log.data)
        elif event:
            event_data = {
                "entity_name": entity.name,
                "action_name": request.template_name,
            }

    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)

            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = dict(entry.data)
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    if not action_log_entries and event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

    grid = get_map()
    floor_objects = []
    for obj_uuid, obj_pos in grid._object_positions.items():
        obj = BaseBlock.get(obj_uuid)
        if obj:
            map_char = getattr(obj, 'map_char', '\u03c6')
            floor_objects.append(APIFloorObject(
                uuid=str(obj_uuid),
                name=obj.name or "Object",
                position=list(obj_pos),
                map_char=map_char,
                state=_get_floor_object_state(obj),
            ))
    game_state = APIGameState(
        grid=APIGrid.create(grid, requesting_entity_uuid=entity.uuid),
        entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
        encounter=APIEncounter.create(sim.encounter) if sim.encounter else None,
        floor_objects=floor_objects,
    )

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or f"{request.template_name} executed",
        event_type=request.template_name.lower(),
        event_data=event_data,
        entity_hp=entity.get_hp(),
        target_hp=target_hp,
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries,
        available_actions=updated_actions,
        state=game_state,
        **action_cursor_fields(),
    )


@app.post("/action/position/preview")
async def preview_position_action(request: PositionActionRequest) -> AoEPreviewResult:
    """Preview AoE at a position: returns affected cells and entities without executing."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    template = entity.get_action_template(request.action_name)
    if template is None:
        return AoEPreviewResult(success=False, message=f"Unknown action: {request.action_name}")

    if template.target_type != TargetType.POSITION_AOE or template.aoe_shape is None:
        return AoEPreviewResult(success=False, message=f"{request.action_name} is not a position AoE action")

    pos = (request.position[0], request.position[1])
    grid = get_map()

    shape = template.aoe_shape.model_copy(update={'target': pos})
    shape.compute_subjective(
        entity.position, entity.senses,
        fov_cache={}, barrier_positions=grid.get_barrier_positions(),
        caster_uuid=entity.uuid,
    )

    affected_uuids = list(shape.affected_entity_uuids)

    if not template.include_self:
        affected_uuids = [uid for uid in affected_uuids if uid != entity.uuid]

    vtf = template.valid_target_filter
    if vtf != "all":
        filtered = []
        for uid in affected_uuids:
            ent = Entity.get(uid)
            if ent:
                if vtf == "enemies" and entity.is_enemy(ent):
                    filtered.append(uid)
                elif vtf == "allies" and entity.is_ally(ent):
                    filtered.append(uid)
                elif vtf == "self_or_allies":
                    if uid == entity.uuid or entity.is_ally(ent):
                        filtered.append(uid)
        affected_uuids = filtered

    if not template.include_dead:
        affected_uuids = [uid for uid in affected_uuids if (ent := Entity.get(uid)) and ent.has_hp]

    affected_names = []
    for uid in affected_uuids:
        ent = Entity.get(uid)
        if ent:
            affected_names.append(ent.name or "Unknown")

    return AoEPreviewResult(
        success=True,
        affected_positions=list(shape.affected_positions),
        affected_entity_names=affected_names,
        affected_count=len(affected_uuids),
    )


@app.post("/simulation/start-human")
async def start_human_simulation(character_class: str = "fighter"):
    """
    Start a new combat with human control (player vs AI).

    This creates a game session and auto-assigns entities:
    - Hero (heroes faction) goes to the first human session that joins
    - All monsters faction entities are controlled by AI

    Args:
        character_class: "fighter", "barbarian", or "sorcerer" - the hero's class.
    """

    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_arena_combat(pvp_mode=False, character_class=character_class)
    sim.paused = False
    sim.encounter.clear_combat_log()

    game = sim.create_game_session(sim.encounter)

    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Monsters")
    game.add_player(ai_session)

    for entity in Entity.get_all_entities():
        if entity.faction == "monsters":
            game.assign_entity(entity.uuid, ai_session.session_id)

    result = await advance_encounter()

    hero_uuid = None
    for entity in Entity.get_all_entities():
        if entity.faction == "heroes":
            hero_uuid = str(entity.uuid)
            break

    return {
        "status": "started",
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": hero_uuid,
        "message": "Create a session and join with hero_uuid to control the Hero",
        **result.model_dump(mode="json"),
    }


@app.post("/simulation/start-aoe-test")
async def start_aoe_test():
    """
    Start arena configured for AoE spell testing.

    Layout:
    - Open 15x15 grid (no walls)
    - Sorcerer (hero) at (2, 7) with Fireball, Magic Missile, etc.
    - 3 Goblins clustered at (12, 4), (12, 5), (12, 6) - within Fireball radius
    """

    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_aoe_test_arena(character_class="sorcerer")
    sim.paused = False
    sim.encounter.clear_combat_log()

    game = sim.create_game_session(sim.encounter)

    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Monsters")
    game.add_player(ai_session)

    for entity in Entity.get_all_entities():
        if entity.faction == "monsters":
            game.assign_entity(entity.uuid, ai_session.session_id)

    result = await advance_encounter()

    hero_uuid = None
    for entity in Entity.get_all_entities():
        if entity.faction == "heroes":
            hero_uuid = str(entity.uuid)
            break

    return {
        "status": "started",
        "test_type": "aoe",
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": hero_uuid,
        "message": "AoE test arena: Sorcerer vs 3 clustered Goblins",
        **result.model_dump(mode="json"),
    }


@app.post("/simulation/start-pvp")
async def start_pvp_simulation(character_class: str = "fighter"):
    """
    Start PvP combat where both entities are human-controlled.

    Player 1 (Hero) = controlled by user via CLI (PlayerType.HUMAN)
    Player 2 (Skeleton) = controlled by Codex via agent CLI (PlayerType.CODEX)

    Both players create sessions and join to control their entities.

    Args:
        character_class: "fighter", "barbarian", or "sorcerer" - the hero's class.
    """

    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_arena_combat(pvp_mode=True, character_class=character_class)
    sim.paused = False
    sim.encounter.clear_combat_log()

    _ = sim.create_game_session(sim.encounter)

    hero_uuid = None
    skeleton_uuid = None
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
            hero_uuid = entity.uuid
        elif entity.name == "Skeleton":
            skeleton_uuid = entity.uuid

    result = await advance_encounter()

    return {
        "status": "pvp_started",
        "mode": "pvp",
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": str(hero_uuid) if hero_uuid else None,
        "skeleton_uuid": str(skeleton_uuid) if skeleton_uuid else None,
        "message": "PvP mode: Create sessions and join - Hero (human) vs Skeleton (codex)",
        **result.model_dump(mode="json"),
    }


@app.post("/agent/ping")
async def agent_ping():
    """
    DEPRECATED: Use /session/{session_id}/ping instead.

    Legacy endpoint for backward compatibility.
    Agent should create a session and use session ping instead.
    """

    game = sim.game
    is_my_turn = False
    skeleton_uuid = None

    if game and sim.encounter:
        current_entity = sim.encounter.get_current_entity()
        if current_entity and current_entity.name == "Skeleton":
            is_my_turn = True
            skeleton_uuid = str(current_entity.uuid)
        else:

            for entity in Entity.get_all_entities():
                if entity.name == "Skeleton":
                    skeleton_uuid = str(entity.uuid)
                    break

    return {
        "status": "ok",
        "message": "DEPRECATED: Use /session/create and /session/{id}/ping instead",
        "is_my_turn": is_my_turn,
        "skeleton_uuid": skeleton_uuid
    }


@app.get("/pvp/status")
async def get_pvp_status():
    """
    Get PvP game status including session connections and faction info.

    Used by CLIs to check game state and who's connected.
    """
    game = sim.game

    current_turn = None
    is_hero_turn = False
    is_skeleton_turn = False
    hero_uuid = None
    skeleton_uuid = None

    factions: dict = {}
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
            hero_uuid = entity.uuid
        elif entity.name == "Skeleton":
            skeleton_uuid = entity.uuid

        faction_key = entity.faction if entity.faction else "(no faction)"
        if faction_key not in factions:
            factions[faction_key] = {"total": 0, "alive": 0}
        factions[faction_key]["total"] += 1
        if entity.has_hp:
            factions[faction_key]["alive"] += 1

    if sim.encounter:
        current_entity = sim.encounter.get_current_entity()
        if current_entity:
            current_turn = current_entity.name
            is_hero_turn = hero_uuid and current_entity.uuid == hero_uuid
            is_skeleton_turn = skeleton_uuid and current_entity.uuid == skeleton_uuid

    ACTIVITY_TIMEOUT = 5.0

    human_connected = False
    codex_connected = False

    if game:
        for session in game.players.values():
            if session.player_type == PlayerType.HUMAN:
                human_connected = session.connection_status == ConnectionStatus.CONNECTED
            elif session.player_type == PlayerType.CODEX:

                time_since_activity = time.time() - session.last_activity
                codex_connected = time_since_activity < ACTIVITY_TIMEOUT

    return {
        "pvp_mode": game is not None,
        "human_connected": human_connected,
        "codex_connected": codex_connected,
        "current_turn": current_turn,
        "is_hero_turn": is_hero_turn,
        "is_skeleton_turn": is_skeleton_turn,
        "hero_uuid": str(hero_uuid) if hero_uuid else None,
        "skeleton_uuid": str(skeleton_uuid) if skeleton_uuid else None,
        "factions": factions
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event streaming.

    Connect and receive events as JSON messages.
    Send {"type": "ping"} to check connection.
    Send {"type": "filter", "event_types": ["attack", "movement"]} to filter events.
    """
    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    event_monitor.add_listener(queue)

    event_type_filter: Optional[Set[str]] = None

    try:

        await websocket.send_json({
            "type": "connected",
            "message": "Connected to D&D Engine Event Server",
            "event_count": len(EventQueue._all_events)
        })

        async def receive_commands():
            nonlocal event_type_filter
            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif msg_type == "filter":

                        types = data.get("event_types")
                        if types:
                            event_type_filter = set(types)
                            await websocket.send_json({
                                "type": "filter_set",
                                "event_types": list(event_type_filter)
                            })
                        else:
                            event_type_filter = None
                            await websocket.send_json({
                                "type": "filter_cleared"
                            })

                    elif msg_type == "get_history":

                        limit = data.get("limit", 50)
                        events = EventQueue._all_events[-limit:]
                        for event in events:
                            event_data = event.model_dump(mode="json")
                            if event_type_filter is None or event_data.get("event_type") in event_type_filter:
                                await websocket.send_json({
                                    "type": "event",
                                    "event": event_data
                                })

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"Error receiving command: {e}")
                    break

        async def send_events():
            while True:
                try:
                    event_data = await queue.get()

                    if event_type_filter is not None:
                        if event_data.get("event_type") not in event_type_filter:
                            continue

                    await websocket.send_json({
                        "type": "event",
                        "event": event_data
                    })
                except Exception as e:
                    print(f"Error sending event: {e}")
                    break

        receive_task = asyncio.create_task(receive_commands())
        send_task = asyncio.create_task(send_events())

        _, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        event_monitor.remove_listener(queue)
        print(f"WebSocket client disconnected. Active listeners: {event_monitor.listener_count}")


def kill_process_on_port(port: int) -> bool:
    """Kill any process using the specified port. Returns True if killed something."""
    import subprocess
    import sys

    try:
        if sys.platform == "win32":

            result = subprocess.run(
                f"netstat -ano | findstr :{port}",
                shell=True, capture_output=True, text=True
            )
            for line in result.stdout.strip().split('\n'):
                if line and 'LISTENING' in line:
                    parts = line.split()
                    pid = parts[-1]
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                    print(f"Killed process {pid} on port {port}")
                    return True
        else:

            result = subprocess.run(
                f"lsof -ti:{port}",
                shell=True, capture_output=True, text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True)
                    print(f"Killed process {pid} on port {port}")
                return True
    except Exception as e:
        print(f"Error killing process: {e}")
    return False


def run_server(host: str = "0.0.0.0", port: int = 8000, force: bool = False):
    """Run the event server."""
    if force:
        kill_process_on_port(port)
        time.sleep(0.5)

    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D&D Engine Event Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--force", "-f", action="store_true", help="Kill existing process on port")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, force=args.force)
