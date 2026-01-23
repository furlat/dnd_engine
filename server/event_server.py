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

from pydantic import Field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from dnd.core.events import Event, EventQueue, EventType, EventPhase
from dnd.core.gridmap import get_map, reset_map
from dnd.entity import Entity
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.monsters.bestiary import create_goblin, create_skeleton, create_goblin_archer
from dnd.controller import Controller, TurnContext, HumanController
from dnd.available_actions import get_available_actions
from dnd.actions import Attack, Move, Dash, Dodge, Disengage
from dnd.blocks.equipment import WeaponSlot
from dnd.core.base_actions import BaseAction
from dnd.reactions import add_opportunity_attack_handler

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter,
    APIGameState, APISimulationStatus,
    APICurrentTurn, MoveRequest, AttackRequest, SimpleActionRequest, ActionResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse
)
from server.session import (
    SessionManager, PlayerSession, GameSession,
    PlayerType, ConnectionStatus, get_session_manager
)


def extract_attack_data_from_event(event: Event, source: "Entity | None", target: "Entity | None", weapon_name: str) -> dict:
    """
    Extract standardized attack data from an AttackEvent.

    This helper ensures consistent attack data extraction for both
    player attacks and AI attacks, including modifier breakdowns.
    """
    attack_outcome = getattr(event, 'attack_outcome', None)
    damage_rolls = getattr(event, 'damage_rolls', None)
    dice_roll = getattr(event, 'dice_roll', None)
    ac_mv = getattr(event, 'ac', None)
    attack_bonus_mv = getattr(event, 'attack_bonus', None)

    # Extract d20 results
    all_d20_rolls = []
    d20_result = None
    advantage_status = "none"
    attack_bonus = 0

    if dice_roll:
        results = getattr(dice_roll, 'results', None)
        if isinstance(results, list):
            all_d20_rolls = list(results)
            if hasattr(dice_roll, 'advantage_status'):
                adv = dice_roll.advantage_status
                advantage_status = adv.value.lower() if hasattr(adv, 'value') else str(adv).lower()
                if len(results) >= 2:
                    if advantage_status == "advantage":
                        d20_result = max(results)
                    elif advantage_status == "disadvantage":
                        d20_result = min(results)
                    else:
                        d20_result = results[0]
                elif len(results) == 1:
                    d20_result = results[0]
        elif isinstance(results, int):
            all_d20_rolls = [results]
            d20_result = results
        attack_bonus = getattr(dice_roll, 'bonus', 0)

    # Get target AC
    target_ac = None
    if ac_mv:
        target_ac = ac_mv.normalized_score
    elif target:
        target_ac = target.equipment.ac_bonus().normalized_score

    # Calculate damage
    total_damage = sum(r.total for r in damage_rolls) if damage_rolls else 0
    outcome_str = attack_outcome.value if attack_outcome else "unknown"

    # Build damage roll details
    damage_details = []
    damage_dice_str = ""
    if damage_rolls:
        for dr in damage_rolls:
            damage_details.append({
                "dice": list(dr.results) if hasattr(dr, 'results') else [],
                "bonus": dr.bonus if hasattr(dr, 'bonus') else 0,
                "total": dr.total
            })
        # Build damage dice string
        if damage_rolls and hasattr(damage_rolls[0], 'results'):
            num_dice = len(damage_rolls[0].results) if isinstance(damage_rolls[0].results, list) else 1
            # Try to get dice size from weapon
            weapon_slot = getattr(event, 'weapon_slot', None)
            dice_size = 6
            if source and weapon_slot:
                weapon_obj = source.equipment._get_weapon_by_slot(weapon_slot)
                if weapon_obj and hasattr(weapon_obj, 'damage_dice'):
                    dice_size = weapon_obj.damage_dice
            damage_dice_str = f"{num_dice}d{dice_size}"

    # Extract modifier breakdowns
    attack_breakdown = []
    ac_breakdown = []
    damage_breakdown = []

    if attack_bonus_mv and hasattr(attack_bonus_mv, 'get_breakdown'):
        attack_breakdown = attack_bonus_mv.get_breakdown()

    if ac_mv and hasattr(ac_mv, 'get_breakdown'):
        ac_breakdown = ac_mv.get_breakdown()

    # Get damage bonus breakdown from event damages
    damages = getattr(event, 'damages', None)
    if damages:
        for dmg in damages:
            if hasattr(dmg, 'damage_bonus') and dmg.damage_bonus and hasattr(dmg.damage_bonus, 'get_breakdown'):
                damage_breakdown.extend(dmg.damage_bonus.get_breakdown())

    return {
        "attacker": source.name if source else "Unknown",
        "target": target.name if target else "Unknown",
        "weapon": weapon_name,
        "d20": d20_result,
        "all_d20_rolls": all_d20_rolls,
        "advantage_status": advantage_status,
        "attack_bonus": attack_bonus,
        "attack_total": dice_roll.total if dice_roll else None,
        "target_ac": target_ac,
        "outcome": outcome_str,
        "damage_rolls": damage_details,
        "total_damage": total_damage,
        "attack_breakdown": attack_breakdown,
        "ac_breakdown": ac_breakdown,
        "damage_breakdown": damage_breakdown,
        "damage_dice_str": damage_dice_str,
    }


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
# AI Controller
# =============================================================================

class ClaudeController(Controller):
    """
    Controller for Claude-controlled entities.

    Like HumanController, actions come via external API calls.
    Has its own controller_type for proper identification and debugging.
    """

    name: str = Field(default="Claude Controller")
    controller_type: str = Field(default="claude")

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional[BaseAction]:
        # Actions come via API, not from this method
        return None

    def can_continue_turn(self, entity: 'Entity', context: TurnContext) -> bool:
        # Return False to exit run_turn loop - server handles via API
        return False


class MeleeAIController(Controller):
    """
    Simple AI that moves toward enemies and attacks in melee.
    1. If enemy in weapon range -> Attack
    2. If can still attack after moving -> Move closer, then Attack
    3. Otherwise -> End turn
    """

    name: str = "Melee AI"
    controller_type: str = "melee_ai"

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional[BaseAction]:
        """Pick the next action based on available options."""
        available = get_available_actions(entity)

        # Priority 1: Attack if we can
        for attack in available.attacks:
            if attack.can_afford and attack.valid_targets:
                target_uuid = attack.valid_targets[0]
                return Attack(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=target_uuid,
                    weapon_slot=attack.weapon_slot or WeaponSlot.MELEE_MAIN,
                    name=f"{entity.name}'s Attack"
                )

        # Priority 2: Move toward enemy if we can still attack afterward
        can_still_attack = entity.action_economy.can_afford("actions", 1)
        if can_still_attack and available.can_move and available.movement:
            move_action = available.movement[0]

            # Find closest position to any enemy
            closest_pos = None
            closest_dist = float('inf')
            current_min_dist = float('inf')

            # Current distance to nearest enemy
            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue
                dist = abs(entity.position[0] - enemy_pos[0]) + abs(entity.position[1] - enemy_pos[1])
                if dist < current_min_dist:
                    current_min_dist = dist

            # Find position that gets us closer
            # (valid_positions already excludes occupied cells via GridMap.compute_paths)
            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue
                for pos in move_action.valid_positions:
                    dist = abs(pos[0] - enemy_pos[0]) + abs(pos[1] - enemy_pos[1])
                    if dist < closest_dist and dist < current_min_dist:
                        closest_dist = dist
                        closest_pos = pos

            if closest_pos and closest_pos != entity.position:
                return Move(
                    source_entity_uuid=entity.uuid,
                    end_position=closest_pos,
                    name=f"{entity.name}'s Movement"
                )

        # No good action, end turn
        return None


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

        # Server-side combat log - unified log for all players
        self._combat_log: list[dict] = []

    def add_combat_log(self, entry_type: str, message: str, details: Optional[dict] = None) -> int:
        """
        Add an entry to the combat log.

        Args:
            entry_type: Type of entry (attack, move, action, turn_start, turn_end, etc.)
            message: Human-readable message
            details: Optional dict with structured data (rolls, damage, etc.)

        Returns:
            The index of the new entry
        """
        entry = {
            "index": len(self._combat_log),
            "type": entry_type,
            "message": message,
            "details": details or {}
        }
        self._combat_log.append(entry)
        return entry["index"]

    def get_combat_log(self, since: int = 0) -> list[dict]:
        """Get combat log entries since a given index."""
        return self._combat_log[since:]

    def clear_combat_log(self):
        """Clear the combat log (call when starting new game)."""
        self._combat_log = []

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
    EventQueue._all_events.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()

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


def setup_combat_with_human(human_position: tuple = (2, 7), ai_position: tuple = (12, 7)) -> Encounter:
    """Initialize combat with one human-controlled entity vs one AI."""
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()  # Reset session manager
    EventQueue._all_events.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Add a vertical wall in the middle (blocking LOS)
    # Wall from (7, 3) to (7, 11) with a gap at (7, 7)
    for y in range(3, 12):
        if y != 7:  # Leave a gap in the middle for tactical play
            grid.set_tile(7, y, walkable=False, visible=False)

    # Create combatants - Hero is a Goblin Archer with ranged weapon
    player = create_goblin_archer(name="Hero", position=human_position)
    enemy = create_skeleton(name="Skeleton", position=ai_position)

    # Register opportunity attack handlers for both entities
    add_opportunity_attack_handler(player)
    add_opportunity_attack_handler(enemy)

    # Use larger vision range to cover the arena
    Entity.update_all_entities_senses(max_distance=20)

    # Create encounter with human + AI controllers
    encounter = Encounter(name="Arena Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))
    encounter.add_combatant(enemy, MeleeAIController(source_entity_uuid=enemy.uuid))

    return encounter


def setup_combat_pvp(player_position: tuple = (2, 7), opponent_position: tuple = (12, 7)) -> Encounter:
    """
    Initialize PvP combat where both entities are human-controlled.

    Player 1 (Hero) = controlled by user via CLI (Goblin Archer with ranged weapon)
    Player 2 (Skeleton) = controlled by Claude via agent CLI
    """
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()  # Reset session manager
    EventQueue._all_events.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Add a vertical wall in the middle (blocking LOS)
    for y in range(3, 12):
        if y != 7:  # Leave a gap in the middle
            grid.set_tile(7, y, walkable=False, visible=False)

    # Create combatants - Hero is now a Goblin Archer with ranged weapon
    player = create_goblin_archer(name="Hero", position=player_position)
    opponent = create_skeleton(name="Skeleton", position=opponent_position)

    # Register opportunity attack handlers
    add_opportunity_attack_handler(player)
    add_opportunity_attack_handler(opponent)

    Entity.update_all_entities_senses(max_distance=20)

    # PvP: Hero uses HumanController, Skeleton uses ClaudeController
    encounter = Encounter(name="PvP Arena", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))
    encounter.add_combatant(opponent, ClaudeController(source_entity_uuid=opponent.uuid))

    return encounter


async def advance_encounter() -> dict:
    """
    Advance encounter, auto-run AI turns, stop on human turn.

    Returns status dict indicating what happened, including AI actions.
    """
    if sim.encounter is None:
        return {"status": "no_encounter"}

    if sim.encounter.state == EncounterState.NOT_STARTED:
        sim.encounter.roll_initiative()
        sim.encounter.start_encounter()

    if sim.encounter.state == EncounterState.ENDED:
        return {"status": "encounter_ended"}

    # Track AI actions during this call
    ai_actions: list = []

    def capture_ai_event(event: Event) -> None:
        """Capture events during AI turn for logging."""
        # Only capture COMPLETION phase events (final state)
        if event.phase != EventPhase.COMPLETION:
            return

        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

        # Capture attack events (including opportunity attacks)
        if event_type == "attack":
            source = Entity.get(event.source_entity_uuid)
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None

            # Get weapon name from the event's weapon_slot
            weapon_name = "Unknown"
            if source:
                weapon_slot = getattr(event, 'weapon_slot', None)
                if weapon_slot:
                    weapon = source.equipment._get_weapon_by_slot(weapon_slot)
                    weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"
                else:
                    weapon_name = "Unarmed"

            # Use helper to extract all attack data including breakdowns
            attack_data = extract_attack_data_from_event(event, source, target, weapon_name)

            # Check if this was an opportunity attack
            is_opportunity_attack = "opportunity" in (event.name or "").lower()

            # Add type and message fields
            attack_data["type"] = "attack"
            attack_data["is_opportunity_attack"] = is_opportunity_attack
            attack_data["message"] = f"{attack_data['attacker']} attacks {attack_data['target']} with {weapon_name}: {attack_data['outcome']}" + (f" for {attack_data['total_damage']} damage!" if attack_data['outcome'].lower() in ("hit", "crit") else "")

            ai_actions.append(attack_data)

        # Capture movement events
        elif event_type == "movement":
            source = Entity.get(event.source_entity_uuid)
            start_pos = getattr(event, 'start_position', None)
            end_pos = getattr(event, 'end_position', None)
            path = getattr(event, 'path', None)

            if source and start_pos and end_pos:
                ai_actions.append({
                    "type": "move",
                    "entity": source.name,
                    "from": list(start_pos),
                    "to": list(end_pos),
                    "path": [list(p) for p in path] if path else [],
                    "message": f"{source.name} moves from {start_pos} to {end_pos}"
                })

    # Register callback to capture events
    EventQueue.add_on_event_callback(capture_ai_event)

    try:
        # Loop through turns until we hit a human
        while sim.encounter.state == EncounterState.ACTIVE:
            controller = sim.encounter.get_current_controller()

            if controller is None:
                return {"status": "error", "message": "No controller for current entity"}

            if controller.controller_type in ("human", "claude"):
                # Human or Claude turn - start it and wait for API input
                if sim.encounter.turn_state != TurnState.IN_PROGRESS:
                    sim.encounter.start_turn()

                entity = sim.encounter.get_current_entity()

                status = "waiting_for_human" if controller.controller_type == "human" else "waiting_for_claude"
                return {
                    "status": status,
                    "entity_uuid": str(entity.uuid) if entity else None,
                    "entity_name": entity.name if entity else None,
                    "round": sim.encounter.round_number,
                    "turn_index": sim.encounter.current_turn_index,
                    "ai_actions": ai_actions  # Include what AI did
                }

            else:
                # AI turn - run it completely
                ai_entity = sim.encounter.get_current_entity()
                ai_actions.append({
                    "type": "turn_start",
                    "entity": ai_entity.name if ai_entity else "Unknown",
                    "message": f"{ai_entity.name if ai_entity else 'Unknown'}'s turn"
                })

                sim.encounter.run_turn()

                if not sim.auto_run_ai:
                    # Manual stepping mode - return after each AI turn
                    return {
                        "status": "ai_turn_complete",
                        "round": sim.encounter.round_number,
                        "turn_index": sim.encounter.current_turn_index,
                        "ai_actions": ai_actions
                    }

                # Brief delay for AI turns (only in auto mode)
                await asyncio.sleep(sim.turn_delay)

        return {"status": "encounter_ended", "ai_actions": ai_actions}

    finally:
        # Always remove the callback
        EventQueue.remove_on_event_callback(capture_ai_event)


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
    Get combat log entries.

    Args:
        since: Only return entries with index >= since (for polling)

    Returns:
        List of log entries with index, type, message, and details
    """
    entries = sim.get_combat_log(since)
    return {
        "entries": entries,
        "count": len(entries),
        "total": len(sim._combat_log)
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

    If entity_uuids is provided, assigns those entities to the session.
    Otherwise, auto-assigns based on player type (human gets Hero, claude gets Skeleton).
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
        # Assign specific entities
        for uuid_str in request.entity_uuids:
            try:
                entity_uuid = UUID(uuid_str)
                if game.assign_entity(entity_uuid, session.session_id):
                    assigned.append(str(entity_uuid))
            except ValueError:
                pass  # Skip invalid UUIDs
    else:
        # Auto-assign based on player type and entity name
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

    # Convert to JSON-serializable format
    # AvailableActionsResult has UUIDs and tuples that need conversion
    return {
        "entity_uuid": str(actions.entity_uuid),
        "attacks": [
            {
                **a.model_dump(),
                "valid_targets": [str(t) for t in a.valid_targets],
                "valid_positions": [list(p) for p in a.valid_positions]
            }
            for a in actions.attacks
        ],
        "movement": [
            {
                **a.model_dump(),
                "valid_targets": [str(t) for t in a.valid_targets],
                "valid_positions": [list(p) for p in a.valid_positions]
            }
            for a in actions.movement
        ],
        "other_actions": [a.model_dump() for a in actions.other_actions],
        "bonus_actions": [a.model_dump() for a in actions.bonus_actions],
        "reactions": [a.model_dump() for a in actions.reactions],
        "free_actions": [a.model_dump() for a in actions.free_actions],
        "can_attack": actions.can_attack,
        "can_move": actions.can_move,
        "remaining_movement": actions.remaining_movement,
        "blocking_conditions": actions.blocking_conditions
    }


@app.post("/action/move", response_model=ActionResult)
async def execute_move(request: MoveRequest):
    """Execute a move action for the session's entity."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Track opportunity attacks triggered by this movement
    triggered_reactions: list = []

    def capture_opportunity_attack(event: Event) -> None:
        """Capture attack events targeting the moving entity (opportunity attacks)."""
        if event.phase != EventPhase.COMPLETION:
            return

        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

        # Only capture attacks targeting the moving entity
        if event_type == "attack" and event.target_entity_uuid == entity.uuid:
            source = Entity.get(event.source_entity_uuid)

            # Get weapon name from the event's weapon_slot
            weapon_name = "Unknown"
            if source:
                weapon_slot = getattr(event, 'weapon_slot', None)
                if weapon_slot:
                    weapon = source.equipment._get_weapon_by_slot(weapon_slot)
                    weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"
                else:
                    weapon_name = "Unarmed"

            # Use helper to extract all attack data including breakdowns
            reaction_data = extract_attack_data_from_event(event, source, entity, weapon_name)
            reaction_data["type"] = "opportunity_attack"
            reaction_data["is_opportunity_attack"] = True
            triggered_reactions.append(reaction_data)

    # Register callback before move
    EventQueue.add_on_event_callback(capture_opportunity_attack)

    try:
        # Create and execute move
        move = Move(
            source_entity_uuid=entity.uuid,
            end_position=tuple(request.position),
            name=f"{entity.name} moves"
        )

        event = move.apply()
    finally:
        # Always remove the callback
        EventQueue.remove_on_event_callback(capture_opportunity_attack)

    # Check for deaths - DeathEvent has entity_name attribute
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Extract event data safely (including path for display)
    event_data = None
    if event and hasattr(event, 'start_position') and hasattr(event, 'end_position'):
        event_data = {
            "entity": entity.name,  # Include entity name for consistent logging
            "start": list(event.start_position),
            "end": list(event.end_position),
            "path": [list(p) for p in event.path] if hasattr(event, 'path') and event.path else []
        }

        # Add to combat log
        sim.add_combat_log("move", f"{entity.name} moves to {tuple(event.end_position)}.", {
            "entity": entity.name,
            "from": list(event.start_position),
            "to": list(event.end_position)
        })

        # Log opportunity attacks that were triggered
        for reaction in triggered_reactions:
            attacker = reaction.get("attacker", "Unknown")
            target_name = reaction.get("target", entity.name)
            d20 = reaction.get("d20", "?")
            all_d20_rolls = reaction.get("all_d20_rolls", [])
            adv_status = reaction.get("advantage_status", "none")
            atk_bonus = reaction.get("attack_bonus", 0)
            atk_total = reaction.get("attack_total", "?")
            target_ac = reaction.get("target_ac", "?")
            outcome = reaction.get("outcome", "unknown")
            total_dmg = reaction.get("total_damage", 0)

            bonus_str = f"+{atk_bonus}" if atk_bonus >= 0 else str(atk_bonus)
            if adv_status == "advantage" and len(all_d20_rolls) >= 2:
                roll_str = f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20}){bonus_str}={atk_total}"
            elif adv_status == "disadvantage" and len(all_d20_rolls) >= 2:
                roll_str = f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20}){bonus_str}={atk_total}"
            else:
                roll_str = f"d20({d20}){bonus_str}={atk_total}"

            if outcome == "crit":
                oa_msg = f"(OA) {attacker} CRITS {target_name}! {roll_str} vs AC {target_ac} → {total_dmg} damage!"
            elif outcome == "hit":
                oa_msg = f"(OA) {attacker} hits {target_name}. {roll_str} vs AC {target_ac} → {total_dmg} damage"
            else:
                oa_msg = f"(OA) {attacker} misses {target_name}. {roll_str} vs AC {target_ac}"

            sim.add_combat_log("opportunity_attack", oa_msg, reaction)

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or ("Moved successfully" if event and not event.canceled else "Move failed"),
        event_type="movement",
        event_data=event_data,
        entity_hp=entity.get_hp(),
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended,
        encounter_ended=encounter_ended
    )


@app.post("/action/attack", response_model=ActionResult)
async def execute_attack(request: AttackRequest):
    """Execute an attack action for the session's entity."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    try:
        target_uuid = UUID(request.target_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target UUID format")

    target = Entity.get(target_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    # Parse weapon slot - support both old API (main_hand/off_hand) and new slot names
    slot_mapping = {
        "main_hand": WeaponSlot.MELEE_MAIN,      # Backward compat
        "off_hand": WeaponSlot.MELEE_OFF,        # Backward compat
        "melee_main": WeaponSlot.MELEE_MAIN,
        "melee_off": WeaponSlot.MELEE_OFF,
        "ranged_main": WeaponSlot.RANGED_MAIN,
        "ranged_off": WeaponSlot.RANGED_OFF,
    }
    slot = slot_mapping.get(request.weapon_slot.lower(), WeaponSlot.MELEE_MAIN)

    # Get weapon name before attack
    weapon = entity.equipment._get_weapon_by_slot(slot)
    weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"

    # Create and execute attack
    attack = Attack(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=slot,
        name=f"{entity.name} attacks {target.name}"
    )

    event = attack.apply()

    # Check for deaths - DeathEvent has entity_name attribute
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_names = [d.entity_name for d in deaths]

    # Check if encounter ended
    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    # Build detailed event data using helper
    event_data = None
    if event:
        # Use helper to extract all attack data including breakdowns
        event_data = extract_attack_data_from_event(event, entity, target, weapon_name)

        # Add legacy fields for backwards compat
        event_data["roll"] = event_data.get("attack_total")
        event_data["damage"] = event_data.get("total_damage", 0)

        # Build log message
        attack_bonus = event_data.get("attack_bonus", 0)
        all_d20_rolls = event_data.get("all_d20_rolls", [])
        d20_result = event_data.get("d20")
        advantage_status = event_data.get("advantage_status", "none")
        target_ac = event_data.get("target_ac", 0)
        total_damage = event_data.get("total_damage", 0)
        attack_total = event_data.get("attack_total", 0)
        outcome_str = (event_data.get("outcome") or "unknown").lower()

        bonus_str = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)
        if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
            roll_str = f"ADV d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20_result}){bonus_str}={attack_total}"
        elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
            roll_str = f"DIS d20({all_d20_rolls[0]},{all_d20_rolls[1]}→{d20_result}){bonus_str}={attack_total}"
        else:
            roll_str = f"d20({d20_result}){bonus_str}={attack_total}"

        if outcome_str == "crit":
            log_msg = f"{entity.name} CRITS {target.name}! {roll_str} vs AC {target_ac} → {total_damage} damage!"
        elif outcome_str == "hit":
            log_msg = f"{entity.name} hits {target.name}. {roll_str} vs AC {target_ac} → {total_damage} damage"
        elif outcome_str == "crit miss":
            log_msg = f"{entity.name} critically misses {target.name}! {roll_str} vs AC {target_ac}"
        else:
            log_msg = f"{entity.name} misses {target.name}. {roll_str} vs AC {target_ac}"

        # Add target HP for combat log
        log_data = dict(event_data)
        log_data["target_hp"] = target.get_hp()
        sim.add_combat_log("attack", log_msg, log_data)

        # Log deaths
        for death_name in death_names:
            sim.add_combat_log("death", f"{death_name} has been defeated!", {"entity": death_name})

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Attack executed",
        event_type="attack",
        event_data=event_data,
        entity_hp=entity.get_hp(),
        target_hp=target.get_hp(),
        deaths=death_names,
        turn_continues=not encounter_ended,
        encounter_ended=encounter_ended
    )


@app.post("/action/dash", response_model=ActionResult)
async def execute_dash(request: SimpleActionRequest):
    """Execute a dash action for the session's entity."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    dash = Dash(source_entity_uuid=entity.uuid)
    event = dash.apply()

    # Add to combat log
    sim.add_combat_log("action", f"{entity.name} takes the Dash action.", {"entity": entity.name, "action": "dash"})

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Dashed",
        event_type="dash",
        entity_hp=entity.get_hp(),
        turn_continues=True,
        encounter_ended=False
    )


@app.post("/action/dodge", response_model=ActionResult)
async def execute_dodge(request: SimpleActionRequest):
    """Execute a dodge action for the session's entity."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    dodge = Dodge(source_entity_uuid=entity.uuid)
    event = dodge.apply()

    # Add to combat log
    sim.add_combat_log("action", f"{entity.name} takes the Dodge action.", {"entity": entity.name, "action": "dodge"})

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Dodging",
        event_type="dodge",
        entity_hp=entity.get_hp(),
        turn_continues=True,
        encounter_ended=False
    )


@app.post("/action/disengage", response_model=ActionResult)
async def execute_disengage(request: SimpleActionRequest):
    """Execute a disengage action for the session's entity."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    disengage = Disengage(source_entity_uuid=entity.uuid)
    event = disengage.apply()

    # Add to combat log
    sim.add_combat_log("action", f"{entity.name} takes the Disengage action.", {"entity": entity.name, "action": "disengage"})

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Disengaging",
        event_type="disengage",
        entity_hp=entity.get_hp(),
        turn_continues=True,
        encounter_ended=False
    )


@app.post("/action/end-turn")
async def end_human_turn(request: SimpleActionRequest):
    """End the session's entity turn and advance to next."""
    entity = validate_session_action(request.session_id, request.entity_uuid)

    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter")

    # Add to combat log
    sim.add_combat_log("turn_end", f"{entity.name} ends their turn.", {"entity": entity.name})

    # End the turn
    sim.encounter.end_turn()

    # Advance turn index (session state is derived, no need to clear manually)
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED

    # Advance encounter (runs AI turns until next human or end)
    result = await advance_encounter()

    return result


@app.post("/simulation/start-human")
async def start_human_simulation():
    """
    Start a new combat with human control (player vs AI).

    This creates a game session and auto-assigns entities:
    - Hero goes to the first human session that joins
    - Skeleton is controlled by AI
    """
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_combat_with_human()
    sim.paused = False
    sim.clear_combat_log()  # Clear combat log for new game

    # Create game session
    game = sim.create_game_session(sim.encounter)

    # Create AI session for the Skeleton
    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Skeleton")
    game.add_player(ai_session)

    # Assign Skeleton to AI
    for entity in Entity.get_all_entities():
        if entity.name == "Skeleton":
            game.assign_entity(entity.uuid, ai_session.session_id)
            break

    # Advance to first turn (may be human or AI)
    result = await advance_encounter()

    # Return info about which entity needs a human session
    hero_uuid = None
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
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
async def start_pvp_simulation():
    """
    Start PvP combat where both entities are human-controlled.

    Player 1 (Hero) = controlled by user via CLI (PlayerType.HUMAN)
    Player 2 (Skeleton) = controlled by Claude via agent CLI (PlayerType.CLAUDE)

    Both players create sessions and join to control their entities.
    """
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_combat_pvp()
    sim.paused = False
    sim.clear_combat_log()  # Clear combat log for new game

    # Create game session
    game = sim.create_game_session(sim.encounter)

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
    Get PvP game status including session connections.

    Used by CLIs to check game state and who's connected.
    """
    game = sim.game

    # Determine whose turn it is
    current_turn = None
    is_hero_turn = False
    is_skeleton_turn = False
    hero_uuid = None
    skeleton_uuid = None

    # Get entity UUIDs
    for entity in Entity.get_all_entities():
        if entity.name == "Hero":
            hero_uuid = entity.uuid
        elif entity.name == "Skeleton":
            skeleton_uuid = entity.uuid

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
        "skeleton_uuid": str(skeleton_uuid) if skeleton_uuid else None
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
