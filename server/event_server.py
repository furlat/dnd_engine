"""
WebSocket server for broadcasting game events + REST API for game state.

This server:
1. Hooks into EventQueue to capture all events
2. Broadcasts events to connected WebSocket clients
3. Provides REST endpoints for game state queries
4. Controls simulation (start/pause/resume/step)

Usage:
    # Start server
    python -m server.event_server

    # Or import and run programmatically
    from server.event_server import run_server
    run_server(host="0.0.0.0", port=8000)
"""

import asyncio
from typing import Set, Optional
from uuid import UUID, uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from dnd.core.events import Event, EventQueue, EventType, EventPhase
from dnd.core.gridmap import get_map, reset_map
from dnd.entity import Entity
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.classes.fighter_factory import create_fighter, FighterConfig
from dnd.classes.barbarian_factory import create_barbarian, BarbarianConfig, PrimalPathChoice
from dnd.items import create_shortsword, create_dagger, create_longbow
from dnd.blocks.equipment import WeaponSlot
from dnd.controller import Controller, HumanController, ClaudeController, MeleeAIController
from dnd.actions_functional import get_available_actions, execute_action, execute_by_index
from dnd.actions import MovementEvent, JumpEvent
from dnd.core.base_actions import TargetType, AvailableTarget
from dnd.reactions import add_opportunity_attack_handler

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter,
    APIGameState, APISimulationStatus,
    APICurrentTurn, SimpleActionRequest, ActionResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    SelfActionRequest, EntityActionRequest, PositionActionRequest, ExecuteByIndexRequest
)
from server.session import (
    SessionManager, GameSession,
    PlayerType, ConnectionStatus, get_session_manager
)


def add_event_to_combat_log(sim_state: "SimulationState", event: Event, entry_type_override: Optional[str] = None) -> Optional[int]:
    """Add event's combat log entry to encounter's combat log.

    Uses event.combat_log if available (auto-generated at COMPLETION phase).
    Returns the log entry index, or None if no log entry was created.

    Args:
        sim_state: The SimulationState (used to access encounter).
        event: The event containing the combat log.
        entry_type_override: Unused, kept for backward compatibility.

    Returns:
        Log entry index if successful, None otherwise.
    """
    # entry_type_override is kept for backward compatibility but not used
    del entry_type_override

    if event.combat_log is None:
        return None

    # Use encounter's combat log directly
    if sim_state.encounter:
        return sim_state.encounter.add_event_to_combat_log(event)

    return None


class EventMonitor:
    """
    Monitors EventQueue and broadcasts events to listeners.

    Uses EventQueue's on_event_callback system to receive ALL events
    regardless of phase, then broadcasts them to connected listeners.
    """

    def __init__(self):
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

        # Debug: log attack events
        if event.event_type.value == 'attack':
            attack_outcome = getattr(event, 'attack_outcome', None)
            dice_roll = getattr(event, 'dice_roll', None)
            print(f"[WS BROADCAST] attack {event.phase.value}: outcome={attack_outcome}, dice={dice_roll}")

        # Serialize event to JSON-compatible dict
        try:
            event_data = event.model_dump(mode='json')
            for queue in self._listeners:
                try:
                    queue.put_nowait(event_data)
                except asyncio.QueueFull:
                    pass  # Drop event if queue is full
        except Exception as e:
            print(f"Error serializing event: {e}")

    def start(self) -> None:
        """Start monitoring events."""
        if self._running:
            return

        EventQueue.add_on_event_callback(self._on_event)
        self._running = True
        print("EventMonitor started")

    def stop(self) -> None:
        """Stop monitoring events."""
        if not self._running:
            return

        EventQueue.remove_on_event_callback(self._on_event)
        self._running = False
        print("EventMonitor stopped")


# Global event monitor instance
event_monitor = EventMonitor()


# =============================================================================
# Simulation State & Control
# =============================================================================

class SimulationState:
    """Holds the current simulation state."""
    def __init__(self):
        self.encounter: Optional[Encounter] = None
        self.combat_task: Optional[asyncio.Task] = None
        self.paused: bool = True
        self.turn_delay: float = 1.5  # seconds between turns
        self.auto_run_ai: bool = True  # Auto-advance through AI turns

        # Session manager integration
        self._session_manager = get_session_manager()
        self._game_session: Optional[GameSession] = None

    @property
    def game(self) -> Optional[GameSession]:
        """Get the active game session."""
        return self._game_session

    @property
    def waiting_for_human(self) -> bool:
        """Check if waiting for a human/claude player (derived from session state)."""
        if not self._game_session or not self.encounter:
            return False
        active_player = self._game_session.active_player
        if not active_player:
            return False
        # Waiting if active player is human or claude (not AI)
        return active_player.player_type in (PlayerType.HUMAN, PlayerType.CLAUDE)

    @property
    def human_entity_uuid(self) -> Optional[UUID]:
        """Get the active entity UUID if it's a human/claude turn."""
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


# Global simulation state
sim = SimulationState()


def setup_combat() -> Encounter:
    """Initialize grid, entities, and encounter."""
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    EventQueue.reset()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create combatants
    goblin = create_goblin(name="Goblin Scout", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton Warrior", position=(12, 7))
    Entity.update_all_entities_senses()

    # Create encounter with AI controllers
    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(goblin, MeleeAIController(source_entity_uuid=goblin.uuid))
    encounter.add_combatant(skeleton, MeleeAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def setup_arena_combat(
    player_position: tuple = (2, 7),
    pvp_mode: bool = False,
    character_class: str = "fighter"
) -> Encounter:
    """
    Initialize arena combat with Hero (heroes faction) vs 3 Skeletons (monsters faction).

    Args:
        player_position: Starting position for Hero
        pvp_mode: If True, Skeletons use ClaudeController (PvP).
                  If False, Skeletons use MeleeAIController (vs AI).
        character_class: "fighter" or "barbarian" - the hero's class
    """
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()
    EventQueue.reset()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Add a vertical wall in the middle (blocking LOS)
    for y in range(3, 12):
        if y != 7:  # Leave a gap in the middle
            grid.set_tile(7, y, walkable=False, visible=False)

    # ADD: Jump test island in top-left corner
    # Create water barrier around island (visible=True, walkable=False)
    # Water at column 2 from y=0 to y=3 (vertical barrier)
    for y in range(4):
        grid.set_tile(2, y, walkable=False, visible=True, name="Water")
    # Water at row 3 from x=0 to x=1 (horizontal barrier, completing the box)
    for x in range(2):
        grid.set_tile(x, 3, walkable=False, visible=True, name="Water")
    # The island is at (0,0), (0,1), (0,2), (1,0), (1,1), (1,2) - floor tiles
    # Now isolated by water - reachable only by Jump (LOS passes through water)

    # Create Hero based on character class
    if character_class == "barbarian":
        player = create_barbarian_hero(name="Hero", position=player_position, faction="heroes")
    else:
        # Default to fighter
        player = create_dex_fighter(name="Hero", position=player_position, faction="heroes")

    # Create 3 Skeletons (monsters faction) at different positions
    skeleton_positions = [(12, 5), (12, 7), (12, 9)]
    skeletons = []
    for i, pos in enumerate(skeleton_positions):
        skeleton = create_skeleton(
            name=f"Skeleton {i+1}",
            position=pos,
            faction="monsters"
        )
        skeletons.append(skeleton)

    # Register opportunity attack handlers
    add_opportunity_attack_handler(player)
    for skeleton in skeletons:
        add_opportunity_attack_handler(skeleton)

    Entity.update_all_entities_senses(max_distance=20)

    # Create encounter with appropriate controllers
    encounter_name = "PvP Arena" if pvp_mode else "Arena Combat"
    encounter = Encounter(name=encounter_name, source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))

    for skeleton in skeletons:
        if pvp_mode:
            encounter.add_combatant(skeleton, ClaudeController(source_entity_uuid=skeleton.uuid))
        else:
            encounter.add_combatant(skeleton, MeleeAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def create_dex_fighter(name: str = "Hero", position: tuple = (0, 0), faction: Optional[str] = None) -> Entity:
    """
    Create a Level 5 DEX-based Fighter with dual wielding and archery.

    Stats: High DEX, high CON, decent STR
    Fighting Style: Two Weapon Fighting
    Equipment: Shortsword + Dagger (melee), Longbow (ranged)
    """
    config = FighterConfig(
        level=5,
        name=name,
        position=position,
        faction=faction,
        # DEX-based: High DEX, high CON, decent STR
        base_strength=12,      # Decent STR
        base_dexterity=15,     # High DEX (will be 17 with +2 bonus)
        base_constitution=14,  # High CON (will be 15 with +1 bonus)
        base_intelligence=10,
        base_wisdom=10,
        base_charisma=8,
        # Racial bonuses
        bonus_plus_2="dexterity",     # DEX = 17
        bonus_plus_1="constitution",  # CON = 15
        # Two Weapon Fighting for dual wield damage
        fighting_style="two_weapon",
        # Use studded leather for DEX build (no preset fits, so use archery preset base)
        equipment_preset="archery",  # We'll replace weapons below
        # ASI at L4: +2 DEX to hit 19
        asi_4=[("dexterity", 2)],
    )

    fighter = create_fighter(config)

    # Replace weapons: Shortsword + Dagger for melee, keep Longbow for ranged
    # First unequip the default archery preset weapons
    fighter.equipment.unequip(WeaponSlot.MELEE_MAIN)
    fighter.equipment.unequip(WeaponSlot.RANGED_MAIN)

    # Equip dual wield melee weapons
    shortsword = create_shortsword(fighter.uuid)
    dagger = create_dagger(fighter.uuid)
    longbow = create_longbow(fighter.uuid)

    fighter.equipment.equip(shortsword, WeaponSlot.MELEE_MAIN)
    fighter.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    fighter.equipment.equip(longbow, WeaponSlot.RANGED_MAIN)

    return fighter


def create_barbarian_hero(name: str = "Hero", position: tuple = (0, 0), faction: Optional[str] = None) -> Entity:
    """
    Create a Level 5 Berserker Barbarian with greataxe.

    Stats: STR 19, CON 15, DEX 13 (after bonuses and L4 ASI)
    Features: Rage (3 uses), Unarmored Defense, Reckless Attack,
              Danger Sense, Frenzy, Extra Attack, Fast Movement
    Equipment: Greataxe (1d12 slashing, two-handed)
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
        bonus_plus_2="strength",      # STR = 17
        bonus_plus_1="constitution",  # CON = 15
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],      # STR = 19
        equipment_preset="greataxe",
    )
    return create_barbarian(config)


async def advance_encounter() -> dict:
    """
    Advance encounter, auto-run AI turns, stop on human turn.

    Uses Encounter.advance_until_player() which auto-captures combat logs.
    Returns status dict indicating what happened.
    """
    if sim.encounter is None:
        return {"status": "no_encounter"}

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.roll_initiative()
        sim.encounter.start_encounter()

    if sim.encounter.state == EncounterState.ENDED:
        return {"status": "encounter_ended"}

    # Get log index before advancing (to fetch new AI entries later)
    log_start = len(sim.encounter.combat_log)

    # Use encounter's advance_until_player - it auto-captures combat logs
    result = sim.encounter.advance_until_player()

    # Build ai_actions from new combat log entries (raw CombatLogEntry.to_dict())
    new_entries = sim.encounter.get_combat_log(log_start)
    ai_actions = [e.to_dict() for e in new_entries]

    return {
        "status": result.status,
        "entity_uuid": str(result.entity_uuid) if result.entity_uuid else None,
        "entity_name": result.entity_name,
        "round": result.round_number,
        "turn_index": result.turn_index,
        "ai_actions": ai_actions,
        "new_log_since": log_start
    }


def validate_session_action(session_id_str: str, entity_uuid_str: str) -> Entity:
    """
    Validate that a session can perform an action with an entity.

    This is the new session-based validation that replaces the old
    validate_human_action. It checks:
    1. Session exists and is connected
    2. Session owns the entity
    3. Entity is the active entity (it's their turn)
    4. Turn is in progress

    Args:
        session_id_str: UUID string of the session
        entity_uuid_str: UUID string of the entity trying to act

    Returns:
        The Entity object if valid

    Raises:
        HTTPException if invalid
    """
    # Parse UUIDs
    try:
        session_id = UUID(session_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    try:
        entity_uuid = UUID(entity_uuid_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity UUID format")

    # Use session manager validation
    mgr = sim.get_session_manager()
    _, _ = mgr.validate_action(session_id, entity_uuid)

    # Get and return the entity
    entity = Entity.get(entity_uuid)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return entity


async def run_combat_loop():
    """Combat loop that respects pause state."""
    if sim.encounter is None:
        return

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.start_encounter()

    while sim.encounter.state == EncounterState.ACTIVE:
        if sim.paused:
            await asyncio.sleep(0.1)  # Check pause flag frequently
            continue

        sim.encounter.run_turn()
        await asyncio.sleep(sim.turn_delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for FastAPI app."""
    # Startup
    event_monitor.start()
    yield
    # Shutdown
    event_monitor.stop()
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()


# Create FastAPI app
app = FastAPI(
    title="D&D Engine Event Server",
    description="WebSocket server for real-time game events + REST API",
    lifespan=lifespan
)

# Add CORS middleware for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health & Info Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "listeners": event_monitor.listener_count,
        "event_count": len(EventQueue._all_events),
        "has_encounter": sim.encounter is not None,
        "paused": sim.paused
    }


# =============================================================================
# Game State Endpoints
# =============================================================================

@app.get("/state", response_model=APIGameState)
async def get_state():
    """Get full game state (grid, entities, encounter)."""
    grid = get_map()

    # Get active encounter
    encounter_data = None
    if sim.encounter:
        encounter_data = APIEncounter.create(sim.encounter)

    return APIGameState(
        grid=APIGrid.create(grid),
        entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
        encounter=encounter_data
    )


@app.get("/entities")
async def get_entities():
    """Get all entities (lightweight)."""
    return {
        "entities": [APIEntitySummary.create(e).model_dump() for e in Entity.get_all_entities()]
    }


@app.get("/visibility")
async def get_visibility():
    """Get visibility data for all entities (which cells each entity can see)."""
    result = {}
    for entity in Entity.get_all_entities():
        # Get visible positions from entity's senses
        visible_positions = [
            list(pos) for pos, is_visible in entity.senses.visible.items()
            if is_visible
        ]
        result[str(entity.uuid)] = {
            "name": entity.name,
            "position": list(entity.position),
            "visible_cells": visible_positions
        }
    return result


@app.get("/entity/{entity_uuid}", response_model=APIEntityFull)
async def get_entity(entity_uuid: str):
    """Get full details for a single entity."""
    try:
        uuid_obj = UUID(entity_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    entity = Entity.get(uuid_obj)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return APIEntityFull.create(entity)


@app.get("/grid", response_model=APIGrid)
async def get_grid():
    """Get grid/map data."""
    return APIGrid.create(get_map())


@app.get("/encounter")
async def get_encounter():
    """Get current encounter state."""
    if not sim.encounter:
        return {"active": False, "encounter": None}
    return {
        "active": True,
        "encounter": APIEncounter.create(sim.encounter).model_dump()
    }


@app.get("/combat-log")
async def get_combat_log(since: int = 0):
    """
    Get combat log entries from Encounter.

    Args:
        since: Only return entries with index >= since (for polling)

    Returns:
        List of log entries as CombatLogEntry.to_dict() (raw model_dump)
    """
    if not sim.encounter:
        return {"entries": [], "count": 0, "total": 0}

    entries = sim.encounter.get_combat_log(since)
    return {
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
        "total": len(sim.encounter.combat_log)
    }


# =============================================================================
# Simulation Control Endpoints
# =============================================================================

@app.post("/simulation/start")
async def start_simulation():
    """Reset and start a new combat simulation."""
    # Cancel existing task
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
    """Stop current combat and reset to fresh state (paused)."""
    # Cancel existing task
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
    """Pause the combat loop."""
    sim.paused = True
    return {"status": "paused"}


@app.post("/simulation/resume")
async def resume_simulation():
    """Resume the combat loop."""
    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No simulation to resume. Call /simulation/reset first.")

    sim.paused = False

    # Restart loop if task is done or doesn't exist
    if sim.combat_task is None or sim.combat_task.done():
        sim.combat_task = asyncio.create_task(run_combat_loop())

    return {"status": "resumed"}


@app.post("/simulation/step")
async def step_simulation():
    """Execute a single turn (useful when paused)."""
    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No simulation. Call /simulation/reset first.")

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
    """Get current simulation status."""
    return APISimulationStatus(
        has_encounter=sim.encounter is not None,
        paused=sim.paused,
        encounter_state=sim.encounter.state.value if sim.encounter else None,
        round_number=sim.encounter.round_number if sim.encounter else None,
        turn_delay=sim.turn_delay
    )


@app.post("/simulation/set-delay")
async def set_turn_delay(delay: float):
    """Set the delay between turns (in seconds)."""
    if delay < 0.1:
        raise HTTPException(status_code=400, detail="Delay must be at least 0.1 seconds")
    if delay > 10:
        raise HTTPException(status_code=400, detail="Delay cannot exceed 10 seconds")

    sim.turn_delay = delay
    return {"status": "delay_set", "turn_delay": sim.turn_delay}


# =============================================================================
# Session Management Endpoints
# =============================================================================

@app.post("/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new player session.

    Args:
        player_type: "human" or "claude"
        name: Optional display name

    Returns:
        Session ID and details
    """
    # Parse player type
    try:
        ptype = PlayerType(request.player_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid player_type: {request.player_type}. Must be 'human' or 'claude'"
        )

    # Create session
    mgr = sim.get_session_manager()
    session = mgr.create_session(ptype, request.name)

    return CreateSessionResponse(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name
    )


@app.post("/session/{session_id}/ping", response_model=SessionPingResponse)
async def ping_session(session_id: str):
    """
    Ping a session to update activity and get current status.

    Call this periodically to:
    1. Keep the session alive (prevent timeout)
    2. Check if it's your turn
    3. Get the active entity info
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update activity
    session.ping()

    # Get game state
    game = sim.game
    is_my_turn = False
    active_entity_uuid = None
    active_entity_name = None

    if game:
        active_entity_uuid = game.active_entity_uuid
        if active_entity_uuid:
            entity = Entity.get(active_entity_uuid)
            active_entity_name = entity.name if entity else None
            # Check if this session's turn
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


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete/disconnect a session."""
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    mgr.remove_session(sid)

    return {"status": "deleted", "session_id": session_id}


@app.post("/game/join", response_model=JoinGameResponse)
async def join_game(request: JoinGameRequest):
    """
    Join the active game with a session.

    Priority:
    1. If entity_uuids is provided, assigns those specific entities
    2. If faction is provided, assigns all entities with that faction
    3. Otherwise, auto-assigns based on player type (human gets Hero, claude gets Skeleton)
    """
    try:
        sid = UUID(request.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    game = sim.game
    if not game:
        raise HTTPException(status_code=400, detail="No active game to join")

    # Add player to game if not already
    if session.session_id not in game.players:
        game.add_player(session)

    # Assign entities
    assigned = []
    if request.entity_uuids:
        # Priority 1: Assign specific entities by UUID
        for uuid_str in request.entity_uuids:
            try:
                entity_uuid = UUID(uuid_str)
                if game.assign_entity(entity_uuid, session.session_id):
                    assigned.append(str(entity_uuid))
            except ValueError:
                pass  # Skip invalid UUIDs
    elif request.faction:
        # Priority 2: Assign all entities with the given faction
        for entity in Entity.get_all_entities():
            if entity.faction == request.faction:
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
    else:
        # Priority 3: Auto-assign based on player type and entity name
        for entity in Entity.get_all_entities():
            # Human players get "Hero", Claude players get other entities
            if session.player_type == PlayerType.HUMAN and entity.name == "Hero":
                if game.assign_entity(entity.uuid, session.session_id):
                    assigned.append(str(entity.uuid))
            elif session.player_type == PlayerType.CLAUDE and entity.name != "Hero":
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
    """Get current game status including all sessions."""
    game = sim.game

    if not game:
        return {
            "active": False,
            "game": None,
            "sessions": []
        }

    # Build session info
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
    """
    Get list of entities controlled by a session.

    Returns entity details including uuid, name, faction, hp, and position.
    """
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    mgr = sim.get_session_manager()
    session = mgr.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

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


# =============================================================================
# Event Endpoints (existing)
# =============================================================================


@app.get("/events")
async def get_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    phase: Optional[str] = None
):
    """Get recent events from the queue."""
    events = EventQueue._all_events[-limit:]

    # Filter by type if specified
    if event_type:
        try:
            et = EventType(event_type)
            events = [e for e in events if e.event_type == et]
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown event_type: {event_type}"}
            )

    # Filter by phase if specified
    if phase:
        try:
            ep = EventPhase(phase)
            events = [e for e in events if e.phase == ep]
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown phase: {phase}"}
            )

    return {
        "count": len(events),
        "events": [e.model_dump(mode='json') for e in events]
    }


@app.get("/event-types")
async def get_event_types():
    """List all available event types."""
    return {
        "event_types": [et.value for et in EventType],
        "phases": [ep.value for ep in EventPhase]
    }


# =============================================================================
# Human Control Endpoints
# =============================================================================

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

    # Get action economy if entity exists
    actions = bonus = reactions = movement = 0
    if entity:
        ae = entity.action_economy
        actions = ae.actions.normalized_score
        bonus = ae.bonus_actions.normalized_score
        reactions = ae.reactions.normalized_score
        movement = ae.movement.normalized_score

    # is_human_turn means "waiting for manual input" (human OR claude, not AI)
    needs_input = controller.controller_type in ("human", "claude") if controller else False

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


@app.get("/entity/{entity_uuid}/available-actions")
async def get_entity_available_actions(entity_uuid: str):
    """Get all available actions for an entity."""
    try:
        uuid_obj = UUID(entity_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    entity = Entity.get(uuid_obj)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    actions = get_available_actions(entity)

    # Convert to JSON-serializable format using new AvailableActionsResult structure
    def serialize_target(t):
        result = {"index": t.index}
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
        return result

    def serialize_action(a):
        return {
            "template_name": a.template_name,
            "target_type": a.target_type.value,
            "valid_targets": [serialize_target(t) for t in a.valid_targets],
            "can_afford": a.can_afford,
            "display_name": a.display_name,
            "description": a.description,
            "cost_type": a.cost_type,
            "cost_amount": a.cost_amount,
            "weapon_slot": a.weapon_slot,
            "weapon_name": a.weapon_name
        }

    return {
        "entity_uuid": str(actions.entity_uuid),
        "entity_actions": [serialize_action(a) for a in actions.entity_actions],
        "position_actions": [serialize_action(a) for a in actions.position_actions],
        "self_actions": [serialize_action(a) for a in actions.self_actions],
        "remaining_movement": actions.remaining_movement
    }


@app.post("/action/end-turn")
async def end_human_turn(request: SimpleActionRequest):
    """End the session's entity turn and advance through AI turns."""
    _ = validate_session_action(request.session_id, request.entity_uuid)  # Validates session/entity

    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter")

    # End turn (fires TurnEndEvent) and advance to next combatant
    sim.encounter.end_turn()

    # Advance turn index for next turn
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED

    # Advance through AI turns until next human/claude or encounter ends
    result = await advance_encounter()

    return result


# =============================================================================
# New Generic Action Endpoints (using functional API)
# =============================================================================

@app.post("/action/self", response_model=ActionResult)
async def execute_self_action(request: SelfActionRequest):
    """Execute a self-targeting action (Dash, Dodge, Disengage, StandUp).

    Uses the new functional action API.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Get and validate the template
    template = entity.get_action_template(request.action_name)
    if template is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action_name}")

    if template.target_type != TargetType.SELF:
        raise HTTPException(
            status_code=400,
            detail=f"Action {request.action_name} is not a SELF action (is {template.target_type.value})"
        )

    # Execute via functional API
    target = AvailableTarget(index=0)
    try:
        event = execute_action(entity, request.action_name, target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Collect combat log entries
    action_log_entries: list = []

    # Add to combat log using event.combat_log
    if event and event.combat_log:
        add_event_to_combat_log(sim, event)
        action_log_entries.append(event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or f"{request.action_name} executed",
        event_type=request.action_name.lower(),
        entity_hp=entity.get_hp(),
        turn_continues=True,
        encounter_ended=False,
        combat_log_entries=action_log_entries
    )


@app.post("/action/entity", response_model=ActionResult)
async def execute_entity_action(request: EntityActionRequest):
    """Execute an entity-targeting action (Attack).

    Uses the new functional action API. Captures opportunity attacks.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Parse and validate target
    try:
        target_uuid = UUID(request.target_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target UUID format")

    target = Entity.get(target_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    # Get and validate the template
    template = entity.get_action_template(request.action_name)
    if template is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action_name}")

    if template.target_type != TargetType.ENTITY:
        raise HTTPException(
            status_code=400,
            detail=f"Action {request.action_name} is not an ENTITY action (is {template.target_type.value})"
        )

    # Execute via functional API
    action_target = AvailableTarget(index=0, target_uuid=target_uuid, target_name=target.name)
    try:
        event = execute_action(entity, request.action_name, action_target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for deaths
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Collect combat log entries
    action_log_entries: list = []

    # Build event data for attacks using event.combat_log
    event_data = None
    if event and hasattr(event, 'attack_outcome') and event.combat_log:
        add_event_to_combat_log(sim, event)
        action_log_entries.append(event.combat_log.to_dict())
        # Pass through the full combat log data - CLI now supports new structure
        event_data = dict(event.combat_log.data)
        # Add target_hp for ActionResult
        event_data["target_hp"] = target.get_hp()

    # Log death events to encounter's combat log
    for death_event in deaths:
        if sim.encounter and death_event.combat_log:
            sim.encounter.add_event_to_combat_log(death_event)
            action_log_entries.append(death_event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Action executed",
        event_type=request.action_name.lower().replace("_", " "),
        event_data=event_data,
        entity_hp=entity.get_hp(),
        target_hp=target.get_hp(),
        deaths=death_names,
        turn_continues=not encounter_ended,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries
    )


@app.post("/action/position", response_model=ActionResult)
async def execute_position_action(request: PositionActionRequest):
    """Execute a position-targeting action (Move).

    Uses the new functional action API. Captures opportunity attacks.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Get and validate the template
    template = entity.get_action_template(request.action_name)
    if template is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action_name}")

    # Accept both POSITION_PATH (path-based like Move) and POSITION_LOS (LOS-based like Jump)
    if template.target_type not in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        raise HTTPException(
            status_code=400,
            detail=f"Action {request.action_name} is not a position action (is {template.target_type.value})"
        )

    # Track opportunity attacks triggered by movement
    captured_oa_events: list = []  # Store events for combat_log usage

    def capture_opportunity_attack(event: Event) -> None:
        """Capture attack events targeting the moving entity (opportunity attacks)."""
        if event.phase != EventPhase.COMPLETION:
            return

        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

        if event_type == "attack" and event.target_entity_uuid == entity.uuid:
            captured_oa_events.append(event)  # Store event for combat_log

    # Register callback before move
    EventQueue.add_on_event_callback(capture_opportunity_attack)

    try:
        # Execute via functional API
        pos = (request.position[0], request.position[1])  # Ensure Tuple[int, int]
        action_target = AvailableTarget(index=0, position=pos)
        event = execute_action(entity, request.action_name, action_target)
    except ValueError as e:
        EventQueue.remove_on_event_callback(capture_opportunity_attack)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        EventQueue.remove_on_event_callback(capture_opportunity_attack)

    # Check for deaths
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Collect combat log entries
    action_log_entries: list = []

    # Extract event data
    event_data = None
    triggered_reactions: list = []

    if isinstance(event, (MovementEvent, JumpEvent)):
        # Log move/jump using event.combat_log
        if event.combat_log:
            add_event_to_combat_log(sim, event)
            action_log_entries.append(event.combat_log.to_dict())
            # Pass through the full combat log data
            event_data = dict(event.combat_log.data)
        else:
            # Fallback if no combat_log (shouldn't happen)
            event_data = {
                "entity_name": entity.name,
                "start_position": list(event.start_position),
                "end_position": list(event.end_position),
                "path": [list(p) for p in event.path] if event.path else []
            }

        # Log opportunity attacks using event.combat_log
        for oa_event in captured_oa_events:
            if oa_event.combat_log:
                add_event_to_combat_log(sim, oa_event, entry_type_override="opportunity_attack")
                # Add to combat_log_entries with type override
                entry_dict = oa_event.combat_log.to_dict()
                entry_dict["entry_type"] = "opportunity_attack"
                action_log_entries.append(entry_dict)
                # Pass through full combat log data - CLI now supports new structure
                oa_data = dict(oa_event.combat_log.data)
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    # Log death events
    for death_event in deaths:
        if sim.encounter and death_event.combat_log:
            sim.encounter.add_event_to_combat_log(death_event)
            action_log_entries.append(death_event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or ("Moved successfully" if event and not event.canceled else "Move failed"),
        event_type="movement",
        event_data=event_data,
        entity_hp=entity.get_hp(),
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries
    )


@app.post("/action/execute", response_model=ActionResult)
async def execute_action_by_index(request: ExecuteByIndexRequest):
    """Execute action by template name and target index.

    Enables 'attack 0', 'move 3' style commands from the available actions list.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Get template to determine action type
    template = entity.get_action_template(request.template_name)
    if template is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.template_name}")

    # For POSITION actions (Move), need to capture opportunity attacks
    captured_oa_events: list = []  # Store events for combat_log usage

    def capture_opportunity_attack(event: Event) -> None:
        if event.phase != EventPhase.COMPLETION:
            return
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        if event_type == "attack" and event.target_entity_uuid == entity.uuid:
            captured_oa_events.append(event)  # Store event for combat_log

    # Register callback if this might trigger OAs (position-based movement actions)
    if template.target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        EventQueue.add_on_event_callback(capture_opportunity_attack)

    try:
        event = execute_by_index(entity, request.template_name, request.target_index)
    except ValueError as e:
        if template.target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
            EventQueue.remove_on_event_callback(capture_opportunity_attack)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if template.target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
            EventQueue.remove_on_event_callback(capture_opportunity_attack)

    # Check for deaths
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Collect combat log entries
    action_log_entries: list = []

    # Build response based on action type
    event_data = None
    target_hp = None

    triggered_reactions: list = []

    if template.target_type == TargetType.ENTITY and event and event.combat_log:
        # Entity-targeting actions (attacks, shove, grapple, etc.)
        add_event_to_combat_log(sim, event)
        action_log_entries.append(event.combat_log.to_dict())
        event_data = dict(event.combat_log.data)

        # Add target HP for attacks
        if hasattr(event, 'attack_outcome'):
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            target_hp = target.get_hp() if target else None
            event_data["target_hp"] = target_hp

    elif template.target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        # Movement actions (Move, Jump) - both have start_position, end_position, path
        if event and isinstance(event, (MovementEvent, JumpEvent)):
            if event.combat_log:
                add_event_to_combat_log(sim, event)
                action_log_entries.append(event.combat_log.to_dict())
                event_data = dict(event.combat_log.data)
            else:
                # Fallback if no combat_log
                event_data = {
                    "entity_name": entity.name,
                    "start_position": list(event.start_position),
                    "end_position": list(event.end_position),
                    "path": [list(p) for p in event.path] if event.path else []
                }

            # Log opportunity attacks using event.combat_log
            for oa_event in captured_oa_events:
                if oa_event.combat_log:
                    add_event_to_combat_log(sim, oa_event, entry_type_override="opportunity_attack")
                    # Add to combat_log_entries with type override
                    entry_dict = oa_event.combat_log.to_dict()
                    entry_dict["entry_type"] = "opportunity_attack"
                    action_log_entries.append(entry_dict)
                    # Pass through full combat log data - CLI now supports new structure
                    oa_data = dict(oa_event.combat_log.data)
                    oa_data["type"] = "opportunity_attack"
                    oa_data["is_opportunity_attack"] = True
                    triggered_reactions.append(oa_data)

    elif template.target_type == TargetType.SELF:
        # Self action - use event.combat_log
        if event and event.combat_log:
            add_event_to_combat_log(sim, event)
            action_log_entries.append(event.combat_log.to_dict())
            event_data = dict(event.combat_log.data)
        elif event:
            # Fallback if no combat_log
            event_data = {
                "entity_name": entity.name,
                "action_name": request.template_name,
            }

    # Log deaths to encounter's combat log
    for death_event in deaths:
        if sim.encounter and death_event.combat_log:
            sim.encounter.add_event_to_combat_log(death_event)
            action_log_entries.append(death_event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or f"{request.template_name} executed",
        event_type=request.template_name.lower(),
        event_data=event_data,
        entity_hp=entity.get_hp(),
        target_hp=target_hp,
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries
    )


@app.post("/simulation/start-human")
async def start_human_simulation(character_class: str = "fighter"):
    """
    Start a new combat with human control (player vs AI).

    This creates a game session and auto-assigns entities:
    - Hero (heroes faction) goes to the first human session that joins
    - All monsters faction entities are controlled by AI

    Args:
        character_class: "fighter" or "barbarian" - the hero's class
    """
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_arena_combat(pvp_mode=False, character_class=character_class)
    sim.paused = False
    sim.encounter.clear_combat_log()  # Clear combat log for new game

    # Create game session
    game = sim.create_game_session(sim.encounter)

    # Create AI session for all monsters
    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Monsters")
    game.add_player(ai_session)

    # Assign all monsters faction entities to AI
    for entity in Entity.get_all_entities():
        if entity.faction == "monsters":
            game.assign_entity(entity.uuid, ai_session.session_id)

    # Advance to first turn (may be human or AI)
    result = await advance_encounter()

    # Return info about which entity needs a human session
    hero_uuid = None
    for entity in Entity.get_all_entities():
        if entity.faction == "heroes":
            hero_uuid = str(entity.uuid)
            break

    return {
        "status": "started",
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": hero_uuid,  # Client should create session and join with this entity
        "message": "Create a session and join with hero_uuid to control the Hero",
        **result
    }


@app.post("/simulation/start-pvp")
async def start_pvp_simulation(character_class: str = "fighter"):
    """
    Start PvP combat where both entities are human-controlled.

    Player 1 (Hero) = controlled by user via CLI (PlayerType.HUMAN)
    Player 2 (Skeleton) = controlled by Claude via agent CLI (PlayerType.CLAUDE)

    Both players create sessions and join to control their entities.

    Args:
        character_class: "fighter" or "barbarian" - the hero's class
    """
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_arena_combat(pvp_mode=True, character_class=character_class)
    sim.paused = False
    sim.encounter.clear_combat_log()  # Clear combat log for new game

    # Create game session (side effect sets up session manager)
    _ = sim.create_game_session(sim.encounter)

    # Get entity UUIDs
    hero_uuid = None
    skeleton_uuid = None
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
            hero_uuid = entity.uuid
        elif entity.name == "Skeleton":
            skeleton_uuid = entity.uuid

    # Roll initiative and start - will wait for first player
    result = await advance_encounter()

    return {
        "status": "pvp_started",
        "mode": "pvp",
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": str(hero_uuid) if hero_uuid else None,
        "skeleton_uuid": str(skeleton_uuid) if skeleton_uuid else None,
        "message": "PvP mode: Create sessions and join - Hero (human) vs Skeleton (claude)",
        **result
    }


@app.post("/agent/ping")
async def agent_ping():
    """
    DEPRECATED: Use /session/{session_id}/ping instead.

    Legacy endpoint for backward compatibility.
    Agent should create a session and use session ping instead.
    """
    # This is kept for backward compat, but doesn't do much now
    # Agents should use the session system
    game = sim.game
    is_my_turn = False
    skeleton_uuid = None

    if game and sim.encounter:
        current_entity = sim.encounter.get_current_entity()
        if current_entity and current_entity.name == "Skeleton":
            is_my_turn = True
            skeleton_uuid = str(current_entity.uuid)
        else:
            # Find skeleton UUID
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

    # Determine whose turn it is
    current_turn = None
    is_hero_turn = False
    is_skeleton_turn = False
    hero_uuid = None
    skeleton_uuid = None

    # Get entity UUIDs and collect faction info
    factions: dict = {}  # faction -> {total: int, alive: int}
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
            hero_uuid = entity.uuid
        elif entity.name == "Skeleton":
            skeleton_uuid = entity.uuid

        # Track faction stats
        faction_key = entity.faction if entity.faction else "(no faction)"
        if faction_key not in factions:
            factions[faction_key] = {"total": 0, "alive": 0}
        factions[faction_key]["total"] += 1
        if entity.get_hp() > 0:
            factions[faction_key]["alive"] += 1

    if sim.encounter:
        current_entity = sim.encounter.get_current_entity()
        if current_entity:
            current_turn = current_entity.name
            is_hero_turn = hero_uuid and current_entity.uuid == hero_uuid
            is_skeleton_turn = skeleton_uuid and current_entity.uuid == skeleton_uuid

    # Check session connections
    # Claude is "connected" if they had activity in the last 5 seconds
    import time
    ACTIVITY_TIMEOUT = 5.0  # seconds

    human_connected = False
    claude_connected = False

    if game:
        for session in game.players.values():
            if session.player_type == PlayerType.HUMAN:
                human_connected = session.connection_status == ConnectionStatus.CONNECTED
            elif session.player_type == PlayerType.CLAUDE:
                # Check if Claude had recent activity (action or watch poll)
                time_since_activity = time.time() - session.last_activity
                claude_connected = time_since_activity < ACTIVITY_TIMEOUT

    return {
        "pvp_mode": game is not None,
        "human_connected": human_connected,
        "claude_connected": claude_connected,
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

    # Create a queue for this connection
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    event_monitor.add_listener(queue)

    # Optional event type filter
    event_type_filter: Optional[Set[str]] = None

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to D&D Engine Event Server",
            "event_count": len(EventQueue._all_events)
        })

        # Handle both receiving commands and sending events
        async def receive_commands():
            nonlocal event_type_filter
            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif msg_type == "filter":
                        # Set event type filter
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
                        # Send recent events
                        limit = data.get("limit", 50)
                        events = EventQueue._all_events[-limit:]
                        for event in events:
                            event_data = event.model_dump(mode='json')
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

                    # Apply filter if set
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

        # Run both tasks concurrently
        receive_task = asyncio.create_task(receive_commands())
        send_task = asyncio.create_task(send_events())

        # Wait for either task to complete (disconnect)
        _, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
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
            # Windows
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
            # Linux/Mac
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
        import time
        time.sleep(0.5)  # Brief pause to let port release

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D&D Engine Event Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--force", "-f", action="store_true", help="Kill existing process on port")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, force=args.force)
