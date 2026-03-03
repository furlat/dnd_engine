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
import logging
import time
import traceback
from typing import Dict, Set, Optional
from uuid import UUID, uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("dnd_server")

from dnd.core.events import Event, EventQueue, EventType, EventPhase
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
    create_healing_potion, create_potion_of_greater_invisibility,
    TrapLever, PullLeverAction, create_torch, create_wall_torch,
    TestDoorA,
)
from dnd.blocks.equipment import WeaponSlot
from dnd.controller import Controller, HumanController, ClaudeController, MeleeAIController
from dnd.actions_functional import get_available_actions, execute_action, execute_by_index, execute_use_action
from dnd.actions import MovementEvent, JumpEvent
from dnd.core.base_actions import TargetType, AvailableTarget, AvailableActionsResult
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.reactions import add_opportunity_attack_handler
from dnd.tiles import create_spike_zone
from dnd.core.base_tiles import difficult_terrain_factory

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter, APIFloorObject,
    APIGameState, APISimulationStatus,
    APICurrentTurn, SimpleActionRequest, ActionResult, AoEPreviewResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    SelfActionRequest, EntityActionRequest, PositionActionRequest, ExecuteByIndexRequest,
    ToggleHandlerRequest
)
from server.session import (
    SessionManager, GameSession,
    PlayerType, ConnectionStatus, get_session_manager
)

# Cache available actions per entity UUID (populated by GET, consumed by POST execute)
_available_actions_cache: Dict[str, AvailableActionsResult] = {}


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
        if y != 7:  # Leave a gap — door goes here
            grid.set_tile(7, y, walkable=False, visible=False, name="Wall")

    # Closed door at the wall gap — blocks movement and vision until opened
    door = TestDoorA(source_entity_uuid=uuid4())
    grid.place_object(door.uuid, (7, 7))

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

    # ADD: Spike zone in bottom-left corner (opposite the water island)
    # x: 0-4, y: 11-14 (5x4 = 20 tiles, ONE handler)
    spike_positions = {(x, y) for x in range(5) for y in range(11, 15)}
    spike_tiles, spike_handler = create_spike_zone(spike_positions)
    for tile in spike_tiles:
        grid._tiles[tile.position] = tile
        grid._tiles_by_uuid[tile.uuid] = tile.position

    # ADD: Difficult terrain at wall ends (3x3 zones)
    # Top of wall: x: 6-8, y: 0-2
    for x in range(6, 9):
        for y in range(0, 3):
            tile = difficult_terrain_factory((x, y))
            grid._tiles[tile.position] = tile
            grid._tiles_by_uuid[tile.uuid] = tile.position
    # Bottom of wall: x: 6-8, y: 12-14
    for x in range(6, 9):
        for y in range(12, 15):
            tile = difficult_terrain_factory((x, y))
            grid._tiles[tile.position] = tile
            grid._tiles_by_uuid[tile.uuid] = tile.position

    # Whole arena is dark — torch is the only light source
    for tile in grid._tiles.values():
        tile.default_light = LightLevel.DARKNESS

    # Wall-mounted torches at dark side corners (visible on map, toggleable)
    create_wall_torch(position=(14, 1), owner_uuid=uuid4(), lit=True)
    create_wall_torch(position=(14, 13), owner_uuid=uuid4(), lit=True)

    # Create Hero based on character class
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
        # Default to fighter
        player = create_dex_fighter(name="Hero", position=player_position, faction="heroes")

    # Give hero a lit torch for exploring the dark side
    torch = create_torch(player.uuid)
    player.loot_item(torch)
    torch.ignite(player.uuid)

    # Add Greater Invisibility potion to all heroes for stealth testing
    potion = create_potion_of_greater_invisibility(player.uuid)
    player.loot_item(potion)

    # Healing potions on floor inside the spike zone
    for pot_pos in [(1, 12), (3, 13)]:
        hp_potion = create_healing_potion(uuid4(), heal_amount=10)
        grid.place_object(hp_potion.uuid, pot_pos)

    # Trap lever adjacent to spike zone (deactivates spikes)
    lever_action = PullLeverAction(
        source_entity_uuid=uuid4(), trap_handler_uuid=spike_handler.uuid, template=True
    )
    lever = TrapLever(
        source_entity_uuid=uuid4(), use_action_templates=[lever_action], charges=1
    )
    lever_pos = (5, 12)
    grid.place_object(lever.uuid, lever_pos)

    # Spell scrolls for sorcerer only
    if character_class == "sorcerer":
        scroll_mm1 = create_scroll_of_magic_missile(player.uuid, cast_level=1)
        scroll_mm2 = create_scroll_of_magic_missile(player.uuid, cast_level=1)  # Stacks with mm1
        scroll_fb3 = create_scroll_of_fireball(player.uuid, cast_level=3)
        scroll_fb5 = create_scroll_of_fireball(player.uuid, cast_level=5)
        player.loot_item(scroll_mm1)
        player.loot_item(scroll_mm2)  # Merges into mm1, stack_count=2
        player.loot_item(scroll_fb3)
        player.loot_item(scroll_fb5)

    # Create 3 specialized Skeletons (monsters faction) at different positions
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


def setup_aoe_test_arena(
    player_position: tuple = (2, 7),
    character_class: str = "sorcerer"
) -> Encounter:
    """
    Initialize arena for AoE spell testing.

    Layout:
    - 15x15 open grid (no walls blocking LOS)
    - Sorcerer at (2, 7)
    - 3 Goblins clustered at (12, 4), (12, 5), (12, 6) - within Fireball radius
    """
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()
    EventQueue.reset()

    # Create open grid (no walls for clean AoE testing)
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)
    # No walls - open arena for clear LOS

    # Create player based on character class
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
        # Default to fighter
        player = create_dex_fighter(name="Hero", position=player_position, faction="heroes")

    # Create 3 Goblins CLUSTERED for AoE testing
    # Vertical stack at x=12, y=4,5,6 - all within 20ft radius
    goblin_positions = [(12, 4), (12, 5), (12, 6)]
    goblins = []
    for i, pos in enumerate(goblin_positions):
        goblin = create_goblin(
            name=f"Goblin {i+1}",
            position=pos,
            faction="monsters"
        )
        goblins.append(goblin)

    # Register opportunity attack handlers
    add_opportunity_attack_handler(player)
    for goblin in goblins:
        add_opportunity_attack_handler(goblin)

    Entity.update_all_entities_senses(max_distance=20)

    # Create encounter with AI controllers for goblins
    encounter = Encounter(name="AoE Test Arena", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))

    for goblin in goblins:
        encounter.add_combatant(goblin, MeleeAIController(source_entity_uuid=goblin.uuid))

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


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Log request duration for every endpoint."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"  TIMING: {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.1f}ms)")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Log all HTTP errors with full detail to server console."""
    logger.error(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions with full traceback."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}:\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


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
# Fields inherited from BaseBlock/BaseObject — internal machinery, not object state
_BASE_BLOCK_FIELDS = set(BaseBlock.model_fields.keys()) | {
    'use_register', 'blocks_dict_name_uuid', 'blocks_dict_uuid_name',
    'values_dict_name_uuid', 'values_dict_uuid_name',
}

# Additional fields already serialized as top-level APIFloorObject fields
_ALREADY_SERIALIZED = {'uuid', 'name', 'map_char'}


def _get_floor_object_state(obj: BaseBlock) -> dict:
    """Extract object-specific state fields for API serialization.

    Dumps all fields defined on the object's class that aren't inherited
    BaseBlock/BaseObject internals or already top-level in APIFloorObject.
    """
    all_fields = set(type(obj).model_fields.keys())
    state_fields = all_fields - _BASE_BLOCK_FIELDS - _ALREADY_SERIALIZED
    return obj.model_dump(mode='json', include=state_fields)


# =============================================================================

@app.get("/state", response_model=APIGameState)
async def get_state():
    """Get full game state (grid, entities, encounter)."""
    grid = get_map()

    # Get active encounter
    encounter_data = None
    if sim.encounter:
        encounter_data = APIEncounter.create(sim.encounter)

    # Build floor objects list from GridMap
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
            "visible_cells": visible_positions,
            "visible_entities": [str(uuid) for uuid in entity.senses.entities.keys()],
            "seen_cells": [list(pos) for pos in entity.senses.seen],
            "sense_modes": [
                {"sense_type": sm.sense_type.value, "range_feet": sm.range_feet}
                for sm in entity.senses.get_sense_modes()
            ],
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


@app.get("/tile/{x}/{y}")
async def get_tile_info(x: int, y: int):
    """
    Get detailed information about a specific tile.

    Returns tile data including conditions, handlers, and entities at position.
    """
    grid = get_map()
    tile = grid.get_tile(x, y)

    if not tile:
        raise HTTPException(status_code=404, detail=f"No tile at ({x}, {y})")

    # Get entities at this position
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

    # Get objects at this position
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

    # Get handler names
    handler_names = [h.name for h in tile.event_handlers.values()]

    # Light level
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
        "events": [e.model_dump(mode='json') for e in events],
        "count": len(events),
        "total": len(all_events),
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
    # AoE-specific fields
    if t.affected_entity_uuids:
        result["affected_entity_uuids"] = [str(uuid) for uuid in t.affected_entity_uuids]
    if t.affected_entity_names:
        result["affected_entity_names"] = t.affected_entity_names
    if t.affected_count is not None:
        result["affected_count"] = t.affected_count
    if t.affected_positions:
        result["affected_positions"] = [list(p) for p in t.affected_positions]
    # Hazard pathfinding fields
    if t.is_path_hazardous:
        result["is_path_hazardous"] = True
        if t.safe_path_cost is not None:
            result["safe_path_cost"] = t.safe_path_cost
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
    # Multi-target fields
    if a.num_projectiles is not None:
        result["num_projectiles"] = a.num_projectiles
    if a.allow_same_target is not None:
        result["allow_same_target"] = a.allow_same_target
    # Item use fields
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
    # Add handler details (private to acting entity)
    if actions.handler_details:
        result["handler_details"] = actions.handler_details

    # Add spell slots for spellcasters
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

    # Add custom resources (sorcery points, rage, second wind, etc.)
    if ae.resources:
        custom_resources = {}
        for res_name, resource in ae.resources.items():
            if res_name == "extra_attacks":
                continue  # Already exposed as extra_attacks_remaining
            custom_resources[res_name] = {
                "current": resource.current,
                "max": resource.maximum,
            }
        if custom_resources:
            result["resources"] = custom_resources

    return result


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

    # Cache for execute endpoint
    _available_actions_cache[entity_uuid] = actions

    return _serialize_available_actions(entity, actions)


@app.get("/entity/{entity_uuid}/handlers")
async def get_entity_handlers(entity_uuid: str):
    """Get all event handlers for an entity with their enabled state."""
    try:
        uuid_obj = UUID(entity_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    entity = Entity.get(uuid_obj)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

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
    return {"entity_uuid": entity_uuid, "handlers": handlers}


@app.post("/entity/{entity_uuid}/handlers/{handler_name}/toggle")
async def toggle_entity_handler(entity_uuid: str, handler_name: str, request: ToggleHandlerRequest):
    """Toggle a handler's enabled state by name.

    Validates that the session owns the entity and it's their turn.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Verify path entity_uuid matches request body
    if entity_uuid != request.entity_uuid:
        raise HTTPException(status_code=400, detail="Entity UUID mismatch")

    found = entity.set_handler_enabled(handler_name, request.enabled)
    if not found:
        raise HTTPException(status_code=404, detail=f"Handler '{handler_name}' not found")

    return {
        "success": True,
        "handler_name": handler_name,
        "enabled": request.enabled,
    }


@app.post("/action/end-turn")
async def end_human_turn(request: SimpleActionRequest):
    """End the session's entity turn and advance through AI turns."""
    _ = validate_session_action(request.session_id, request.entity_uuid)  # Validates session/entity

    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter")

    # Invalidate available actions cache (state changes on turn end)
    _available_actions_cache.clear()

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

    # Collect combat log entries (callback adds to encounter.combat_log automatically)
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

    # Collect combat log entries (callback adds to encounter.combat_log automatically)
    action_log_entries: list = []

    # Build event data for attacks using event.combat_log
    event_data = None
    if event and hasattr(event, 'attack_outcome') and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())
        # Pass through the full combat log data - CLI now supports new structure
        event_data = dict(event.combat_log.data)
        # Add target_hp for ActionResult
        event_data["target_hp"] = target.get_hp()

    # Death events are added to encounter.combat_log by callback
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
        # Check for scroll/item use actions (template_name contains __item_<uuid>)
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
                raise HTTPException(status_code=400, detail=str(e))

            # Invalidate cache after execution
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
                combat_log_entries=action_log_entries
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action_name}")

    # Accept POSITION_PATH (path-based like Move), POSITION_LOS (LOS-based like Jump), and POSITION_AOE (AoE spells)
    if template.target_type not in (TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
        raise HTTPException(
            status_code=400,
            detail=f"Action {request.action_name} is not a position action (is {template.target_type.value})"
        )

    # Track combat log length before action to capture all new entries
    log_start_index = len(sim.encounter.combat_log) if sim.encounter else 0

    try:
        # Execute via functional API
        pos = (request.position[0], request.position[1])  # Ensure Tuple[int, int]
        action_target = AvailableTarget(index=0, position=pos)
        event = execute_action(entity, request.action_name, action_target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for deaths
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Extract event data for movement/jump (callback adds to encounter.combat_log automatically)
    event_data = None
    if isinstance(event, (MovementEvent, JumpEvent)):
        if event.combat_log:
            event_data = dict(event.combat_log.data)
        else:
            # Fallback if no combat_log (shouldn't happen)
            event_data = {
                "entity_name": entity.name,
                "start_position": list(event.start_position),
                "end_position": list(event.end_position),
                "path": [list(p) for p in event.path] if event.path else []
            }
    elif template.target_type == TargetType.POSITION_AOE and event:
        # AoE spell - extract event data (callback adds to combat_log automatically)
        if event.combat_log:
            event_data = dict(event.combat_log.data)
        # Per-target logs are also added by callback via parent_event linkage

    # Death events are added to encounter.combat_log by callback

    # Collect ALL new combat log entries since action started (includes terrain damage, OAs, deaths)
    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)
            # Identify opportunity attacks (attack entries targeting the mover)
            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = dict(entry.data)
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    # Fallback: if no entries from combat_log, add primary event directly
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
        combat_log_entries=action_log_entries
    )


@app.post("/action/execute", response_model=ActionResult)
async def execute_action_by_index(request: ExecuteByIndexRequest):
    """Execute action by template name and target index.

    Enables 'attack 0', 'move 3' style commands from the available actions list.
    Uses cached available actions from the display call to avoid recomputing.
    """
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Use cached available actions from display call (avoid recomputing)
    available = _available_actions_cache.get(request.entity_uuid)
    if available is None:
        available = get_available_actions(entity)

    # Find action info to determine target type
    action_info = next(
        (a for a in available.all_actions if a.template_name == request.template_name),
        None
    )
    if action_info is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.template_name}")

    target_type = action_info.target_type

    # Track combat log length before action to capture all new entries
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
        raise HTTPException(status_code=400, detail=str(e))

    # Invalidate cache after execution (state changed)
    _available_actions_cache.pop(request.entity_uuid, None)

    # Check for deaths
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Re-compute available actions after execution so agent sees new options (Extra Attack etc.)
    updated_actions = None
    if not encounter_ended and entity.has_hp:
        new_available = get_available_actions(entity)
        _available_actions_cache[request.entity_uuid] = new_available
        updated_actions = _serialize_available_actions(entity, new_available)

    # Extract event_data and add main event to combat log
    event_data = None
    target_hp = None

    # Extract event_data for response (callback adds to encounter.combat_log automatically)
    if target_type == TargetType.ENTITY and event and event.combat_log:
        # Entity-targeting actions (attacks, shove, grapple, etc.)
        event_data = dict(event.combat_log.data)
        # Add target HP for attacks
        if hasattr(event, 'attack_outcome'):
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            target_hp = target.get_hp() if target else None
            event_data["target_hp"] = target_hp

    elif target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):
        # Movement actions (Move, Jump)
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
        # AoE spells (Fireball, Lightning Bolt, etc.)
        if event and event.combat_log:
            event_data = dict(event.combat_log.data)
        # Per-target logs are added by callback via parent_event linkage

    elif target_type == TargetType.MULTI_ENTITY:
        # Multi-target spells (Magic Missile)
        if event and event.combat_log:
            event_data = dict(event.combat_log.data)
        # Per-target logs are added by callback via parent_event linkage

    elif target_type == TargetType.SELF:
        # Self action
        if event and event.combat_log:
            event_data = dict(event.combat_log.data)
        elif event:
            event_data = {
                "entity_name": entity.name,
                "action_name": request.template_name,
            }

    # Death events are added to encounter.combat_log by callback

    # Collect ALL new combat log entries since action started (includes terrain damage, OAs, deaths)
    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)
            # Identify opportunity attacks (attack entries targeting the mover)
            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = dict(entry.data)
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    # Fallback: if no entries from combat_log, add primary event directly
    if not action_log_entries and event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

    # Build full game state snapshot
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

    # Compute shape at position (same as _compute_aoe_at_position but skip aoe_require_targets)
    shape = template.aoe_shape.model_copy(update={'target': pos})
    shape.compute_subjective(
        entity.position, entity.senses,
        fov_cache={}, barrier_positions=grid.get_barrier_positions(),
        caster_uuid=entity.uuid,
    )

    affected_uuids = list(shape.affected_entity_uuids)

    # Apply include_self filter
    if not template.include_self:
        affected_uuids = [uid for uid in affected_uuids if uid != entity.uuid]

    # Apply valid_target_filter
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

    # Filter dead entities
    if not template.include_dead:
        affected_uuids = [uid for uid in affected_uuids if (ent := Entity.get(uid)) and ent.has_hp]

    # Build names
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


@app.post("/simulation/start-aoe-test")
async def start_aoe_test():
    """
    Start arena configured for AoE spell testing.

    Layout:
    - Open 15x15 grid (no walls)
    - Sorcerer (hero) at (2, 7) with Fireball, Magic Missile, etc.
    - 3 Goblins clustered at (12, 4), (12, 5), (12, 6) - within Fireball radius
    """
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_aoe_test_arena(character_class="sorcerer")
    sim.paused = False
    sim.encounter.clear_combat_log()

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

    # Advance to first turn
    result = await advance_encounter()

    # Return hero UUID for client to join
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
        if entity.has_hp:
            factions[faction_key]["alive"] += 1

    if sim.encounter:
        current_entity = sim.encounter.get_current_entity()
        if current_entity:
            current_turn = current_entity.name
            is_hero_turn = hero_uuid and current_entity.uuid == hero_uuid
            is_skeleton_turn = skeleton_uuid and current_entity.uuid == skeleton_uuid

    # Check session connections
    # Claude is "connected" if they had activity in the last 5 seconds
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
