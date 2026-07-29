"""Assignment-owned decision epochs over the canonical subjective projector."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationCombatantState,
    ObservationEncounterState,
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.runtime.decision_epoch import DecisionEpochBuild, build_decision_epoch
from dnd.ai.runtime.subjective_projection import (
    observers_that_see,
    project_subjective_world,
    resolve_controlled_observers,
)
from dnd.controller import TurnContext
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class AIDecisionState:
    """One public subjective state and its private exact execution authority."""

    world: SubjectiveWorldState
    epoch_build: DecisionEpochBuild


class SubjectiveAIStateProjector:
    """Project one side's retained knowledge without any transport/session layer."""

    def __init__(
        self,
        *,
        assignment_id: str,
        controlled_entity_uuids: tuple[UUID, ...],
    ) -> None:
        if not assignment_id:
            raise ValueError("assignment_id must not be empty")
        if not controlled_entity_uuids:
            raise ValueError("AI assignment must control at least one entity")
        if len(controlled_entity_uuids) != len(set(controlled_entity_uuids)):
            raise ValueError("controlled_entity_uuids contains duplicates")
        self._assignment_id = assignment_id
        self._controlled_entity_uuids = tuple(
            sorted(controlled_entity_uuids, key=str)
        )
        self._observation_cursor = 0
        self._world: SubjectiveWorldState | None = None

    @property
    def world(self) -> SubjectiveWorldState | None:
        """Return the most recently projected immutable model."""
        return self._world

    @property
    def observation_cursor(self) -> int:
        """Return the latest assignment-local projection cursor."""
        return self._observation_cursor

    def project_decision(
        self,
        actor: Entity,
        context: TurnContext,
        *,
        reason: DecisionEpochReason,
    ) -> AIDecisionState:
        """Project current knowledge and build exact action authority once."""
        world = self.project_world(actor, context)
        epoch_build = build_decision_epoch(
            actor,
            epoch_namespace=self._assignment_id,
            round_number=context.round_number,
            turn_index=context.turn_index,
            observation_cursor=world.observation_cursor,
            reason=reason,
        )
        if epoch_build is None:
            raise ValueError("active AI actor cannot build a decision epoch")
        world = world.model_copy(update={"current_epoch": epoch_build.epoch})
        self._world = world
        return AIDecisionState(world=world, epoch_build=epoch_build)

    def project_world(
        self,
        actor: Entity,
        context: TurnContext,
    ) -> SubjectiveWorldState:
        """Refresh subjective facts while retaining only prior unseen values."""
        if actor.uuid not in self._controlled_entity_uuids:
            raise ValueError("actor is not controlled by this AI assignment")
        self._observation_cursor += 1
        observers = resolve_controlled_observers(self._controlled_entity_uuids)
        if not observers:
            raise ValueError("AI assignment has no live controlled entities")
        visible_entities = {
            entity_uuid
            for observer in observers
            for entity_uuid in observer.senses.entities
        }
        visible_entities.update(self._controlled_entity_uuids)

        session = self._session_state(actor)
        encounter = self._encounter_state(
            actor=actor,
            context=context,
            observers=observers,
            visible_entity_uuids=visible_entities,
        )
        self._world = project_subjective_world(
            observation_cursor=self._observation_cursor,
            session=session,
            encounter=encounter,
            controlled_entity_uuids=self._controlled_entity_uuids,
            prior_world=self._world,
            combat_logs=self._world.combat_logs if self._world else (),
            current_epoch=None,
            epoch_cursor=self._observation_cursor,
        )
        return self._world

    def _session_state(self, actor: Entity) -> ObservationSessionState:
        return ObservationSessionState(
            session_id=self._assignment_id,
            player_type="ai",
            name=f"AI {self._assignment_id}",
            connection_status="connected",
            controlled_entity_uuids=[
                str(entity_uuid) for entity_uuid in self._controlled_entity_uuids
            ],
            active_entity_uuid=str(actor.uuid),
            active_entity_name=actor.name,
            is_my_turn=True,
        )


    def _encounter_state(
        self,
        *,
        actor: Entity,
        context: TurnContext,
        observers: tuple[Entity, ...],
        visible_entity_uuids: set[UUID],
    ) -> ObservationEncounterState | None:
        if context.encounter_uuid is None:
            return None
        rows: list[ObservationCombatantState] = []
        for entity_uuid in context.initiative_order:
            if entity_uuid not in visible_entity_uuids:
                continue
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            rows.append(
                ObservationCombatantState(
                    uuid=str(entity_uuid),
                    name=entity.name,
                    initiative=context.initiative_totals.get(entity_uuid),
                    life_state=entity.health.life_state,
                    is_dead=entity.health.life_state is LifeState.DEAD,
                    is_controlled=entity_uuid in self._controlled_entity_uuids,
                    knowledge_state=KnowledgeState.VISIBLE,
                    observer_uuids=observers_that_see(entity_uuid, observers),
                )
            )
        subjective_turn_index = next(
            (
                index
                for index, row in enumerate(rows)
                if row.uuid == str(actor.uuid)
            ),
            -1,
        )
        return ObservationEncounterState(
            uuid=str(context.encounter_uuid),
            name=context.encounter_name or "Encounter",
            state=context.encounter_state or "active",
            round_number=context.round_number,
            current_turn_index=subjective_turn_index,
            current_entity_uuid=str(actor.uuid),
            current_entity_name=actor.name,
            turn_started_source_event_cursor=(
                context.turn_started_source_event_cursor
            ),
            initiative_order=rows,
        )

def current_source_event_cursor() -> int:
    """Return the objective cursor only for diagnostics/replay correlation."""
    return EventQueue.event_cursor()
