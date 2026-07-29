"""Tutorial tests for event reactions, result processors, and spatial handlers."""

from typing import Optional
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.dice import Dice, DiceRoll, RollType, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    AttackD20RollResultEvent,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialHandler,
    StepMovementEvent,
    Trigger,
)
from dnd.core.values import BaseValue, ModifiableValue


def reset_reaction_state() -> None:
    """Clear global state touched by these event-reaction examples."""
    EventQueue.reset()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()
    EventQueue.set_combat_log_callback(None)


def test_first_reaction_example_prints_visible_handler_result(capsys) -> None:
    """One handler prints quiet nonmatches and the matching modified event."""
    reset_reaction_state()

    hero_id = uuid4()
    door_id = uuid4()
    chest_id = uuid4()
    alarm_id = uuid4()
    calls: list[tuple[str, UUID]] = []

    def alarm_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
        """Mark a matching door event as modified and record the handler source."""
        calls.append((event.name, handler_source_uuid))
        return event.model_copy(
            update={
                "modified": True,
                "status_message": "Alarm bell rings",
            }
        )

    alarm_handler = EventHandler(
        name="Alarm Bell",
        source_entity_uuid=alarm_id,
        trigger_conditions=[
            Trigger(
                name="Door Opened",
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=hero_id,
                event_target_entity_uuid=door_id,
            )
        ],
        event_processor=alarm_processor,
    )
    EventQueue.add_event_handler(alarm_handler)

    wrong_target = Event(
        name="Open Chest",
        source_entity_uuid=hero_id,
        target_entity_uuid=chest_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)
    opened_door = Event(
        name="Open Door",
        source_entity_uuid=hero_id,
        target_entity_uuid=door_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    handler_source = "alarm" if calls and calls[0][1] == alarm_id else "unknown"
    readout_lines = [
        f"handler: {alarm_handler.name}",
        f"wrong target status: {wrong_target.status_message or 'quiet'}",
        f"matching event status: {opened_door.status_message}",
        f"matching event modified: {opened_door.modified}",
        f"calls recorded: {len(calls)}",
        f"handler source: {handler_source}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "handler: Alarm Bell",
        "wrong target status: quiet",
        "matching event status: Alarm bell rings",
        "matching event modified: True",
        "calls recorded: 1",
        "handler source: alarm",
    ]
    assert readout_lines == expected_lines
    assert calls == [("Open Door", alarm_id)]
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_triggered_handler_modifies_matching_effect_event(capsys) -> None:
    """A trigger-indexed handler prints the one event it matches."""
    reset_reaction_state()
    hero_id = uuid4()
    door_id = uuid4()
    chest_id = uuid4()
    alarm_id = uuid4()
    calls: list[tuple[str, UUID]] = []

    def alarm_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
        calls.append((event.name, handler_source_uuid))
        return event.model_copy(
            update={
                "modified": True,
                "status_message": "Alarm bell rings",
            }
        )

    alarm_handler = EventHandler(
        name="Alarm Bell",
        source_entity_uuid=alarm_id,
        trigger_conditions=[
            Trigger(
                name="Door Opened",
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=hero_id,
                event_target_entity_uuid=door_id,
            )
        ],
        event_processor=alarm_processor,
    )
    EventQueue.add_event_handler(alarm_handler)

    wrong_target = Event(
        name="Open Chest",
        source_entity_uuid=hero_id,
        target_entity_uuid=chest_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert wrong_target.status_message is None
    assert calls == []

    opened_door = Event(
        name="Open Door",
        source_entity_uuid=hero_id,
        target_entity_uuid=door_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert opened_door.modified is True
    assert opened_door.status_message == "Alarm bell rings"
    assert calls == [("Open Door", alarm_id)]

    trigger_lines = [
        f"wrong target status: {wrong_target.status_message or 'quiet'}",
        f"matching event status: {opened_door.status_message}",
        f"matching event modified: {opened_door.modified}",
        f"handler calls: {len(calls)}",
        f"handler source matched: {calls[0][1] == alarm_id}",
    ]

    print("\n".join(trigger_lines))

    expected_trigger_lines = [
        "wrong target status: quiet",
        "matching event status: Alarm bell rings",
        "matching event modified: True",
        "handler calls: 1",
        "handler source matched: True",
    ]
    assert trigger_lines == expected_trigger_lines
    assert capsys.readouterr().out.splitlines() == expected_trigger_lines


def test_disabled_handlers_and_completion_handlers_do_not_fire(capsys) -> None:
    """Disabled and completion-phase handlers print quiet dispatch state."""
    reset_reaction_state()
    hero_id = uuid4()
    calls: list[str] = []

    def effect_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
        calls.append(event.name)
        return None

    effect_handler = EventHandler(
        name="Disabled Effect Handler",
        source_entity_uuid=hero_id,
        enabled=False,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=effect_processor,
    )
    EventQueue.add_event_handler(effect_handler)

    Event(
        name="Try Lever",
        source_entity_uuid=hero_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert calls == []

    completion_calls: list[str] = []

    def completion_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
        completion_calls.append(event.name)
        return None

    completion_handler = EventHandler(
        name="Completion Handler",
        source_entity_uuid=hero_id,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.COMPLETION,
            )
        ],
        event_processor=completion_processor,
    )
    EventQueue.add_event_handler(completion_handler)

    completion_event = Event(
        name="Finish Lever",
        source_entity_uuid=hero_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(
        EventPhase.COMPLETION
    )

    assert completion_calls == []
    assert completion_event.phase == EventPhase.COMPLETION

    quiet_lines = [
        f"disabled handler calls: {len(calls)}",
        f"completion handler calls: {len(completion_calls)}",
        f"completion event phase: {completion_event.phase.value}",
        (
            "completion stored: "
            f"{EventQueue.get_event_by_uuid(completion_event.uuid) is completion_event}"
        ),
    ]

    print("\n".join(quiet_lines))

    expected_quiet_lines = [
        "disabled handler calls: 0",
        "completion handler calls: 0",
        "completion event phase: completion",
        "completion stored: True",
    ]
    assert quiet_lines == expected_quiet_lines
    assert capsys.readouterr().out.splitlines() == expected_quiet_lines


def test_canceling_handler_stops_later_handlers(capsys) -> None:
    """A canceling handler prints the cancel result and skipped later handler."""
    reset_reaction_state()
    hero_id = uuid4()
    ward_id = uuid4()
    later_handler_calls: list[str] = []

    def ward_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
        return event.cancel(status_message="Arcane ward blocks the action")

    def later_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
        later_handler_calls.append(event.name)
        return None

    ward_handler = EventHandler(
        name="Arcane Ward",
        source_entity_uuid=ward_id,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=ward_processor,
    )
    later_handler = EventHandler(
        name="Later Handler",
        source_entity_uuid=hero_id,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=later_processor,
    )
    EventQueue.add_event_handler(ward_handler)
    EventQueue.add_event_handler(later_handler)

    result = Event(
        name="Cross Warded Door",
        source_entity_uuid=hero_id,
        event_type=EventType.BASE_ACTION,
    ).phase_to(EventPhase.EFFECT)

    assert result.phase == EventPhase.CANCEL
    assert result.canceled is True
    assert result.status_message == "Arcane ward blocks the action"
    assert later_handler_calls == []

    cancel_lines = [
        f"result phase: {result.phase.value}",
        f"canceled: {result.canceled}",
        f"reason: {result.status_message}",
        f"later handler calls: {len(later_handler_calls)}",
    ]

    print("\n".join(cancel_lines))

    expected_cancel_lines = [
        "result phase: cancel",
        "canceled: True",
        "reason: Arcane ward blocks the action",
        "later handler calls: 0",
    ]
    assert cancel_lines == expected_cancel_lines
    assert capsys.readouterr().out.splitlines() == expected_cancel_lines


def test_d20_result_processor_replaces_low_attack_roll(capsys) -> None:
    """A d20 result processor prints original and effective roll state."""
    reset_reaction_state()
    hero_id = uuid4()
    target_id = uuid4()

    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        value_name="Attack Bonus",
        base_value=4,
    )
    attack_d20 = Dice(
        count=1,
        value=20,
        bonus=attack_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(5):
        low_roll = attack_d20.roll

    def focus_processor(
        event: AttackD20RollResultEvent,
        _handler_source_uuid: UUID,
    ) -> Optional[AttackD20RollResultEvent]:
        effective_roll = event.get_effective_roll()
        if effective_roll.total >= 12:
            return None

        replacement = effective_roll.model_copy(
            update={
                "results": [14],
                "total": 18,
            }
        )
        return event.replace_roll(
            replacement,
            "Tutorial Focus",
            "raise low attack roll",
        )

    focus_handler = EventHandler(
        name="Tutorial Focus",
        source_entity_uuid=hero_id,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK_D20_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=focus_processor,
    )
    EventQueue.add_event_handler(focus_handler)

    roll_result = AttackD20RollResultEvent(
        source_entity_uuid=hero_id,
        target_entity_uuid=target_id,
        original_roll=low_roll,
        dc=15,
        bonus=attack_bonus,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).phase_to(EventPhase.EFFECT)

    assert low_roll.total == 9
    assert roll_result.modified is True
    assert roll_result.original_roll.total == 9
    assert roll_result.get_effective_roll().results == [14]
    assert roll_result.get_effective_roll().total == 18
    assert len(roll_result.roll_modifications) == 1
    modification = roll_result.roll_modifications[0]
    handler_name = modification.handler_name
    reason = modification.reason
    assert handler_name == "Tutorial Focus"
    assert reason == "raise low attack roll"
    assert modification.previous_total == 9
    assert modification.final_total == 18

    roll_lines = [
        f"original roll: faces={low_roll.results}, total={low_roll.total}",
        (
            "effective roll: "
            f"faces={roll_result.get_effective_roll().results}, "
            f"total={roll_result.get_effective_roll().total}"
        ),
        f"event modified: {roll_result.modified}",
        f"modification handler: {handler_name}",
        (
            "audit captures totals: "
            f"{modification.previous_total} -> {modification.final_total}"
        ),
    ]

    print("\n".join(roll_lines))

    expected_roll_lines = [
        "original roll: faces=[5], total=9",
        "effective roll: faces=[14], total=18",
        "event modified: True",
        "modification handler: Tutorial Focus",
        "audit captures totals: 9 -> 18",
    ]
    assert roll_lines == expected_roll_lines
    assert capsys.readouterr().out.splitlines() == expected_roll_lines


def test_spatial_handler_uses_position_index_and_can_move(capsys) -> None:
    """A spatial handler prints indexed cell hits and moved-zone state."""
    reset_reaction_state()
    druid_id = uuid4()
    runner_id = uuid4()
    entries: list[tuple[tuple[int, int], UUID, UUID]] = []

    def thorn_processor(
        event: SpatialChangeEvent,
        handler_source_uuid: UUID,
    ) -> Optional[SpatialChangeEvent]:
        entries.append((event.position, event.entity_uuid, handler_source_uuid))
        return event.model_copy(
            update={
                "modified": True,
                "status_message": "Thorns bite",
            }
        )

    thorn_handler = SpatialHandler(
        name="Thorny Ground",
        source_entity_uuid=druid_id,
        positions={(2, 2)},
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT,
        event_processor=thorn_processor,
    )
    EventQueue.add_spatial_handler(thorn_handler)

    safe_entry = EventQueue.register(
        SpatialChangeEvent(
            source_entity_uuid=runner_id,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=(1, 1),
            entity_uuid=runner_id,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )

    assert safe_entry.modified is False
    assert entries == []

    thorn_entry = EventQueue.register(
        SpatialChangeEvent(
            source_entity_uuid=runner_id,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=(2, 2),
            entity_uuid=runner_id,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )

    assert thorn_entry.modified is True
    assert thorn_entry.status_message == "Thorns bite"
    assert entries == [((2, 2), runner_id, druid_id)]
    assert EventQueue.get_spatial_handlers_at((2, 2)) == [thorn_handler]

    assert EventQueue.update_spatial_handler_positions(thorn_handler.uuid, {(3, 3)})
    assert EventQueue.get_spatial_handlers_at((2, 2)) == []
    assert EventQueue.get_spatial_handlers_at((3, 3)) == [thorn_handler]

    EventQueue.register(
        SpatialChangeEvent(
            source_entity_uuid=runner_id,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=(2, 2),
            entity_uuid=runner_id,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )
    EventQueue.register(
        SpatialChangeEvent(
            source_entity_uuid=runner_id,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            position=(3, 3),
            entity_uuid=runner_id,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )

    assert entries == [
        ((2, 2), runner_id, druid_id),
        ((3, 3), runner_id, druid_id),
    ]

    entry_positions = [entry[0] for entry in entries]
    spatial_lines = [
        f"safe cell status: {safe_entry.status_message or 'quiet'}",
        f"watched cell status: {thorn_entry.status_message}",
        f"entries after watched cell: {entry_positions[:1]}",
        f"old cell handlers after move: {len(EventQueue.get_spatial_handlers_at((2, 2)))}",
        f"new cell handlers after move: {len(EventQueue.get_spatial_handlers_at((3, 3)))}",
        f"entries after moved zone: {entry_positions}",
    ]

    print("\n".join(spatial_lines))

    expected_spatial_lines = [
        "safe cell status: quiet",
        "watched cell status: Thorns bite",
        "entries after watched cell: [(2, 2)]",
        "old cell handlers after move: 0",
        "new cell handlers after move: 1",
        "entries after moved zone: [(2, 2), (3, 3)]",
    ]
    assert spatial_lines == expected_spatial_lines
    assert capsys.readouterr().out.splitlines() == expected_spatial_lines


def test_step_movement_and_forced_movement_are_different_reaction_surfaces(
    capsys,
) -> None:
    """Opportunity-style handlers print voluntary-step-only reactions."""
    reset_reaction_state()
    watcher_id = uuid4()
    mover_id = uuid4()
    shover_id = uuid4()
    movement_reactions: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def opportunity_like_processor(
        event: StepMovementEvent,
        _handler_source_uuid: UUID,
    ) -> Optional[StepMovementEvent]:
        movement_reactions.append((event.from_position, event.to_position))
        return None

    opportunity_like_handler = EventHandler(
        name="Opportunity-Like Reaction",
        source_entity_uuid=watcher_id,
        trigger_conditions=[
            Trigger(
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=opportunity_like_processor,
    )
    EventQueue.add_event_handler(opportunity_like_handler)

    step_event = EventQueue.register(
        StepMovementEvent(
            source_entity_uuid=mover_id,
            from_position=(1, 1),
            to_position=(2, 1),
            path_index=1,
            total_path_length=2,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )
    forced_event = EventQueue.register(
        ForcedMovementEvent(
            source_entity_uuid=shover_id,
            target_entity_uuid=mover_id,
            start_position=(2, 1),
            end_position=(4, 1),
            direction=(1, 0),
            intended_distance=10,
            actual_distance=10,
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )

    assert movement_reactions == [((1, 1), (2, 1))]
    assert step_event.event_type == EventType.STEP_MOVEMENT
    assert forced_event.event_type == EventType.FORCED_MOVEMENT

    movement_lines = [
        f"step event type: {step_event.event_type.value}",
        f"forced event type: {forced_event.event_type.value}",
        f"reactions recorded: {movement_reactions}",
        f"forced movement provoked: {forced_event in movement_reactions}",
    ]

    print("\n".join(movement_lines))

    expected_movement_lines = [
        "step event type: step_movement",
        "forced event type: forced_movement",
        "reactions recorded: [((1, 1), (2, 1))]",
        "forced movement provoked: False",
    ]
    assert movement_lines == expected_movement_lines
    assert capsys.readouterr().out.splitlines() == expected_movement_lines
