"""Subjective controller revalidation at committed movement-step boundaries."""

from typing import cast
from uuid import uuid4

from dnd.actions import MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
    MovementTerminationReason,
    movement_continuation_scope,
)
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationTileFact,
)
from dnd.ai.contracts.observation_replay import materialize_snapshot
from server.agent_runtime.observation_journal import build_observation_snapshot
from dnd.ai.runtime.movement_revalidation import (
    MovementRevalidationCause,
    movement_revalidation_cause,
)
from tests.manual.test_09_action_discovery_and_costs import (
    create_tutorial_actor,
    reset_action_state,
)
from tests.manual.test_28_subjective_observation_stream import (
    create_observation_game,
)


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
    assert actor.action_economy.movement.normalized_score == 25

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


def test_subjective_revalidator_interrupts_for_new_hostile_but_not_new_ally() -> None:
    """Faction-aware visible-contact changes use only subjective entity facts."""
    _client, session_id, hero, monster, _encounter = create_observation_game(
        hidden_monster=True,
    )
    snapshot = build_observation_snapshot(session_id)
    before = materialize_snapshot(snapshot)
    enemy = ObservationEntityFact(
        uuid=str(monster.uuid),
        name=monster.name,
        knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=[str(hero.uuid)],
        position=monster.position,
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


def test_subjective_revalidator_interrupts_for_hazard_or_actor_change() -> None:
    """New hazards and material actor changes invalidate the remaining path."""
    _client, session_id, hero, _monster, _encounter = create_observation_game()
    before = materialize_snapshot(
        build_observation_snapshot(session_id)
    )
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


def test_ai_command_stream_reveals_hostile_then_returns_interrupted_epoch() -> None:
    """AI movement stops at first contact and continues through the same stream."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    Entity.update_entity_position(monster, (8, 1))
    grid = get_map()
    for y in range(grid.height):
        if y == 4:
            continue
        tile = grid.get_tile(4, y)
        assert tile is not None
        tile.visible = False
    grid._bump_spatial_revisions({"vision"})
    hero.senses.clear_visibility_cache()
    monster.senses.clear_visibility_cache()
    Entity.update_all_entities_senses(max_distance=20)
    monster_visible_before_move = monster.uuid in hero.senses.entities
    assert monster_visible_before_move is False

    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    epoch = snapshot["current_epoch"]
    row = next(
        candidate
        for candidate in epoch["affordances"]["position_actions"]
        if candidate["row_id"] == "position|Move|pos=5,5"
    )
    command_id = str(uuid4())

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["action_resolution"] == "interrupted"
    assert payload["outcome_code"] == "movement.subjective_revalidation"
    assert payload["revalidation_required"] is True
    assert payload["revalidation_reason"] == "newly_visible_hostile"
    assert hero.position != (5, 5)
    monster_visible_after_move = monster.uuid in hero.senses.entities
    assert monster_visible_after_move is True

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    result_index = next(
        index
        for index, frame in enumerate(frames)
        if frame["frame_type"] == "command_result"
        and frame["source_command_id"] == command_id
    )
    followup = next(
        frame
        for frame in frames[result_index + 1 :]
        if frame["frame_type"] == "decision_epoch"
    )
    assert any(
        frame["source_kind"] == "sensory_event"
        for frame in frames[:result_index]
    )
    streamed_result = frames[result_index]["command_result"]
    assert streamed_result["revalidation_required"] is True
    assert streamed_result["revalidation_reason"] == "newly_visible_hostile"
    assert followup["decision_epoch"]["reason"] == "movement_revalidation"
    assert followup["decision_epoch"]["economy"]["movement_remaining"] < 30

    stale = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
        },
    )
    assert stale.status_code == 200
    assert stale.json()["status"] == "stale"
