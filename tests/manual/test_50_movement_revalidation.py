"""Subjective controller revalidation at committed movement-step boundaries."""

from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest

from dnd.actions import MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationTileFact,
    SubjectiveWorldState,
)
from dnd.ai.runtime.movement_revalidation import (
    MovementRevalidationCause,
    movement_revalidation_cause,
)
from dnd.ai.runtime.state_projection import SubjectiveAIStateProjector
from dnd.ai.runtime.knowledge_system import bind_ai_knowledge, open_assignment_knowledge
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.controller import TurnContext
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
    MovementTerminationReason,
    movement_continuation_scope,
)
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from tests.manual.test_09_action_discovery_and_costs import (
    create_tutorial_actor,
    reset_action_state,
)


@pytest.fixture
def hero_world() -> Iterator[tuple[Entity, SubjectiveWorldState]]:
    """Project one controlled hero's subjective world through the native AI projector."""
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        hero = Entity.create(uuid4(), "Scout", config=EntityConfig(
            position=(1, 1),
            faction="heroes",
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
        ))
        setup_standard_actions(hero)
        hero.compose_entity()
        game.deploy_entity(hero, (1, 1))
        knowledge = bind_ai_knowledge()
        open_assignment_knowledge(knowledge, hero.uuid, (hero.uuid,))
        projector = SubjectiveAIStateProjector(
            assignment_id="movement-revalidation",
            controlled_entity_uuids=(hero.uuid,),
            knowledge=knowledge,
            knowledge_key=hero.uuid,
        )
        yield hero, projector.project_world(hero, TurnContext(
            source_entity_uuid=hero.uuid,
            entity_uuid=hero.uuid,
            initiative_order=[hero.uuid],
        ))
    finally:
        game.close()
        reset_engine_runtime()


class _InterruptAfterFirstCommittedStep:
    """Test guard that records the first fully committed movement boundary."""

    def __init__(self) -> None:
        self.boundaries: list[MovementStepBoundary] = []

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        """Interrupt after retaining the exact boundary for assertions."""
        self.boundaries.append(boundary)
        return MovementContinuationResult(
            decision=MovementContinuationDecision.INTERRUPT,
            reason="newly_visible_hostile",
            observation_cursor=17,
        )


def test_voluntary_move_interrupts_only_after_one_committed_paid_step() -> None:
    """A controller interruption completes the truthful traversed movement."""
    reset_action_state()
    actor = create_tutorial_actor(name="Scout", position=(0, 5))
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    move = next(
        action
        for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        candidate
        for candidate in move.valid_targets
        if candidate.position == (3, 5)
    )
    assert target.path is not None
    requested_path = list(target.path)
    guard = _InterruptAfterFirstCommittedStep()

    with movement_continuation_scope(guard):
        result = execute_by_index(
            actor,
            "Move",
            target.index,
            available=available,
            prefer_safe=False,
        )

    assert result is not None
    movement = cast(MovementEvent, result)
    assert not movement.canceled
    assert movement.requested_end_position == (3, 5)
    assert movement.end_position == requested_path[1]
    assert movement.path == requested_path[:2]
    assert movement.termination_reason is MovementTerminationReason.SUBJECTIVE_REVALIDATION
    assert movement.controller_revalidation is True
    assert movement.controller_revalidation_reason == "newly_visible_hostile"
    assert movement.outcome_code == "movement.subjective_revalidation"
    assert actor.position == requested_path[1]
    assert actor.action_economy.movement_remaining() == 25

    assert len(guard.boundaries) == 1
    boundary = guard.boundaries[0]
    assert boundary.from_position == requested_path[0]
    assert boundary.to_position == requested_path[1]
    assert boundary.traversed_path == tuple(requested_path[:2])
    assert boundary.movement_spent == 5
    assert boundary.movement_remaining == 25
    assert boundary.source_event_cursor_end >= boundary.source_event_cursor_start


def test_voluntary_move_reaches_destination_before_controller_revalidation() -> None:
    """A final-step discovery completes movement but still opens a new epoch."""
    reset_action_state()
    actor = create_tutorial_actor(name="Scout", position=(0, 5))
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    move = next(
        action
        for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        candidate
        for candidate in move.valid_targets
        if candidate.position == (1, 5)
    )
    guard = _InterruptAfterFirstCommittedStep()

    with movement_continuation_scope(guard):
        result = execute_by_index(
            actor,
            "Move",
            target.index,
            available=available,
            prefer_safe=False,
        )

    assert result is not None
    movement = cast(MovementEvent, result)
    assert movement.end_position == (1, 5)
    assert movement.requested_end_position == (1, 5)
    assert movement.termination_reason is MovementTerminationReason.COMPLETED
    assert movement.controller_revalidation is True
    assert movement.controller_revalidation_reason == "newly_visible_hostile"
    assert movement.outcome_code == "movement.subjective_revalidation"


def test_subjective_revalidator_interrupts_for_new_hostile_but_not_new_ally(
    hero_world: tuple[Entity, SubjectiveWorldState],
) -> None:
    """Faction-aware visible-contact changes use only subjective entity facts."""
    hero, before = hero_world
    enemy = ObservationEntityFact(
        uuid=str(uuid4()),
        name="Observation Skeleton",
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=[str(hero.uuid)],
        position=(5, 1),
        faction="monsters",
        is_dead=False,
    )
    enemy_world = before.model_copy(update={
        "known_entities": {
            **before.known_entities,
            enemy.uuid: enemy,
        },
    })

    assert movement_revalidation_cause(
        before,
        enemy_world,
        str(hero.uuid),
    ) is MovementRevalidationCause.NEWLY_VISIBLE_HOSTILE

    ally = enemy.model_copy(update={
        "uuid": "visible-ally",
        "name": "Visible Ally",
        "faction": "heroes",
    })
    ally_world = before.model_copy(update={
        "known_entities": {
            **before.known_entities,
            ally.uuid: ally,
        },
    })
    assert movement_revalidation_cause(
        before,
        ally_world,
        str(hero.uuid),
    ) is None


def test_subjective_revalidator_interrupts_for_hazard_or_actor_change(
    hero_world: tuple[Entity, SubjectiveWorldState],
) -> None:
    """New hazards and material actor changes invalidate the remaining path."""
    hero, before = hero_world
    hazard = ObservationTileFact(
        key="3,1",
        position=(3, 1),
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=[str(hero.uuid)],
        walkable=True,
        walking_cost=5,
        is_hazardous=True,
    )
    hazard_world = before.model_copy(update={
        "known_tiles": {
            **before.known_tiles,
            hazard.key: hazard,
        },
    })
    assert movement_revalidation_cause(
        before,
        hazard_world,
        str(hero.uuid),
    ) is MovementRevalidationCause.NEWLY_VISIBLE_HAZARD

    actor = before.known_entities[str(hero.uuid)]
    changed_actor = actor.model_copy(update={
        "conditions": [*actor.conditions, "Poisoned"],
    })
    actor_world = before.model_copy(update={
        "known_entities": {
            **before.known_entities,
            str(hero.uuid): changed_actor,
        },
    })
    assert movement_revalidation_cause(
        before,
        actor_world,
        str(hero.uuid),
    ) is MovementRevalidationCause.ACTOR_STATE_CHANGED
