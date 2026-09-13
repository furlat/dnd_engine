"""Assignment-owned recorded knowledge and exact native decision authority."""

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
from dnd.ai.runtime.knowledge_reduction import AIKnowledge
from dnd.controller import TurnContext
from dnd.core.events import EventQueue
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
        self._source_generation = EventQueue.generation_id()
        self._knowledge = AIKnowledge(self._controlled_entity_uuids)

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
        """Consume committed source facts, then expose this decision's knowledge."""
        if actor.uuid not in self._controlled_entity_uuids:
            raise ValueError("actor is not controlled by this AI assignment")
        if EventQueue.generation_id() != self._source_generation:
            raise RuntimeError("AI assignment belongs to an earlier event generation")
        self._knowledge.consume(
            (index, event, None)
            for index, event in EventQueue.iter_events_since(self._knowledge.source_cursor)
        )
        self._observation_cursor += 1
        knowledge = self._knowledge
        if actor.uuid not in knowledge.actors:
            raise ValueError("AI actor requires its recorded birth before a decision")
        session = self._session_state(actor)
        encounter = self._encounter_state(actor=actor, context=context)
        # Fact values are immutable and shared; only publication containers are
        # copied so a movement guard retains its genuine previous observation.
        self._world = SubjectiveWorldState.model_construct(
            observation_cursor=self._observation_cursor,
            session=session, encounter=encounter,
            observers=dict(knowledge.observers),
            known_entities=dict(knowledge.known_entities),
            known_objects=dict(knowledge.known_objects),
            known_tiles=dict(knowledge.known_tiles),
            combat_logs=self._world.combat_logs if self._world else [],
            current_epoch=None, epoch_cursor=self._observation_cursor,
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
            active_entity_name=self._knowledge.actors[actor.uuid].name,
            is_my_turn=True,
        )


    def _encounter_state(
        self,
        *,
        actor: Entity,
        context: TurnContext,
    ) -> ObservationEncounterState | None:
        if context.encounter_uuid is None:
            return None
        rows: list[ObservationCombatantState] = []
        for entity_uuid in context.initiative_order:
            fact = self._knowledge.known_entities.get(str(entity_uuid))
            if fact is None or fact.knowledge_state is not KnowledgeState.VISIBLE:
                continue
            rows.append(
                ObservationCombatantState(
                    uuid=str(entity_uuid),
                    name=fact.name,
                    initiative=context.initiative_totals.get(entity_uuid),
                    life_state=fact.life_state,
                    is_dead=fact.is_dead,
                    is_controlled=entity_uuid in self._controlled_entity_uuids,
                    knowledge_state=KnowledgeState.VISIBLE,
                    observer_uuids=fact.observer_uuids,
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
            current_entity_name=self._knowledge.actors[actor.uuid].name,
            turn_started_source_event_cursor=(
                context.turn_started_source_event_cursor
            ),
            initiative_order=rows,
        )

def current_source_event_cursor() -> int:
    """Return the objective cursor only for diagnostics/replay correlation."""
    return EventQueue.event_cursor()
