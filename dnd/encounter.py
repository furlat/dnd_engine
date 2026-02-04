"""
Encounter - Turn-based combat management.

The Encounter class orchestrates combat:
- Tracks combatants and their controllers
- Manages initiative order
- Handles turn/round lifecycle
- Fires appropriate events
- Integrates with action economy and conditions
"""

from typing import Optional, Dict, List, ClassVar, Tuple

__all__ = [
    "EncounterState",
    "TurnState",
    "AdvanceResult",
    "Encounter",
]
from uuid import UUID
from datetime import datetime
from pydantic import Field
from enum import Enum

from dnd.core.base_object import BaseObject
from dnd.core.dice import Dice, RollType
from dnd.core.events import (
    Event, EventPhase,
    EncounterStartEvent, EncounterEndEvent,
    RoundStartEvent, RoundEndEvent,
    TurnStartEvent, TurnEndEvent,
    DeathEvent, UnconsciousEvent
)
from dnd.core.combat_log import CombatLogEntry
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.controller import Controller, TurnContext


class EncounterState(str, Enum):
    """Current state of the encounter."""
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class TurnState(str, Enum):
    """Current state of a turn."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class AdvanceResult(BaseObject):
    """Result of advancing through turns via advance_until_player()."""

    status: str = Field(description="Result status: waiting_for_human, waiting_for_claude, encounter_ended, error")
    entity_uuid: Optional[UUID] = Field(default=None, description="UUID of entity waiting for input")
    entity_name: Optional[str] = Field(default=None, description="Name of entity waiting for input")
    round_number: int = Field(default=0, description="Current round number")
    turn_index: int = Field(default=0, description="Current turn index")
    log_start_index: int = Field(default=0, description="Combat log index before AI turns (for fetching new entries)")


class CombatantState(BaseObject):
    """
    Per-entity state within an encounter.

    Tracks initiative, controller assignment, and turn-specific state.
    """

    entity_uuid: UUID = Field(description="UUID of the entity")
    controller_uuid: UUID = Field(description="UUID of the controller for this entity")

    # Initiative
    initiative_roll: int = Field(default=0, description="The d20 roll for initiative")
    initiative_bonus: int = Field(default=0, description="Modifier added to initiative")
    initiative_total: int = Field(default=0, description="Final initiative value")

    # Turn tracking
    has_acted_this_round: bool = Field(default=False, description="Whether entity has taken their turn this round")
    turn_count: int = Field(default=0, description="Number of turns this entity has taken")

    # Special states
    surprised: bool = Field(default=False, description="Cannot act in first round if surprised")
    delaying: bool = Field(default=False, description="Holding action to act later")
    is_dead: bool = Field(default=False, description="Whether this combatant is dead")

    @property
    def entity(self) -> Optional[Entity]:
        """Get the entity for this combatant."""
        return Entity.get(self.entity_uuid)

    @property
    def controller(self) -> Optional[Controller]:
        """Get the controller for this combatant."""
        return Controller.get(self.controller_uuid)

    @property
    def is_alive(self) -> bool:
        """Check if combatant is alive (not dead and has HP > 0)."""
        if self.is_dead:
            return False
        entity = self.entity
        if entity is None:
            return False
        return entity.get_hp() > 0


class Encounter(BaseObject):
    """
    Manages a tactical combat encounter.

    Responsibilities:
    - Track combatants and initiative order
    - Manage turn/round progression
    - Fire lifecycle events
    - Coordinate with entity action economy and conditions
    """

    # Class-level registry
    _encounter_registry: ClassVar[Dict[UUID, 'Encounter']] = {}

    name: str = Field(default="Encounter", description="Name of this encounter")

    # Combatants
    combatants: Dict[UUID, CombatantState] = Field(
        default_factory=dict,
        description="Entity UUID -> CombatantState"
    )

    # Turn order
    initiative_order: List[UUID] = Field(
        default_factory=list,
        description="Entity UUIDs sorted by initiative (highest first)"
    )
    current_turn_index: int = Field(default=0, description="Index into initiative_order")
    round_number: int = Field(default=0, description="Current round (1-indexed when active)")

    # State
    state: EncounterState = Field(default=EncounterState.NOT_STARTED)
    turn_state: TurnState = Field(default=TurnState.NOT_STARTED)
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)

    # Combat log - unified log for all players
    combat_log: List[CombatLogEntry] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._encounter_registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Encounter']:
        """Get an encounter by UUID."""
        return cls._encounter_registry.get(uuid)

    @classmethod
    def clear_registry(cls) -> None:
        """Clear the encounter registry (for testing)."""
        cls._encounter_registry.clear()

    # =========================================================================
    # Combatant Management
    # =========================================================================

    def add_combatant(
        self,
        entity: Entity,
        controller: Controller,
        surprised: bool = False
    ) -> CombatantState:
        """
        Add an entity to the encounter.

        Args:
            entity: The entity to add
            controller: The controller that will manage this entity
            surprised: Whether this entity is surprised (can't act round 1)

        Returns:
            The created CombatantState
        """
        if entity.uuid in self.combatants:
            raise ValueError(f"Entity {entity.uuid} already in encounter")

        # Initiative bonus from entity.initiative (includes DEX mod + feats)
        init_bonus = entity.initiative.normalized_score

        combatant = CombatantState(
            source_entity_uuid=entity.uuid,
            entity_uuid=entity.uuid,
            controller_uuid=controller.uuid,
            initiative_bonus=init_bonus,
            surprised=surprised
        )

        self.combatants[entity.uuid] = combatant
        return combatant

    def remove_combatant(self, entity_uuid: UUID) -> Optional[CombatantState]:
        """
        Remove an entity from the encounter.

        Args:
            entity_uuid: UUID of the entity to remove

        Returns:
            The removed CombatantState, or None if not found
        """
        combatant = self.combatants.pop(entity_uuid, None)
        if combatant and entity_uuid in self.initiative_order:
            # Adjust current_turn_index if needed
            removed_index = self.initiative_order.index(entity_uuid)
            self.initiative_order.remove(entity_uuid)

            if removed_index < self.current_turn_index:
                self.current_turn_index -= 1
            elif removed_index == self.current_turn_index:
                # Current entity removed, index now points to next
                if self.current_turn_index >= len(self.initiative_order):
                    self.current_turn_index = 0

        return combatant

    def get_combatant(self, entity_uuid: UUID) -> Optional[CombatantState]:
        """Get combatant state for an entity."""
        return self.combatants.get(entity_uuid)

    def get_controller_for(self, entity_uuid: UUID) -> Optional[Controller]:
        """Get the controller for an entity in this encounter."""
        combatant = self.combatants.get(entity_uuid)
        return combatant.controller if combatant else None

    # =========================================================================
    # Initiative
    # =========================================================================

    def roll_initiative(self) -> None:
        """
        Roll initiative for all combatants and establish turn order.

        Ties are broken by:
        1. Higher DEX modifier
        2. Random (the earlier roll wins)
        """
        # Roll for each combatant
        for combatant in self.combatants.values():
            entity = combatant.entity
            if not entity:
                continue
            # Use entity.initiative as the bonus (includes DEX mod + feats)
            dice = Dice(count=1, value=20, bonus=entity.initiative, roll_type=RollType.CHECK)
            roll = dice.roll
            # roll.results is Union[List[int], int] - for 1d20 it's an int
            roll_result = roll.results if isinstance(roll.results, int) else roll.results[0]
            combatant.initiative_roll = roll_result
            combatant.initiative_total = roll.total

        # Sort by initiative (highest first), then by DEX mod for ties
        sorted_combatants = sorted(
            self.combatants.values(),
            key=lambda c: (c.initiative_total, c.initiative_bonus),
            reverse=True
        )

        self.initiative_order = [c.entity_uuid for c in sorted_combatants]

    def get_initiative_order_display(self) -> List[Tuple[str, int, int]]:
        """
        Get initiative order for display.

        Returns:
            List of (entity_name, initiative_total, initiative_roll)
        """
        result = []
        for entity_uuid in self.initiative_order:
            combatant = self.combatants[entity_uuid]
            entity = combatant.entity
            name = entity.name if entity else "Unknown"
            result.append((name, combatant.initiative_total, combatant.initiative_roll))
        return result

    # =========================================================================
    # Current Turn/Entity
    # =========================================================================

    def get_current_entity(self) -> Optional[Entity]:
        """Get the entity whose turn it is."""
        if not self.initiative_order or self.state != EncounterState.ACTIVE:
            return None
        entity_uuid = self.initiative_order[self.current_turn_index]
        return Entity.get(entity_uuid)

    def get_current_combatant(self) -> Optional[CombatantState]:
        """Get the combatant state for current turn."""
        if not self.initiative_order or self.state != EncounterState.ACTIVE:
            return None
        entity_uuid = self.initiative_order[self.current_turn_index]
        return self.combatants.get(entity_uuid)

    def get_current_controller(self) -> Optional[Controller]:
        """Get the controller for the current turn."""
        combatant = self.get_current_combatant()
        return combatant.controller if combatant else None

    # =========================================================================
    # Encounter Lifecycle
    # =========================================================================

    def start_encounter(self) -> EncounterStartEvent:
        """
        Start the encounter.

        Rolls initiative if not already done, notifies controllers,
        and fires EncounterStartEvent.
        """
        if self.state != EncounterState.NOT_STARTED:
            raise ValueError(f"Cannot start encounter in state {self.state}")

        if not self.combatants:
            raise ValueError("Cannot start encounter with no combatants")

        # Roll initiative if not done
        if not self.initiative_order:
            self.roll_initiative()

        self.state = EncounterState.ACTIVE
        self.started_at = datetime.now()
        self.round_number = 1

        # Notify controllers
        self._notify_controllers_encounter_start()

        # Fire event
        event = EncounterStartEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            combatant_uuids=list(self.combatants.keys()),
            initiative_order=self.initiative_order.copy(),
            phase=EventPhase.COMPLETION
        )

        # Start round 1
        self._fire_round_start()

        return event

    def end_encounter(self, reason: str = "Combat ended") -> EncounterEndEvent:
        """
        End the encounter.

        Args:
            reason: Why the encounter ended

        Returns:
            EncounterEndEvent
        """
        if self.state == EncounterState.ENDED:
            raise ValueError("Encounter already ended")

        # End current turn if in progress
        if self.turn_state == TurnState.IN_PROGRESS:
            self.end_turn()

        self.state = EncounterState.ENDED
        self.ended_at = datetime.now()

        # Notify controllers
        self._notify_controllers_encounter_end()

        # Fire event
        event = EncounterEndEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            combatant_uuids=list(self.combatants.keys()),
            reason=reason,
            phase=EventPhase.COMPLETION
        )

        return event

    # =========================================================================
    # Round Lifecycle
    # =========================================================================

    def _fire_round_start(self) -> RoundStartEvent:
        """Fire round start event."""
        event = RoundStartEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            round_number=self.round_number,
            phase=EventPhase.COMPLETION
        )
        return event

    def _fire_round_end(self) -> RoundEndEvent:
        """Fire round end event."""
        event = RoundEndEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            round_number=self.round_number,
            phase=EventPhase.COMPLETION
        )
        return event

    def _advance_round(self) -> None:
        """Advance to the next round."""
        self._fire_round_end()

        self.round_number += 1
        self.current_turn_index = 0

        # Reset has_acted_this_round for all combatants
        for combatant in self.combatants.values():
            combatant.has_acted_this_round = False

        self._fire_round_start()

    # =========================================================================
    # Turn Lifecycle
    # =========================================================================

    def start_turn(self) -> Optional[TurnStartEvent]:
        """
        Start the current entity's turn.

        1. Call entity.on_turn_start() which handles:
           - TurnStartEvent firing through phases (handlers can respond)
           - Condition duration advancement
           - Action economy reset and resource recharge
        2. Update senses
        3. Notify controller
        """
        if self.state != EncounterState.ACTIVE:
            return None

        if self.turn_state == TurnState.IN_PROGRESS:
            raise ValueError("Turn already in progress, call end_turn first")

        entity = self.get_current_entity()
        combatant = self.get_current_combatant()
        controller = self.get_current_controller()

        if not entity or not combatant:
            return None

        # Skip surprised entities in round 1
        if combatant.surprised and self.round_number == 1:
            combatant.has_acted_this_round = True
            return self._skip_to_next_turn()

        # Skip dead combatants
        if combatant.is_dead or not combatant.is_alive:
            combatant.has_acted_this_round = True
            return self._skip_to_next_turn()

        self.turn_state = TurnState.IN_PROGRESS

        # Entity handles turn-start logic:
        # - Fires TurnStartEvent through DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
        # - Handlers (like Survivor) trigger at EXECUTION phase
        # - Advances condition durations
        # - Resets action economy and recharges TURN_START resources
        event = entity.on_turn_start(
            encounter_uuid=self.uuid,
            round_number=self.round_number,
            turn_index=self.current_turn_index
        )

        # Add turn start to combat log
        self.add_event_to_combat_log(event)

        # Update senses (use larger range to cover typical combat arenas)
        entity.update_entity_senses(max_distance=20)

        # Notify controller
        if controller:
            context = self._build_turn_context(entity)
            controller.on_turn_start(entity, context)

        return event

    def end_turn(self) -> Optional[TurnEndEvent]:
        """
        End the current entity's turn.

        1. Entity handles turn-end logic via on_turn_end():
           - Fires TurnEndEvent through phases (handlers can respond at EXECUTION)
        2. Notify controller
        3. Update combatant state
        """
        if self.state != EncounterState.ACTIVE:
            return None

        if self.turn_state != TurnState.IN_PROGRESS:
            return None

        entity = self.get_current_entity()
        combatant = self.get_current_combatant()
        controller = self.get_current_controller()

        if not entity or not combatant:
            return None

        # Entity handles turn-end logic with proper phase progression
        # Handlers (like rage maintenance) trigger at EXECUTION phase
        event = entity.on_turn_end(
            encounter_uuid=self.uuid,
            round_number=self.round_number,
            turn_index=self.current_turn_index
        )

        # Add turn end to combat log
        self.add_event_to_combat_log(event)

        # Notify controller
        if controller:
            context = self._build_turn_context(entity)
            controller.on_turn_end(entity, context)

        # Mark turn complete
        combatant.has_acted_this_round = True
        combatant.turn_count += 1
        self.turn_state = TurnState.ENDED

        return event

    def next_turn(self) -> Optional[TurnStartEvent]:
        """
        Advance to the next turn.

        Ends current turn if in progress, then starts the next one.
        May advance to next round if all entities have acted.
        """
        if self.state != EncounterState.ACTIVE:
            return None

        # End current turn if in progress
        if self.turn_state == TurnState.IN_PROGRESS:
            self.end_turn()

        # Move to next entity
        self.current_turn_index += 1

        # Check if round is over
        if self.current_turn_index >= len(self.initiative_order):
            self._advance_round()

        self.turn_state = TurnState.NOT_STARTED
        return self.start_turn()

    def _skip_to_next_turn(self) -> Optional[TurnStartEvent]:
        """Skip to next turn without ending current (for surprised entities)."""
        self.current_turn_index += 1

        if self.current_turn_index >= len(self.initiative_order):
            self._advance_round()

        return self.start_turn()

    # =========================================================================
    # Action Economy Queries
    # =========================================================================

    def can_continue_turn(self) -> bool:
        """
        Check if the current entity can still act.

        Returns True if entity has any action economy remaining.
        """
        entity = self.get_current_entity()
        if not entity:
            return False

        ae = entity.action_economy

        # Check if any resource is available
        has_action = ae.can_afford("actions", 1)
        has_bonus = ae.can_afford("bonus_actions", 1)
        has_movement = ae.can_afford("movement", 5)  # At least 5ft

        return has_action or has_bonus or has_movement

    def get_remaining_action_economy(self) -> Dict[str, int]:
        """
        Get remaining action economy for current entity.

        Returns dict with actions, bonus_actions, reactions, movement.
        """
        entity = self.get_current_entity()
        if not entity:
            return {"actions": 0, "bonus_actions": 0, "reactions": 0, "movement": 0}

        ae = entity.action_economy
        return {
            "actions": ae.actions.normalized_score,
            "bonus_actions": ae.bonus_actions.normalized_score,
            "reactions": ae.reactions.normalized_score,
            "movement": ae.movement.normalized_score
        }

    def _build_turn_context(self, entity: Entity) -> TurnContext:
        """Build a TurnContext for the current turn state."""
        ae = entity.action_economy
        return TurnContext(
            source_entity_uuid=entity.uuid,
            entity_uuid=entity.uuid,
            round_number=self.round_number,
            turn_index=self.current_turn_index,
            actions_remaining=ae.actions.normalized_score,
            bonus_actions_remaining=ae.bonus_actions.normalized_score,
            reactions_remaining=ae.reactions.normalized_score,
            movement_remaining=ae.movement.normalized_score,
            visible_enemies=entity.get_visible_enemies(),
            visible_allies=entity.get_visible_allies(),
        )

    # =========================================================================
    # Condition Management
    # =========================================================================

    def _advance_entity_conditions(self, entity: Entity) -> List[str]:
        """
        Advance duration for all conditions on entity.

        Called at start of turn. Returns list of removed condition names.
        This timing makes turn-based conditions (Dash, Dodge, Disengage) last
        "until the start of your next turn" per SRD.
        """
        removed = []
        # Copy keys since we might modify during iteration
        condition_names = list(entity.active_conditions.keys())

        for condition_name in condition_names:
            was_removed = entity.advance_duration_condition(condition_name)
            if was_removed:
                removed.append(condition_name)

        return removed

    # =========================================================================
    # Combat Log Management
    # =========================================================================

    def add_event_to_combat_log(self, event: Event) -> Optional[int]:
        """
        Add event's combat_log entry to encounter log.

        Uses event.combat_log if available (auto-generated at COMPLETION phase).

        Args:
            event: The event containing the combat log entry.

        Returns:
            Log entry index if successful, None if no log entry was created.
        """
        if event is None or event.combat_log is None:
            return None

        self.combat_log.append(event.combat_log)
        return len(self.combat_log) - 1

    def get_combat_log(self, since: int = 0) -> List[CombatLogEntry]:
        """
        Get combat log entries since given index.

        Args:
            since: Return entries with index >= since (for polling)

        Returns:
            List of CombatLogEntry
        """
        return self.combat_log[since:]

    def clear_combat_log(self) -> None:
        """Clear the combat log (call when starting new game)."""
        self.combat_log = []

    # =========================================================================
    # Death Handling
    # =========================================================================

    def check_deaths(self) -> List[DeathEvent]:
        """
        Check all combatants for death and handle any that died.

        Called after actions to detect and handle deaths.
        Fires UnconsciousEvent first to allow handlers to react (e.g., rage ending).

        Returns:
            List of DeathEvent for any combatants that died
        """
        death_events = []

        for combatant in self.combatants.values():
            if combatant.is_dead:
                continue  # Already dead

            entity = combatant.entity
            if entity is None:
                continue

            if entity.get_hp() <= 0:
                # Fire UnconsciousEvent first - allows handlers to react
                # (e.g., Barbarian rage ending when unconscious)
                unconscious_event = UnconsciousEvent(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    entity_uuid=entity.uuid,
                    entity_name=entity.name,
                    final_hp=entity.get_hp(),
                    phase=EventPhase.DECLARATION
                )
                # Progress through phases so handlers can react
                unconscious_event = unconscious_event.phase_to(EventPhase.EXECUTION)
                unconscious_event = unconscious_event.phase_to(EventPhase.EFFECT)
                unconscious_event = unconscious_event.phase_to(EventPhase.COMPLETION)

                # Now handle death (entity is still at 0 HP)
                event = self._handle_death(combatant)
                if event:
                    death_events.append(event)

        # Check if encounter should end (only one side remaining)
        if death_events:
            # Note: Senses are updated reactively via DEATH events
            # Each observer's SpatialSensesCallback handles path recalculation
            self._check_encounter_end()

        return death_events

    def _handle_death(self, combatant: CombatantState) -> Optional[DeathEvent]:
        """
        Handle the death of a combatant using the Dead condition.

        Uses condition-based approach for clean resurrection support:
        1. Marks combatant as dead (encounter-level flag)
        2. Marks entity as non-blocking in GridMap (stays registered for resurrection/looting)
        3. Applies Dead condition (includes Incapacitated, disables all action economy)

        Event handlers are PRESERVED - Incapacitated sets reactions=0 so OA won't fire.
        Resurrection can simply: remove Dead condition, set blocking, set HP, mark alive.
        """
        entity = combatant.entity
        if entity is None:
            return None

        combatant.is_dead = True

        # === CLEAN APPROACH: Use Dead condition ===
        # 1. Mark as non-blocking in GridMap (stays registered for resurrection/looting)
        get_map().set_entity_blocking(entity.uuid, blocking=False)

        # 2. Apply Dead condition (includes Incapacitated, disables all action economy)
        #    Event handlers are PRESERVED - Incapacitated sets reactions=0 so OA won't fire
        from dnd.conditions import Dead
        dead_condition = Dead(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
        entity.add_condition(dead_condition, check_save_throw=False)
        # === END CLEAN APPROACH ===

        # Note: Dead entities are filtered from attack targets via
        # get_visible_enemies(include_dead=False) which checks HP.
        # They remain visible for looting, resurrection, corpse-explosion, etc.

        # Fire death event
        event = DeathEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            entity_uuid=entity.uuid,
            entity_name=entity.name,
            final_hp=entity.get_hp(),
            encounter_uuid=self.uuid,
            phase=EventPhase.COMPLETION
        )

        # Manually generate combat_log since we're created directly at COMPLETION
        event.combat_log = event.generate_combat_log()

        # Post event so callbacks (like SpatialSensesCallback) can react
        # This triggers senses recalculation for observers - paths through
        # dead body's cell become available
        event.post()

        return event

    def _check_encounter_end(self) -> bool:
        """
        Check if the encounter should end (only one faction has survivors).

        Uses faction-based detection: entities with same faction are allies.
        Entities with faction=None are treated as their own faction (enemy to all).

        Returns:
            True if encounter ended
        """
        # Collect alive count per faction
        # Entities with faction=None are treated as their own "faction" (uuid-based)
        factions_alive: Dict[str, int] = {}
        for combatant in self.combatants.values():
            entity = combatant.entity
            if entity is None:
                continue
            # Use faction if set, else use entity uuid (each factionless entity is own faction)
            faction_key = entity.faction if entity.faction else str(entity.uuid)
            if faction_key not in factions_alive:
                factions_alive[faction_key] = 0
            if combatant.is_alive:
                factions_alive[faction_key] += 1

        # End if only one faction (or none) has survivors
        factions_with_alive = [f for f, c in factions_alive.items() if c > 0]

        if len(factions_with_alive) <= 1:
            self.end_encounter()
            return True

        return False

    def get_alive_combatants(self) -> List[CombatantState]:
        """Get list of combatants that are still alive."""
        return [c for c in self.combatants.values() if c.is_alive]

    def get_dead_combatants(self) -> List[CombatantState]:
        """Get list of combatants that are dead."""
        return [c for c in self.combatants.values() if c.is_dead]

    # =========================================================================
    # Controller Notifications
    # =========================================================================

    def _notify_controllers_encounter_start(self) -> None:
        """Notify all controllers that encounter is starting."""
        # Group entities by controller
        controller_entities: Dict[UUID, List[Entity]] = {}
        for combatant in self.combatants.values():
            controller_uuid = combatant.controller_uuid
            if controller_uuid not in controller_entities:
                controller_entities[controller_uuid] = []
            entity = combatant.entity
            if entity:
                controller_entities[controller_uuid].append(entity)

        # Notify each controller
        for controller_uuid, entities in controller_entities.items():
            controller = Controller.get(controller_uuid)
            if controller:
                controller.on_encounter_start(entities)

    def _notify_controllers_encounter_end(self) -> None:
        """Notify all controllers that encounter is ending."""
        # Group entities by controller
        controller_entities: Dict[UUID, List[Entity]] = {}
        for combatant in self.combatants.values():
            controller_uuid = combatant.controller_uuid
            if controller_uuid not in controller_entities:
                controller_entities[controller_uuid] = []
            entity = combatant.entity
            if entity:
                controller_entities[controller_uuid].append(entity)

        # Notify each controller
        for controller_uuid, entities in controller_entities.items():
            controller = Controller.get(controller_uuid)
            if controller:
                controller.on_encounter_end(entities)

    # =========================================================================
    # Turn Execution Loop (for external callers)
    # =========================================================================

    def run_turn(self) -> Optional[TurnEndEvent]:
        """
        Execute a complete turn for the current entity.

        This is the main loop that:
        1. Starts the turn
        2. Repeatedly asks controller for actions
        3. Executes actions until turn ends
        4. Ends the turn

        Returns:
            TurnEndEvent when turn is complete
        """
        if self.state != EncounterState.ACTIVE:
            raise ValueError(f"Cannot run turn in state {self.state}")

        # Start turn if not started
        if self.turn_state != TurnState.IN_PROGRESS:
            turn_start = self.start_turn()
            if turn_start is None:
                # Couldn't start (e.g., no valid entity)
                return None

        entity = self.get_current_entity()
        controller = self.get_current_controller()

        if not entity or not controller:
            return self.end_turn()

        # Main turn loop
        while self.can_continue_turn():
            context = self._build_turn_context(entity)

            if not controller.can_continue_turn(entity, context):
                break

            action = controller.get_next_action(entity, context)

            if action is None:
                # Controller signals end turn
                break

            # Execute the action
            event = action.apply()

            # AUTO-CAPTURE: Add event's combat log to encounter
            if event:
                self.add_event_to_combat_log(event)

            # Check for deaths after action
            deaths = self.check_deaths()
            for death_event in deaths:
                self.add_event_to_combat_log(death_event)

            if deaths and self.state != EncounterState.ACTIVE:
                # Someone died and encounter ended
                return None

        # End turn and advance to next combatant
        end_event = self.end_turn()

        # Advance turn index for next run_turn() call
        self.current_turn_index += 1
        if self.current_turn_index >= len(self.initiative_order):
            self._advance_round()
        self.turn_state = TurnState.NOT_STARTED

        return end_event

    # =========================================================================
    # Advance Until Player Turn
    # =========================================================================

    def advance_until_player(self) -> AdvanceResult:
        """
        Run AI turns until human/claude turn or encounter ends.

        This method runs through the turn order, executing AI turns
        automatically and stopping when it reaches a player-controlled
        entity (human or claude) or when the encounter ends.

        Combat log entries are auto-captured during AI turns via run_turn().

        Returns:
            AdvanceResult with status and context for the caller
        """
        log_start = len(self.combat_log)

        while self.state == EncounterState.ACTIVE:
            entity = self.get_current_entity()
            combatant = self.get_current_combatant()
            controller = self.get_current_controller()

            # Skip dead combatants - advance turn index without calling run_turn()
            if combatant and (combatant.is_dead or not combatant.is_alive):
                combatant.has_acted_this_round = True
                self.current_turn_index += 1
                if self.current_turn_index >= len(self.initiative_order):
                    self._advance_round()
                continue

            if controller is None:
                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status="error",
                    log_start_index=log_start
                )

            # Human or Claude: stop and wait for API
            if controller.controller_type in ("human", "claude"):
                # Start the turn if not already started
                if self.turn_state != TurnState.IN_PROGRESS:
                    self.start_turn()

                entity = self.get_current_entity()
                status = "waiting_for_human" if controller.controller_type == "human" else "waiting_for_claude"

                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status=status,
                    entity_uuid=entity.uuid if entity else None,
                    entity_name=entity.name if entity else None,
                    round_number=self.round_number,
                    turn_index=self.current_turn_index,
                    log_start_index=log_start
                )

            # AI: run turn (auto-captures combat log)
            self.run_turn()

        return AdvanceResult(
            source_entity_uuid=self.uuid,
            status="encounter_ended",
            round_number=self.round_number,
            turn_index=self.current_turn_index,
            log_start_index=log_start
        )

    # =========================================================================
    # HTTP Action Execution (for API-controlled players)
    # =========================================================================

    def execute_action(
        self,
        entity_uuid: UUID,
        template_name: str,
        target_index: Optional[int] = None
    ) -> Optional[Event]:
        """
        Execute action for HTTP-based players.

        Uses template + index pattern for discovery/validation.
        Auto-captures to combat log.
        Checks for deaths after execution.

        Args:
            entity_uuid: UUID of the entity executing the action
            template_name: Name of the action template to execute
            target_index: Optional target index (required for ENTITY/POSITION actions)

        Returns:
            The resulting event, or None if action failed

        Raises:
            ValueError: If entity not found or action fails
        """
        from dnd.actions_functional import execute_by_index

        entity = Entity.get(entity_uuid)
        if not entity:
            raise ValueError(f"Entity {entity_uuid} not found")

        # Execute via functional API (handles template lookup + instantiation)
        event = execute_by_index(entity, template_name, target_index or 0)

        # Capture to combat log
        if event:
            self.add_event_to_combat_log(event)

        # Check deaths
        deaths = self.check_deaths()
        for death_event in deaths:
            self.add_event_to_combat_log(death_event)

        return event
