"""Turn-based encounter management.

An encounter owns initiative order, round and turn boundaries, controller
coordination, combat-log capture, and end-of-combat detection.
"""

from typing import Any, Optional, Dict, List, ClassVar, Set, Tuple, Callable

__all__ = [
    "EncounterState",
    "TurnState",
    "AdvanceResult",
    "Encounter",
]
from uuid import UUID
from datetime import UTC, datetime
from pydantic import Field, computed_field
from enum import Enum

from dnd.core.base_object import BaseObject
from dnd.core.dice import Dice, RollType
from dnd.core.events import (
    Event, EventPhase, EventQueue,
    EncounterStartEvent, EncounterEndEvent,
    RoundStartEvent, RoundEndEvent,
    TurnStartEvent, TurnEndEvent,
    DeathEvent,
    SensoryUpdateReason,
)
from dnd.blocks.sensory import capture_senses_snapshot, emit_sensory_update_delta
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.entity import Entity
from dnd.controller import (
    Controller,
    ControllerExecutionMode,
    ControllerStepResult,
    TurnContext,
)
from dnd.actions_functional import execute_by_index


def _scan_logs_for_reveals(logs: List[CombatLogEntry], revealed: Set[str]) -> None:
    """Recursively scan condition-owned perceivability removals."""
    for log in logs:
        if log.entry_type == CombatLogEntryType.CONDITION_REMOVED:
            if log.data.get("reveals_target") and log.target_uuid:
                target = Entity.get(UUID(log.target_uuid))
                if target and not target.stealth_dc and not target.is_invisible:
                    revealed.add(log.target_uuid)
        _scan_logs_for_reveals(log.sub_entries, revealed)


def _compute_revealed_entities(event: Event, child_logs: List[CombatLogEntry]) -> Set[str]:
    """Return entities revealed during an event chain.

    The scan checks condition-removal combat-log entries and then verifies the
    current entity state, so an entity is only marked revealed when it is no
    longer hidden or invisible after the event chain resolves.
    """
    revealed: Set[str] = set()
    _scan_logs_for_reveals(child_logs, revealed)
    return revealed


def _compute_perceivers(event: Event) -> Set[str]:
    """Return observer UUIDs that should receive an event log."""
    grid = get_map()

    positions: Set[Tuple[int, int]] = event.get_affected_positions()

    participant_uuids = event.get_participant_entity_uuids()
    for uuid in participant_uuids:
        if uuid:
            pos = grid.get_entity_position(uuid)
            if pos:
                positions.add(pos)

    perceivers: Set[str] = set()
    for pos in positions:
        perceivers |= {str(u) for u in grid.get_subscribers_at(pos)}

    for uuid in participant_uuids:
        if uuid:
            perceivers.add(str(uuid))

    return perceivers


def _compute_identified_entity_observers(event: Event) -> Dict[str, Set[str]]:
    """Capture which observers identify each entity participating in an event."""
    grid = get_map()
    grants: Dict[str, Set[str]] = {}
    participant_uuids = {
        entity_uuid
        for entity_uuid in event.get_participant_entity_uuids()
        if Entity.get(entity_uuid) is not None
    }

    for participant_uuid in participant_uuids:
        observer_uuids = {participant_uuid}
        position = grid.get_entity_position(participant_uuid)
        if position is not None:
            observer_uuids.update(grid.get_subscribers_at(position))

        identified_by: Set[str] = set()
        for observer_uuid in observer_uuids:
            observer = Entity.get(observer_uuid)
            if observer is None:
                continue
            if observer_uuid == participant_uuid or participant_uuid in observer.senses.entities:
                identified_by.add(str(observer_uuid))
        grants[str(participant_uuid)] = identified_by

    return grants


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
    """Result of advancing automated turns until external input is needed.

    Attributes:
        status: Result status for the advancement attempt.
        entity_uuid: UUID of the entity waiting for input, when applicable.
        entity_name: Name of the entity waiting for input, when applicable.
        round_number: Current encounter round number.
        turn_index: Current initiative-order index.
        log_start_index: Combat-log index before automated turns ran.
    """

    status: str = Field(description="Result status for the advancement attempt.")
    entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity waiting for input, when applicable.",
    )
    entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity waiting for input, when applicable.",
    )
    round_number: int = Field(default=0, description="Current encounter round number.")
    turn_index: int = Field(default=0, description="Current initiative-order index.")
    log_start_index: int = Field(
        default=0,
        description="Combat-log index before automated turns ran.",
    )


class CombatantState(BaseObject):
    """Per-entity state within an encounter.

    Attributes:
        entity_uuid: UUID of the entity in the encounter.
        controller_uuid: UUID of the controller assigned to the entity.
        initiative_roll: Natural d20 result used for initiative.
        initiative_bonus: Modifier added to the initiative roll.
        initiative_total: Final initiative total.
        has_acted_this_round: Whether the entity has taken this round's turn.
        turn_count: Number of turns this entity has taken in the encounter.
        surprised: Whether the entity is surprised during round one.
        delaying: Whether the entity is currently delaying.
        is_dead: Computed view of the entity's authoritative life state.
    """

    entity_uuid: UUID = Field(description="UUID of the entity in the encounter.")
    controller_uuid: UUID = Field(description="UUID of the controller assigned to the entity.")
    initiative_roll: int = Field(default=0, description="Natural d20 result used for initiative.")
    initiative_bonus: int = Field(default=0, description="Modifier added to the initiative roll.")
    initiative_total: int = Field(default=0, description="Final initiative total.")
    has_acted_this_round: bool = Field(
        default=False,
        description="Whether the entity has taken this round's turn.",
    )
    turn_count: int = Field(
        default=0,
        description="Number of turns this entity has taken in the encounter.",
    )
    surprised: bool = Field(default=False, description="Whether the entity is surprised during round one.")
    delaying: bool = Field(default=False, description="Whether the entity is currently delaying.")

    @property
    def entity(self) -> Optional[Entity]:
        """Get the entity for this combatant."""
        return Entity.get(self.entity_uuid)

    @property
    def controller(self) -> Optional[Controller]:
        """Get the controller for this combatant."""
        return Controller.get(self.controller_uuid)

    @computed_field
    @property
    def is_dead(self) -> bool:
        """Return whether the entity's authoritative life state is DEAD."""
        entity = self.entity
        return entity is None or entity.health.life_state is LifeState.DEAD

    @property
    def is_alive(self) -> bool:
        """Check if combatant is alive (not dead and has HP > 0)."""
        entity = self.entity
        if entity is None:
            return False
        return entity.is_encounter_alive


class Encounter(BaseObject):
    """Manage tactical combat turn flow and combat-log capture.

    Attributes:
        name: Display name of the encounter.
        combatants: Combatant state mapped by entity UUID.
        initiative_order: Entity UUIDs sorted in initiative order.
        current_turn_index: Index into the initiative order.
        round_number: Current one-indexed round number while active.
        state: Current encounter lifecycle state.
        turn_state: Current turn lifecycle state.
        started_at: Wall-clock timestamp when the encounter started.
        ended_at: Wall-clock timestamp when the encounter ended.
        combat_log: Unified combat-log entries captured for the encounter.
        current_turn_started_source_event_cursor: Objective cursor of turn start.
    """

    _encounter_registry: ClassVar[Dict[UUID, 'Encounter']] = {}
    _active_encounter: ClassVar[Optional['Encounter']] = None
    _combat_log_listeners: ClassVar[List[Callable[['Encounter', int, CombatLogEntry, Event], None]]] = []

    name: str = Field(default="Encounter", description="Display name of the encounter.")
    combatants: Dict[UUID, CombatantState] = Field(
        default_factory=dict,
        description="Combatant state mapped by entity UUID.",
    )
    initiative_order: List[UUID] = Field(
        default_factory=list,
        description="Entity UUIDs sorted in initiative order.",
    )
    current_turn_index: int = Field(default=0, description="Index into the initiative order.")
    round_number: int = Field(default=0, description="Current one-indexed round number while active.")
    state: EncounterState = Field(
        default=EncounterState.NOT_STARTED,
        description="Current encounter lifecycle state.",
    )
    turn_state: TurnState = Field(
        default=TurnState.NOT_STARTED,
        description="Current turn lifecycle state.",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Wall-clock timestamp when the encounter started.",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="Wall-clock timestamp when the encounter ended.",
    )
    combat_log: List[CombatLogEntry] = Field(
        default_factory=list,
        description="Unified combat-log entries captured for the encounter.",
    )
    current_turn_started_source_event_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Objective event cursor of the current turn-start completion.",
    )
    current_turn_execution_id: Optional[UUID] = Field(
        default=None,
        description="Opaque causal identity of the currently active actual turn.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.__class__._encounter_registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Encounter']:
        """Get an encounter by UUID."""
        return cls._encounter_registry.get(uuid)

    @classmethod
    def get_active(cls) -> Optional['Encounter']:
        """Get the currently active encounter (if any)."""
        return cls._active_encounter

    @classmethod
    def clear_registry(cls) -> None:
        """Clear the encounter registry."""
        cls._encounter_registry.clear()
        cls._active_encounter = None

    @classmethod
    def add_combat_log_listener(
        cls,
        callback: Callable[['Encounter', int, CombatLogEntry, Event], None],
    ) -> None:
        """Register a passive listener for appended combat log entries."""
        if callback not in cls._combat_log_listeners:
            cls._combat_log_listeners.append(callback)

    @classmethod
    def remove_combat_log_listener(
        cls,
        callback: Callable[['Encounter', int, CombatLogEntry, Event], None],
    ) -> None:
        """Remove a combat log append listener."""
        if callback in cls._combat_log_listeners:
            cls._combat_log_listeners.remove(callback)

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
            removed_index = self.initiative_order.index(entity_uuid)
            self.initiative_order.remove(entity_uuid)

            if removed_index < self.current_turn_index:
                self.current_turn_index -= 1
            elif removed_index == self.current_turn_index:
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

    def set_controller_for(self, entity_uuid: UUID, controller: Controller) -> UUID:
        """Replace the controller assigned to one combatant.

        Args:
            entity_uuid: UUID of the combatant whose controller should change.
            controller: New controller for the combatant.

        Returns:
            UUID of the previous controller.

        Raises:
            ValueError: If the entity is not part of this encounter.
        """
        combatant = self.combatants.get(entity_uuid)
        if combatant is None:
            raise ValueError(f"Entity {entity_uuid} is not in this encounter")
        previous_controller_uuid = combatant.controller_uuid
        combatant.controller_uuid = controller.uuid
        return previous_controller_uuid

    def roll_initiative(self) -> None:
        """
        Roll initiative for all combatants and establish turn order.

        Ties are broken by:
        1. Higher DEX modifier
        2. Random (the earlier roll wins)
        """
        for combatant in self.combatants.values():
            entity = combatant.entity
            if not entity:
                continue
            dice = Dice(count=1, value=20, bonus=entity.initiative, roll_type=RollType.CHECK)
            roll = dice.roll
            roll_result = roll.results if isinstance(roll.results, int) else roll.results[0]
            combatant.initiative_roll = roll_result
            combatant.initiative_total = roll.total

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

        if not self.initiative_order:
            self.roll_initiative()

        self.state = EncounterState.ACTIVE
        self.started_at = datetime.now(UTC)
        self.round_number = 1

        Encounter._active_encounter = self

        EventQueue.set_combat_log_callback(self._on_event_combat_log)
        EventQueue.set_perceiver_computer(_compute_perceivers)
        EventQueue.set_revealed_computer(_compute_revealed_entities)
        EventQueue.set_identified_entity_observer_computer(_compute_identified_entity_observers)

        self._apply_surprise_reaction_lockouts()

        self._notify_controllers_encounter_start()

        event = EncounterStartEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            combatant_uuids=list(self.combatants.keys()),
            initiative_order=self.initiative_order.copy(),
            phase=EventPhase.COMPLETION
        )

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

        if self.turn_state == TurnState.IN_PROGRESS:
            self.end_turn()

        self.state = EncounterState.ENDED
        self.ended_at = datetime.now(UTC)

        if Encounter._active_encounter is self:
            Encounter._active_encounter = None

        EventQueue.set_combat_log_callback(None)
        EventQueue.set_perceiver_computer(None)
        EventQueue.set_revealed_computer(None)
        EventQueue.set_identified_entity_observer_computer(None)

        self._notify_controllers_encounter_end()

        event = EncounterEndEvent(
            source_entity_uuid=self.uuid,
            encounter_uuid=self.uuid,
            combatant_uuids=list(self.combatants.keys()),
            reason=reason,
            phase=EventPhase.COMPLETION
        )

        return event

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

    def _environment_step(self) -> None:
        """Advance tile and floor-item condition durations. Called at end of each round."""
        grid = get_map()
        for tile in grid.get_tiles_with_conditions():
            for cond_name in list(tile.active_conditions.keys()):
                tile.advance_duration(cond_name)
        for item_block in grid.get_objects_with_conditions():
            for cond_name in list(item_block.active_conditions.keys()):
                item_block.advance_duration(cond_name)

    def _advance_round(self) -> None:
        """Advance to the next round."""
        self._fire_round_end()
        self._environment_step()

        self.round_number += 1
        self.current_turn_index = 0

        for combatant in self.combatants.values():
            combatant.has_acted_this_round = False

        self._fire_round_start()

    def _apply_surprise_reaction_lockouts(self) -> None:
        """Spend initial reactions for surprised combatants until their first turn ends."""
        for combatant in self.combatants.values():
            if not combatant.surprised:
                continue
            entity = combatant.entity
            if entity is None:
                continue
            available_reactions = entity.action_economy.reactions.normalized_score
            if available_reactions > 0:
                entity.action_economy.consume("reactions", available_reactions, "Surprised")

    def _skip_surprised_turn(
        self,
        entity: Entity,
        combatant: CombatantState,
        controller: Optional[Controller],
    ) -> Optional[TurnStartEvent]:
        """Run turn boundary hooks for a surprised combatant without allowing actions."""
        self.turn_state = TurnState.IN_PROGRESS
        self._begin_turn_execution()

        try:
            event = entity.on_turn_start(
                encounter_uuid=self.uuid,
                round_number=self.round_number,
                turn_index=self.current_turn_index,
            )
            self.current_turn_started_source_event_cursor = EventQueue.event_cursor()
            self._refresh_turn_start_senses(entity, event)

            if controller:
                controller.on_turn_start(entity, self._build_turn_context(entity))

            entity.on_turn_end(
                encounter_uuid=self.uuid,
                round_number=self.round_number,
                turn_index=self.current_turn_index,
            )

            if controller:
                controller.on_turn_end(entity, self._build_turn_context(entity))

            combatant.has_acted_this_round = True
            combatant.turn_count += 1
            self.turn_state = TurnState.ENDED
        finally:
            self._end_turn_execution()
        return self._skip_to_next_turn()

    def _begin_turn_execution(self) -> UUID:
        """Open the one causal identity shared by every event in this turn."""
        if self.current_turn_execution_id is not None:
            raise RuntimeError("Encounter turn execution is already active")
        execution_id = EventQueue.begin_turn_execution()
        self.current_turn_execution_id = execution_id
        return execution_id

    def _end_turn_execution(self) -> None:
        """Close the active causal turn identity, if this encounter owns one."""
        execution_id = self.current_turn_execution_id
        if execution_id is None:
            return
        EventQueue.end_turn_execution(execution_id)
        self.current_turn_execution_id = None

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

        if combatant.surprised and self.round_number == 1:
            return self._skip_surprised_turn(entity, combatant, controller)

        if combatant.is_dead or not combatant.is_alive:
            combatant.has_acted_this_round = True
            return self._skip_to_next_turn()

        self.turn_state = TurnState.IN_PROGRESS
        self._begin_turn_execution()

        try:
            event = entity.on_turn_start(
                encounter_uuid=self.uuid,
                round_number=self.round_number,
                turn_index=self.current_turn_index
            )
            self.current_turn_started_source_event_cursor = EventQueue.event_cursor()

            self._refresh_turn_start_senses(entity, event)

            if controller:
                context = self._build_turn_context(entity)
                controller.on_turn_start(entity, context)
        except Exception:
            self._end_turn_execution()
            self.turn_state = TurnState.NOT_STARTED
            raise

        return event

    def _refresh_turn_start_senses(
        self,
        entity: Entity,
        turn_start_event: TurnStartEvent,
    ) -> None:
        """Recompute one actor's senses and emit the complete subjective delta.

        Args:
            entity: Actor whose turn is starting.
            turn_start_event: Completed turn event that caused the refresh.
        """
        before = capture_senses_snapshot(entity.senses)
        entity.senses.collision_blocked.clear()
        entity.senses.directional_collision_blocked.clear()
        entity.update_entity_senses(max_distance=20)
        after = capture_senses_snapshot(entity.senses)
        emit_sensory_update_delta(
            entity.senses,
            entity.uuid,
            turn_start_event,
            before,
            after,
            SensoryUpdateReason.TURN_START,
        )

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

        try:
            event = entity.on_turn_end(
                encounter_uuid=self.uuid,
                round_number=self.round_number,
                turn_index=self.current_turn_index
            )

            if controller:
                context = self._build_turn_context(entity)
                controller.on_turn_end(entity, context)

            combatant.has_acted_this_round = True
            combatant.turn_count += 1
            self.turn_state = TurnState.ENDED
        finally:
            self._end_turn_execution()

        return event

    def next_turn(self) -> Optional[TurnStartEvent]:
        """
        Advance to the next turn.

        Ends current turn if in progress, then starts the next one.
        May advance to next round if all entities have acted.
        """
        if self.state != EncounterState.ACTIVE:
            return None

        if self.turn_state == TurnState.IN_PROGRESS:
            self.end_turn()

        self.current_turn_index += 1

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

    def can_continue_turn(self) -> bool:
        """
        Check if the current entity can still act.

        Returns True if entity has any action economy remaining.
        """
        entity = self.get_current_entity()
        if not entity:
            return False

        ae = entity.action_economy

        has_action = ae.can_afford("actions", 1)
        has_bonus = ae.can_afford("bonus_actions", 1)
        has_five_feet_movement = ae.can_afford("movement", 5)

        return has_action or has_bonus or has_five_feet_movement

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
            encounter_uuid=self.uuid,
            encounter_name=self.name,
            encounter_state=self.state.value,
            initiative_order=self.initiative_order.copy(),
            initiative_totals={
                entity_uuid: combatant.initiative_total
                for entity_uuid, combatant in self.combatants.items()
            },
            turn_started_source_event_cursor=(
                self.current_turn_started_source_event_cursor
            ),
        )

    def _advance_entity_conditions(self, entity: Entity) -> List[str]:
        """
        Advance duration for all conditions on entity.

        Called at start of turn. Returns list of removed condition names.
        This timing makes turn-based conditions (Dash, Dodge, Disengage) last
        "until the start of your next turn" per SRD.
        """
        removed = []
        condition_names = list(entity.active_conditions.keys())

        for condition_name in condition_names:
            was_removed = entity.advance_duration_condition(condition_name)
            if was_removed:
                removed.append(condition_name)

        return removed

    def _on_event_combat_log(self, event: Event) -> None:
        """Callback for auto-capturing event combat logs.

        Called by EventQueue when a top-level event (parent_event=None)
        completes with a combat_log. The combat_log already includes
        nested sub_entries from child events.
        """
        self.add_event_to_combat_log(event)

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
        index = len(self.combat_log) - 1
        for listener in list(self.__class__._combat_log_listeners):
            try:
                listener(self, index, event.combat_log, event)
            except Exception:
                pass
        return index

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

    def check_deaths(self) -> List[DeathEvent]:
        """
        Check all combatants for death and handle any that died.

        Called after actions to detect and handle deaths.
        Note: Death is now primarily handled by Entity.receive_damage(), which
        commits LifeState.DEAD and fires DeathEvent. This method handles
        deaths that occur outside of receive_damage (e.g., HP set directly).

        Returns:
            List of DeathEvent for any combatants that died
        """
        death_events = []
        for combatant in self.combatants.values():
            entity = combatant.entity
            if entity is None:
                continue

            if entity.health.life_state is LifeState.DEAD:
                continue

            if not entity.has_hp:
                if entity.uses_death_saves:
                    if entity.health.life_state is LifeState.ALIVE:
                        entity.enter_dying_state()
                    continue
                event = self._handle_death(combatant)
                if event:
                    death_events.append(event)

        if self.state is EncounterState.ACTIVE:
            self._check_encounter_end()

        return death_events

    def _handle_death(self, combatant: CombatantState) -> Optional[DeathEvent]:
        """Emit the standard death lifecycle for an unhandled zero-HP entity."""
        entity = combatant.entity
        if entity is None:
            return None
        if entity.health.life_state is LifeState.DEAD:
            return None
        return entity._fire_death_event(
            source_entity_uuid=entity.uuid,
            encounter_uuid=self.uuid,
            reason=LifeStateChangeReason.DIRECT_STATE_CHECK,
        )

    def _check_encounter_end(self) -> bool:
        """
        Check if the encounter should end (only one faction has survivors).

        Uses faction-based detection: entities with same faction are allies.
        Entities with faction=None are treated as their own faction (enemy to all).

        Returns:
            True if encounter ended
        """
        factions_alive: Dict[str, int] = {}
        for combatant in self.combatants.values():
            entity = combatant.entity
            if entity is None:
                continue
            faction_key = entity.faction if entity.faction else str(entity.uuid)
            if faction_key not in factions_alive:
                factions_alive[faction_key] = 0
            if combatant.is_alive:
                factions_alive[faction_key] += 1

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

    def _notify_controllers_encounter_start(self) -> None:
        """Notify all controllers that encounter is starting."""
        controller_entities: Dict[UUID, List[Entity]] = {}
        for combatant in self.combatants.values():
            controller_uuid = combatant.controller_uuid
            if controller_uuid not in controller_entities:
                controller_entities[controller_uuid] = []
            entity = combatant.entity
            if entity:
                controller_entities[controller_uuid].append(entity)

        for controller_uuid, entities in controller_entities.items():
            controller = Controller.get(controller_uuid)
            if controller:
                controller.on_encounter_start(entities)

    def _notify_controllers_encounter_end(self) -> None:
        """Notify all controllers that encounter is ending."""
        controller_entities: Dict[UUID, List[Entity]] = {}
        for combatant in self.combatants.values():
            controller_uuid = combatant.controller_uuid
            if controller_uuid not in controller_entities:
                controller_entities[controller_uuid] = []
            entity = combatant.entity
            if entity:
                controller_entities[controller_uuid].append(entity)

        for controller_uuid, entities in controller_entities.items():
            controller = Controller.get(controller_uuid)
            if controller:
                controller.on_encounter_end(entities)

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

        if self.turn_state != TurnState.IN_PROGRESS:
            turn_start = self.start_turn()
            if turn_start is None:
                return None

        entity = self.get_current_entity()
        controller = self.get_current_controller()

        if not entity or not controller:
            return self.end_turn()

        while self.can_continue_turn():
            context = self._build_turn_context(entity)

            if not controller.can_continue_turn(entity, context):
                break

            step = controller.execute_next_action(entity, context)
            if step.end_turn:
                break
            _event = step.event

            deaths = self.check_deaths()

            if deaths and self.state != EncounterState.ACTIVE:
                return None

        return self._complete_current_turn()

    def _complete_current_turn(self) -> Optional[TurnEndEvent]:
        """Commit the current turn end and advance to the next initiative slot."""
        end_event = self.end_turn()
        self.current_turn_index += 1
        if self.current_turn_index >= len(self.initiative_order):
            self._advance_round()
        self.turn_state = TurnState.NOT_STARTED
        return end_event

    def advance_until_player(self) -> AdvanceResult:
        """
        Run AI turns until human/codex turn or encounter ends.

        This method runs through the turn order, executing AI turns
        automatically and stopping when it reaches a player-controlled
        entity (human or codex) or when the encounter ends.

        Combat log entries are auto-captured during AI turns via run_turn().

        Returns:
            AdvanceResult with status and context for the caller
        """
        log_start = len(self.combat_log)

        while True:
            result = self.advance_one_controller_boundary()
            if result.status == "advanced_autonomous":
                continue
            return result.model_copy(update={"log_start_index": log_start})

    def advance_one_controller_boundary(self) -> AdvanceResult:
        """Advance one complete synchronous controller turn.

        Server coordinators use :meth:`advance_one_controller_action_boundary`
        instead so they can yield between decisions without changing the
        encounter's deterministic turn semantics.
        """
        log_start = len(self.combat_log)
        while True:
            result = self.advance_one_controller_action_boundary()
            if result.status != "autonomous_action_completed":
                return result.model_copy(update={"log_start_index": log_start})

    def advance_one_controller_action_boundary(self) -> AdvanceResult:
        """Execute one decision as one passive replication transaction.

        A turn boundary may emit many lifecycle events even when the
        controller elects only to end its turn.  Player replication observes
        the committed decision boundary, not every intermediate event write,
        so retain those events in one causal batch and project the world once.
        Nested action batches naturally join this outer transaction.
        """
        with EventQueue.batch_on_event_callbacks():
            return self._advance_one_controller_action_boundary()

    def _advance_one_controller_action_boundary(self) -> AdvanceResult:
        """Implement one autonomous decision or expose a wait boundary."""
        log_start = len(self.combat_log)
        if self.state is EncounterState.ENDED:
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status="encounter_ended",
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )
        if self.state is not EncounterState.ACTIVE:
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status="error",
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )

        entity = self.get_current_entity()
        combatant = self.get_current_combatant()
        controller = self.get_current_controller()
        if entity is None or combatant is None or controller is None:
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status="error",
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )

        if combatant.is_dead or not combatant.is_alive:
            combatant.has_acted_this_round = True
            self.current_turn_index += 1
            if self.current_turn_index >= len(self.initiative_order):
                self._advance_round()
            self.turn_state = TurnState.NOT_STARTED
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status="advanced_autonomous",
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )

        if controller.execution_mode in {
            ControllerExecutionMode.EXTERNAL,
            ControllerExecutionMode.DEFERRED_AUTONOMOUS,
        }:
            actor_uuid = entity.uuid
            if self.turn_state is not TurnState.IN_PROGRESS:
                self.start_turn()
            current_entity = self.get_current_entity()
            if self.state is EncounterState.ENDED:
                status = "encounter_ended"
            elif (
                current_entity is None
                or current_entity.uuid != actor_uuid
            ):
                status = "advanced_autonomous"
            else:
                status = controller.external_boundary_status or "waiting_for_external"
            current = self.get_current_entity()
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status=status,
                entity_uuid=current.uuid if current else None,
                entity_name=current.name if current else None,
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )

        actor_uuid = entity.uuid
        if self.turn_state is not TurnState.IN_PROGRESS:
            self.start_turn()
            if self.state is EncounterState.ENDED:
                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status="encounter_ended",
                    round_number=self.round_number,
                    turn_index=self.current_turn_index,
                    log_start_index=log_start,
                )
            entity = self.get_current_entity()
            combatant = self.get_current_combatant()
            controller = self.get_current_controller()
            if (
                entity is None
                or combatant is None
                or controller is None
                or entity.uuid != actor_uuid
            ):
                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status="advanced_autonomous",
                    round_number=self.round_number,
                    turn_index=self.current_turn_index,
                    log_start_index=log_start,
                )

        context = self._build_turn_context(entity)
        if (
            not self.can_continue_turn()
            or not controller.can_continue_turn(entity, context)
        ):
            self._complete_current_turn()
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status=(
                    "encounter_ended"
                    if self.state is EncounterState.ENDED
                    else "advanced_autonomous"
                ),
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )

        step = controller.execute_next_action(entity, context)
        if step.event is not None:
            deaths = self.check_deaths()
            if deaths and self.state is not EncounterState.ACTIVE:
                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status="encounter_ended",
                    round_number=self.round_number,
                    turn_index=self.current_turn_index,
                    log_start_index=log_start,
                )
        current = self.get_current_entity()
        current_controller = self.get_current_controller()
        should_end = (
            step.end_turn
            or current is None
            or current.uuid != actor_uuid
            or current_controller is None
            or current_controller.uuid != controller.uuid
            or not self.can_continue_turn()
            or not controller.can_continue_turn(
                entity,
                self._build_turn_context(entity),
            )
        )
        if should_end:
            if (
                self.state is EncounterState.ACTIVE
                and self.turn_state is TurnState.IN_PROGRESS
                and current is not None
                and current.uuid == actor_uuid
            ):
                self._complete_current_turn()
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status=(
                    "encounter_ended"
                    if self.state is EncounterState.ENDED
                    else "advanced_autonomous"
                ),
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )
        return AdvanceResult(
            source_entity_uuid=self.uuid,
            status="autonomous_action_completed",
            entity_uuid=entity.uuid,
            entity_name=entity.name,
            round_number=self.round_number,
            turn_index=self.current_turn_index,
            log_start_index=log_start,
        )

    def build_current_turn_context(self) -> TurnContext:
        """Return the exact live context for the current in-progress actor."""
        if self.state is not EncounterState.ACTIVE:
            raise ValueError("encounter is not active")
        if self.turn_state is not TurnState.IN_PROGRESS:
            raise ValueError("encounter turn is not in progress")
        entity = self.get_current_entity()
        if entity is None:
            raise ValueError("encounter has no current actor")
        return self._build_turn_context(entity)

    def resolve_deferred_controller_step(
        self,
        *,
        entity_uuid: UUID,
        controller_uuid: UUID,
        step: ControllerStepResult,
    ) -> AdvanceResult:
        """Commit one already-executed deferred AI step against exact ownership."""
        log_start = len(self.combat_log)
        entity = self.get_current_entity()
        controller = self.get_current_controller()
        if self.state is not EncounterState.ACTIVE:
            raise ValueError("encounter is not active")
        if self.turn_state is not TurnState.IN_PROGRESS:
            raise ValueError("deferred controller turn is not in progress")
        if entity is None or entity.uuid != entity_uuid:
            raise ValueError("deferred controller actor fence changed")
        if controller is None or controller.uuid != controller_uuid:
            raise ValueError("deferred controller ownership fence changed")
        if (
            controller.execution_mode
            is not ControllerExecutionMode.DEFERRED_AUTONOMOUS
        ):
            raise ValueError("controller is not deferred autonomous")

        if step.event is not None:
            deaths = self.check_deaths()
            if deaths and self.state is not EncounterState.ACTIVE:
                return AdvanceResult(
                    source_entity_uuid=self.uuid,
                    status="encounter_ended",
                    round_number=self.round_number,
                    turn_index=self.current_turn_index,
                    log_start_index=log_start,
                )

        context = self._build_turn_context(entity)
        should_end = (
            step.end_turn
            or not self.can_continue_turn()
            or not controller.can_continue_turn(entity, context)
        )
        if should_end:
            self._complete_current_turn()
            return AdvanceResult(
                source_entity_uuid=self.uuid,
                status=(
                    "encounter_ended"
                    if self.state is EncounterState.ENDED
                    else "advanced_autonomous"
                ),
                round_number=self.round_number,
                turn_index=self.current_turn_index,
                log_start_index=log_start,
            )
        return AdvanceResult(
            source_entity_uuid=self.uuid,
            status="deferred_action_completed",
            entity_uuid=entity.uuid,
            entity_name=entity.name,
            round_number=self.round_number,
            turn_index=self.current_turn_index,
            log_start_index=log_start,
        )

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
        entity = Entity.get(entity_uuid)
        if not entity:
            raise ValueError(f"Entity {entity_uuid} not found")

        event = execute_by_index(entity, template_name, target_index or 0)

        _ = self.check_deaths()

        return event
