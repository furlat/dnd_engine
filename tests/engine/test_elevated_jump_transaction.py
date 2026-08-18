"""Atomic elevated Jump settlement and takeoff-only reaction truth."""

from dnd.actions.standard import (
    Jump,
)
from dnd.core.events.action_events import (
    JumpEvent,
)
from uuid import UUID, uuid4

import pytest

from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.action_execution import (
    MovementProvocationPolicy,
)
from dnd.core.events.world_events import (
    MovementTrajectory,
    StepMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entities.entity import Entity
from tests.engine.support import create_test_monster
from dnd.actions.reactions import add_opportunity_attack_handler
from tests.engine.support import (
    force_attack_crit,
    force_attack_hit,
    remove_attack_modifier,
    set_hp,
)
from tests.engine.test_combat_actions import (
    fixed_dice,
    reset_core_action_state,
    strong_entity,
)


def _set_height(position: tuple[int, int], height: int) -> None:
    get_map().set_tile_elevation(
        position,
        height=height,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )


def _jump_steps(source_uuid: UUID) -> list[StepMovementEvent]:
    return [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == source_uuid
    ]


def test_elevated_jump_commits_one_direct_arc_with_exact_support_cost() -> None:
    reset_core_action_state()
    jumper = strong_entity("Elevated Jumper", (1, 1), "heroes", strength=18)
    _set_height((4, 1), 2)
    Entity.update_all_entities_senses(max_distance=20)

    result = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(4, 1),
    ).apply()

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.requested_end_position == (4, 1)
    assert result.end_position == (4, 1)
    assert result.objective_end_position == (4, 1)
    assert result.start_elevation_feet == 0
    assert result.requested_end_elevation_feet == 10
    assert result.end_elevation_feet == 10
    assert result.jump_distance == 15
    assert result.combat_log is not None
    assert result.combat_log.data["movement_type"] == "jump"
    assert jumper.position == (4, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert jumper.action_economy.movement.normalized_score == 15


def test_step_handler_cannot_rewrite_jump_root_to_underpay_landing() -> None:
    """Jump debit and landing retain the accepted root EFFECT snapshot."""
    reset_core_action_state()
    jumper = strong_entity("Root Guarded Jumper", (1, 1), "heroes", strength=18)
    Entity.update_all_entities_senses(max_distance=20)

    def rewrite_parent_jump(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is not None:
            stored_root = EventQueue.get_event_by_uuid(event.parent_event)
            if type(stored_root) is JumpEvent:
                stored_root.requested_end_position = (2, 1)
                stored_root.requested_end_elevation_feet = 999
                stored_root.end_position = (2, 1)
                stored_root.objective_end_position = (2, 1)
                stored_root.path = ((1, 1), (2, 1))
                stored_root.jump_distance = 5
                stored_root.movement_spent = 5
        return event

    jumper.add_event_handler(EventHandler(
        name="Rewrite Jump root during Step EFFECT",
        source_entity_uuid=jumper.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=rewrite_parent_jump,
    ))

    result = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(4, 1),
    ).apply()

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.requested_end_position == (4, 1)
    assert result.requested_end_elevation_feet == 0
    assert result.end_position == (4, 1)
    assert result.path == ((1, 1), (2, 1), (3, 1), (4, 1))
    assert result.jump_distance == 15
    assert result.movement_spent == 15
    assert jumper.position == (4, 1)
    assert jumper.action_economy.movement.normalized_score == 15
    completed_steps = [
        event
        for event in _jump_steps(jumper.uuid)
        if event.phase is EventPhase.COMPLETION
    ]
    assert len(completed_steps) == 1
    assert completed_steps[0].movement_cost == 15
    assert completed_steps[0].to_position == (4, 1)

    steps = _jump_steps(jumper.uuid)
    assert steps[0].phase is EventPhase.DECLARATION
    assert steps[1].phase is EventPhase.EXECUTION
    assert steps[-1].phase is EventPhase.COMPLETION
    assert all(
        event.to_position == (4, 1)
        and event.disclosed_path == ((1, 1), (2, 1), (3, 1), (4, 1))
        and event.movement_cost == 15
        for event in steps
        if event.phase is EventPhase.EFFECT
    )
    completed = steps[-1]
    assert completed.committed is True
    assert completed.trajectory is MovementTrajectory.DIRECT_ARC
    assert completed.from_position == (1, 1)
    assert completed.to_position == (4, 1)
    assert completed.disclosed_path == ((1, 1), (2, 1), (3, 1), (4, 1))
    assert completed.from_elevation_feet == 0
    assert completed.to_elevation_feet == 0
    assert completed.movement_cost == 15
    assert completed.provocation_policy is MovementProvocationPolicy.ORDINARY_EXIT


def test_jump_arc_does_not_recruit_intermediate_only_reactor() -> None:
    reset_core_action_state()
    jumper = strong_entity("Arc Jumper", (5, 5), "heroes", strength=18)
    intermediate_reactor = create_test_monster("monster.skeleton", 
        name="Intermediate Reactor",
        position=(6, 7),
        faction="monsters",
    )
    add_opportunity_attack_handler(intermediate_reactor)
    Entity.update_all_entities_senses(max_distance=20)
    hit_modifier = force_attack_hit(intermediate_reactor)
    hp_before = jumper.get_hp()

    try:
        result = Jump(
            source_entity_uuid=jumper.uuid,
            end_position=(5, 9),
        ).apply()
    finally:
        remove_attack_modifier(intermediate_reactor, hit_modifier)

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert jumper.position == (5, 9)
    assert jumper.get_hp() == hp_before
    assert intermediate_reactor.action_economy.reactions.normalized_score == 1
    assert not any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )
    assert len({event.lineage_uuid for event in _jump_steps(jumper.uuid)}) == 1


def test_lethal_takeoff_reaction_keeps_fixed_cost_but_not_movement_cost() -> None:
    reset_core_action_state()
    jumper = strong_entity(
        "Fragile Jumper",
        (5, 6),
        "heroes",
        strength=18,
    )
    set_hp(jumper, 1)
    watcher = create_test_monster("monster.skeleton", 
        name="Takeoff Watcher",
        position=(5, 5),
        faction="monsters",
    )
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)
    movement_handles_before = set(
        jumper.action_economy.movement.self_static.value_modifiers
    )
    bonus_handles_before = set(
        jumper.action_economy.bonus_actions.self_static.value_modifiers
    )
    hit_modifier = force_attack_hit(watcher)
    crit_modifier = force_attack_crit(watcher)

    try:
        with fixed_dice(10, 6, 6):
            result = Jump(
                source_entity_uuid=jumper.uuid,
                end_position=(5, 9),
            ).apply()
    finally:
        remove_attack_modifier(watcher, hit_modifier)
        remove_attack_modifier(watcher, crit_modifier)

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.end_position == (5, 6)
    assert result.objective_end_position == (5, 6)
    assert result.termination_reason is not None
    assert jumper.health.life_state is LifeState.DEAD
    assert jumper.position == (5, 6)
    assert set(
        jumper.action_economy.bonus_actions.self_static.value_modifiers
    ) > bonus_handles_before
    assert set(
        jumper.action_economy.movement.self_static.value_modifiers
    ) == movement_handles_before
    steps = _jump_steps(jumper.uuid)
    assert [event.phase for event in steps][-1] is EventPhase.COMPLETION
    assert steps[-1].committed is False


def test_jump_root_effect_veto_spends_nothing_and_publishes_no_step() -> None:
    reset_core_action_state()
    jumper = strong_entity("Vetoed Jumper", (1, 1), "heroes", strength=18)
    Entity.update_all_entities_senses(max_distance=20)
    handler = EventHandler(
        name="Veto Jump Effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Veto Jump",
            event_type=EventType.MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=lambda event, _source: (
            event.cancel(status_message="Jump vetoed")
            if type(event) is JumpEvent
            else event
        ),
    )
    EventQueue.add_event_handler(handler)
    try:
        result = Jump(
            source_entity_uuid=jumper.uuid,
            end_position=(4, 1),
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.EFFECT
    assert result.end_position == (1, 1)
    assert result.termination_reason.value == "canceled"
    assert jumper.position == (1, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 1
    assert jumper.action_economy.movement.normalized_score == 30
    assert _jump_steps(jumper.uuid) == []
    assert not any(
        type(event) is JumpEvent and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
    )


def test_direct_arc_effect_forgery_stops_without_observable_forged_geometry() -> None:
    reset_core_action_state()
    jumper = strong_entity("Guarded Jumper", (1, 1), "heroes", strength=18)
    Entity.update_all_entities_senses(max_distance=20)

    def forge_arc(event: Event, _source: UUID) -> Event:
        if type(event) is not StepMovementEvent:
            return event
        return event.model_copy(update={
            "to_position": (99, 99),
            "to_elevation_feet": 999,
            "movement_cost": 999,
            "disclosed_path": ((1, 1), (99, 99)),
        })

    handler = EventHandler(
        name="Forge Jump Arc",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Forge Arc Effect",
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=forge_arc,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = Jump(
            source_entity_uuid=jumper.uuid,
            end_position=(4, 1),
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason.value == "step_canceled"
    assert result.fixed_costs_committed is True
    assert result.movement_spent == 0
    assert jumper.position == (1, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert jumper.action_economy.movement.normalized_score == 30
    steps = _jump_steps(jumper.uuid)
    assert steps[-1].phase is EventPhase.COMPLETION
    assert steps[-1].committed is False
    assert all(step.to_position == (4, 1) for step in steps)
    assert all(step.to_elevation_feet == 0 for step in steps)
    assert all(step.movement_cost == 15 for step in steps)
    assert all((99, 99) not in step.disclosed_path for step in steps)


def test_jump_position_staging_failure_undoes_only_movement_debit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_core_action_state()
    jumper = strong_entity("Staging Jumper", (1, 1), "heroes", strength=18)
    Entity.update_all_entities_senses(max_distance=20)
    grid = get_map()
    original = grid.recompute_tile_directional_blocking
    movement_handles_before = set(
        jumper.action_economy.movement.self_static.value_modifiers
    )

    def fail_landing(position: tuple[int, int]):
        if position == (4, 1):
            raise RuntimeError("injected Jump staging failure")
        return original(position)

    monkeypatch.setattr(grid, "recompute_tile_directional_blocking", fail_landing)
    with pytest.raises(PositionCommitError):
        Jump(
            source_entity_uuid=jumper.uuid,
            end_position=(4, 1),
        ).apply()

    assert jumper.position == (1, 1)
    assert jumper.senses.position == (1, 1)
    assert grid.get_entity_position(jumper.uuid) == (1, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert set(
        jumper.action_economy.movement.self_static.value_modifiers
    ) == movement_handles_before
    assert not any(
        type(event) is JumpEvent and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
    )


def test_jump_spatial_publication_failure_preserves_committed_position_and_cost() -> None:
    reset_core_action_state()
    jumper = strong_entity("Publishing Jumper", (1, 1), "heroes", strength=18)
    Entity.update_all_entities_senses(max_distance=20)
    handler = EventHandler(
        name="Fail Jump Spatial Publication",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Raise On Jump Left",
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=lambda _event, _source: (_ for _ in ()).throw(
            RuntimeError("injected Jump publication failure")
        ),
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(PositionPublicationError):
            Jump(
                source_entity_uuid=jumper.uuid,
                end_position=(4, 1),
            ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert jumper.position == (4, 1)
    assert jumper.senses.position == (4, 1)
    assert get_map().get_entity_position(jumper.uuid) == (4, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert jumper.action_economy.movement.normalized_score == 15
    assert not any(
        type(event) is JumpEvent and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
    )


def test_jump_arrival_handler_cannot_mutate_stored_step_or_root_effect() -> None:
    """Landing callbacks cannot rewrite the accepted Jump arc or settlement."""
    reset_core_action_state()
    jumper = strong_entity("Arrival Guarded Jumper", (1, 1), "heroes", strength=18)
    _set_height((4, 1), 2)
    Entity.update_all_entities_senses(max_distance=20)

    def mutate_stored_effects(event: Event, _source: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        stored_step.disclosed_path = ((1, 1), (99, 99))
        if type(stored_root) is JumpEvent:
            stored_root.requested_end_position = (99, 99)
            stored_root.objective_end_position = (99, 99)
            stored_root.requested_end_elevation_feet = 999
            stored_root.end_elevation_feet = 999
            stored_root.jump_distance = 999
            stored_root.movement_spent = 999
            stored_root.path = ((1, 1), (99, 99))
        return event

    jumper.add_event_handler(EventHandler(
        name="Mutate stored Jump effects during arrival",
        source_entity_uuid=jumper.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=mutate_stored_effects,
    ))

    result = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(4, 1),
    ).apply()

    assert type(result) is JumpEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.requested_end_position == (4, 1)
    assert result.end_position == (4, 1)
    assert result.objective_end_position == (4, 1)
    assert result.requested_end_elevation_feet == 10
    assert result.end_elevation_feet == 10
    assert result.jump_distance == 15
    assert result.movement_spent == 15
    assert result.path is not None
    assert (99, 99) not in result.path
    assert result.combat_log is not None
    assert result.combat_log.data["end_position"] == (4, 1)
    assert result.combat_log.data["distance_feet"] == 15
    steps = _jump_steps(jumper.uuid)
    assert all(step.to_position == (4, 1) for step in steps)
    assert all(step.to_elevation_feet == 10 for step in steps)
    assert all(step.movement_cost == 15 for step in steps)
    assert all((99, 99) not in step.disclosed_path for step in steps)


def test_jump_arrival_mutation_is_restored_before_publication_error_escapes() -> None:
    """A committed Jump failure cannot retain forged Step/root history."""
    reset_core_action_state()
    jumper = strong_entity("Failing Arrival Jumper", (1, 1), "heroes", strength=18)
    _set_height((4, 1), 2)
    Entity.update_all_entities_senses(max_distance=20)

    def mutate_effects_then_raise(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.uuid = uuid4()
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        if type(stored_root) is JumpEvent:
            stored_root.uuid = uuid4()
            stored_root.requested_end_position = (99, 99)
            stored_root.requested_end_elevation_feet = 999
            stored_root.jump_distance = 999
            stored_root.path = ((1, 1), (99, 99))
        raise RuntimeError("injected Jump arrival publication failure")

    jumper.add_event_handler(EventHandler(
        name="Mutate and fail Jump arrival publication",
        source_entity_uuid=jumper.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=jumper.uuid,
        )],
        event_processor=mutate_effects_then_raise,
    ))

    with pytest.raises(PositionPublicationError):
        Jump(source_entity_uuid=jumper.uuid, end_position=(4, 1)).apply()

    assert jumper.position == (4, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert jumper.action_economy.movement.normalized_score == 15
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is JumpEvent
        and event.source_entity_uuid == jumper.uuid
        and event.phase is EventPhase.EFFECT
    ]
    steps = [
        event
        for event in _jump_steps(jumper.uuid)
        if event.phase is EventPhase.EFFECT
    ]
    assert len(roots) == 1
    assert len(steps) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert EventQueue.get_event_by_uuid(steps[0].uuid) is steps[0]
    assert roots[0].requested_end_position == (4, 1)
    assert roots[0].requested_end_elevation_feet == 10
    assert roots[0].jump_distance == 15
    assert roots[0].path is not None and (99, 99) not in roots[0].path
    assert steps[0].to_position == (4, 1)
    assert steps[0].to_elevation_feet == 10
    assert steps[0].movement_cost == 15
    assert not any(step.phase is EventPhase.COMPLETION for step in _jump_steps(jumper.uuid))


def test_jump_restores_parent_between_step_handlers_and_when_later_handler_raises() -> None:
    """A Step handler cannot lend forged Jump facts to the next handler."""
    reset_core_action_state()
    jumper = strong_entity("Step Guarded Jumper", (1, 1), "heroes", strength=18)
    _set_height((4, 1), 2)
    Entity.update_all_entities_senses(max_distance=20)
    seen_distances: list[int] = []

    def forge_parent(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is JumpEvent:
                parent.uuid = uuid4()
                parent.requested_end_position = (99, 99)
                parent.jump_distance = 999
        return event

    def observe_reforge_and_raise(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is JumpEvent:
                seen_distances.append(parent.jump_distance)
                if parent.jump_distance == 999:
                    set_hp(jumper, 0)
                parent.uuid = uuid4()
                parent.jump_distance = 888
                parent.requested_end_position = (88, 88)
        raise RuntimeError("injected Jump Step handler failure")

    for name, processor in (
        ("Forge Jump parent in first Step handler", forge_parent),
        ("Observe Jump parent in second Step handler", observe_reforge_and_raise),
    ):
        jumper.add_event_handler(EventHandler(
            name=name,
            source_entity_uuid=jumper.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=jumper.uuid,
            )],
            event_processor=processor,
        ))

    with pytest.raises(RuntimeError, match="injected Jump Step handler failure"):
        Jump(source_entity_uuid=jumper.uuid, end_position=(4, 1)).apply()

    assert seen_distances == [15]
    assert jumper.health.life_state is LifeState.ALIVE
    assert jumper.position == (1, 1)
    assert jumper.action_economy.bonus_actions.normalized_score == 0
    assert jumper.action_economy.movement.normalized_score == 30
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is JumpEvent
        and event.source_entity_uuid == jumper.uuid
        and event.phase is EventPhase.EFFECT
    ]
    assert len(roots) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert roots[0].requested_end_position == (4, 1)
    assert roots[0].jump_distance == 15
