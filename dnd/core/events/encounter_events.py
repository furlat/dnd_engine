"""Encounter, round, turn, death-save, and terminal life event facts."""

from typing import ClassVar, List, Optional
from uuid import UUID

from pydantic import Field

from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    DeathSaveLogData,
    TurnLogData,
    md_color,
)
from dnd.core.dice import DiceRoll
from dnd.core.events.events_registry import Event, EventType
from dnd.types.conditions import ConditionRemovalTrigger
from dnd.types.life import LifeState, LifeStateChangeReason

class EncounterEvent(Event):
    """Base event for encounter lifecycle."""

    name: str = Field(default="Encounter Event", description="Human-readable encounter event label.")
    encounter_uuid: UUID = Field(description="Encounter whose lifecycle changed.")
    combatant_uuids: List[UUID] = Field(default_factory=list, description="Combatants participating in the encounter.")

class EncounterStartEvent(EncounterEvent):
    """Fired when an encounter begins."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Encounter Start", description="Human-readable encounter-start label.")
    event_type: EventType = Field(
        default=EventType.ENCOUNTER_START,
        description="Event category for encounter start.",
    )
    initiative_order: List[UUID] = Field(default_factory=list, description="Combatants sorted by initiative.")

class EncounterEndEvent(EncounterEvent):
    """Fired when an encounter ends."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Encounter End", description="Human-readable encounter-end label.")
    event_type: EventType = Field(
        default=EventType.ENCOUNTER_END,
        description="Event category for encounter end.",
    )
    reason: Optional[str] = Field(default=None, description="Reason the encounter ended.")

class RoundEvent(Event):
    """Base event for round lifecycle."""

    name: str = Field(default="Round Event", description="Human-readable round event label.")
    encounter_uuid: UUID = Field(description="Encounter whose round changed.")
    round_number: int = Field(description="Current 1-indexed round number.")

class RoundStartEvent(RoundEvent):
    """Fired at the start of a new round."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Round Start", description="Human-readable round-start label.")
    event_type: EventType = Field(default=EventType.ROUND_START, description="Event category for round start.")

class RoundEndEvent(RoundEvent):
    """Fired at the end of a round."""

    name: str = Field(default="Round End", description="Human-readable round-end label.")
    event_type: EventType = Field(default=EventType.ROUND_END, description="Event category for round end.")

class TurnEvent(Event):
    """Base event for turn lifecycle."""

    name: str = Field(default="Turn Event", description="Human-readable turn event label.")
    encounter_uuid: UUID = Field(description="Encounter whose turn order advanced.")
    entity_uuid: UUID = Field(description="Entity whose turn is represented.")
    round_number: int = Field(description="Current round number.")
    turn_index: int = Field(description="0-indexed position in initiative order.")

class TurnStartEvent(TurnEvent):
    """Fired at the start of an entity's turn."""

    name: str = Field(default="Turn Start", description="Human-readable turn-start label.")
    event_type: EventType = Field(default=EventType.TURN_START, description="Event category for turn start.")
    actions_available: int = Field(default=1, description="Actions available at turn start.")
    bonus_actions_available: int = Field(default=1, description="Bonus actions available at turn start.")
    movement_available: int = Field(default=30, description="Movement available at turn start, in feet.")
    reaction_available: int = Field(default=1, description="Reactions available at turn start.")

    def resolve_sub_events(self) -> None:
        """Reduce the observer's turn-start projection."""
        from dnd.blocks.sensory import spatial_senses_system

        spatial_senses_system.reduce_event(self)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn start."""
        entity_name = self.source_entity_name or "Unknown"

        text = f"─── {md_color(entity_name, 'bold yellow')}'s turn ───"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_START,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
            data=TurnLogData(
                entity_name=entity_name,
                entity_uuid=str(self.entity_uuid),
                round_number=self.round_number,
                turn_index=self.turn_index,
            ).model_dump()
        )

class TurnEndEvent(TurnEvent):
    """Fired at the end of an entity's turn."""

    name: str = Field(default="Turn End", description="Human-readable turn-end label.")
    event_type: EventType = Field(default=EventType.TURN_END, description="Event category for turn end.")
    actions_used: int = Field(default=0, description="Actions spent during this turn.")
    bonus_actions_used: int = Field(default=0, description="Bonus actions spent during this turn.")
    movement_used: int = Field(default=0, description="Movement spent during this turn, in feet.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for turn end."""
        entity_name = self.source_entity_name or "Unknown"

        text = f"─ {md_color(entity_name, 'dim')}'s turn ends ─"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.TURN_END,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
            data=TurnLogData(
                entity_name=entity_name,
                entity_uuid=str(self.entity_uuid),
                round_number=self.round_number,
                turn_index=self.turn_index,
            ).model_dump()
        )

class LifeStateChangeEvent(Event):
    """Typed transition of an entity's authoritative health life state."""

    name: str = Field(default="Life State Change", description="Human-readable lifecycle transition label.")
    event_type: EventType = Field(
        default=EventType.LIFE_STATE_CHANGE,
        description="Event category for authoritative life-state transitions.",
    )
    entity_uuid: UUID = Field(description="Entity whose life state is changing.")
    entity_name: str = Field(default="", description="Display name of the affected entity.")
    previous_state: LifeState = Field(description="Authoritative state before execution.")
    new_state: LifeState = Field(description="Authoritative state after the transition.")
    reason: LifeStateChangeReason = Field(description="Rules-facing cause of the transition.")
    normal_hit_points: int = Field(
        default=0,
        description="Normal hit points observed when the transition was requested.",
    )

    def resolve_sub_events(self) -> None:
        """Retire source-owned conditions, then reduce perception."""
        if self.previous_state is LifeState.ALIVE and self.new_state is not LifeState.ALIVE:
            from dnd.core.base_conditions import BaseCondition

            candidate_uuids = sorted(
                (
                    condition.uuid
                    for condition in BaseCondition._registry.values()
                    if (
                        isinstance(condition, BaseCondition)
                        and condition.use_register
                        and condition.applied
                        and condition.source_entity_uuid == self.entity_uuid
                        and ConditionRemovalTrigger.SOURCE_LEFT_PLAY
                        in condition.removal_triggers
                    )
                ),
                key=lambda condition_uuid: condition_uuid.int,
            )
            for condition_uuid in candidate_uuids:
                condition = BaseCondition.get(condition_uuid)
                if not isinstance(condition, BaseCondition):
                    continue
                if not (
                    condition.use_register
                    and condition.applied
                    and condition.source_entity_uuid == self.entity_uuid
                    and ConditionRemovalTrigger.SOURCE_LEFT_PLAY
                    in condition.removal_triggers
                ):
                    continue
                condition.remove_from_runtime_owner(parent_event=self)
                current = BaseCondition.get(condition_uuid)
                if (
                    isinstance(current, BaseCondition)
                    and current.use_register
                    and current.applied
                    and current.source_entity_uuid == self.entity_uuid
                    and ConditionRemovalTrigger.SOURCE_LEFT_PLAY
                    in current.removal_triggers
                ):
                    raise RuntimeError(
                        "Source-left-play condition did not remove itself: "
                        f"{type(current).__name__} {condition_uuid}"
                    )

        from dnd.blocks.sensory import spatial_senses_system

        spatial_senses_system.reduce_event(self)

class ReviveEvent(Event):
    """Typed revival request with revival-specific condition options."""

    name: str = Field(default="Revive", description="Human-readable revival label.")
    event_type: EventType = Field(default=EventType.REVIVE, description="Event category for revival.")
    entity_uuid: UUID = Field(description="Entity being restored to life.")
    entity_name: str = Field(default="", description="Display name of the revived entity.")
    hit_points: int = Field(default=1, ge=1, description="Normal hit points restored by revival.")
    reduce_exhaustion: bool = Field(
        default=True,
        description="Whether condition-owned revival rules may reduce Exhaustion.",
    )

class DeathSaveEvent(Event):
    """Fired when a player-style dying entity makes a death saving throw."""

    name: str = Field(default="Death Save", description="Human-readable death-save event label.")
    event_type: EventType = Field(default=EventType.DEATH_SAVE, description="Event category for death saving throws.")
    entity_uuid: UUID = Field(description="Entity making the death saving throw.")
    entity_name: str = Field(default="", description="Display name of the entity making the death save.")
    roll: Optional[DiceRoll] = Field(default=None, description="Effective d20 roll after result handlers.")
    natural_roll: Optional[int] = Field(default=None, description="Natural d20 face used for death-save special rules.")
    dc: int = Field(default=10, description="Death saving throw DC.")
    succeeded: bool = Field(default=False, description="Whether this death save succeeded.")
    successes: int = Field(default=0, ge=0, description="Death-save successes after this event.")
    failures: int = Field(default=0, ge=0, description="Death-save failures after this event.")
    became_stable: bool = Field(default=False, description="Whether this event stabilized the entity.")
    regained_hit_point: bool = Field(default=False, description="Whether a natural 20 restored 1 hit point.")
    died: bool = Field(default=False, description="Whether this event caused death.")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for a death saving throw."""
        entity_name = self.entity_name or self.source_entity_name or "Unknown"
        roll_total = self.roll.total if self.roll else 0
        natural = self.natural_roll if self.natural_roll is not None else roll_total
        outcome = "success" if self.succeeded else "failure"
        if self.regained_hit_point:
            outcome = "natural 20"
        elif self.died:
            outcome = "death"
        elif self.became_stable:
            outcome = "stable"

        text = (
            f"{md_color(entity_name, 'yellow')} death save "
            f"{md_color(str(natural), 'cyan')} vs DC {self.dc}: {outcome} "
            f"({self.successes} successes, {self.failures} failures)"
        )
        data = DeathSaveLogData(
            entity_name=entity_name,
            entity_uuid=str(self.entity_uuid),
            roll=roll_total,
            natural_roll=natural,
            dc=self.dc,
            successes=self.successes,
            failures=self.failures,
            became_stable=self.became_stable,
            regained_hit_point=self.regained_hit_point,
            died=self.died,
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.DEATH_SAVE,
            source_name=entity_name,
            source_uuid=str(self.entity_uuid),
            target_name=entity_name,
            target_uuid=str(self.entity_uuid),
            compact=text,
            verbose=text,
            detailed=text,
            data=data.model_dump(),
            success=self.succeeded or self.regained_hit_point or self.became_stable,
        )

class DeathEvent(Event):
    """Fired when an accepted rule transitions an entity to dead."""

    name: str = Field(default="Death", description="Human-readable death event label.")
    event_type: EventType = Field(default=EventType.DEATH, description="Event category for entity death.")
    entity_uuid: UUID = Field(description="Entity that died.")
    entity_name: str = Field(default="", description="Display name of the dead entity.")
    killer_uuid: Optional[UUID] = Field(default=None, description="Entity that dealt the killing blow, if known.")
    killer_name: str = Field(default="", description="Display name of the killer, if known.")
    final_hp: int = Field(default=0, description="Final HP value after lethal damage.")
    encounter_uuid: Optional[UUID] = Field(default=None, description="Encounter where the death occurred, if any.")

    def resolve_sub_events(self) -> None:
        """Reduce perception after the death fact commits."""
        from dnd.blocks.sensory import spatial_senses_system

        spatial_senses_system.reduce_event(self)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log entry for death."""
        compact_text = f"☠ {md_color(self.entity_name, 'bold red')} has been defeated!"
        verbose_text = compact_text
        detailed_text = f"☠ {md_color(self.entity_name, 'bold red')} has been defeated!"
        detailed_text += f"\n  Dropped to {self.final_hp} HP"
        if self.killer_name:
            detailed_text += f"\n  Killed by: {md_color(self.killer_name, 'cyan')}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.DEATH,
            source_name=self.entity_name,
            source_uuid=str(self.entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={"entity_name": self.entity_name, "final_hp": self.final_hp},
            success=True
        )

class InstantDeathEvent(Event):
    """Interruptible event for effects that kill without dealing damage."""

    name: str = Field(default="Instant Death", description="Human-readable instant-death event label.")
    event_type: EventType = Field(default=EventType.INSTANT_DEATH, description="Event category for no-damage death effects.")
    entity_uuid: UUID = Field(description="Entity subjected to the instant-death effect.")
    entity_name: str = Field(default="", description="Display name of the affected entity.")
    killer_uuid: Optional[UUID] = Field(default=None, description="Entity or effect source causing the instant-death effect.")
    killer_name: str = Field(default="", description="Display name of the instant-death source, if known.")
    source_description: str = Field(default="", description="Rules-facing source or effect description.")
