"""Focused integration tests for canonical live subjective replication."""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import GridMap
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import DndEventStream
from server.player_replication.journal import (
    SubjectiveJournalIdentityError,
    SubjectiveJournalStore,
    SubjectiveProjectionError,
    SubjectiveSubscriptionClosedError,
)
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationContext,
    CanonicalSubjectiveReplicationRuntime,
    SubjectiveRuntimeIdentityError,
)
from server.player_replication_contract import (
    EntityUpsertPatch,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveSyncDelivery,
)
from server.replication_perspective import PerspectiveScope
from server.subjective_authority import ResolvedSubjectiveAuthority
from server.timeline_contracts import CombatLogProjection


@dataclass(frozen=True)
class RuntimeScene:
    grid: GridMap
    observer: Entity
    encounter: Encounter
    authority: ResolvedSubjectiveAuthority
    source_stream: DndEventStream
    runtime: CanonicalSubjectiveReplicationRuntime
    context: CanonicalSubjectiveReplicationContext


def _authority(
    observer: Entity,
    *,
    epoch: str = "perspective-1",
    session_id: str = "session-1",
) -> ResolvedSubjectiveAuthority:
    observer_uuid = str(observer.uuid)
    return ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id=session_id,
            membership_id="membership-1",
            authority_epoch=1,
            projection=CombatLogProjection.SUBJECTIVE,
            controlled_entity_uuids=(observer_uuid,),
            observer_entity_uuids=(observer_uuid,),
            active_observer_uuid=observer_uuid,
        ),
        perspective_epoch_id=epoch,
    )


@pytest.fixture
def runtime_scene() -> Iterator[RuntimeScene]:
    grid = reset_engine_runtime(grid_size=(3, 1))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}

    encounter = Encounter(name="Runtime encounter", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    authority = _authority(observer)
    context = runtime.bind(authority, encounter=encounter)
    try:
        yield RuntimeScene(
            grid=grid,
            observer=observer,
            encounter=encounter,
            authority=authority,
            source_stream=source_stream,
            runtime=runtime,
            context=context,
        )
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def _log(observer: Entity, text: str) -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=observer.name,
        source_uuid=str(observer.uuid),
        compact=text,
        verbose=text,
        detailed=text,
    )


def test_normal_log_is_delivered_after_its_causal_observation_frame(
    runtime_scene: RuntimeScene,
) -> None:
    """Objective finalization cannot overtake the reducer's event barrier."""
    context = runtime_scene.context
    snapshot = context.subscribe_with_backfill(
        from_observation_cursor=0,
        from_combat_log_cursor=0,
    )
    subscription = snapshot.subscription
    sync = asyncio.run(subscription.get())
    assert isinstance(sync, SubjectiveSyncDelivery)
    assert sync == snapshot.sync
    assert snapshot.observation_backfill.frames == ()
    assert snapshot.combat_log_backfill.frames == ()

    with EventQueue.batch_on_event_callbacks():
        declaration = Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=runtime_scene.observer.uuid,
            combat_log=_log(runtime_scene.observer, "Observed action"),
        )
        declaration.phase_to(EventPhase.COMPLETION)

    frame_delivery = asyncio.run(subscription.get())
    log_delivery = asyncio.run(subscription.get())
    assert isinstance(frame_delivery, SubjectiveFrameDelivery)
    assert isinstance(log_delivery, SubjectiveCombatLogDelivery)
    assert frame_delivery.frame.presentation == ()
    assert frame_delivery.frame.watermarks.source_event_cursor == EventQueue.event_cursor()
    assert frame_delivery.frame.watermarks.observation_cursor == 1
    assert frame_delivery.frame.watermarks.combat_log_cursor == 0
    assert log_delivery.frame.event_cursor == frame_delivery.frame.watermarks.source_event_cursor
    assert log_delivery.frame.combat_log_cursor == 1
    assert log_delivery.watermarks.observation_cursor == 1
    assert log_delivery.watermarks.combat_log_cursor == 1
    assert context.journal.watermarks == log_delivery.watermarks


def test_standalone_log_releases_immediately_behind_consumed_barrier(
    runtime_scene: RuntimeScene,
) -> None:
    """A standalone exact slot needs no later dummy event to reach subscribers."""
    context = runtime_scene.context
    subscription = context.subscribe()
    asyncio.run(subscription.get())
    opening_watermarks = context.journal.watermarks

    EventQueue.push_combat_log(
        _log(runtime_scene.observer, "Standalone observation"),
        runtime_scene.observer.uuid,
    )

    delivery = asyncio.run(subscription.get())
    assert isinstance(delivery, SubjectiveCombatLogDelivery)
    assert delivery.frame.event_cursor == opening_watermarks.source_event_cursor
    assert delivery.watermarks.observation_cursor == opening_watermarks.observation_cursor
    assert delivery.watermarks.combat_log_cursor == 1


def test_bind_catches_up_exact_existing_logs_at_the_opening_event_cursor() -> None:
    """A mid-game perspective seed includes all exact reducer log inputs."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Late observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
    )
    observer.senses.visible = {(0, 0): True}
    observer.senses.seen = {(0, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    encounter = Encounter(name="Existing history", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    source_stream.ensure_attached()
    with EventQueue.batch_on_event_callbacks():
        declaration = Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=observer.uuid,
            combat_log=_log(observer, "Before join"),
        )
        declaration.phase_to(EventPhase.COMPLETION)

    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    try:
        context = runtime.bind(_authority(observer), encounter=encounter)
        bootstrap = context.bootstrap()
        assert bootstrap.watermarks.source_event_cursor == EventQueue.event_cursor()
        assert bootstrap.watermarks.observation_cursor == 0
        assert bootstrap.watermarks.combat_log_cursor == 1
        assert bootstrap.combat_log_frames.total == 1
        assert bootstrap.combat_log_frames.frames[0].entry is not None
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def test_batch_world_diff_is_injected_as_typed_patches(
    runtime_scene: RuntimeScene,
) -> None:
    """Every consumed causal batch carries the same-boundary world reduction."""
    subscription = runtime_scene.context.subscribe()
    asyncio.run(subscription.get())
    runtime_scene.observer.name = "Renamed observer"

    Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=runtime_scene.observer.uuid,
    )

    delivery = asyncio.run(subscription.get())
    assert isinstance(delivery, SubjectiveFrameDelivery)
    upserts = [
        patch
        for patch in delivery.frame.patches
        if isinstance(patch, EntityUpsertPatch)
    ]
    assert len(upserts) == 1
    assert upserts[0].entity.name == "Renamed observer"


def test_repeated_bootstrap_reuses_memory_without_leaking_hidden_mutation(
    runtime_scene: RuntimeScene,
) -> None:
    """A request cannot rebuild unseen cells from mutable objective state."""
    first = runtime_scene.context.bootstrap()
    first_tile = next(tile for tile in first.world.state.grid.tiles if (tile.x, tile.y) == (1, 0))
    assert first_tile.visible is True
    original_name = first_tile.name

    runtime_scene.observer.senses.visible[(1, 0)] = False
    hidden_tile = runtime_scene.grid.get_tile(1, 0)
    assert hidden_tile is not None
    hidden_tile.name = "Secret changed terrain"

    repeated = runtime_scene.context.bootstrap()
    remembered = next(
        tile
        for tile in repeated.world.state.grid.tiles
        if (tile.x, tile.y) == (1, 0)
    )
    assert remembered.visible is False
    assert remembered.name == original_name
    assert "Secret changed terrain" not in repeated.model_dump_json()


def test_authority_rotation_closes_stream_and_drops_old_spatial_memory(
    runtime_scene: RuntimeScene,
) -> None:
    """A new perspective epoch cannot resume a prior epoch's journal or memory."""
    old_context = runtime_scene.context
    old_key = old_context.partition_key
    subscription = old_context.subscribe()
    asyncio.run(subscription.get())

    runtime_scene.observer.senses.visible[(1, 0)] = False
    hidden_tile = runtime_scene.grid.get_tile(1, 0)
    assert hidden_tile is not None
    hidden_tile.name = "Changed after authority rotation"
    rotated = _authority(runtime_scene.observer, epoch="perspective-2")
    new_context = runtime_scene.runtime.bind(rotated, encounter=runtime_scene.encounter)

    assert new_context is not old_context
    assert new_context.partition_key != old_key
    assert old_context.healthy is False
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())
    with pytest.raises(SubjectiveJournalIdentityError):
        runtime_scene.runtime.get(old_key)
    assert all(
        (tile.x, tile.y) != (1, 0)
        for tile in new_context.bootstrap().world.state.grid.tiles
    )


def test_generation_reset_retires_context_and_reattaches_in_source_first_order(
    runtime_scene: RuntimeScene,
) -> None:
    """Reset closes stale subscribers and opens only a new generation partition."""
    old_context = runtime_scene.context
    old_key = old_context.partition_key
    subscription = old_context.subscribe()
    asyncio.run(subscription.get())

    EventQueue.reset()
    EventQueue.set_combat_log_callback(runtime_scene.encounter._on_event_combat_log)
    runtime_scene.runtime.ensure_attached()

    assert old_context.healthy is False
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())
    with pytest.raises(SubjectiveJournalIdentityError):
        runtime_scene.runtime.get(old_key)
    with pytest.raises(SubjectiveRuntimeIdentityError):
        old_context.bootstrap()

    new_context = runtime_scene.runtime.bind(
        runtime_scene.authority,
        encounter=runtime_scene.encounter,
    )
    assert new_context.protocol.generation_id == str(EventQueue.generation_id())
    assert new_context.partition_key != old_key


def test_expected_identity_validation_never_falls_back(
    runtime_scene: RuntimeScene,
) -> None:
    with pytest.raises(SubjectiveRuntimeIdentityError):
        runtime_scene.context.validate_identity(expected_generation_id="stale")


def test_transient_initial_projection_failure_can_rebind_without_reusing_bad_state() -> None:
    """A failed provisional open is discarded without tombstoning its identity."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Retry observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
    )
    observer.senses.visible = {(0, 0): True}
    observer.senses.seen = {(0, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    encounter = Encounter(name="Retry encounter", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    source_stream = DndEventStream()
    attempts = 0

    def flaky_grid_provider() -> GridMap:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient grid capture failure")
        return grid

    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=flaky_grid_provider,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    authority = _authority(observer)
    try:
        with pytest.raises(SubjectiveProjectionError, match="transient grid"):
            runtime.bind(authority, encounter=encounter)

        context = runtime.bind(authority, encounter=encounter)
        assert context.healthy is True
        assert context.bootstrap().protocol == context.protocol
        assert attempts >= 2
    finally:
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()
