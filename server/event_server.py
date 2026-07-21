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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Set, Optional
from uuid import UUID, uuid4
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("dnd_server")

from dnd.core.events import BodyPart, Event, EventQueue, EventType, EventPhase, RingSlot
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
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
from dnd.scenarios.ai_validation_arenas import (
    create_ai_validation_arena,
    list_ai_validation_arena_specs,
)
from dnd.scenarios.evaluation.assembler import (
    IncompatibleScenarioError,
    assemble_composed_scenario,
    assemble_legacy_scenario,
)
from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS, get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
    get_combatant_configuration,
)
from dnd.scenarios.evaluation.compatibility import CompatibilityReport, check_compatibility
from dnd.scenarios.evaluation.deployment_catalog import DEPLOYMENTS, get_deployment
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES, get_legacy_recipe
from dnd.scenarios.evaluation.wardrobes import (
    BERSERKER_WARDROBE,
    BESTIARY_WARDROBES,
    equip_wardrobe,
)
from dnd.blocks.equipment import WeaponSlot
from dnd.controller import Controller, HumanController, CodexController, ExternalAIController
from dnd.actions_functional import execute_available_action, get_available_actions, execute_action, execute_use_action
from ai.runtime_performance import latency_sensitive_gc
from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.actions import MovementEvent, JumpEvent
from dnd.core.base_actions import (
    AvailableActionsResult,
    AvailableHandlerInfo,
    AvailableTarget,
    TargetType,
)
from dnd.core.base_block import BaseBlock
from dnd.core.action_execution import movement_continuation_scope
from dnd.reactions import add_opportunity_attack_handler

from server.api_models import (
    APIEntitySummary, APIEntityFull, APIGrid, APIEncounter, APIFloorObject,
    APIAvailableActions, APIEntityListResponse, APIEntityVisibility, APIServerTiming,
    APIVisibilityResponse,
    APIGameState, APISimulationStatus,
    APICurrentTurn, SimpleActionRequest, ActionResult, AoEPreviewResult,
    CreateSessionRequest, CreateSessionResponse, SessionPingResponse,
    JoinGameRequest, JoinGameResponse,
    GameCreationCatalogResponse, GameCreationComposedScenario,
    GameCreationPreflightRequest, GameCreationPreset, GameCreationPresetScenario,
    GameCreationSideRequest, GameCreationSideResult,
    GameCreationStartRequest, GameCreationStartResponse,
    EventContractSummary, EventHistoryResponse, CombatLogHistoryResponse,
    SelfActionRequest, EntityActionRequest, PositionActionRequest, ExecuteByIndexRequest,
    ToggleHandlerRequest,
    APIEquipmentOverview, APIItemSummary, APIEquippableItems, APIEntityHandlersResponse,
    EquipRequest, UnequipRequest, EquipmentMutationResult, ToggleHandlerResponse,
    AdvanceEncounterResult, StartHumanSimulationResponse,
    AgentSessionEntityRow, AgentSessionListResponse, AgentSessionRow,
    TakeoverClaimResponse, TakeoverEntityRow, TakeoverHeartbeatResponse, TakeoverListResponse,
    TakeoverReleaseResponse, TakeoverRequest,
    SpellCatalogResponse,
    MapEditorCatalog, MapEditorCreateMapRequest, MapEditorLightResponse, MapEditorMapSnapshot,
    MapEditorObjectDeleteRequest, MapEditorObjectPlaceRequest, MapEditorTilePatchRequest, MapEditorVisibilityResponse,
    MapEditorWalkabilityResponse, MapEditorSaveMapRequest, MapEditorSavedMapDocument,
    MapEditorSavedMapList, MapEditorSavedMapMetadata,
    ReplicationBootstrapResponse, ReplicationProtocolIdentity,
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
from server.request_timing import RequestTimingMiddleware
from server.spell_catalog import build_spell_catalog
from server.event_stream import (
    BoundedSubscription,
    EvictedPayload,
    HeartbeatPayload,
    StreamSyncPayload,
    event_stream,
    format_sse,
    make_stream_id,
)
from server.event_contract import (
    EVENT_CONTRACT_HASH,
    EVENT_CONTRACT_VERSION,
    event_contract_summary,
    serialize_event,
)
from server.agent_event_stream import agent_event_stream
from server.gauntlet_event_stream import gauntlet_event_stream
from server.action_serialization import serialize_available_actions
from server.session import (
    SessionManager, GameSession,
    PlayerSession, PlayerType, ConnectionStatus, get_session_manager
)
from ai.evaluation.gauntlet_contract import (
    GauntletEventIngestRequest,
    GauntletSummary,
    apply_gauntlet_latency_audit,
    project_live_watcher_state,
    project_watcher_state,
)
from server.ai_process_manager import AIProcessStartError, ExternalAIProcessManager
from server.ai_takeover_manager import AITakeoverManager, TakeoverClaim, TakeoverError
from ai.observation import (
    ObservationAccessError,
    ObservationFrame,
    ObservationFramesResponse,
    ObservationOwnershipBoundary,
    ObservationSnapshot,
    append_command_result_frame,
    append_decision_epoch_frame,
    append_epoch_clear_frame,
    build_observation_snapshot,
    clear_observation_projection_cache,
    get_observation_cursor,
    get_materialized_observation_world,
    iter_observation_frames,
    observation_wakeup_stream,
    prepare_observation_ownership_change,
    publish_observation_ownership_changes,
)
from ai.policy.source import PolicySourceSnapshot, policy_source_snapshot
from ai.protocol.control import (
    ActionAffordance,
    ActionResolutionStatus,
    AgentEndTurnCommandRequest,
    AgentExecuteCommandRequest,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
)
from ai.protocol.semantics import ActionTag
from ai.subjective.movement_revalidation import (
    SessionMovementContinuationGuard,
)
from ai.subjective.epochs import (
    ActionExecutionBinding,
    DecisionEpochExecutionAuthority,
    build_decision_epoch as build_subjective_decision_epoch,
    clear_epoch_value_caches,
)
from ai.subjective.models import (
    AgentEventHistoryResponse,
    AgentEventIngestRequest,
)

_available_actions_cache: Dict[str, AvailableActionsResult] = {}
_last_published_epoch_by_session: Dict[str, str] = {}
_current_epoch_by_session: Dict[str, DecisionEpoch] = {}
_execution_authority_by_epoch_id: Dict[str, DecisionEpochExecutionAuthority] = {}
ai_process_manager = ExternalAIProcessManager()
ai_takeover_manager = AITakeoverManager()


@dataclass
class _ServerCommandTiming:
    """Low-overhead phase timing for one server-side AI command."""

    command_type: str
    diagnostics_enabled: bool = False
    started_at: float = field(default_factory=time.perf_counter)
    phases: Dict[str, float] = field(default_factory=dict)
    phase_counts: Dict[str, int] = field(default_factory=dict)
    phase_max_ms: Dict[str, float] = field(default_factory=dict)

    def add(self, phase: str, started_at: float) -> None:
        """Add elapsed time to one named phase."""
        self.add_elapsed(phase, (time.perf_counter() - started_at) * 1000)

    def add_elapsed(self, phase: str, elapsed_ms: float) -> None:
        """Add a measured duration and retain its multiplicity and maximum."""
        self.phases[phase] = self.phases.get(phase, 0.0) + elapsed_ms
        self.phase_counts[phase] = self.phase_counts.get(phase, 0) + 1
        self.phase_max_ms[phase] = max(self.phase_max_ms.get(phase, 0.0), elapsed_ms)

    def payload(self) -> dict[str, Any]:
        """Return a JSON-friendly timing payload."""
        return {
            "command_type": self.command_type,
            "diagnostics_enabled": self.diagnostics_enabled,
            "total_ms": round((time.perf_counter() - self.started_at) * 1000, 3),
            "phases": {
                phase: round(elapsed_ms, 3)
                for phase, elapsed_ms in self.phases.items()
            },
            "phase_counts": dict(self.phase_counts),
            "phase_max_ms": {
                phase: round(elapsed_ms, 3)
                for phase, elapsed_ms in self.phase_max_ms.items()
            },
        }


def _prefixed_timing_recorder(
    timing: Optional[_ServerCommandTiming],
    prefix: str,
) -> Optional[Callable[[str, float], None]]:
    """Return a timing callback that records observation subphases."""
    if timing is None or not timing.diagnostics_enabled:
        return None

    def record(phase: str, started_at: float) -> None:
        timing.add(f"{prefix}.{phase}", started_at)

    return record


async def _first_subscription_envelope(
    subscriptions: list[BoundedSubscription],
    *,
    timeout: float,
) -> Optional[dict[str, Any]]:
    """Return the first live SSE envelope while cleaning up losing wait tasks."""
    tasks = [asyncio.create_task(subscription.get()) for subscription in subscriptions]
    try:
        done, _pending = await asyncio.wait(
            set(tasks),
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            return None
        return next(iter(done)).result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def clear_subjective_projection_state() -> None:
    """Clear subjective projection and epoch publication caches."""
    clear_observation_projection_cache()
    clear_epoch_value_caches()
    _last_published_epoch_by_session.clear()
    _current_epoch_by_session.clear()
    _execution_authority_by_epoch_id.clear()


def _store_current_epoch(session_id: str, epoch: DecisionEpoch) -> None:
    """Store one active epoch and release superseded private authority."""
    previous = _current_epoch_by_session.get(session_id)
    _current_epoch_by_session[session_id] = epoch
    if previous is not None and previous.epoch_id != epoch.epoch_id:
        _execution_authority_by_epoch_id.pop(previous.epoch_id, None)


def _forget_current_epoch(session_id: str) -> Optional[DecisionEpoch]:
    """Forget one active epoch and its private execution bindings."""
    epoch = _current_epoch_by_session.pop(session_id, None)
    if epoch is not None:
        _execution_authority_by_epoch_id.pop(epoch.epoch_id, None)
    return epoch


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
            event_data = serialize_event(event)

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
        ai_takeover_manager.clear(self.encounter, self._game_session)
        ai_process_manager.stop_all()
        clear_subjective_projection_state()
        agent_event_stream.clear_all()
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
        Encounter containing one goblin and one skeleton with external AI controllers.
    """
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    EventQueue.reset()
    event_stream.ensure_attached()

    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    goblin = equip_wardrobe(
        create_goblin(name="Goblin Scout", position=(2, 7)),
        BESTIARY_WARDROBES["goblin"],
    )
    skeleton = create_skeleton(name="Skeleton Warrior", position=(12, 7))
    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
    encounter.add_combatant(goblin, ExternalAIController(source_entity_uuid=goblin.uuid))
    encounter.add_combatant(skeleton, ExternalAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def setup_arena_combat(
    player_position: tuple = (2, 7),
    pvp_mode: bool = False,
    character_class: str = "fighter",
) -> Encounter:
    """Initialize arena combat with one hero against three skeletons.

    Args:
        player_position: Starting position for the hero.
        pvp_mode: Whether skeletons use Codex controllers instead of external AI.
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
            encounter.add_combatant(skeleton, ExternalAIController(source_entity_uuid=skeleton.uuid))

    return encounter


def prioritize_hero_opening_turn(encounter: Encounter) -> None:
    """Roll initiative but place the player hero first for human arena bootstrap."""
    encounter.roll_initiative()
    hero = next((entity for entity in Entity.get_all_entities() if entity.faction == "heroes"), None)
    if hero is None or hero.uuid not in encounter.initiative_order:
        return
    encounter.initiative_order = [
        hero.uuid,
        *[entity_uuid for entity_uuid in encounter.initiative_order if entity_uuid != hero.uuid],
    ]
    encounter.current_turn_index = 0


async def prepare_new_simulation_start() -> None:
    """Stop active automation and clear session-side projection state."""
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    ai_process_manager.stop_all()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()
    sim._game_session = None
    sim._session_manager.sessions.clear()
    sim._session_manager.games.clear()
    sim._session_manager.active_game = None
    _available_actions_cache.clear()
    sim.paused = False


def apply_validation_arena_controllers(encounter: Encounter, mode: str) -> None:
    """Swap passive validation controllers for a live validation mode.

    Args:
        encounter: Validation encounter returned by the scenario catalog.
        mode: Either ``human_hero`` or ``codex_monsters``.

    Raises:
        ValueError: If the mode is unknown.
    """
    if mode not in {"human_hero", "codex_monsters"}:
        raise ValueError(f"Unsupported validation mode: {mode}")

    for entity in Entity.get_all_entities():
        if entity.uuid not in encounter.combatants:
            continue
        if entity.faction == "heroes":
            controller = (
                HumanController(source_entity_uuid=entity.uuid)
                if mode == "human_hero"
                else ExternalAIController(source_entity_uuid=entity.uuid)
            )
        elif entity.faction == "monsters":
            controller = ExternalAIController(source_entity_uuid=entity.uuid)
        else:
            continue
        encounter.set_controller_for(entity.uuid, controller)


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
        equip_wardrobe(goblin, BESTIARY_WARDROBES["goblin"])
        goblins.append(goblin)

    add_opportunity_attack_handler(player)
    for goblin in goblins:
        add_opportunity_attack_handler(goblin)

    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="AoE Test Arena", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))

    for goblin in goblins:
        encounter.add_combatant(goblin, ExternalAIController(source_entity_uuid=goblin.uuid))

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
    return equip_wardrobe(create_barbarian(config), BERSERKER_WARDROBE)


async def advance_encounter(
    timing: Optional[_ServerCommandTiming] = None,
    *,
    publish_decision_epoch: bool = True,
) -> AdvanceEncounterResult:
    """Advance the encounter until a player-controlled turn or terminal state.

    Returns:
        Structured advancement result with AI combat-log entries and replication
        cursors.
    """
    if sim.encounter is None:
        return AdvanceEncounterResult(status="no_encounter")

    started = time.perf_counter()
    restore_expired_takeovers()
    if timing is not None:
        timing.add("advance.restore_expired_takeovers_ms", started)

    if sim.encounter.state == EncounterState.NOT_STARTED:
        if not sim.encounter.initiative_order:
            sim.encounter.roll_initiative()
        sim.encounter.start_encounter()

    if sim.encounter.state == EncounterState.ENDED:
        return AdvanceEncounterResult(
            status="encounter_ended",
            **action_cursor_fields(),
        )

    log_start = len(sim.encounter.combat_log)

    started = time.perf_counter()
    result = sim.encounter.advance_until_player()
    if timing is not None:
        timing.add("advance.advance_until_player_ms", started)

    if publish_decision_epoch:
        started = time.perf_counter()
        _publish_decision_epoch_for_active_session(
            DecisionEpochReason.TURN_START,
            timing=timing,
        )
        if timing is not None:
            timing.add("advance.publish_active_epoch_ms", started)

    started = time.perf_counter()
    new_entries = sim.encounter.get_combat_log(log_start)
    ai_actions = list(new_entries)
    if timing is not None:
        timing.add("advance.serialize_logs_ms", started)

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


def serialize_takeover_claim(claim: TakeoverClaim) -> TakeoverClaimResponse:
    """Serialize a takeover claim with current entity/controller context."""
    rows = []
    for entity_uuid in claim.entity_uuids:
        state = claim.entity_states[entity_uuid]
        entity = Entity.get(entity_uuid)
        previous_controller = Controller.get(state.previous_controller_uuid)
        current_controller = sim.encounter.get_controller_for(entity_uuid) if sim.encounter else None
        rows.append(TakeoverEntityRow(
            entity_uuid=str(entity_uuid),
            entity_name=entity.name if entity else "Unknown",
            faction=entity.faction if entity else None,
            previous_controller_uuid=str(state.previous_controller_uuid),
            previous_controller_type=previous_controller.controller_type if previous_controller else None,
            current_controller_type=current_controller.controller_type if current_controller else None,
            previous_owner_session_id=(
                str(state.previous_owner_session_id)
                if state.previous_owner_session_id else None
            ),
        ))
    return TakeoverClaimResponse(
        claim_id=str(claim.claim_id),
        session_id=str(claim.session_id),
        name=claim.name,
        faction=claim.faction,
        created_at=claim.created_at,
        last_heartbeat_at=claim.last_heartbeat_at,
        lease_seconds=claim.lease_seconds,
        expires_at=claim.expires_at,
        is_expired=claim.is_expired(),
        claimed_entities=rows,
    )


def restore_expired_takeovers() -> list[TakeoverClaim]:
    """Restore expired claims while preserving append-only subjective history."""
    boundary = prepare_observation_ownership_change(sim.get_session_manager())
    expired = ai_takeover_manager.restore_expired(sim.encounter, sim.game)
    if expired:
        _publish_takeover_ownership_changes(boundary, "takeover_expired")
    return expired


def _publish_takeover_ownership_changes(
    boundary: ObservationOwnershipBoundary,
    reason: str,
) -> list[str]:
    """Publish ownership replacements and reconcile affected decision epochs."""
    changed_session_ids = publish_observation_ownership_changes(
        boundary,
        reason=reason,
        session_manager=sim.get_session_manager(),
    )
    for session_id in changed_session_ids:
        current = _forget_current_epoch(session_id)
        _last_published_epoch_by_session.pop(session_id, None)
        if current is not None:
            append_epoch_clear_frame(
                session_id,
                reason=reason,
                session_manager=sim.get_session_manager(),
            )
    _publish_decision_epoch_for_active_session(DecisionEpochReason.RESYNC)
    return changed_session_ids


def _takeover_http_exception(error: TakeoverError, **context: Any) -> HTTPException:
    """Convert a takeover manager error to a structured HTTP exception."""
    return _api_http_exception(
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        **context,
    )


def _parse_optional_uuid(value: Optional[str], field_name: str) -> Optional[UUID]:
    """Parse an optional UUID request field."""
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise _api_http_exception(
            status_code=400,
            code=f"invalid_{field_name}",
            message=f"Invalid {field_name} UUID format",
            **{field_name: value},
        )


def _parse_uuid_list(values: Optional[list[str]], field_name: str) -> Optional[list[UUID]]:
    """Parse an optional list of UUID request fields."""
    if values is None:
        return None
    parsed = []
    for value in values:
        parsed_uuid = _parse_optional_uuid(value, field_name)
        if parsed_uuid is not None:
            parsed.append(parsed_uuid)
    return parsed


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


def _serialize_entity_handlers(entity: Entity) -> list[AvailableHandlerInfo]:
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
        handlers.append(AvailableHandlerInfo(
            name=handler.name,
            uuid=handler.uuid,
            enabled=handler.enabled,
            trigger_event=trigger_event,
        ))
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
        valid_handler_names=[handler.name for handler in handlers],
        handlers=[handler.model_dump(mode="json") for handler in handlers],
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


def _observation_http_exception(
    error: ObservationAccessError,
    session_id: Optional[str] = None,
) -> HTTPException:
    """Convert observation access errors into structured session errors."""
    status_code = 400 if error.code == "invalid_session_uuid" else 404
    return _session_http_exception(
        status_code=status_code,
        code=error.code,
        message=error.message,
        session_id=session_id,
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

    restore_expired_takeovers()
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
    with latency_sensitive_gc():
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
app.add_middleware(RequestTimingMiddleware)


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


def _build_public_state() -> APIGameState:
    """Build the canonical public state snapshot used by every client route."""
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
                position=obj_pos,
                map_char=map_char,
                state=_get_floor_object_state(obj),
            ))

    return APIGameState(
        grid=APIGrid.create(grid),
        entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
        encounter=encounter_data,
        floor_objects=floor_objects,
    )


def _build_visibility_state() -> APIVisibilityResponse:
    """Build the canonical observer-indexed visibility snapshot."""
    result: Dict[str, APIEntityVisibility] = {}
    for entity in Entity.get_all_entities():
        result[str(entity.uuid)] = APIEntityVisibility(
            name=entity.name,
            position=entity.position,
            visible_cells=[
                position
                for position, is_visible in entity.senses.visible.items()
                if is_visible
            ],
            visible_entities=[str(uuid) for uuid in entity.senses.entities],
            visible_objects=[str(uuid) for uuid in entity.senses.objects],
            seen_cells=list(entity.senses.seen),
            sense_modes=list(entity.senses.get_sense_modes()),
            effective_light_levels=entity.senses.get_effective_light_levels(entity.uuid),
        )
    return APIVisibilityResponse(root=result)


@app.get("/state", response_model=APIGameState)
async def get_state():
    """Return the canonical public game-state snapshot."""
    return _build_public_state()


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


@app.get("/entities", response_model=APIEntityListResponse)
async def get_entities():
    """Return lightweight summaries for all registered entities.

    Returns:
        Mapping with serialized entity summaries.
    """
    return APIEntityListResponse(
        entities=[APIEntitySummary.create(entity) for entity in Entity.get_all_entities()]
    )


@app.get("/visibility", response_model=APIVisibilityResponse)
async def get_visibility():
    """Return visibility data for all registered entities.

    Returns:
        Mapping from entity UUID to visible cells, seen cells, visible objects,
        visible entities, and active sense modes.
    """
    return _build_visibility_state()


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
        return CombatLogHistoryResponse(
            generation_id=str(EventQueue.generation_id()),
            entries=[],
            count=0,
            total=0,
        )

    entries = sim.encounter.get_combat_log(since)
    return CombatLogHistoryResponse(
        generation_id=str(EventQueue.generation_id()),
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

    ai_process_manager.stop_all()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()

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

    ai_process_manager.stop_all()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()

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
            message=f"Invalid player_type: {request.player_type}",
            player_type=request.player_type,
            valid_player_types=[player_type.value for player_type in PlayerType],
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


@app.get("/replication/bootstrap", response_model=ReplicationBootstrapResponse)
async def get_replication_bootstrap(
    session_id: Optional[str] = None,
) -> ReplicationBootstrapResponse:
    """Return one coherent replication base state and its following cursors.

    Args:
        session_id: Optional player session whose status should be included.

    Returns:
        Snapshot, visibility, session status, protocol identity, and cursors
        captured without yielding control to another server request.

    Raises:
        HTTPException: If the optional session UUID is invalid or unknown.
    """
    session_status: Optional[SessionPingResponse] = None
    if session_id is not None:
        try:
            sid = UUID(session_id)
        except ValueError:
            raise _session_http_exception(
                status_code=400,
                code="invalid_session_uuid",
                message="Invalid session ID format",
                session_id=session_id,
            )
        session_status = build_session_status(sid, ping=False)

    state = _build_public_state()
    visibility = _build_visibility_state()
    generation_id = str(EventQueue.generation_id())
    return ReplicationBootstrapResponse(
        protocol=ReplicationProtocolIdentity(
            generation_id=generation_id,
            event_contract_version=EVENT_CONTRACT_VERSION,
            event_contract_hash=EVENT_CONTRACT_HASH,
        ),
        event_cursor=EventQueue.event_cursor(),
        combat_log_cursor=len(sim.encounter.combat_log) if sim.encounter else 0,
        state=state,
        visibility=visibility,
        combat_log=list(sim.encounter.combat_log) if sim.encounter else [],
        session=session_status,
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
    requested_entity_uuids = request.requested_entity_uuids()
    try:
        sid = UUID(request.session_id)
    except ValueError:
        raise _session_http_exception(
            status_code=400,
            code="invalid_session_uuid",
            message="Invalid session ID format",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
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
            requested_entity_uuids=requested_entity_uuids,
            requested_faction=request.faction,
        )

    game = sim.game
    if not game:
        raise _session_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game to join",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
            requested_faction=request.faction,
        )

    if session.session_id not in game.players:
        game.add_player(session)

    if session.player_type == PlayerType.OBSERVER and (requested_entity_uuids or request.faction):
        raise _session_http_exception(
            status_code=400,
            code="observer_cannot_control_entities",
            message="Observer sessions cannot claim entities or factions",
            session_id=request.session_id,
            requested_entity_uuids=requested_entity_uuids,
            requested_faction=request.faction,
        )

    ownership_boundary = prepare_observation_ownership_change(mgr)
    assigned = []
    if requested_entity_uuids:
        for uuid_str in requested_entity_uuids:
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

    _publish_takeover_ownership_changes(ownership_boundary, "game_join_assignment")

    observer_join = session.player_type == PlayerType.OBSERVER
    return JoinGameResponse(
        success=observer_join or len(assigned) > 0,
        game_id=str(game.game_id),
        session_id=str(session.session_id),
        controlled_entities=assigned,
        message=(
            "Joined game as observer"
            if observer_join
            else f"Joined game, controlling {len(assigned)} entities"
        ),
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
        generation_id=str(EventQueue.generation_id()),
        events=events,
        count=len(events),
        total=len(all_events),
    )


@app.get("/event-contract", response_model=EventContractSummary)
async def get_event_contract() -> EventContractSummary:
    """Return the identity and exhaustive discriminators of the event wire contract."""
    return EventContractSummary.model_validate(event_contract_summary())


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

    def session_status_payload() -> Optional[SessionPingResponse]:
        if sid is None:
            return None
        return build_session_status(sid, ping=True)

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
                generation_id=str(EventQueue.generation_id()),
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
                        generation_id=str(EventQueue.generation_id()),
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


def _build_decision_epoch(
    session_id: str,
    reason: DecisionEpochReason = DecisionEpochReason.SNAPSHOT,
    *,
    reuse_current: bool = True,
    timing: Optional[_ServerCommandTiming] = None,
    phase_prefix: str = "epoch",
) -> Optional[DecisionEpoch]:
    """Build a decision epoch when the session controls the active actor."""
    if sim.encounter is None or sim.game is None:
        return None

    started = time.perf_counter()
    try:
        parsed_session_id = UUID(session_id)
    except ValueError:
        return None
    if timing is not None:
        timing.add(f"{phase_prefix}.parse_session_id_ms", started)

    started = time.perf_counter()
    session = sim.get_session_manager().get_session(parsed_session_id)
    if session is None:
        return None
    if timing is not None:
        timing.add(f"{phase_prefix}.resolve_session_ms", started)

    if reuse_current:
        started = time.perf_counter()
        cached = _current_decision_epoch(session_id, session)
        if timing is not None:
            timing.add(f"{phase_prefix}.current_epoch_cache_check_ms", started)
        if cached is not None:
            return cached

    try:
        started = time.perf_counter()
        observation_cursor = get_observation_cursor(
            session_id,
            session_manager=sim.get_session_manager(),
            record_timing=_prefixed_timing_recorder(timing, f"{phase_prefix}.observation_cursor")
            if timing is not None
            else None,
        )
        if timing is not None:
            timing.add(f"{phase_prefix}.get_observation_cursor_ms", started)
    except ObservationAccessError:
        return None

    build = build_subjective_decision_epoch(
        session=session,
        game=sim.game,
        encounter=sim.encounter,
        observation_cursor=observation_cursor,
        reason=reason,
        record_timing=_prefixed_timing_recorder(timing, phase_prefix),
    )
    if build is None:
        return None
    _available_actions_cache[build.epoch.actor_uuid] = build.available_actions
    _execution_authority_by_epoch_id[build.epoch.epoch_id] = build.execution_authority
    if reason == DecisionEpochReason.SNAPSHOT:
        _store_current_epoch(session_id, build.epoch)
    return build.epoch


def _current_decision_epoch(session_id: str, session: Any) -> Optional[DecisionEpoch]:
    """Return the published active epoch while it still describes the turn."""
    epoch = _current_epoch_by_session.get(session_id)
    if epoch is None or sim.encounter is None or sim.game is None:
        return None
    active_uuid = sim.game.active_entity_uuid
    if (
        active_uuid is None
        or str(active_uuid) != epoch.actor_uuid
        or active_uuid not in session.controlled_entities
        or sim.encounter.round_number != epoch.round_number
        or sim.encounter.current_turn_index != epoch.turn_index
    ):
        _forget_current_epoch(session_id)
        return None
    return epoch


def _snapshot_with_epoch(session_id: str) -> ObservationSnapshot:
    """Build a subjective snapshot and attach the current epoch when present."""
    snapshot = build_observation_snapshot(session_id, session_manager=sim.get_session_manager())
    epoch = _build_decision_epoch(
        session_id,
        DecisionEpochReason.SNAPSHOT,
        phase_prefix="build.current_epoch",
    )
    return snapshot.model_copy(update={"current_epoch": epoch})


def _find_affordance(epoch: DecisionEpoch, row_id: str) -> Optional[ActionAffordance]:
    """Return the affordance row selected by row id."""
    return epoch.affordances.row_by_id(row_id)


def _find_execution_binding(
    epoch: DecisionEpoch,
    affordance: ActionAffordance,
) -> Optional[ActionExecutionBinding]:
    """Return private exact engine authority for one current epoch row."""
    authority = _execution_authority_by_epoch_id.get(epoch.epoch_id)
    return authority.binding_for(affordance) if authority is not None else None


def _command_result(
    status: CommandResultStatus,
    session_id: str,
    *,
    command_id: Optional[str] = None,
    actor_uuid: Optional[str] = None,
    requested_epoch_id: Optional[str] = None,
    current_epoch_id: Optional[str] = None,
    row_id: Optional[str] = None,
    action_resolution: Optional[ActionResolutionStatus] = None,
    outcome_code: Optional[str] = None,
    revalidation_required: bool = False,
    revalidation_reason: Optional[str] = None,
    message: str = "",
    payload: Optional[dict[str, Any]] = None,
    resync_required: bool = False,
) -> CommandResult:
    """Create a command result payload."""
    return CommandResult(
        status=status,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=actor_uuid,
        requested_epoch_id=requested_epoch_id,
        current_epoch_id=current_epoch_id,
        row_id=row_id,
        action_resolution=action_resolution,
        outcome_code=outcome_code,
        revalidation_required=revalidation_required,
        revalidation_reason=revalidation_reason,
        message=message,
        payload=payload or {},
        resync_required=resync_required,
    )


def _with_server_timing(
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Return a command result with current server timing attached."""
    payload = dict(result.payload)
    payload["server_timing"] = timing.payload()
    return result.model_copy(update={"payload": payload})


def _publish_command_result(
    session_id: str,
    result: CommandResult,
    *,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> CommandResult:
    """Append a command result to the subjective observation stream."""
    frame = append_command_result_frame(
        session_id,
        result,
        session_manager=sim.get_session_manager(),
        record_timing=record_timing,
    )
    return frame.command_result or result


def _publish_command_result_timed(
    session_id: str,
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Publish a command result and account for publication time."""
    started = time.perf_counter()
    published = _publish_command_result(
        session_id,
        _with_server_timing(result, timing),
        record_timing=_prefixed_timing_recorder(timing, "publish.command_result"),
    )
    timing.add("publish.command_result_ms", started)
    return _with_server_timing(published, timing)


def _command_ack(result: CommandResult) -> CommandResult:
    """Return the small HTTP acknowledgement form of a command result."""
    payload: dict[str, Any] = {}
    if result.status != CommandResultStatus.ACCEPTED:
        return result.model_copy(update={"payload": _compact_command_failure_payload(result)})
    if "server_timing" in result.payload:
        payload["server_timing"] = result.payload["server_timing"]
    if "success" in result.payload:
        payload["success"] = result.payload["success"]
    if "turn_continues" in result.payload:
        payload["turn_continues"] = result.payload["turn_continues"]
    if "encounter_ended" in result.payload:
        payload["encounter_ended"] = result.payload["encounter_ended"]
    elif result.payload.get("status") == "encounter_ended":
        payload["encounter_ended"] = True
    return result.model_copy(update={"payload": payload})


def _compact_command_failure_payload(result: CommandResult) -> dict[str, Any]:
    """Return actionable failure details without objective game state."""
    payload: dict[str, Any] = {"message": result.message}
    source = result.payload if isinstance(result.payload, dict) else {}
    for key in ("code", "reason", "engine_message"):
        if key in source:
            payload[key] = source[key]
    if "server_timing" in source:
        payload["server_timing"] = source["server_timing"]
    detail = source.get("detail")
    if isinstance(detail, dict):
        payload["detail"] = {
            key: value
            for key, value in detail.items()
            if key != "available_actions"
        }
    elif detail is not None:
        payload["detail"] = detail
    action_result = source.get("action_result")
    if isinstance(action_result, dict):
        payload["action_result"] = {
            key: action_result.get(key)
            for key in (
                "success",
                "message",
                "event_type",
                "event_data",
                "entity_hp",
                "target_hp",
                "deaths",
                "turn_continues",
                "encounter_ended",
                "event_cursor_after",
                "combat_log_cursor_after",
            )
            if key in action_result
        }
    return payload


def _publish_command_result_ack(
    session_id: str,
    result: CommandResult,
) -> CommandResult:
    """Publish a detailed command result frame and return a small HTTP ack."""
    return _command_ack(_publish_command_result(session_id, result))


def _command_ack_with_timing(
    result: CommandResult,
    timing: _ServerCommandTiming,
) -> CommandResult:
    """Return a compact command ack with final server timing attached."""
    return _command_ack(_with_server_timing(result, timing))


def _publish_decision_epoch_for_session(
    session_id: str,
    reason: DecisionEpochReason,
    *,
    source_command_id: Optional[str] = None,
    timing: Optional[_ServerCommandTiming] = None,
    phase_prefix: str = "publish.followup_epoch",
) -> Optional[DecisionEpoch]:
    """Append a current decision epoch frame for a session when one exists."""
    started = time.perf_counter()
    epoch = _build_decision_epoch(
        session_id,
        reason,
        reuse_current=False,
        timing=timing,
        phase_prefix=phase_prefix,
    )
    if timing is not None:
        timing.add(f"{phase_prefix}.build_decision_epoch_total_ms", started)
    if epoch is None:
        return None
    started = time.perf_counter()
    last_key = f"{epoch.epoch_id}|cmd={source_command_id or ''}"
    if _last_published_epoch_by_session.get(session_id) == last_key:
        _store_current_epoch(session_id, epoch)
        if timing is not None:
            timing.add(f"{phase_prefix}.duplicate_epoch_cache_ms", started)
        return epoch
    if timing is not None:
        timing.add(f"{phase_prefix}.duplicate_epoch_check_ms", started)
    started = time.perf_counter()
    append_decision_epoch_frame(
        session_id,
        epoch,
        source_command_id=source_command_id,
        session_manager=sim.get_session_manager(),
        record_timing=_prefixed_timing_recorder(timing, phase_prefix),
    )
    if timing is not None:
        timing.add(f"{phase_prefix}.append_decision_epoch_total_ms", started)
    started = time.perf_counter()
    _last_published_epoch_by_session[session_id] = last_key
    _store_current_epoch(session_id, epoch)
    if timing is not None:
        timing.add(f"{phase_prefix}.store_current_epoch_ms", started)
    return epoch


def _publish_epoch_clear_for_session(
    session_id: str,
    reason: str,
    *,
    source_command_id: Optional[str] = None,
    actor_uuid: Optional[str] = None,
) -> None:
    """Append an epoch-clear frame and forget the matching active epoch."""
    current = _current_epoch_by_session.get(session_id)
    if actor_uuid is not None and current is not None and current.actor_uuid != actor_uuid:
        return
    append_epoch_clear_frame(
        session_id,
        reason=reason,
        source_command_id=source_command_id,
        session_manager=sim.get_session_manager(),
    )
    if actor_uuid is None or current is None or current.actor_uuid == actor_uuid:
        _last_published_epoch_by_session.pop(session_id, None)
        _forget_current_epoch(session_id)


def _publish_post_command_control(
    session_id: str,
    *,
    command_id: Optional[str],
    actor_uuid: str,
    next_epoch_reason: DecisionEpochReason,
    clear_reason: str,
    timing: Optional[_ServerCommandTiming] = None,
) -> Optional[DecisionEpoch]:
    """Publish exactly one correlated control boundary after a command result."""
    next_epoch = _publish_decision_epoch_for_session(
        session_id,
        next_epoch_reason,
        source_command_id=command_id,
        timing=timing,
        phase_prefix="publish.followup_epoch",
    )
    if next_epoch is not None:
        return next_epoch
    _publish_epoch_clear_for_session(
        session_id,
        clear_reason,
        source_command_id=command_id,
        actor_uuid=actor_uuid,
    )
    _publish_decision_epoch_for_active_session(
        DecisionEpochReason.TURN_START,
        timing=timing,
    )
    return None


def _publish_decision_epoch_for_active_session(
    reason: DecisionEpochReason,
    *,
    timing: Optional[_ServerCommandTiming] = None,
) -> Optional[DecisionEpoch]:
    """Append a decision epoch for the currently active session when possible."""
    started = time.perf_counter()
    game = sim.game
    if timing is not None:
        timing.add("advance.publish_active_epoch.resolve_game_ms", started)
    if game is None:
        return None
    started = time.perf_counter()
    active_player = game.active_player
    if timing is not None:
        timing.add("advance.publish_active_epoch.resolve_active_player_ms", started)
    if active_player is None:
        return None
    if active_player.player_type == PlayerType.HUMAN:
        started = time.perf_counter()
        if timing is not None:
            timing.add("advance.publish_active_epoch.skip_human_session_ms", started)
        return None
    session_id = str(active_player.session_id)
    if (
        active_player.player_type == PlayerType.CODEX
        and not observation_wakeup_stream.has_subscribers(session_id)
        and not ai_takeover_manager.has_active_session_claim(active_player.session_id)
    ):
        started = time.perf_counter()
        if timing is not None:
            timing.add("advance.publish_active_epoch.skip_unwatched_codex_session_ms", started)
        return None
    started = time.perf_counter()
    epoch = _publish_decision_epoch_for_session(
        session_id,
        reason,
        timing=timing,
        phase_prefix="advance.publish_active_epoch",
    )
    if timing is not None:
        timing.add("advance.publish_active_epoch.publish_session_total_ms", started)
    return epoch


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
        "available_actions": serialize_available_actions(entity, available).model_dump(mode="json"),
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


@app.get("/entity/{entity_uuid}/available-actions", response_model=APIAvailableActions)
async def get_entity_available_actions(entity_uuid: str):
    """Get all available actions for an entity."""
    entity = _resolve_entity_or_raise(entity_uuid)

    actions = get_available_actions(entity)

    _available_actions_cache[entity_uuid] = actions

    return serialize_available_actions(entity, actions)


@app.post("/ai/takeover", response_model=TakeoverClaimResponse)
async def create_ai_takeover(request: TakeoverRequest):
    """Claim combatants for Codex control without spawning a subprocess."""
    if sim.encounter is None or sim.game is None:
        raise _api_http_exception(
            status_code=400,
            code="no_active_game",
            message="No active game is available for takeover",
        )

    session_id = _parse_optional_uuid(request.session_id, "session_id")
    entity_uuids = _parse_uuid_list(request.entity_uuids, "entity_uuid")
    ownership_boundary = prepare_observation_ownership_change(sim.get_session_manager())
    try:
        claim = ai_takeover_manager.claim(
            encounter=sim.encounter,
            game=sim.game,
            session_manager=sim.get_session_manager(),
            faction=request.faction,
            entity_uuids=entity_uuids,
            session_id=session_id,
            name=request.name,
            force=request.force,
            lease_seconds=request.lease_seconds,
        )
    except TakeoverError as error:
        raise _takeover_http_exception(error, faction=request.faction, entity_uuids=request.entity_uuids)

    _publish_takeover_ownership_changes(ownership_boundary, "takeover_claimed")
    return serialize_takeover_claim(claim)


@app.get("/ai/takeover", response_model=TakeoverListResponse)
async def list_ai_takeovers():
    """List active Codex takeover claims."""
    restore_expired_takeovers()
    return TakeoverListResponse(
        claims=[
            serialize_takeover_claim(claim)
            for claim in ai_takeover_manager.active_claims()
        ],
    )


@app.get("/ai/policy/source", response_model=PolicySourceSnapshot)
async def get_policy_source():
    """Return the exact shared policy source manifest and hash."""
    return policy_source_snapshot()


@app.post("/ai/takeover/{claim_id}/heartbeat", response_model=TakeoverHeartbeatResponse)
async def heartbeat_ai_takeover(claim_id: str):
    """Refresh a takeover claim lease."""
    parsed_claim_id = _parse_optional_uuid(claim_id, "claim_id")
    if parsed_claim_id is None:
        raise _api_http_exception(status_code=400, code="invalid_claim_id", message="Invalid claim UUID")
    restore_expired_takeovers()
    claim = ai_takeover_manager.heartbeat(parsed_claim_id)
    if claim is None:
        raise _api_http_exception(
            status_code=404,
            code="takeover_not_found",
            message="Takeover claim not found",
            claim_id=claim_id,
        )
    return TakeoverHeartbeatResponse(status="heartbeat", claim=serialize_takeover_claim(claim))


@app.post("/ai/takeover/{claim_id}/release", response_model=TakeoverReleaseResponse)
async def release_ai_takeover(claim_id: str):
    """Release a takeover claim and restore previous controllers."""
    parsed_claim_id = _parse_optional_uuid(claim_id, "claim_id")
    if parsed_claim_id is None:
        raise _api_http_exception(status_code=400, code="invalid_claim_id", message="Invalid claim UUID")
    ownership_boundary = prepare_observation_ownership_change(sim.get_session_manager())
    claim = ai_takeover_manager.release(parsed_claim_id, sim.encounter, sim.game)
    if claim is None:
        raise _api_http_exception(
            status_code=404,
            code="takeover_not_found",
            message="Takeover claim not found",
            claim_id=claim_id,
        )
    _publish_takeover_ownership_changes(ownership_boundary, "takeover_released")
    advance_result = await advance_encounter() if sim.encounter is not None else None
    return TakeoverReleaseResponse(
        status="released",
        claim=serialize_takeover_claim(claim),
        advance_result=advance_result,
    )


@app.get("/ai/sessions", response_model=AgentSessionListResponse)
async def list_ai_observer_sessions(include_empty: bool = False):
    """List AI/Codex sessions available to telemetry observers.

    Args:
        include_empty: Whether to include sessions with no controlled entities
            and no live takeover claim.

    Returns:
        Read-only session rows containing telemetry cursors and owned entity
        labels. The payload intentionally omits objective state, visibility,
        HP, positions, legal actions, and enemy facts.
    """
    restore_expired_takeovers()
    manager = sim.get_session_manager()
    game = sim.game
    claim_ids_by_session: dict[UUID, list[str]] = {}
    for claim in ai_takeover_manager.active_claims():
        claim_ids_by_session.setdefault(claim.session_id, []).append(str(claim.claim_id))

    rows = []
    for session in sorted(manager.sessions.values(), key=lambda row: (row.player_type.value, row.name, str(row.session_id))):
        if session.player_type not in (PlayerType.AI, PlayerType.CODEX):
            continue
        claim_ids = sorted(claim_ids_by_session.get(session.session_id, []))
        if not include_empty and not session.controlled_entities and not claim_ids:
            continue
        rows.append(_serialize_agent_session_row(str(session.session_id), claim_ids))

    return AgentSessionListResponse(
        sessions=rows,
        active_game_id=str(game.game_id) if game else None,
        encounter_active=bool(game and game.encounter is not None and game.encounter.state.value == "active"),
    )


@app.get(
    "/ai/sessions/{session_id}/observation/snapshot",
    response_model=ObservationSnapshot,
)
async def get_ai_observation_snapshot(session_id: str):
    """Return a strict session-subjective observation snapshot."""
    try:
        return _snapshot_with_epoch(session_id)
    except ObservationAccessError as error:
        raise _observation_http_exception(error, session_id=session_id)


@app.get(
    "/ai/sessions/{session_id}/observation/frames",
    response_model=ObservationFramesResponse,
)
async def get_ai_observation_frames(
    session_id: str,
    since: int = 0,
    limit: int = 50,
):
    """Return replayable strict session-subjective observation frames."""
    try:
        return iter_observation_frames(
            session_id,
            since=since,
            limit=limit,
            session_manager=sim.get_session_manager(),
        )
    except ObservationAccessError as error:
        raise _observation_http_exception(error, session_id=session_id)


@app.get("/ai/sessions/{session_id}/observation/subscribe")
async def subscribe_ai_observation(
    request: Request,
    session_id: str,
    since: int = 0,
):
    """Subscribe to strict session-subjective observation frames."""

    async def event_generator():
        cursor = max(0, since)
        subjective_subscription = observation_wakeup_stream.subscribe(session_id)
        try:
            snapshot = _snapshot_with_epoch(session_id)
        except ObservationAccessError as error:
            observation_wakeup_stream.unsubscribe(session_id, subjective_subscription)
            yield format_sse(
                "error",
                {"code": error.code, "message": error.message},
            )
            return

        try:
            if cursor > snapshot.observation_cursor:
                yield format_sse(
                    "error",
                    {
                        "code": "observation_cursor_ahead",
                        "message": (
                            f"Requested cursor {cursor} is ahead of current "
                            f"cursor {snapshot.observation_cursor}."
                        ),
                    },
                )
                return
            yield format_sse(
                "sync",
                {
                    "observation_cursor": snapshot.observation_cursor,
                    "source_event_cursor": snapshot.source_event_cursor,
                    "source_combat_log_cursor": snapshot.source_combat_log_cursor,
                    "current_epoch_id": snapshot.current_epoch.epoch_id if snapshot.current_epoch else None,
                },
                f"o={snapshot.observation_cursor}",
            )

            try:
                replay = iter_observation_frames(
                    session_id,
                    since=cursor,
                    limit=0,
                    session_manager=sim.get_session_manager(),
                )
            except ObservationAccessError as error:
                yield format_sse(
                    "error",
                    {"code": error.code, "message": error.message},
                )
                return
            for frame in replay.frames:
                cursor = frame.observation_cursor
                yield format_sse(
                    "observation_frame",
                    frame,
                    f"o={frame.observation_cursor}",
                )
            while True:
                if await request.is_disconnected():
                    break
                envelope = await _first_subscription_envelope(
                    [subjective_subscription],
                    timeout=10.0,
                )
                if envelope is None:
                    current_snapshot = _snapshot_with_epoch(session_id)
                    yield format_sse(
                        "heartbeat",
                        {
                            "server_time": time.time(),
                            "observation_cursor": current_snapshot.observation_cursor,
                            "source_event_cursor": current_snapshot.source_event_cursor,
                            "source_combat_log_cursor": current_snapshot.source_combat_log_cursor,
                            "current_epoch_id": (
                                current_snapshot.current_epoch.epoch_id
                                if current_snapshot.current_epoch is not None
                                else None
                            ),
                        },
                        f"o={current_snapshot.observation_cursor}",
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse(
                        "evicted",
                        envelope["data"],
                        envelope.get("id"),
                    )
                    break

                frame_data = envelope.get("data")
                frame = (
                    frame_data
                    if isinstance(frame_data, ObservationFrame)
                    else ObservationFrame.model_validate(frame_data)
                )
                if frame.observation_cursor <= cursor:
                    continue
                if frame.observation_cursor == cursor + 1:
                    cursor = frame.observation_cursor
                    yield format_sse(
                        "observation_frame",
                        frame,
                        f"o={frame.observation_cursor}",
                    )
                    continue

                try:
                    response = iter_observation_frames(
                        session_id,
                        since=cursor,
                        limit=0,
                        session_manager=sim.get_session_manager(),
                    )
                except ObservationAccessError as error:
                    yield format_sse(
                        "error",
                        {"code": error.code, "message": error.message},
                    )
                    break
                for frame in response.frames:
                    cursor = frame.observation_cursor
                    yield format_sse(
                        "observation_frame",
                        frame,
                        f"o={frame.observation_cursor}",
                    )
        finally:
            observation_wakeup_stream.unsubscribe(session_id, subjective_subscription)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/ai/sessions/{session_id}/commands/execute",
    response_model=CommandResult,
)
async def execute_ai_session_command(
    session_id: str,
    request: AgentExecuteCommandRequest,
):
    """Execute one row from the session's current decision epoch."""
    timing = _ServerCommandTiming(
        "execute",
        diagnostics_enabled=request.include_diagnostics,
    )
    started = time.perf_counter()
    epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
    timing.add("build.current_epoch_ms", started)
    if epoch is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            row_id=request.row_id,
            message="Session does not currently control an active actor.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_epoch_clear_for_session(
            session_id,
            "no_active_actor",
            source_command_id=request.command_id,
            actor_uuid=request.actor_uuid,
        )
        timing.add("publish.epoch_clear_ms", started)
        return _command_ack_with_timing(published, timing)

    if epoch.epoch_id != request.basis_epoch_id or epoch.actor_uuid != request.actor_uuid:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command was based on a stale decision epoch.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_STALE,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    affordance = _find_affordance(epoch, request.row_id)
    timing.add("validate.find_affordance_ms", started)
    if affordance is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Decision epoch row id is not available.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    if affordance.bucket == "special_commands":
        return await _end_ai_session_turn_from_epoch(
            session_id,
            request.actor_uuid,
            request.basis_epoch_id,
            command_id=request.command_id,
            include_diagnostics=request.include_diagnostics,
        )

    if not affordance.can_afford or not affordance.targets:
        reason = "Decision epoch row is not affordable." if not affordance.can_afford else "Decision epoch row has no legal target."
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message=reason,
            payload={
                "code": "row_not_executable",
                "reason": reason,
            },
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    try:
        extra_target_uuids = affordance.validated_extra_target_uuids(
            request.extra_target_uuids or (),
        )
    except ValueError as exc:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command target allocation is not authorized by the decision epoch.",
            payload={
                "code": "invalid_target_allocation",
                "reason": str(exc),
            },
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    execution_binding = _find_execution_binding(epoch, affordance)
    if execution_binding is None:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Decision epoch execution authority is no longer available.",
            payload={"code": "execution_authority_unavailable"},
            resync_required=True,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        return _command_ack_with_timing(published, timing)

    target = affordance.targets[0]
    started = time.perf_counter()
    semantics = epoch.affordances.semantics_for(affordance)
    movement_guard = None
    if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags:
        movement_guard = SessionMovementContinuationGuard.from_world(
            get_materialized_observation_world(
                session_id,
                session_manager=sim.get_session_manager(),
            ),
            request.actor_uuid,
        )
    timing.add("execute.build_movement_guard_ms", started)
    try:
        started = time.perf_counter()
        execution_scope = (
            movement_continuation_scope(movement_guard)
            if movement_guard is not None
            else nullcontext()
        )
        with execution_scope:
            result = await _execute_action_by_index_impl(
                ExecuteByIndexRequest(
                    session_id=session_id,
                    entity_uuid=request.actor_uuid,
                    template_name=affordance.template_name,
                    target_index=target.index,
                    extra_target_uuids=list(extra_target_uuids)
                    if extra_target_uuids
                    else None,
                    prefer_safe=request.prefer_safe,
                    return_available_actions=False,
                    include_state=False,
                    include_timing=request.include_diagnostics,
                ),
                execution_binding=execution_binding,
            )
        if movement_guard is not None:
            for sample_ms in movement_guard.processing_samples_ms:
                timing.add_elapsed(
                    "execute.movement_revalidation_ms",
                    sample_ms,
                )
        timing.add("execute.action_by_index_ms", started)
    except HTTPException as exc:
        timing.add("execute.action_by_index_ms", started)
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=request.command_id,
            actor_uuid=request.actor_uuid,
            requested_epoch_id=request.basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            row_id=request.row_id,
            message="Command was rejected by the engine.",
            payload={"detail": exc.detail},
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=request.command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    result_payload = _safe_action_result_payload(result)
    timing.add("serialize.safe_action_result_ms", started)
    if _action_result_ends_actor_turn(result_payload):
        started = time.perf_counter()
        advance_result = await _advance_after_non_continuing_action(
            request.actor_uuid,
            publish_decision_epoch=False,
        )
        timing.add("advance.after_non_continuing_action_ms", started)
        if advance_result is not None:
            result_payload["encounter_ended"] = advance_result.status == "encounter_ended"

    action_resolution = _command_action_resolution(result)
    revalidation_reason = _command_revalidation_reason(result)
    result = _command_result(
        CommandResultStatus.ACCEPTED,
        session_id,
        command_id=request.command_id,
        actor_uuid=request.actor_uuid,
        requested_epoch_id=request.basis_epoch_id,
        current_epoch_id=None,
        row_id=request.row_id,
        action_resolution=action_resolution,
        outcome_code=result.outcome_code,
        revalidation_required=revalidation_reason is not None,
        revalidation_reason=revalidation_reason,
        message=result.message,
        payload=result_payload,
        resync_required=False,
    )
    published = _publish_command_result_timed(session_id, result, timing)
    started = time.perf_counter()
    next_epoch = _publish_post_command_control(
        session_id,
        command_id=request.command_id,
        actor_uuid=request.actor_uuid,
        next_epoch_reason=(
            DecisionEpochReason.TURN_START
            if _action_result_ends_actor_turn(result_payload)
            else _followup_epoch_reason(
                result.action_resolution,
                revalidation_required=result.revalidation_required,
            )
        ),
        clear_reason=(
            result.action_resolution.value
            if result.action_resolution is not None
            else "action_completed"
        ),
        timing=timing,
    )
    timing.add("publish.post_command_control_ms", started)
    if published.current_epoch_id is None and next_epoch is not None:
        published = published.model_copy(update={"current_epoch_id": next_epoch.epoch_id})
    return _command_ack_with_timing(published, timing)


def _command_action_resolution(result: ActionResult) -> ActionResolutionStatus:
    """Map one engine action response to the controller protocol result."""
    if result.outcome_code == "movement.subjective_revalidation":
        event_data = result.event_data or {}
        if event_data.get("termination_reason") == "completed":
            return ActionResolutionStatus.COMPLETED
        return ActionResolutionStatus.INTERRUPTED
    if result.success:
        return ActionResolutionStatus.COMPLETED
    return ActionResolutionStatus.CANCELED


def _followup_epoch_reason(
    resolution: ActionResolutionStatus | None,
    *,
    revalidation_required: bool = False,
) -> DecisionEpochReason:
    """Return the epoch reason corresponding to an accepted action result."""
    if revalidation_required:
        return DecisionEpochReason.MOVEMENT_REVALIDATION
    if resolution is ActionResolutionStatus.INTERRUPTED:
        return DecisionEpochReason.MOVEMENT_REVALIDATION
    if resolution is ActionResolutionStatus.CANCELED:
        return DecisionEpochReason.ACTION_CANCELED
    return DecisionEpochReason.ACTION_COMPLETED


def _command_revalidation_reason(result: ActionResult) -> Optional[str]:
    """Return the typed controller revalidation cause from movement data."""
    if result.outcome_code != "movement.subjective_revalidation":
        return None
    event_data = result.event_data or {}
    reason = event_data.get("controller_revalidation_reason")
    return reason if isinstance(reason, str) and reason else None


def _action_result_ends_actor_turn(payload: dict[str, Any]) -> bool:
    """Return whether an accepted action result says the actor cannot continue."""
    return payload.get("turn_continues") is False and payload.get("encounter_ended") is not True


async def _advance_after_non_continuing_action(
    actor_uuid: str,
    *,
    publish_decision_epoch: bool = True,
) -> Optional[AdvanceEncounterResult]:
    """Advance when the active actor died or otherwise cannot continue after a command."""
    if sim.encounter is None or sim.game is None or sim.encounter.state != EncounterState.ACTIVE:
        return None
    active_uuid = sim.game.active_entity_uuid
    if active_uuid is None or str(active_uuid) != actor_uuid:
        return None

    _available_actions_cache.clear()
    sim.encounter.end_turn()
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED
    return await advance_encounter(
        publish_decision_epoch=publish_decision_epoch,
    )


@app.post(
    "/ai/sessions/{session_id}/commands/end-turn",
    response_model=CommandResult,
)
async def end_ai_session_turn(
    session_id: str,
    request: AgentEndTurnCommandRequest,
):
    """End the actor turn from the session's current decision epoch."""
    return await _end_ai_session_turn_from_epoch(
        session_id,
        request.actor_uuid,
        request.basis_epoch_id,
        command_id=request.command_id,
        include_diagnostics=request.include_diagnostics,
    )


async def _end_ai_session_turn_from_epoch(
    session_id: str,
    actor_uuid: str,
    basis_epoch_id: str,
    *,
    command_id: Optional[str] = None,
    include_diagnostics: bool = False,
) -> CommandResult:
    """Validate an epoch and end the active actor turn."""
    timing = _ServerCommandTiming(
        "end_turn",
        diagnostics_enabled=include_diagnostics,
    )
    started = time.perf_counter()
    epoch = _build_decision_epoch(
        session_id,
        DecisionEpochReason.SNAPSHOT,
        timing=timing,
        phase_prefix="build.current_epoch",
    )
    timing.add("build.current_epoch_ms", started)
    if epoch is None:
        result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            message="Session does not currently control an active actor.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_epoch_clear_for_session(
            session_id,
            "no_active_actor",
            source_command_id=command_id,
            actor_uuid=actor_uuid,
        )
        timing.add("publish.epoch_clear_ms", started)
        return _command_ack_with_timing(published, timing)
    if epoch.epoch_id != basis_epoch_id or epoch.actor_uuid != actor_uuid:
        result = _command_result(
            CommandResultStatus.STALE,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            message="End-turn command was based on a stale decision epoch.",
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_STALE,
            source_command_id=command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)
    try:
        started = time.perf_counter()
        result = await _end_turn_and_advance(
            session_id,
            actor_uuid,
            timing=timing,
            publish_decision_epoch=False,
        )
        timing.add("end_turn.total_route_ms", started)
    except HTTPException as exc:
        command_result = _command_result(
            CommandResultStatus.REJECTED,
            session_id,
            command_id=command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=basis_epoch_id,
            current_epoch_id=epoch.epoch_id,
            message="End-turn command was rejected by the engine.",
            payload={"detail": exc.detail},
            resync_required=False,
        )
        published = _publish_command_result_timed(session_id, command_result, timing)
        started = time.perf_counter()
        _publish_decision_epoch_for_session(
            session_id,
            DecisionEpochReason.ACTION_REJECTED,
            source_command_id=command_id,
            timing=timing,
            phase_prefix="publish.followup_epoch",
        )
        timing.add("publish.followup_epoch_ms", started)
        return _command_ack_with_timing(published, timing)

    started = time.perf_counter()
    payload = _safe_advance_result_payload(result)
    timing.add("serialize.advance_result_ms", started)
    command_result = _command_result(
        CommandResultStatus.ACCEPTED,
        session_id,
        command_id=command_id,
        actor_uuid=actor_uuid,
        requested_epoch_id=basis_epoch_id,
        current_epoch_id=None,
        row_id="special|End Turn|index=0",
        message="Turn ended.",
        payload=payload,
        resync_required=False,
    )
    published = _publish_command_result_timed(session_id, command_result, timing)
    started = time.perf_counter()
    next_epoch = _publish_post_command_control(
        session_id,
        command_id=command_id,
        actor_uuid=actor_uuid,
        next_epoch_reason=DecisionEpochReason.TURN_START,
        clear_reason="turn_ended",
        timing=timing,
    )
    timing.add("publish.post_command_control_ms", started)
    if published.current_epoch_id is None and next_epoch is not None:
        published = published.model_copy(update={"current_epoch_id": next_epoch.epoch_id})
    return _command_ack_with_timing(published, timing)


def _safe_action_result_payload(result: ActionResult) -> dict[str, Any]:
    """Return protocol outcome metadata while gameplay arrives through events."""
    payload: dict[str, Any] = {
        "success": result.success,
        "turn_continues": result.turn_continues,
        "encounter_ended": result.encounter_ended,
    }
    action_timing = result.server_timing
    if action_timing is not None:
        payload["action_server_timing"] = action_timing
    return payload


def _safe_advance_result_payload(result: AdvanceEncounterResult) -> dict[str, Any]:
    """Return advancement protocol state without raw automated-controller facts."""
    return {
        "status": result.status,
        "encounter_ended": result.status == "encounter_ended",
    }


@app.post("/ai/sessions/{session_id}/agent-events")
async def post_agent_events(
    session_id: str,
    request: AgentEventIngestRequest,
):
    """Append agent telemetry events to the per-session stream."""
    session = _require_agent_stream_session(session_id)
    rows = []
    for event in request.events:
        actor_uuid = None
        if event.actor_uuid is not None:
            try:
                actor_uuid = UUID(event.actor_uuid)
            except ValueError:
                raise _api_http_exception(
                    status_code=400,
                    code="invalid_agent_event_actor_uuid",
                    message="Agent event actor UUID is invalid.",
                    session_id=session_id,
                    actor_uuid=event.actor_uuid,
                )
        if actor_uuid is not None and actor_uuid not in session.controlled_entities:
            raise _api_http_exception(
                status_code=403,
                code="agent_event_actor_not_controlled",
                message="Agent event actor is not controlled by this session.",
                session_id=session_id,
                actor_uuid=event.actor_uuid,
            )
        rows.append(agent_event_stream.publish(session_id, event))
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": agent_event_stream.current_agent_cursor(session_id),
        "next_agent_cursor": rows[-1].agent_cursor if rows else agent_event_stream.current_agent_cursor(session_id),
    }


@app.get(
    "/ai/sessions/{session_id}/agent-events",
    response_model=AgentEventHistoryResponse,
)
async def get_agent_events(
    session_id: str,
    since: int = 0,
    limit: int = 100,
):
    """Return agent telemetry events after a session-local cursor."""
    _require_agent_stream_session(session_id)
    rows = agent_event_stream.iter_agent_events_since(session_id, since, limit)
    return AgentEventHistoryResponse(
        events=rows,
        count=len(rows),
        total=agent_event_stream.current_agent_cursor(session_id),
        next_agent_cursor=rows[-1].agent_cursor if rows else max(0, since),
        earliest_agent_cursor=agent_event_stream.earliest_agent_cursor(session_id),
        resync_required=agent_event_stream.is_cursor_evicted(session_id, since),
    )


@app.get("/ai/sessions/{session_id}/agent-events/subscribe")
async def subscribe_agent_events(
    request: Request,
    session_id: str,
    since: int = 0,
):
    """Subscribe to per-session agent telemetry events."""
    _require_agent_stream_session(session_id)

    async def event_generator():
        cursor = max(0, since)
        subscription = agent_event_stream.subscribe(session_id)
        try:
            observation_cursor = _safe_observation_cursor(session_id)
            if agent_event_stream.is_cursor_evicted(session_id, cursor):
                yield format_sse(
                    "evicted",
                    EvictedPayload(reason="agent_history_evicted"),
                    agent_event_stream.current_stream_id(session_id, observation_cursor),
                )
                return
            epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
            yield format_sse(
                "sync",
                agent_event_stream.sync_payload(
                    session_id,
                    observation_cursor=observation_cursor,
                    epoch_id=epoch.epoch_id if epoch else None,
                    session=_agent_stream_session_payload(session_id),
                ),
                agent_event_stream.current_stream_id(session_id, observation_cursor),
            )

            for payload in agent_event_stream.iter_agent_events_since(session_id, cursor, 500):
                cursor = payload.agent_cursor
                yield format_sse(
                    "agent_event",
                    payload,
                    agent_event_stream.current_stream_id(session_id, payload.observation_cursor),
                )

            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(subscription.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    observation_cursor = _safe_observation_cursor(session_id)
                    epoch = _build_decision_epoch(session_id, DecisionEpochReason.SNAPSHOT)
                    yield format_sse(
                        "heartbeat",
                        agent_event_stream.heartbeat_payload(
                            session_id,
                            observation_cursor=observation_cursor,
                            epoch_id=epoch.epoch_id if epoch else None,
                            session=_agent_stream_session_payload(session_id),
                        ),
                        agent_event_stream.current_stream_id(session_id, observation_cursor),
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse("evicted", envelope["data"], envelope.get("id"))
                    break
                payload = envelope["data"]
                if isinstance(payload, dict):
                    cursor = int(payload.get("agent_cursor", cursor))
                else:
                    cursor = getattr(payload, "agent_cursor", cursor)
                yield format_sse(envelope["event"], payload, envelope.get("id"))
        finally:
            agent_event_stream.unsubscribe(session_id, subscription)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


GAUNTLET_SUMMARY_DIRECTORY = Path("ai/evidence/gauntlets")


@app.get("/ai/gauntlets/latest")
async def get_latest_gauntlet_summary():
    """Return the latest retained gauntlet summary JSON."""
    summary = _load_gauntlet_summary("latest")
    return summary.model_dump(mode="json")


@app.get("/ai/gauntlets/live/latest")
async def get_latest_live_gauntlet_watcher_state():
    """Return watcher state for the most recently observed live gauntlet."""
    gauntlet_id = gauntlet_event_stream.latest_gauntlet_id()
    if gauntlet_id is None:
        raise _api_http_exception(
            status_code=404,
            code="live_gauntlet_not_found",
            message="No live gauntlet watcher events are retained.",
        )
    events = gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=0)
    return project_live_watcher_state(gauntlet_id, events).model_dump(mode="json")


@app.get("/ai/gauntlets/{gauntlet_id}/watch")
async def get_gauntlet_watcher_state(gauntlet_id: str):
    """Return the current watcher projection for a gauntlet."""
    live_events = gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=0)
    try:
        summary = _load_gauntlet_summary(gauntlet_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        if not live_events:
            raise
        return project_live_watcher_state(gauntlet_id, live_events).model_dump(mode="json")
    events = live_events or summary.events
    return project_watcher_state(summary, events).model_dump(mode="json")


@app.get("/ai/gauntlets/{gauntlet_id}/events")
async def get_gauntlet_events(
    gauntlet_id: str,
    since: int = 0,
    limit: int = 100,
):
    """Return retained live watcher events after a gauntlet cursor."""
    _ensure_gauntlet_known(gauntlet_id)
    rows = gauntlet_event_stream.since(since, gauntlet_id=gauntlet_id, limit=limit)
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": gauntlet_event_stream.current_cursor(),
        "next_cursor": rows[-1].cursor if rows else max(0, since),
        "earliest_cursor": gauntlet_event_stream.earliest_cursor(gauntlet_id),
        "resync_required": gauntlet_event_stream.is_cursor_evicted(since, gauntlet_id),
    }


@app.post("/ai/gauntlets/events")
async def post_gauntlet_events(request: GauntletEventIngestRequest):
    """Publish externally produced gauntlet watcher events."""
    rows = [gauntlet_event_stream.publish(event) for event in request.events]
    return {
        "events": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
        "total": gauntlet_event_stream.current_cursor(),
        "next_cursor": rows[-1].cursor if rows else gauntlet_event_stream.current_cursor(),
    }


@app.get("/ai/gauntlets/{gauntlet_id}/events/subscribe")
async def subscribe_gauntlet_events(
    request: Request,
    gauntlet_id: str,
    since: int = 0,
):
    """Subscribe to live gauntlet watcher events."""
    _ensure_gauntlet_known(gauntlet_id)

    async def event_generator():
        cursor = max(0, since)
        subscription = gauntlet_event_stream.subscribe(gauntlet_id)
        try:
            if gauntlet_event_stream.is_cursor_evicted(cursor, gauntlet_id):
                yield format_sse(
                    "evicted",
                    EvictedPayload(reason="gauntlet_history_evicted"),
                    gauntlet_event_stream.current_stream_id(),
                )
                return
            yield format_sse(
                "sync",
                {
                    "gauntlet_id": gauntlet_id,
                    "cursor": gauntlet_event_stream.current_cursor(),
                    "earliest_cursor": gauntlet_event_stream.earliest_cursor(gauntlet_id),
                },
                gauntlet_event_stream.current_stream_id(),
            )
            for event in gauntlet_event_stream.since(cursor, gauntlet_id=gauntlet_id, limit=500):
                cursor = event.cursor
                yield format_sse("gauntlet_event", event, f"g={event.cursor}")

            while True:
                if await request.is_disconnected():
                    break
                try:
                    envelope = await asyncio.wait_for(subscription.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    yield format_sse(
                        "heartbeat",
                        {
                            "gauntlet_id": gauntlet_id,
                            "cursor": gauntlet_event_stream.current_cursor(),
                            "server_time": time.time(),
                        },
                        gauntlet_event_stream.current_stream_id(),
                    )
                    continue

                if envelope["event"] == "evicted":
                    yield format_sse("evicted", envelope["data"], envelope.get("id"))
                    break
                payload = envelope["data"]
                cursor = payload.cursor if hasattr(payload, "cursor") else cursor
                yield format_sse(envelope["event"], payload, envelope.get("id"))
        finally:
            gauntlet_event_stream.unsubscribe(gauntlet_id, subscription)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _load_gauntlet_summary(gauntlet_id: str) -> GauntletSummary:
    """Load a retained gauntlet summary by id or latest pointer."""
    file_name = "latest.json" if gauntlet_id == "latest" else f"{gauntlet_id}.json"
    path = GAUNTLET_SUMMARY_DIRECTORY / file_name
    if not path.exists():
        raise _api_http_exception(
            status_code=404,
            code="gauntlet_summary_not_found",
            message="Gauntlet summary was not found.",
            gauntlet_id=gauntlet_id,
            path=str(path),
        )
    try:
        return apply_gauntlet_latency_audit(GauntletSummary.model_validate_json(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        raise _api_http_exception(
            status_code=500,
            code="invalid_gauntlet_summary",
            message="Gauntlet summary JSON could not be parsed.",
            gauntlet_id=gauntlet_id,
            path=str(path),
            error=str(exc),
        ) from exc


def _ensure_gauntlet_known(gauntlet_id: str) -> None:
    """Accept a gauntlet id when it has retained JSON or live events."""
    if gauntlet_id == "latest":
        _load_gauntlet_summary("latest")
        return
    if gauntlet_event_stream.since(0, gauntlet_id=gauntlet_id, limit=1):
        return
    _load_gauntlet_summary(gauntlet_id)


def _serialize_agent_session_row(session_id: str, takeover_claim_ids: list[str]) -> AgentSessionRow:
    """Serialize one AI/Codex session for the observer index."""
    session = _require_agent_stream_session(session_id)
    game = sim.game
    active_uuid = game.active_entity_uuid if game else None
    is_active_turn = bool(active_uuid is not None and active_uuid in session.controlled_entities)
    active_entity = Entity.get(active_uuid) if is_active_turn and active_uuid is not None else None
    epoch = _current_decision_epoch(session_id, session)

    return AgentSessionRow(
        session_id=str(session.session_id),
        player_type=session.player_type.value,
        name=session.name,
        connection_status=session.connection_status.value,
        is_active_turn=is_active_turn,
        active_controlled_entity_uuid=str(active_uuid) if is_active_turn and active_uuid is not None else None,
        active_controlled_entity_name=active_entity.name if active_entity else None,
        controlled_entities=[
            _serialize_agent_session_entity(entity_uuid)
            for entity_uuid in sorted(session.controlled_entities, key=str)
        ],
        agent_cursor=agent_event_stream.current_agent_cursor(session_id),
        earliest_agent_cursor=agent_event_stream.earliest_agent_cursor(session_id),
        observation_cursor=_safe_observation_cursor(session_id),
        current_epoch_id=epoch.epoch_id if epoch is not None else None,
        takeover_claim_ids=takeover_claim_ids,
    )


def _serialize_agent_session_entity(entity_uuid: UUID) -> AgentSessionEntityRow:
    """Serialize a controlled entity label without tactical state."""
    entity = Entity.get(entity_uuid)
    controller_type = None
    if sim.encounter is not None and entity_uuid in sim.encounter.combatants:
        controller = sim.encounter.get_controller_for(entity_uuid)
        controller_type = controller.controller_type if controller is not None else None
    active_uuid = sim.game.active_entity_uuid if sim.game else None
    return AgentSessionEntityRow(
        entity_uuid=str(entity_uuid),
        entity_name=entity.name if entity is not None else str(entity_uuid),
        faction=entity.faction if entity is not None else None,
        controller_type=controller_type,
        is_active_actor=active_uuid == entity_uuid,
    )


def _require_agent_stream_session(session_id: str):
    """Resolve an agent-stream session or raise a structured error."""
    parsed = _parse_optional_uuid(session_id, "session_id")
    if parsed is None:
        raise _api_http_exception(status_code=400, code="invalid_session_id", message="Invalid session UUID")
    session = sim.get_session_manager().get_session(parsed)
    if session is None:
        raise _api_http_exception(
            status_code=404,
            code="session_not_found",
            message="Session not found",
            session_id=session_id,
        )
    return session


def _safe_observation_cursor(session_id: str) -> Optional[int]:
    """Return the current observation cursor, if the session is resolvable."""
    try:
        return get_observation_cursor(session_id, session_manager=sim.get_session_manager())
    except ObservationAccessError:
        return None


def _agent_stream_session_payload(session_id: str) -> Optional[dict[str, Any]]:
    """Return serialized session context for agent-event stream sync frames."""
    parsed = _parse_optional_uuid(session_id, "session_id")
    if parsed is None:
        return None
    session = sim.get_session_manager().get_session(parsed)
    return session.to_dict() if session else None


@app.get("/ai/processes")
async def get_ai_processes():
    """Return tracked external AI subprocess state."""
    return {
        "processes": ai_process_manager.process_statuses(),
        "running_session_ids": ai_process_manager.running_session_ids(),
    }


@app.get("/entity/{entity_uuid}/handlers", response_model=APIEntityHandlersResponse)
async def get_entity_handlers(entity_uuid: str) -> APIEntityHandlersResponse:
    """Get all event handlers for an entity with their enabled state."""
    entity = _resolve_entity_or_raise(entity_uuid)
    handlers = _serialize_entity_handlers(entity)
    return APIEntityHandlersResponse(entity_uuid=entity_uuid, handlers=handlers)


@app.post(
    "/entity/{entity_uuid}/handlers/{handler_name}/toggle",
    response_model=ToggleHandlerResponse,
)
async def toggle_entity_handler(
    entity_uuid: str,
    handler_name: str,
    request: ToggleHandlerRequest,
) -> ToggleHandlerResponse:
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

    return ToggleHandlerResponse(
        success=True,
        handler_name=handler_name,
        enabled=request.enabled,
    )


@app.get("/entity/{entity_uuid}/equipment", response_model=APIEquipmentOverview)
async def get_entity_equipment(entity_uuid: str):
    """Get full equipment and inventory state for an entity."""
    entity = _resolve_entity_or_raise(entity_uuid)
    return APIEquipmentOverview.create(entity)


@app.get("/entity/{entity_uuid}/equipment/item/{item_uuid}", response_model=APIItemSummary)
async def get_entity_item_detail(entity_uuid: str, item_uuid: str) -> APIItemSummary:
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
            return APIItemSummary.create(equipped_item)

    if entity.inventory.has_item(item_uuid_obj):
        item = entity.inventory.items[item_uuid_obj]
        return APIItemSummary.create(item)

    raise _equipment_http_exception(
        entity=entity,
        status_code=404,
        code="item_not_found",
        message="Item not found on entity",
        item_uuid=item_uuid,
    )


@app.get("/entity/{entity_uuid}/equippable-items", response_model=APIEquippableItems)
async def get_equippable_items(entity_uuid: str) -> APIEquippableItems:
    """Get inventory items that can be equipped, grouped by valid slots."""
    entity = _resolve_entity_or_raise(entity_uuid)
    return APIEquippableItems(
        entity_uuid=entity_uuid,
        equippable=entity.get_equippable_items(),
    )


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
    return await _end_turn_and_advance(request.session_id, request.entity_uuid)


async def _end_turn_and_advance(
    session_id: str,
    entity_uuid: str,
    *,
    timing: Optional[_ServerCommandTiming] = None,
    publish_decision_epoch: bool = True,
) -> AdvanceEncounterResult:
    """End one validated actor turn and advance to the next controller boundary."""
    started = time.perf_counter()
    entity = validate_session_action(session_id, entity_uuid)
    if timing is not None:
        timing.add("end_turn.validate_session_ms", started)

    if sim.encounter is None:
        raise _api_http_exception(
            status_code=400,
            code="no_active_encounter",
            message="No active encounter",
            session_id=session_id,
            entity_uuid=entity_uuid,
            entity_name=entity.name,
            **_session_context(),
            **_simulation_context(),
        )

    _available_actions_cache.clear()

    started = time.perf_counter()
    sim.encounter.end_turn()
    if timing is not None:
        timing.add("end_turn.encounter_end_turn_ms", started)

    started = time.perf_counter()
    sim.encounter.current_turn_index += 1
    if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
        sim.encounter._advance_round()
    sim.encounter.turn_state = TurnState.NOT_STARTED
    if timing is not None:
        timing.add("end_turn.advance_turn_index_ms", started)

    started = time.perf_counter()
    result = await advance_encounter(
        timing=timing,
        publish_decision_epoch=publish_decision_epoch,
    )
    if timing is not None:
        timing.add("end_turn.advance_encounter_ms", started)

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
        outcome_code=event.outcome_code if event else None,
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

    event_data: Optional[dict[str, Any]] = None
    if event and hasattr(event, 'attack_outcome') and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

        event_data = {
            **event.combat_log.to_dict()["data"],
            "target_hp": target.get_hp(),
        }

    for death_event in deaths:
        if death_event.combat_log:
            action_log_entries.append(death_event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or "Action executed",
        event_type=request.action_name.lower().replace("_", " "),
        outcome_code=event.outcome_code if event else None,
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
                event_data = event.combat_log.to_dict()["data"]

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
                outcome_code=event.outcome_code if event else None,
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
            event_data = event.combat_log.to_dict()["data"]
        else:

            event_data = {
                "entity_name": entity.name,
                "start_position": list(event.start_position),
                "end_position": list(event.end_position),
                "path": [list(p) for p in event.path] if event.path else []
            }
    elif template.target_type == TargetType.POSITION_AOE and event:

        if event.combat_log:
            event_data = event.combat_log.to_dict()["data"]

    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)

            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = entry.to_dict()["data"]
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    if not action_log_entries and event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())

    return ActionResult(
        success=not event.canceled if event else False,
        message=(event.status_message if event else None) or ("Moved successfully" if event and not event.canceled else "Move failed"),
        event_type="movement",
        outcome_code=event.outcome_code if event else None,
        event_data=event_data,
        entity_hp=entity.get_hp(),
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries,
        **action_cursor_fields(),
    )


def _causal_death_rows(combat_log: Optional[CombatLogEntry]) -> list[tuple[str, str]]:
    """Return deduplicated entity identities from one causal log subtree."""
    if combat_log is None:
        return []
    rows: list[tuple[str, str]] = []
    if combat_log.entry_type is CombatLogEntryType.DEATH:
        rows.append((combat_log.source_uuid, combat_log.source_name))
    for child in combat_log.sub_entries:
        rows.extend(_causal_death_rows(child))
    return rows


@app.post("/action/execute", response_model=ActionResult)
async def execute_action_by_index(request: ExecuteByIndexRequest):
    """Execute one public template-name and target-index request."""
    return await _execute_action_by_index_impl(request)


async def _execute_action_by_index_impl(
    request: ExecuteByIndexRequest,
    execution_binding: Optional[ActionExecutionBinding] = None,
):
    """Execute action by template name and target index.

    Enables 'attack 0', 'move 3' style commands from the available actions list.
    Uses cached available actions from the display call to avoid recomputing.
    """
    timing = _ServerCommandTiming("action_execute") if request.include_timing else None
    started = time.perf_counter()
    entity = validate_session_action(request.session_id, request.entity_uuid)
    if timing is not None:
        timing.add("validate_session_action_ms", started)

    started = time.perf_counter()
    available = _available_actions_cache.get(request.entity_uuid)
    if timing is not None:
        timing.add("available_actions_cache_lookup_ms", started)
    if available is None:
        started = time.perf_counter()
        available = get_available_actions(entity)
        if timing is not None:
            timing.add("get_available_actions_on_miss_ms", started)

    started = time.perf_counter()
    action_info = (
        execution_binding.action_info
        if execution_binding is not None
        else next(
            (a for a in available.all_actions if a.template_name == request.template_name),
            None,
        )
    )
    if timing is not None:
        timing.add("find_action_info_ms", started)
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

    selected_target = execution_binding.target if execution_binding is not None else next(
        (
            target
            for target in action_info.valid_targets
            if target.index == request.target_index
        ),
        None,
    )
    if selected_target is None:
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="invalid_action_target",
                message=(
                    f"Target index {request.target_index} not valid for "
                    f"{request.template_name}"
                ),
            ),
        )

    target_type = action_info.target_type

    log_start_index = len(sim.encounter.combat_log) if sim.encounter else 0

    try:
        started = time.perf_counter()
        timing_token = None
        if timing is not None:
            timing_token = set_action_timing_recorder(
                lambda phase, phase_started: timing.add(f"execute_by_index.{phase}", phase_started)
            )
        try:
            event = execute_available_action(
                entity,
                action_info,
                selected_target,
                extra_target_uuids=request.extra_target_uuids,
                prefer_safe=request.prefer_safe,
            )
        finally:
            if timing_token is not None:
                reset_action_timing_recorder(timing_token)
        if timing is not None:
            timing.add("execute_by_index_ms", started)
    except ValueError as e:
        if timing is not None:
            timing.add("execute_by_index_ms", started)
        raise HTTPException(
            status_code=400,
            detail=_action_error_detail(
                entity=entity,
                available=available,
                code="invalid_action_target",
                message=str(e),
            ),
        )

    started = time.perf_counter()
    _available_actions_cache.pop(request.entity_uuid, None)
    if timing is not None:
        timing.add("clear_available_actions_cache_ms", started)

    started = time.perf_counter()
    deaths = sim.encounter.check_deaths() if sim.encounter else []
    death_rows = [
        (str(death.entity_uuid), death.entity_name)
        for death in deaths
    ]
    death_rows.extend(_causal_death_rows(event.combat_log if event else None))
    death_names = []
    seen_death_uuids: set[str] = set()
    for death_uuid, death_name in death_rows:
        if death_uuid in seen_death_uuids:
            continue
        seen_death_uuids.add(death_uuid)
        death_names.append(death_name)
    if timing is not None:
        timing.add("check_deaths_ms", started)

    encounter_ended = sim.encounter.state != EncounterState.ACTIVE if sim.encounter else True

    updated_actions = None
    if request.return_available_actions and not encounter_ended and entity.has_hp:
        started = time.perf_counter()
        new_available = get_available_actions(entity)
        if timing is not None:
            timing.add("recompute_available_actions_ms", started)
        started = time.perf_counter()
        _available_actions_cache[request.entity_uuid] = new_available
        updated_actions = serialize_available_actions(entity, new_available)
        if timing is not None:
            timing.add("serialize_available_actions_ms", started)

    started = time.perf_counter()
    event_data: Optional[dict[str, Any]] = None
    target_hp = None

    if target_type == TargetType.ENTITY and event and event.combat_log:

        event_data = event.combat_log.to_dict()["data"]

    elif target_type in (TargetType.POSITION_PATH, TargetType.POSITION_LOS):

        if event and isinstance(event, (MovementEvent, JumpEvent)):
            if event.combat_log:
                event_data = event.combat_log.to_dict()["data"]
            else:
                event_data = {
                    "entity_name": entity.name,
                    "start_position": list(event.start_position),
                    "end_position": list(event.end_position),
                    "path": [list(p) for p in event.path] if event.path else []
                }

    elif target_type == TargetType.POSITION_AOE:

        if event and event.combat_log:
            event_data = event.combat_log.to_dict()["data"]

    elif target_type == TargetType.MULTI_ENTITY:

        if event and event.combat_log:
            event_data = event.combat_log.to_dict()["data"]

    elif target_type == TargetType.SELF:

        if event and event.combat_log:
            event_data = event.combat_log.to_dict()["data"]
        elif event:
            event_data = {
                "entity_name": entity.name,
                "action_name": request.template_name,
            }

    if event and event.target_entity_uuid:
        target = Entity.get(event.target_entity_uuid)
        target_hp = target.get_hp() if target else None
        if event_data is not None and target_hp is not None:
            event_data["target_hp"] = target_hp
    if timing is not None:
        timing.add("build_event_data_ms", started)

    started = time.perf_counter()
    action_log_entries: list = []
    triggered_reactions: list = []
    if sim.encounter:
        new_entries = sim.encounter.combat_log[log_start_index:]
        for entry in new_entries:
            entry_dict = entry.to_dict()
            action_log_entries.append(entry_dict)

            if entry.entry_type.value == "attack" and entry.target_uuid and str(entry.target_uuid) == str(entity.uuid):
                oa_data = entry.to_dict()["data"]
                oa_data["type"] = "opportunity_attack"
                oa_data["is_opportunity_attack"] = True
                triggered_reactions.append(oa_data)

    if not action_log_entries and event and event.combat_log:
        action_log_entries.append(event.combat_log.to_dict())
    if timing is not None:
        timing.add("collect_combat_logs_ms", started)

    game_state = None
    if request.include_state:
        started = time.perf_counter()
        grid = get_map()
        floor_objects = []
        for obj_uuid, obj_pos in grid._object_positions.items():
            obj = BaseBlock.get(obj_uuid)
            if obj:
                map_char = getattr(obj, 'map_char', '\u03c6')
                floor_objects.append(APIFloorObject(
                    uuid=str(obj_uuid),
                    name=obj.name or "Object",
                    position=obj_pos,
                    map_char=map_char,
                    state=_get_floor_object_state(obj),
                ))
        game_state = APIGameState(
            grid=APIGrid.create(grid, requesting_entity_uuid=entity.uuid),
            entities=[APIEntitySummary.create(e) for e in Entity.get_all_entities()],
            encounter=APIEncounter.create(sim.encounter) if sim.encounter else None,
            floor_objects=floor_objects,
        )
        if timing is not None:
            timing.add("build_game_state_ms", started)

    started = time.perf_counter()
    final_entity_hp = entity.get_hp()
    if timing is not None:
        timing.add("final.entity_hp_ms", started)

    started = time.perf_counter()
    cursor_fields = action_cursor_fields()
    if timing is not None:
        timing.add("final.action_cursor_fields_ms", started)

    if event is None:
        action_message = f"{request.template_name} could not be executed"
    elif event.status_message:
        action_message = event.status_message
    elif event.canceled:
        action_message = f"{request.template_name} was rejected"
    else:
        action_message = f"{request.template_name} executed"

    started = time.perf_counter()
    action_result = ActionResult(
        success=not event.canceled if event else False,
        message=action_message,
        event_type=request.template_name.lower(),
        outcome_code=event.outcome_code if event else None,
        event_data=event_data,
        entity_hp=final_entity_hp,
        target_hp=target_hp,
        deaths=death_names,
        triggered_reactions=triggered_reactions,
        turn_continues=not encounter_ended and entity.has_hp,
        encounter_ended=encounter_ended,
        combat_log_entries=action_log_entries,
        available_actions=updated_actions,
        state=game_state,
        server_timing=None,
        **cursor_fields,
    )
    if timing is not None:
        timing.add("build_action_result_model_ms", started)
        action_result.server_timing = APIServerTiming.model_validate(timing.payload())
    return action_result


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


def _game_creation_preflight(
    request: GameCreationPreflightRequest,
) -> CompatibilityReport:
    """Validate one composed scenario selection without constructing engine state.

    Args:
        request: Four canonical scenario component identifiers.

    Returns:
        Static compatibility report for the selected components.

    Raises:
        HTTPException: If a component identifier is unknown.
    """
    try:
        hero = get_combatant_configuration(request.hero_configuration_id)
        monsters = get_combatant_configuration(request.monster_configuration_id)
        battlefield = get_battlefield(request.battlefield_id)
        deployment = get_deployment(request.deployment_id)
    except ValueError as exc:
        raise _api_http_exception(
            status_code=400,
            code="invalid_game_creation_component",
            message=str(exc),
            selection=request.model_dump(mode="json"),
            valid_hero_configuration_ids=[spec.configuration_id for spec in HERO_CONFIGURATIONS],
            valid_monster_configuration_ids=[spec.configuration_id for spec in MONSTER_PARTY_CONFIGURATIONS],
            valid_battlefield_ids=[spec.battlefield_id for spec in BATTLEFIELDS],
            valid_deployment_ids=[spec.deployment_id for spec in DEPLOYMENTS],
        ) from exc
    return check_compatibility(hero, monsters, battlefield, deployment)


def _game_creation_selection(
    scenario: GameCreationPresetScenario | GameCreationComposedScenario,
) -> tuple[GameCreationPreflightRequest, Optional[str]]:
    """Resolve a preset or composed selection to four canonical component ids.

    Args:
        scenario: Discriminated game-creation scenario request.

    Returns:
        Preflight request and optional historical preset identifier.

    Raises:
        HTTPException: If a preset identifier is unknown.
    """
    if isinstance(scenario, GameCreationComposedScenario):
        return GameCreationPreflightRequest(
            hero_configuration_id=scenario.hero_configuration_id,
            monster_configuration_id=scenario.monster_configuration_id,
            battlefield_id=scenario.battlefield_id,
            deployment_id=scenario.deployment_id,
        ), None
    try:
        recipe = get_legacy_recipe(scenario.arena_id)
    except ValueError as exc:
        raise _api_http_exception(
            status_code=400,
            code="invalid_game_creation_preset",
            message=str(exc),
            arena_id=scenario.arena_id,
            valid_arena_ids=[recipe.arena_id for recipe in LEGACY_RECIPES],
        ) from exc
    return GameCreationPreflightRequest(
        hero_configuration_id=recipe.hero_configuration_id,
        monster_configuration_id=recipe.monster_configuration_id,
        battlefield_id=recipe.battlefield_id,
        deployment_id=recipe.deployment_id,
    ), recipe.arena_id


def _set_game_creation_side_controllers(
    encounter: Encounter,
    entities: tuple[Entity, ...],
    controller_kind: str,
) -> None:
    """Assign the configured external boundary controller to one exact side."""
    controller_class = HumanController if controller_kind == "human" else ExternalAIController
    for entity in entities:
        encounter.set_controller_for(
            entity.uuid,
            controller_class(source_entity_uuid=entity.uuid),
        )


def _create_game_creation_ai_session(
    game: GameSession,
    entities: tuple[Entity, ...],
    participant: GameCreationSideRequest,
    side_id: str,
) -> Optional[PlayerSession]:
    """Create and assign one side-scoped AI session when required."""
    if participant.controller == "human":
        return None
    manager = sim.get_session_manager()
    label = participant.name
    if participant.controller == "codex":
        label = f"{participant.name} fallback AI"
    session = manager.create_session(PlayerType.AI, label)
    game.add_player(session)
    for entity in entities:
        game.assign_entity(entity.uuid, session.session_id)
    logger.info("Created %s fallback session %s for %s", participant.controller, session.session_id, side_id)
    return session


def _game_creation_side_result(
    *,
    side_id: Literal["side_a", "side_b"],
    title: str,
    entities: tuple[Entity, ...],
    participant: GameCreationSideRequest,
    fallback_session: Optional[PlayerSession],
    takeover_claim: Optional[TakeoverClaim],
) -> GameCreationSideResult:
    """Serialize one resolved side assignment."""
    return GameCreationSideResult(
        side_id=side_id,
        title=title,
        controller=participant.controller,
        participant_name=participant.name,
        entities=[APIEntitySummary.create(entity) for entity in entities],
        human_entity_uuids=(
            [str(entity.uuid) for entity in entities]
            if participant.controller == "human"
            else []
        ),
        fallback_ai_session_id=(
            str(fallback_session.session_id)
            if fallback_session is not None
            else None
        ),
        codex_session_id=(
            str(takeover_claim.session_id)
            if takeover_claim is not None
            else None
        ),
        takeover_claim_id=(
            str(takeover_claim.claim_id)
            if takeover_claim is not None
            else None
        ),
        takeover_expires_at=(
            takeover_claim.expires_at
            if takeover_claim is not None
            else None
        ),
    )


@app.get("/game-creation/catalog", response_model=GameCreationCatalogResponse)
async def get_game_creation_catalog() -> GameCreationCatalogResponse:
    """Return canonical scenarios, formations, and controller choices."""
    specs_by_id = {
        spec.arena_id: spec
        for spec in list_ai_validation_arena_specs()
    }
    presets = []
    for recipe in LEGACY_RECIPES:
        spec = specs_by_id[recipe.arena_id]
        presets.append(GameCreationPreset(
            arena_id=recipe.arena_id,
            title=spec.title,
            tags=list(spec.tags),
            expected_pressure=list(spec.expected_pressure),
            map_notes=list(spec.map_notes),
            recipe=recipe,
        ))
    return GameCreationCatalogResponse(
        controllers=["human", "ai", "codex"],
        opening_sides=["initiative", "side_a", "side_b"],
        hero_configurations=list(HERO_CONFIGURATIONS),
        monster_configurations=list(MONSTER_PARTY_CONFIGURATIONS),
        battlefields=list(BATTLEFIELDS),
        deployments=list(DEPLOYMENTS),
        presets=presets,
    )


@app.post("/game-creation/preflight", response_model=CompatibilityReport)
async def preflight_game_creation(
    request: GameCreationPreflightRequest,
) -> CompatibilityReport:
    """Check a composed scenario without replacing the active game."""
    return _game_creation_preflight(request)


@app.post("/game-creation/start", response_model=GameCreationStartResponse)
async def start_created_game(
    request: Request,
    creation: GameCreationStartRequest,
) -> GameCreationStartResponse:
    """Atomically assemble a scenario and configure both controller sides."""
    selection, preset_arena_id = _game_creation_selection(creation.scenario)
    static_report = _game_creation_preflight(selection)
    if not static_report.admitted:
        raise _api_http_exception(
            status_code=400,
            code="incompatible_game_creation",
            message="The selected scenario components are incompatible",
            compatibility=static_report.model_dump(mode="json"),
        )

    await prepare_new_simulation_start()
    opening_faction = {
        "initiative": None,
        "side_a": "heroes",
        "side_b": "monsters",
    }[creation.opening_side]
    try:
        if preset_arena_id is not None:
            arena = assemble_legacy_scenario(
                preset_arena_id,
                opening_faction=opening_faction,
            )
            compatibility = static_report
        else:
            assembled = assemble_composed_scenario(
                selection.hero_configuration_id,
                selection.monster_configuration_id,
                selection.battlefield_id,
                selection.deployment_id,
                opening_faction=opening_faction,
            )
            arena = assembled.arena
            compatibility = assembled.compatibility
    except (IncompatibleScenarioError, ValueError) as exc:
        raise _api_http_exception(
            status_code=400,
            code="game_creation_assembly_failed",
            message=str(exc),
            selection=selection.model_dump(mode="json"),
        ) from exc

    sim.encounter = arena.encounter
    sim.paused = False
    sim.encounter.clear_combat_log()
    side_a = tuple(arena.side_a)
    side_b = tuple(arena.side_b)
    _set_game_creation_side_controllers(sim.encounter, side_a, creation.side_a.controller)
    _set_game_creation_side_controllers(sim.encounter, side_b, creation.side_b.controller)

    game = sim.create_game_session(sim.encounter)
    side_a_fallback = _create_game_creation_ai_session(
        game,
        side_a,
        creation.side_a,
        "side_a",
    )
    side_b_fallback = _create_game_creation_ai_session(
        game,
        side_b,
        creation.side_b,
        "side_b",
    )

    claims: dict[str, TakeoverClaim] = {}
    ownership_boundary = prepare_observation_ownership_change(sim.get_session_manager())
    try:
        for side_id, entities, participant in (
            ("side_a", side_a, creation.side_a),
            ("side_b", side_b, creation.side_b),
        ):
            if participant.controller != "codex":
                continue
            claims[side_id] = ai_takeover_manager.claim(
                encounter=sim.encounter,
                game=game,
                session_manager=sim.get_session_manager(),
                faction=None,
                entity_uuids=[entity.uuid for entity in entities],
                name=participant.name,
                lease_seconds=creation.codex_lease_seconds,
            )
    except TakeoverError as exc:
        ai_takeover_manager.clear(sim.encounter, game)
        raise _takeover_http_exception(exc, faction=None) from exc
    _publish_takeover_ownership_changes(ownership_boundary, "game_creation_claimed")

    base_url = str(request.base_url).rstrip("/")
    try:
        for session in (side_a_fallback, side_b_fallback):
            if session is not None:
                ai_process_manager.start_external_agent(session.session_id, base_url)
    except AIProcessStartError as exc:
        ai_process_manager.stop_all()
        ai_takeover_manager.clear(sim.encounter, game)
        raise _api_http_exception(
            status_code=500,
            code="ai_process_start_failed",
            message="Failed to start a configured AI side",
            error=str(exc),
        ) from exc

    advance = await advance_encounter()
    hero_spec = get_combatant_configuration(selection.hero_configuration_id)
    monster_spec = get_combatant_configuration(selection.monster_configuration_id)
    return GameCreationStartResponse(
        scenario_kind=creation.scenario.kind,
        preset_arena_id=preset_arena_id,
        encounter_uuid=str(sim.encounter.uuid),
        game_id=str(game.game_id),
        encounter_name=sim.encounter.name,
        opening_side=creation.opening_side,
        compatibility=compatibility,
        side_a=_game_creation_side_result(
            side_id="side_a",
            title=hero_spec.title,
            entities=side_a,
            participant=creation.side_a,
            fallback_session=side_a_fallback,
            takeover_claim=claims.get("side_a"),
        ),
        side_b=_game_creation_side_result(
            side_id="side_b",
            title=monster_spec.title,
            entities=side_b,
            participant=creation.side_b,
            fallback_session=side_b_fallback,
            takeover_claim=claims.get("side_b"),
        ),
        **advance.model_dump(mode="json"),
    )


@app.post("/simulation/start-human", response_model=StartHumanSimulationResponse)
async def start_human_simulation(
    request: Request,
    character_class: str = "fighter",
) -> StartHumanSimulationResponse:
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

    ai_process_manager.stop_all()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()

    sim.encounter = setup_arena_combat(
        pvp_mode=False,
        character_class=character_class,
    )
    prioritize_hero_opening_turn(sim.encounter)
    sim.paused = False
    sim.encounter.clear_combat_log()

    game = sim.create_game_session(sim.encounter)

    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Monsters")
    game.add_player(ai_session)

    for entity in Entity.get_all_entities():
        if entity.faction == "monsters":
            game.assign_entity(entity.uuid, ai_session.session_id)

    try:
        ai_process_manager.start_external_agent(
            ai_session.session_id,
            str(request.base_url).rstrip("/"),
        )
    except AIProcessStartError as exc:
        raise _api_http_exception(
            status_code=500,
            code="ai_process_start_failed",
            message="Failed to start external AI subprocess",
            session_id=str(ai_session.session_id),
            error=str(exc),
        )

    result = await advance_encounter()

    hero_uuid = None
    for entity in Entity.get_all_entities():
        if entity.faction == "heroes":
            hero_uuid = str(entity.uuid)
            break

    return StartHumanSimulationResponse(
        **{**result.model_dump(mode="python"), "status": "started"},
        ai_session_id=str(ai_session.session_id),
        encounter_uuid=str(sim.encounter.uuid),
        hero_uuid=hero_uuid,
        message="Create a session and join with hero_uuid to control the Hero",
    )


@app.get("/simulation/ai-validation-arenas")
async def list_ai_validation_arenas():
    """Return opt-in AI validation arena specs."""
    return {
        "arenas": [
            asdict(spec)
            for spec in list_ai_validation_arena_specs()
        ]
    }


@app.post("/simulation/start-ai-validation")
async def start_ai_validation_simulation(
    request: Request,
    arena_id: str = "standard_skeleton_doors",
    mode: str = "human_hero",
):
    """Start an explicit AI validation arena.

    Args:
        arena_id: Stable id from `/simulation/ai-validation-arenas`.
        mode: `human_hero` for a player/Codex hero against external monsters,
            or `codex_monsters` for an external hero against Codex monsters.

    Returns:
        Validation arena bootstrap payload with session and actor ids.
    """
    if mode not in {"human_hero", "codex_monsters"}:
        raise _api_http_exception(
            status_code=400,
            code="invalid_validation_mode",
            message="mode must be 'human_hero' or 'codex_monsters'",
            mode=mode,
            valid_modes=["human_hero", "codex_monsters"],
        )

    await prepare_new_simulation_start()

    try:
        arena = create_ai_validation_arena(arena_id)
    except ValueError as exc:
        raise _api_http_exception(
            status_code=400,
            code="invalid_validation_arena",
            message=str(exc),
            arena_id=arena_id,
            valid_arena_ids=[spec.arena_id for spec in list_ai_validation_arena_specs()],
        )

    sim.encounter = arena.encounter
    apply_validation_arena_controllers(sim.encounter, mode)
    prioritize_hero_opening_turn(sim.encounter)
    sim.encounter.clear_combat_log()

    game = sim.create_game_session(sim.encounter)
    mgr = sim.get_session_manager()

    ai_session = mgr.create_session(
        PlayerType.AI,
        "AI Monsters" if mode == "human_hero" else "AI Hero",
    )
    game.add_player(ai_session)
    takeover_claim: Optional[TakeoverClaim] = None

    for entity in Entity.get_all_entities():
        if mode == "human_hero" and entity.faction == "monsters":
            game.assign_entity(entity.uuid, ai_session.session_id)
        elif mode == "codex_monsters" and entity.faction == "heroes":
            game.assign_entity(entity.uuid, ai_session.session_id)

    if mode == "codex_monsters":
        ownership_boundary = prepare_observation_ownership_change(mgr)
        try:
            takeover_claim = ai_takeover_manager.claim(
                encounter=sim.encounter,
                game=game,
                session_manager=mgr,
                faction="monsters",
                name="Codex Validation Monsters",
                lease_seconds=600.0,
            )
        except TakeoverError as error:
            raise _takeover_http_exception(error, faction="monsters")
        _publish_takeover_ownership_changes(
            ownership_boundary,
            "validation_takeover_claimed",
        )

    try:
        ai_process_manager.start_external_agent(
            ai_session.session_id,
            str(request.base_url).rstrip("/"),
        )
    except AIProcessStartError as exc:
        raise _api_http_exception(
            status_code=500,
            code="ai_process_start_failed",
            message="Failed to start external AI subprocess",
            session_id=str(ai_session.session_id),
            error=str(exc),
        )

    result = await advance_encounter()
    hero_rows = [
        {
            "entity_uuid": str(entity.uuid),
            "entity_name": entity.name,
        }
        for entity in Entity.get_all_entities()
        if entity.faction == "heroes"
    ]
    monster_rows = [
        {
            "entity_uuid": str(entity.uuid),
            "entity_name": entity.name,
        }
        for entity in Entity.get_all_entities()
        if entity.faction == "monsters"
    ]

    return {
        "status": "started",
        "mode": mode,
        "arena_id": arena.spec.arena_id,
        "arena_title": arena.spec.title,
        "arena_tags": list(arena.spec.tags),
        "ai_session_id": str(ai_session.session_id),
        "codex_session_id": str(takeover_claim.session_id) if takeover_claim else None,
        "takeover_claim_id": str(takeover_claim.claim_id) if takeover_claim else None,
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": hero_rows[0]["entity_uuid"] if hero_rows else None,
        "heroes": hero_rows,
        "monsters": monster_rows,
        **result.model_dump(mode="json"),
    }


@app.post("/simulation/start-codex-monsters")
async def start_codex_monsters_simulation(
    request: Request,
    character_class: str = "fighter",
):
    """Start a manual self-play arena with an external-AI hero.

    This is the inverse of `/simulation/start-human`: the Hero is assigned to
    the local external AI process, while the monster faction waits for a Codex
    operator to attach through `/ai/takeover`.

    Args:
        character_class: Hero fixture to create for the automated opponent.

    Returns:
        Arena bootstrap payload with the AI hero session and monster UUIDs.
    """
    if sim.combat_task and not sim.combat_task.done():
        sim.combat_task.cancel()
        try:
            await sim.combat_task
        except asyncio.CancelledError:
            pass

    ai_process_manager.stop_all()
    ai_takeover_manager.clear(sim.encounter, sim.game)
    clear_subjective_projection_state()
    agent_event_stream.clear_all()

    sim.encounter = setup_arena_combat(
        pvp_mode=True,
        character_class=character_class,
    )
    prioritize_hero_opening_turn(sim.encounter)

    hero = next((entity for entity in Entity.get_all_entities() if entity.faction == "heroes"), None)
    if hero is None:
        raise _api_http_exception(
            status_code=500,
            code="hero_not_found",
            message="Could not create Hero for Codex monster arena",
        )
    sim.encounter.set_controller_for(hero.uuid, ExternalAIController(source_entity_uuid=hero.uuid))
    sim.paused = False
    sim.encounter.clear_combat_log()

    game = sim.create_game_session(sim.encounter)
    mgr = sim.get_session_manager()
    ai_session = mgr.create_session(PlayerType.AI, "AI Hero")
    game.add_player(ai_session)
    game.assign_entity(hero.uuid, ai_session.session_id)

    try:
        ai_process_manager.start_external_agent(
            ai_session.session_id,
            str(request.base_url).rstrip("/"),
        )
    except AIProcessStartError as exc:
        raise _api_http_exception(
            status_code=500,
            code="ai_process_start_failed",
            message="Failed to start external AI subprocess",
            session_id=str(ai_session.session_id),
            error=str(exc),
        )

    result = await advance_encounter()
    monster_rows = [
        {
            "entity_uuid": str(entity.uuid),
            "entity_name": entity.name,
        }
        for entity in Entity.get_all_entities()
        if entity.faction == "monsters"
    ]

    return {
        "status": "started",
        "mode": "codex_monsters",
        "hero_ai_session_id": str(ai_session.session_id),
        "encounter_uuid": str(sim.encounter.uuid),
        "hero_uuid": str(hero.uuid),
        "monsters": monster_rows,
        "message": "Attach current Codex to faction=monsters to control the skeleton side.",
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
    prioritize_hero_opening_turn(sim.encounter)
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
                            event_data = serialize_event(event)
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
