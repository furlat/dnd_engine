"""One-way and idempotent spatial-effect reveal regressions."""

from __future__ import annotations

from typing import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_effect,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialEffectChangeEvent,
)
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.content.spike_trap_materialization import materialize_spike_trap_effect
from dnd.spatial.environmental_effects import SpikeTrapGroundEffect
from dnd.runtime_reset import reset_engine_runtime
from dnd.content.spatial_effect_recipes import spike_trap_effect_recipe


def _begin_parent_effect(source_entity_uuid: UUID) -> Event:
    """Publish one real causal parent through its effect phase."""
    declaration = Event(
        name="Reveal Spatial Effect",
        source_entity_uuid=source_entity_uuid,
        source_entity_name="Environment",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    accepted = EventQueue.publish_declaration(declaration)
    assert not accepted.canceled
    execution = accepted.phase_to(EventPhase.EXECUTION)
    assert not execution.canceled
    effect = execution.phase_to(EventPhase.EFFECT)
    assert not effect.canceled
    return effect


def _completed_reveals_since(
    cursor: int,
    effect_uuid: UUID,
) -> Iterator[SpatialEffectChangeEvent]:
    """Yield completed reveal facts for one exact spatial effect."""
    for _, event in EventQueue.iter_events_since(cursor):
        if (
            isinstance(event, SpatialEffectChangeEvent)
            and event.phase is EventPhase.COMPLETION
            and event.spatial_effect_uuid == effect_uuid
            and event.operation is SpatialEffectChangeOperation.REVEALED
        ):
            yield event


def test_hidden_effect_reveals_once_then_becomes_a_true_noop() -> None:
    """The effect DC is the one-way latch for one typed reveal lifecycle."""
    reset_engine_runtime(grid_size=(4, 4))
    positions = {(1, 1), (2, 1)}
    effect = materialize_spike_trap_effect(positions, stealth_dc=20)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor_before_reveal = EventQueue.event_cursor()

    assert effect.stealth_dc == 20

    first = effect.publish_revealed(parent_event=parent)

    assert first is not None
    assert first.phase is EventPhase.COMPLETION
    assert first.operation is SpatialEffectChangeOperation.REVEALED
    assert first.parent_event == parent.uuid
    assert first.spatial_effect_uuid == effect.uuid
    assert first.spatial_effect_content_ref == effect.content_ref
    assert first.affected_positions == tuple(sorted(positions))
    assert first.previous_positions == tuple(sorted(positions))
    assert first.combat_log is not None
    assert first.combat_log.data["operation"] == "revealed"
    assert effect.stealth_dc is None

    cursor_after_first = EventQueue.event_cursor()
    second = effect.publish_revealed(parent_event=parent)

    assert second is None
    assert effect.stealth_dc is None
    assert EventQueue.event_cursor() == cursor_after_first
    assert list(_completed_reveals_since(
        cursor_before_reveal,
        effect.uuid,
    )) == [first]

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_installed_visible_effect_does_not_invent_a_reveal() -> None:
    """An effect authored without concealment has no reveal transition."""
    reset_engine_runtime(grid_size=(4, 4))
    effect = materialize_spike_trap_effect({(1, 1)}, stealth_dc=None)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor = EventQueue.event_cursor()

    assert effect.stealth_dc is None
    assert effect.publish_revealed(parent_event=parent) is None
    assert effect.stealth_dc is None
    assert EventQueue.event_cursor() == cursor
    assert list(_completed_reveals_since(cursor, effect.uuid)) == []

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_uninstalled_effect_cannot_be_revealed() -> None:
    """Installation truth takes precedence over the concealment latch."""
    reset_engine_runtime(grid_size=(4, 4))
    source_entity_uuid = uuid4()
    effect = materialize_spatial_effect(
        spike_trap_effect_recipe(stealth_dc=20),
        source_entity_uuid,
        position=(1, 1),
        faction=None,
        expected_type=SpikeTrapGroundEffect,
    )
    parent = _begin_parent_effect(source_entity_uuid)
    cursor = EventQueue.event_cursor()

    assert effect.stealth_dc == 20
    with pytest.raises(
        RuntimeError,
        match="Cannot reveal an uninstalled spatial effect",
    ):
        effect.publish_revealed(parent_event=parent)

    assert effect.stealth_dc == 20
    assert EventQueue.event_cursor() == cursor
    assert list(_completed_reveals_since(cursor, effect.uuid)) == []

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_reveal_veto_preserves_concealment_and_allows_one_later_reveal() -> None:
    """A canceled reveal leaves objective state unchanged for a clean retry."""
    reset_engine_runtime(grid_size=(4, 4))
    effect = materialize_spike_trap_effect({(1, 1)}, stealth_dc=20)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor_before_veto = EventQueue.event_cursor()

    def veto_reveal(
        event: Event,
        _handler_source_uuid: UUID,
    ) -> Event | None:
        if (
            isinstance(event, SpatialEffectChangeEvent)
            and event.spatial_effect_uuid == effect.uuid
            and event.operation is SpatialEffectChangeOperation.REVEALED
        ):
            return event.cancel(status_message="Reveal vetoed for regression")
        return None

    veto = EventHandler(
        name="Veto Spatial Effect Reveal",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="Veto reveal declaration",
                event_type=EventType.SPATIAL_EFFECT_CHANGED,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=veto_reveal,
    )
    EventQueue.add_event_handler(veto)

    assert effect.publish_revealed(parent_event=parent) is None
    assert effect.stealth_dc == 20
    assert list(_completed_reveals_since(
        cursor_before_veto,
        effect.uuid,
    )) == []

    EventQueue.remove_event_handler(veto)
    revealed = effect.publish_revealed(parent_event=parent)

    assert revealed is not None
    assert effect.stealth_dc is None
    assert list(_completed_reveals_since(
        cursor_before_veto,
        effect.uuid,
    )) == [revealed]

    cursor_after_reveal = EventQueue.event_cursor()
    assert effect.publish_revealed(parent_event=parent) is None
    assert EventQueue.event_cursor() == cursor_after_reveal

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_reentrant_reveal_request_does_not_create_a_nested_lifecycle() -> None:
    """Reveal handlers cannot recursively manufacture a second transition."""
    reset_engine_runtime(grid_size=(4, 4))
    effect = materialize_spike_trap_effect({(1, 1)}, stealth_dc=20)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor = EventQueue.event_cursor()
    handler_calls: list[EventPhase] = []
    nested_results: list[SpatialEffectChangeEvent | None] = []

    def request_nested_reveal(
        event: Event,
        _handler_source_uuid: UUID,
    ) -> None:
        handler_calls.append(event.phase)
        if len(handler_calls) == 1:
            nested_results.append(effect.publish_revealed(parent_event=event))

    handler = EventHandler(
        name="Request Nested Spatial Effect Reveal",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="Re-enter reveal effect",
                event_type=EventType.SPATIAL_EFFECT_CHANGED,
                event_phase=EventPhase.EFFECT,
            ),
        ],
        event_processor=request_nested_reveal,
    )
    EventQueue.add_event_handler(handler)

    revealed = effect.publish_revealed(parent_event=parent)

    assert revealed is not None
    assert effect.stealth_dc is None
    assert handler_calls == [EventPhase.EFFECT]
    assert nested_results == [None]
    assert list(_completed_reveals_since(cursor, effect.uuid)) == [revealed]

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_retired_revealed_effect_still_fails_installation_check_first() -> None:
    """Retirement remains an error even after concealment has been cleared."""
    reset_engine_runtime(grid_size=(4, 4))
    effect = materialize_spike_trap_effect({(1, 1)}, stealth_dc=20)
    parent = _begin_parent_effect(effect.source_entity_uuid)

    revealed = effect.publish_revealed(parent_event=parent)
    assert revealed is not None
    assert effect.stealth_dc is None
    effect.retire(parent_event=parent)
    cursor = EventQueue.event_cursor()

    with pytest.raises(
        RuntimeError,
        match="Cannot reveal an uninstalled spatial effect",
    ):
        effect.publish_revealed(parent_event=parent)

    assert effect.stealth_dc is None
    assert EventQueue.event_cursor() == cursor
    assert list(_completed_reveals_since(cursor, effect.uuid)) == []

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled
