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
from dnd.controller import Controller, TurnContext, HumanController
from dnd.available_actions import get_available_actions
from dnd.actions import Attack, Move, Dash, Dodge, Disengage
from dnd.blocks.equipment import WeaponSlot
from dnd.core.base_actions import BaseAction
from dnd.reactions import add_opportunity_attack_handler

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter,
    APIGameState, APISimulationStatus,
    APICurrentTurn, MoveRequest, AttackRequest, SimpleActionRequest, ActionResult
)


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
                    weapon_slot=attack.weapon_slot or WeaponSlot.MAIN_HAND,
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

        # Human turn tracking
        self.waiting_for_human: bool = False
        self.human_entity_uuid: Optional[UUID] = None


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

    # Create combatants
    player = create_goblin(name="Hero", position=human_position)
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
            attack_outcome = getattr(event, 'attack_outcome', None)
            damage_rolls = getattr(event, 'damage_rolls', None)
            dice_roll = getattr(event, 'dice_roll', None)
            ac_mv = getattr(event, 'ac', None)
            source = Entity.get(event.source_entity_uuid)
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None

            # Get weapon name
            weapon_name = "Unknown"
            if source:
                weapon = source.equipment.weapon_main_hand
                weapon_name = weapon.name if weapon else "Unarmed"

            # Extract d20 results - may have multiple rolls for advantage/disadvantage
            all_d20_rolls = []
            d20_result = None
            advantage_status = "none"
            attack_bonus = 0
            if dice_roll:
                results = getattr(dice_roll, 'results', None)
                if isinstance(results, list):
                    all_d20_rolls = list(results)
                    # The "used" roll depends on advantage status
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

            # Build damage breakdown
            damage_details = []
            if damage_rolls:
                for dr in damage_rolls:
                    damage_details.append({
                        "dice": dr.results if hasattr(dr, 'results') else [],
                        "bonus": dr.bonus if hasattr(dr, 'bonus') else 0,
                        "total": dr.total
                    })

            # Check if this was an opportunity attack
            is_opportunity_attack = "opportunity" in (event.name or "").lower()

            ai_actions.append({
                "type": "attack",
                "is_opportunity_attack": is_opportunity_attack,
                "attacker": source.name if source else "Unknown",
                "target": target.name if target else "Unknown",
                "weapon": weapon_name,
                "d20": d20_result,
                "all_d20_rolls": all_d20_rolls,  # Both rolls for advantage/disadvantage
                "advantage_status": advantage_status,  # "none", "advantage", "disadvantage"
                "attack_bonus": attack_bonus,
                "attack_total": dice_roll.total if dice_roll else None,
                "target_ac": target_ac,
                "outcome": outcome_str,
                "damage_rolls": damage_details,
                "total_damage": total_damage,
                "message": f"{source.name if source else 'Unknown'} attacks {target.name if target else 'Unknown'} with {weapon_name}: {outcome_str}" + (f" for {total_damage} damage!" if outcome_str.lower() in ("hit", "crit") else "")
            })

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

            if controller.controller_type == "human":
                # Human turn - start it and wait for input
                if sim.encounter.turn_state != TurnState.IN_PROGRESS:
                    sim.encounter.start_turn()

                entity = sim.encounter.get_current_entity()
                sim.waiting_for_human = True
                sim.human_entity_uuid = entity.uuid if entity else None

                return {
                    "status": "waiting_for_human",
                    "entity_uuid": str(sim.human_entity_uuid) if sim.human_entity_uuid else None,
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


def validate_human_action(entity_uuid_str: str) -> Entity:
    """
    Validate that it's the specified human's turn.

    Args:
        entity_uuid_str: UUID string of the entity trying to act

    Returns:
        The Entity object if valid

    Raises:
        HTTPException if invalid
    """
    if not sim.waiting_for_human:
        raise HTTPException(status_code=400, detail="Not waiting for human input")

    try:
        entity_uuid = UUID(entity_uuid_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    if sim.human_entity_uuid != entity_uuid:
        raise HTTPException(status_code=403, detail="Not this entity's turn")

    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter")

    if sim.encounter.turn_state != TurnState.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Turn not in progress")

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

    return APICurrentTurn(
        encounter_active=sim.encounter.state == EncounterState.ACTIVE,
        round_number=sim.encounter.round_number,
        turn_index=sim.encounter.current_turn_index,
        current_entity_uuid=str(entity.uuid) if entity else None,
        current_entity_name=entity.name if entity else None,
        is_human_turn=controller.controller_type == "human" if controller else False,
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
    """Execute a move action for the current human."""
    entity = validate_human_action(request.entity_uuid)

    # Track opportunity attacks triggered by this movement
    triggered_reactions: list = []

    def capture_opportunity_attack(event: Event) -> None:
        """Capture attack events targeting the moving entity (opportunity attacks)."""
        if event.phase != EventPhase.COMPLETION:
            return

        event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

        # Only capture attacks targeting the moving entity
        if event_type == "attack" and event.target_entity_uuid == entity.uuid:
            attack_outcome = getattr(event, 'attack_outcome', None)
            damage_rolls = getattr(event, 'damage_rolls', None)
            dice_roll = getattr(event, 'dice_roll', None)
            ac_mv = getattr(event, 'ac', None)
            source = Entity.get(event.source_entity_uuid)

            # Get weapon name
            weapon_name = "Unknown"
            if source:
                weapon = source.equipment.weapon_main_hand
                weapon_name = weapon.name if weapon else "Unarmed"

            # Extract d20 results - may have multiple rolls for advantage/disadvantage
            all_d20_rolls = []
            d20_result = None
            advantage_status = "none"
            attack_bonus = 0
            if dice_roll:
                results = getattr(dice_roll, 'results', None)
                if isinstance(results, list):
                    all_d20_rolls = list(results)
                    # The "used" roll depends on advantage status
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
            target_ac = ac_mv.normalized_score if ac_mv else entity.equipment.ac_bonus().normalized_score

            # Calculate damage
            total_damage = sum(r.total for r in damage_rolls) if damage_rolls else 0
            outcome_str = attack_outcome.value if attack_outcome else "unknown"

            # Build damage breakdown
            damage_details = []
            if damage_rolls:
                for dr in damage_rolls:
                    damage_details.append({
                        "dice": dr.results if hasattr(dr, 'results') else [],
                        "bonus": dr.bonus if hasattr(dr, 'bonus') else 0,
                        "total": dr.total
                    })

            triggered_reactions.append({
                "type": "opportunity_attack",
                "attacker": source.name if source else "Unknown",
                "target": entity.name,
                "weapon": weapon_name,
                "d20": d20_result,
                "all_d20_rolls": all_d20_rolls,  # Both rolls for advantage/disadvantage
                "advantage_status": advantage_status,  # "none", "advantage", "disadvantage"
                "attack_bonus": attack_bonus,
                "attack_total": dice_roll.total if dice_roll else None,
                "target_ac": target_ac,
                "outcome": outcome_str,
                "damage_rolls": damage_details,
                "total_damage": total_damage
            })

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
            "start": list(event.start_position),
            "end": list(event.end_position),
            "path": [list(p) for p in event.path] if hasattr(event, 'path') and event.path else []
        }

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
    """Execute an attack action for the current human."""
    entity = validate_human_action(request.entity_uuid)

    try:
        target_uuid = UUID(request.target_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target UUID format")

    target = Entity.get(target_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    # Parse weapon slot
    slot = WeaponSlot.MAIN_HAND if request.weapon_slot == "main_hand" else WeaponSlot.OFF_HAND

    # Get weapon name before attack
    weapon = entity.equipment.weapon_main_hand if slot == WeaponSlot.MAIN_HAND else entity.equipment.weapon_off_hand
    weapon_name = weapon.name if weapon else "Unarmed"

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

    # Build detailed event data
    event_data = None
    if event:
        attack_outcome = getattr(event, 'attack_outcome', None)
        dice_roll = getattr(event, 'dice_roll', None)
        damage_rolls = getattr(event, 'damage_rolls', None)
        ac_mv = getattr(event, 'ac', None)
        attack_bonus_mv = getattr(event, 'attack_bonus', None)

        # Extract d20 results - may have multiple rolls for advantage/disadvantage
        all_d20_rolls = []
        d20_result = None
        advantage_status = "none"
        if dice_roll and hasattr(dice_roll, 'results'):
            results = dice_roll.results
            if isinstance(results, list):
                all_d20_rolls = list(results)
                # The "used" roll depends on advantage status
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

        # Get attack bonus
        attack_bonus = dice_roll.bonus if dice_roll else 0

        # Get target AC
        target_ac = ac_mv.normalized_score if ac_mv else target.equipment.ac_bonus().normalized_score

        # Build damage breakdown
        damage_details = []
        total_damage = 0
        if damage_rolls:
            for dr in damage_rolls:
                damage_details.append({
                    "dice": dr.results if hasattr(dr, 'results') else [],
                    "bonus": dr.bonus if hasattr(dr, 'bonus') else 0,
                    "total": dr.total
                })
                total_damage += dr.total

        event_data = {
            "attacker": entity.name,
            "target": target.name,
            "weapon": weapon_name,
            "d20": d20_result,
            "all_d20_rolls": all_d20_rolls,  # Both rolls for advantage/disadvantage
            "advantage_status": advantage_status,  # "none", "advantage", "disadvantage"
            "attack_bonus": attack_bonus,
            "attack_total": dice_roll.total if dice_roll else None,
            "target_ac": target_ac,
            "outcome": attack_outcome.value if attack_outcome else None,
            "damage_rolls": damage_details,
            "total_damage": total_damage,
            # Legacy fields for backwards compat
            "roll": dice_roll.total if dice_roll else None,
            "damage": total_damage
        }

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
    """Execute a dash action for the current human."""
    entity = validate_human_action(request.entity_uuid)

    dash = Dash(source_entity_uuid=entity.uuid)
    event = dash.apply()

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
    """Execute a dodge action for the current human."""
    entity = validate_human_action(request.entity_uuid)

    dodge = Dodge(source_entity_uuid=entity.uuid)
    event = dodge.apply()

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
    """Execute a disengage action for the current human."""
    entity = validate_human_action(request.entity_uuid)

    disengage = Disengage(source_entity_uuid=entity.uuid)
    event = disengage.apply()

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
    """End the current human's turn and advance to next."""
    _ = validate_human_action(request.entity_uuid)

    if sim.encounter is None:
        raise HTTPException(status_code=400, detail="No active encounter")

    # End the turn
    sim.encounter.end_turn()

    # Clear human waiting state
    sim.waiting_for_human = False
    sim.human_entity_uuid = None

    # Advance turn index
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED

    # Advance encounter (runs AI turns until next human or end)
    result = await advance_encounter()

    return result


@app.post("/simulation/start-human")
async def start_human_simulation():
    """Start a new combat with human control (player vs AI)."""
    # Cancel existing task
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    sim.encounter = setup_combat_with_human()
    sim.paused = False
    sim.waiting_for_human = False
    sim.human_entity_uuid = None

    # Advance to first turn (may be human or AI)
    result = await advance_encounter()

    return {
        "status": "started",
        "encounter_uuid": str(sim.encounter.uuid),
        **result
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
