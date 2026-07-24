"""Focused invariants for the canonical subjective replication journal."""

import asyncio
from threading import Event as ThreadEvent, Thread

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.life_types import LifeState
from server.world_contracts import (
    APIAppearance,
    APIDirectionalBlockMap,
    APIEntitySummary,
    APIEntityVisibility,
    APIEquipmentOverview,
    APIGrid,
    APITile,
    APIVisibilityResponse,
)
from server.player_replication.journal import (
    SubjectiveCombatLogProjectionContext,
    SubjectiveFrameProjectionContext,
    SubjectiveJournalIdentityError,
    SubjectiveJournalInvariantError,
    SubjectiveJournalPartitionKey,
    SubjectiveJournalResyncRequired,
    SubjectiveJournalStore,
    SubjectiveJournalUnhealthyError,
    SubjectiveProjectionError,
    SubjectiveReplicationJournal,
    SubjectiveSubscription,
    SubjectiveSubscriptionClosedError,
    SubjectiveSubscriptionSnapshot,
)
from server.player_replication.combat_log_projection import (
    CanonicalSubjectiveCombatLogProjector,
)
from server.combat_log_source import CombatLogSourceSlot
from server.player_replication_contract import (
    ActiveWeaponSet,
    MovementKind,
    MovementPresentationCue,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    SubjectiveFrameDelivery,
    SubjectiveCombatLogDelivery,
    SubjectiveCombatLogFrame,
    SubjectiveGameState,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
    SubjectiveReplicationFrame,
    SubjectiveSyncDelivery,
    EntityVisualLoadout,
)


def _protocol(*, generation: str = "generation-1") -> PlayerReplicationProtocolIdentity:
    return PlayerReplicationProtocolIdentity(
        source_stream_id="stream-1",
        generation_id=generation,
    )


def _perspective(*, epoch: str = "epoch-1") -> SubjectivePerspective:
    return SubjectivePerspective(
        perspective_epoch_id=epoch,
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=("hero",),
        observer_entity_uuids=("hero",),
        active_observer_uuid="hero",
    )


def _journal(
    *,
    epoch: str = "epoch-1",
    generation: str = "generation-1",
    source_cursor: int = 0,
    observation_retention: int = 16,
    combat_log_retention: int = 16,
) -> SubjectiveReplicationJournal:
    return SubjectiveReplicationJournal(
        protocol=_protocol(generation=generation),
        perspective=_perspective(epoch=epoch),
        initial_source_event_cursor=source_cursor,
        observation_retention=observation_retention,
        combat_log_retention=combat_log_retention,
    )


def _frame(
    *,
    observation: int,
    source: int,
    presentation_from: int = 0,
    presentation_through: int = 0,
    combat_log: int = 0,
    epoch: str = "epoch-1",
    generation: str = "generation-1",
    presentation_id: str | None = None,
) -> SubjectiveReplicationFrame:
    presentation = ()
    if presentation_through > presentation_from:
        assert presentation_through == presentation_from + 1
        presentation = (
            MovementPresentationCue(
                presentation_cursor=presentation_through,
                presentation_id=(
                    presentation_id
                    if presentation_id is not None
                    else f"{epoch}:{observation}:movement"
                ),
                source_event_cursor=source,
                source_event_uuid=f"event-{source}",
                entity_uuid="hero",
                movement_kind=MovementKind.WALK,
                trajectory=((0, 0), (1, 0)),
                path_start_index=0,
                path_total_steps=1,
                perception_commit="observation_frame",
            ),
        )
    return SubjectiveReplicationFrame(
        source_stream_id="stream-1",
        generation_id=generation,
        perspective_epoch_id=epoch,
        watermarks=PlayerReplicationWatermarks(
            source_event_cursor=source,
            observation_cursor=observation,
            presentation_cursor=presentation_through,
            combat_log_cursor=combat_log,
        ),
        presentation_from_cursor=presentation_from,
        patches=(),
        presentation=presentation,
    )


def _entry(label: str) -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Hero",
        source_uuid="hero",
        compact=label,
        verbose=label,
        detailed=label,
    )


def _log_frame(
    cursor: int,
    *,
    event_cursor: int,
    entry: CombatLogEntry | None,
    epoch: str = "epoch-1",
    generation: str = "generation-1",
) -> SubjectiveCombatLogFrame:
    return SubjectiveCombatLogFrame(
        source_stream_id="stream-1",
        generation_id=generation,
        perspective_epoch_id=epoch,
        combat_log_cursor=cursor,
        event_cursor=event_cursor,
        entry=entry,
    )


def _world() -> SubjectiveReplicatedWorld:
    blocks = APIDirectionalBlockMap(
        north=False,
        south=False,
        east=False,
        west=False,
    )
    tile = APITile(
        x=0,
        y=0,
        visual_key="floor.png",
        walkable=True,
        visible=True,
        name="Floor",
        walking_cost=1,
        is_hazardous=False,
        conditions=[],
        light_level=3,
        directional_blocks_movement=blocks,
        directional_blocks_vision=blocks,
        directional_blocks_light=blocks,
        directional_blocks_propagation=blocks,
    )
    entity = APIEntitySummary(
        uuid="hero",
        name="Hero",
        position=(0, 0),
        hp=10,
        max_hp=10,
        ac=13,
        conditions=[],
        condition_details=[],
        life_state=LifeState.ALIVE,
        is_dead=False,
        faction="heroes",
        creature_type="humanoid",
        size="Medium",
        appearance=APIAppearance(
            portrait_key=None,
            presentation_kind="layered",
            visual_scale=1.0,
            placeholder_tint=0xDDAA88,
            body_category="NakedBody",
            skin_tint=0xDDAA88,
            head_category="Head1",
            hair_tint=0,
            has_beard=False,
            beard_tint=0,
        ),
    )
    return SubjectiveReplicatedWorld(
        state=SubjectiveGameState(
            grid=APIGrid(
                min_x=0,
                min_y=0,
                max_x=0,
                max_y=0,
                tiles=[tile],
            ),
            entities=(entity,),
            encounter=None,
            floor_objects=(),
        ),
        visibility=APIVisibilityResponse(
            root={
                "hero": APIEntityVisibility(
                    name="Hero",
                    position=(0, 0),
                    visible_cells=[(0, 0)],
                    visible_entities=["hero"],
                    visible_objects=[],
                    seen_cells=[(0, 0)],
                    sense_modes=[],
                    effective_light_levels={"0,0": 3},
                )
            }
        ),
        equipment_by_entity={
            "hero": APIEquipmentOverview(slots=[], ac=13, inventory=[])
        },
        visual_loadout_by_entity={
            "hero": EntityVisualLoadout(
                entity_uuid="hero",
                active_weapon_set=ActiveWeaponSet.NONE,
                layers=(),
            )
        },
    )


class _FailingFrameProjector:
    def project_frame(
        self,
        source: object,
        context: SubjectiveFrameProjectionContext,
    ) -> SubjectiveReplicationFrame:
        del source, context
        raise RuntimeError("mapper exploded")


async def _next(subscription: SubjectiveSubscription) -> object:
    return await subscription.get()


def test_observation_and_presentation_cursors_are_exact_and_independent() -> None:
    """Empty hidden-source frames advance observation without inventing cues."""
    journal = _journal(source_cursor=4)
    first = journal.append_frame(_frame(observation=1, source=5))
    second = journal.append_frame(
        _frame(
            observation=2,
            source=7,
            presentation_from=0,
            presentation_through=1,
        )
    )

    page = journal.observation_window(from_observation_cursor=0)
    tail = journal.observation_window(from_observation_cursor=1, limit=1)

    assert first.patches == () and first.presentation == ()
    assert first.watermarks.presentation_cursor == 0
    assert second.watermarks.source_event_cursor == 7
    assert [frame.watermarks.observation_cursor for frame in page.frames] == [1, 2]
    assert page.from_watermarks.source_event_cursor == 4
    assert page.through_watermarks == second.watermarks
    assert tail.from_watermarks == first.watermarks
    assert tail.frames == (second,)


def test_canonical_log_projector_keeps_hidden_slots_and_exact_source_barriers() -> None:
    """Subjective filtering changes only the nullable entry, never cursor coordinates."""
    projector = CanonicalSubjectiveCombatLogProjector()
    entry = _entry("Unobserved action")
    entry.source_name = "Hidden actor"
    entry.source_uuid = "hidden-actor"
    entry.perceiver_uuids = {"another-observer"}
    source = CombatLogSourceSlot(
        source_stream_id="stream-1",
        generation_id="generation-1",
        combat_log_cursor=1,
        event_cursor=5,
        entry=entry,
        finalized=True,
        causal_cursor_exact=True,
    )
    context = SubjectiveCombatLogProjectionContext(
        protocol=_protocol(),
        perspective=_perspective(),
        previous_watermarks=PlayerReplicationWatermarks(
            source_event_cursor=5,
            observation_cursor=1,
            presentation_cursor=0,
            combat_log_cursor=0,
        ),
        next_combat_log_cursor=1,
    )

    frame = projector.project_combat_log(source, context)

    assert frame.combat_log_cursor == 1
    assert frame.event_cursor == 5
    assert frame.entry is None


def test_nullable_hidden_combat_log_slots_release_the_exact_source_barrier() -> None:
    """A hidden log still consumes its slot and survives bootstrap/history."""
    journal = _journal(source_cursor=10)
    journal.append_combat_log(_log_frame(1, event_cursor=4, entry=_entry("seen A")))
    hidden = journal.append_combat_log(_log_frame(2, event_cursor=8, entry=None))
    journal.append_combat_log(_log_frame(3, event_cursor=10, entry=_entry("seen C")))

    page = journal.combat_log_window(from_combat_log_cursor=0)
    bootstrap = journal.bootstrap(_world())

    assert [frame.entry is None for frame in page.frames] == [False, True, False]
    assert hidden.event_cursor == 8
    assert page.through_cursor == 3
    assert bootstrap.watermarks.combat_log_cursor == 3
    assert bootstrap.combat_log_frames.frames[1].entry is None
    assert bootstrap.combat_log_frames.frames[1].event_cursor == 8


def test_retention_preserves_the_consumed_boundary_or_requires_resync() -> None:
    """Bounded rollover never returns a partial observation or log page."""
    journal = _journal(
        source_cursor=0,
        observation_retention=2,
        combat_log_retention=2,
    )
    for cursor in range(1, 5):
        journal.append_frame(
            _frame(
                observation=cursor,
                source=cursor,
                combat_log=cursor - 1,
            )
        )
        journal.append_combat_log(
            _log_frame(cursor, event_cursor=cursor, entry=None)
        )

    assert journal.retained_from_observation_cursor == 2
    assert journal.retained_from_combat_log_cursor == 2
    observation_page = journal.observation_window(from_observation_cursor=2)
    log_page = journal.combat_log_window(from_combat_log_cursor=2)
    assert [frame.watermarks.observation_cursor for frame in observation_page.frames] == [3, 4]
    assert [frame.combat_log_cursor for frame in log_page.frames] == [3, 4]

    with pytest.raises(SubjectiveJournalResyncRequired):
        journal.observation_window(from_observation_cursor=1)
    with pytest.raises(SubjectiveJournalResyncRequired):
        journal.combat_log_window(from_combat_log_cursor=1)


def test_store_never_falls_back_across_generation_or_perspective_epoch() -> None:
    """The same source has distinct generation-and-authority cursor domains."""
    store = SubjectiveJournalStore()
    first = store.open(protocol=_protocol(), perspective=_perspective(epoch="epoch-a"))
    second = store.open(protocol=_protocol(), perspective=_perspective(epoch="epoch-b"))
    next_generation = store.open(
        protocol=_protocol(generation="generation-2"),
        perspective=_perspective(epoch="epoch-a"),
    )
    first.append_frame(_frame(observation=1, source=1, epoch="epoch-a"))

    assert second.watermarks.observation_cursor == 0
    assert next_generation.watermarks.observation_cursor == 0
    assert store.get(first.partition_key) is first
    with pytest.raises(SubjectiveJournalIdentityError):
        store.get(
            SubjectiveJournalPartitionKey(
                source_stream_id="stream-1",
                generation_id="generation-missing",
                perspective_epoch_id="epoch-a",
            )
        )

    conflicting_authority = SubjectivePerspective(
        perspective_epoch_id="epoch-a",
        kind=PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION,
        controlled_entity_uuids=(),
        observer_entity_uuids=("spectator",),
        active_observer_uuid="spectator",
    )
    with pytest.raises(SubjectiveJournalIdentityError, match="reused"):
        store.open(protocol=_protocol(), perspective=conflicting_authority)

    key = second.partition_key
    store.retire(key)
    with pytest.raises(SubjectiveJournalUnhealthyError):
        second.append_frame(_frame(observation=1, source=1, epoch="epoch-b"))
    with pytest.raises(SubjectiveJournalIdentityError, match="cannot be reused"):
        store.open(protocol=_protocol(), perspective=_perspective(epoch="epoch-b"))


def test_store_clear_all_closes_subscribers_and_releases_retired_identities() -> None:
    """A process reset closes live streams and permits clean identity reuse."""
    store = SubjectiveJournalStore()
    retired = store.open(
        protocol=_protocol(),
        perspective=_perspective(epoch="epoch-retired"),
    )
    retired_subscription = retired.subscribe()
    assert isinstance(
        asyncio.run(_next(retired_subscription)),
        SubjectiveSyncDelivery,
    )
    store.retire(retired.partition_key)
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(_next(retired_subscription))
    with pytest.raises(SubjectiveJournalIdentityError, match="cannot be reused"):
        store.open(
            protocol=_protocol(),
            perspective=_perspective(epoch="epoch-retired"),
        )

    active = store.open(
        protocol=_protocol(),
        perspective=_perspective(epoch="epoch-active"),
    )
    active_subscription = active.subscribe()
    assert isinstance(
        asyncio.run(_next(active_subscription)),
        SubjectiveSyncDelivery,
    )

    store.clear_all()

    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(_next(active_subscription))
    reopened_retired = store.open(
        protocol=_protocol(),
        perspective=_perspective(epoch="epoch-retired"),
    )
    reopened_active = store.open(
        protocol=_protocol(),
        perspective=_perspective(epoch="epoch-active"),
    )
    assert reopened_retired.partition_key == retired.partition_key
    assert reopened_active.partition_key == active.partition_key


def test_projection_failure_marks_partition_unhealthy_and_terminates_subscribers() -> None:
    """A mapper exception cannot leave a stream running across a missing frame."""
    journal = _journal()
    subscription = journal.subscribe()

    with pytest.raises(SubjectiveProjectionError, match="mapper exploded"):
        journal.project_and_append_frame(object(), _FailingFrameProjector())

    assert journal.healthy is False
    assert journal.watermarks.observation_cursor == 0
    with pytest.raises(SubjectiveJournalUnhealthyError):
        journal.observation_window(from_observation_cursor=0)
    with pytest.raises(SubjectiveSubscriptionClosedError) as closed:
        asyncio.run(_next(subscription))
    assert closed.value.resync_required is True


def test_invalid_contiguity_fails_closed_instead_of_publishing_a_gap() -> None:
    """A producer cursor gap poisons only its exact journal partition."""
    journal = _journal()

    with pytest.raises(SubjectiveJournalInvariantError, match="exactly one"):
        journal.append_frame(_frame(observation=2, source=2))

    assert journal.watermarks.observation_cursor == 0
    with pytest.raises(SubjectiveJournalUnhealthyError):
        journal.sync_delivery()


def test_presentation_id_cannot_be_reused_by_a_later_frame() -> None:
    """A cue identity denotes exactly one cue across the whole partition."""
    journal = _journal()
    first = journal.append_frame(
        _frame(
            observation=1,
            source=1,
            presentation_from=0,
            presentation_through=1,
            presentation_id="stable-cue-id",
        )
    )

    with pytest.raises(SubjectiveJournalInvariantError, match="already accepted"):
        journal.append_frame(
            _frame(
                observation=2,
                source=2,
                presentation_from=1,
                presentation_through=2,
                presentation_id="stable-cue-id",
            )
        )

    assert journal.watermarks == first.watermarks
    assert journal.retained_from_observation_cursor == 0
    assert journal.healthy is False


def test_evicted_presentation_id_remains_reserved_for_the_live_partition() -> None:
    """Observation retention never weakens the partition-wide identity invariant."""
    journal = _journal(observation_retention=1)
    journal.append_frame(
        _frame(
            observation=1,
            source=1,
            presentation_from=0,
            presentation_through=1,
            presentation_id="evicted-cue-id",
        )
    )
    retained = journal.append_frame(
        _frame(
            observation=2,
            source=2,
            presentation_from=1,
            presentation_through=2,
            presentation_id="retained-cue-id",
        )
    )

    assert journal.retained_from_observation_cursor == 1
    with pytest.raises(SubjectiveJournalInvariantError, match="evicted-cue-id"):
        journal.append_frame(
            _frame(
                observation=3,
                source=3,
                presentation_from=2,
                presentation_through=3,
                presentation_id="evicted-cue-id",
            )
        )

    assert journal.watermarks == retained.watermarks
    assert journal.retained_from_observation_cursor == 1
    assert journal.healthy is False


def test_reused_presentation_id_is_never_partially_fanned_out() -> None:
    """The duplicate frame commits nowhere before fail-closed termination."""
    journal = _journal()
    journal.append_frame(
        _frame(
            observation=1,
            source=1,
            presentation_from=0,
            presentation_through=1,
            presentation_id="already-delivered-cue",
        )
    )
    subscription = journal.subscribe()
    sync = asyncio.run(_next(subscription))
    assert isinstance(sync, SubjectiveSyncDelivery)

    with pytest.raises(SubjectiveJournalInvariantError, match="already accepted"):
        journal.append_frame(
            _frame(
                observation=2,
                source=2,
                presentation_from=1,
                presentation_through=2,
                presentation_id="already-delivered-cue",
            )
        )

    assert journal.watermarks == sync.watermarks
    with pytest.raises(SubjectiveSubscriptionClosedError) as closed:
        asyncio.run(_next(subscription))
    assert closed.value.resync_required is True


def test_multiple_subscribers_receive_one_frozen_canonical_delivery() -> None:
    """Fanout reuses the validated immutable DTO without per-client mutation."""
    journal = _journal()
    first = journal.subscribe()
    second = journal.subscribe()

    first_sync = asyncio.run(_next(first))
    second_sync = asyncio.run(_next(second))
    assert isinstance(first_sync, SubjectiveSyncDelivery)
    assert isinstance(second_sync, SubjectiveSyncDelivery)

    journal.append_frame(_frame(observation=1, source=1))
    first_delivery = asyncio.run(_next(first))
    second_delivery = asyncio.run(_next(second))

    assert isinstance(first_delivery, SubjectiveFrameDelivery)
    assert first_delivery is second_delivery
    with pytest.raises(ValidationError, match="frozen"):
        first_delivery.kind = "frame"


def test_combat_log_cannot_outrun_the_consumed_source_event_watermark() -> None:
    """Sparse source delivery must publish an empty observation frame first."""
    journal = _journal(source_cursor=3)

    with pytest.raises(SubjectiveJournalInvariantError, match="barrier exceeds"):
        journal.append_combat_log(_log_frame(1, event_cursor=4, entry=None))

    assert journal.watermarks.combat_log_cursor == 0
    assert journal.healthy is False


def test_subscribe_backfill_barrier_is_atomic_against_concurrent_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backfill ends at queued sync B and every later commit remains live-only."""
    journal = _journal()
    journal.append_frame(_frame(observation=1, source=1))
    journal.append_combat_log(_log_frame(1, event_cursor=1, entry=_entry("log 1")))

    entered_backfill = ThreadEvent()
    release_backfill = ThreadEvent()
    append_started = ThreadEvent()
    original_observation_window = getattr(journal, "_observation_window")

    def blocking_observation_window(
        *,
        from_observation_cursor: int,
        limit: int | None = None,
    ):
        entered_backfill.set()
        assert release_backfill.wait(timeout=5)
        return original_observation_window(
            from_observation_cursor=from_observation_cursor,
            limit=limit,
        )

    monkeypatch.setattr(
        journal,
        "_observation_window",
        blocking_observation_window,
    )
    snapshots: list[SubjectiveSubscriptionSnapshot] = []
    errors: list[BaseException] = []

    def capture_subscription() -> None:
        try:
            snapshots.append(
                journal.subscribe_with_backfill(
                    from_observation_cursor=0,
                    from_combat_log_cursor=0,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    def append_after_barrier() -> None:
        append_started.set()
        try:
            journal.append_frame(
                _frame(observation=2, source=2, combat_log=1)
            )
            journal.append_combat_log(
                _log_frame(2, event_cursor=2, entry=_entry("log 2"))
            )
        except BaseException as exc:
            errors.append(exc)

    subscribe_thread = Thread(target=capture_subscription)
    subscribe_thread.start()
    assert entered_backfill.wait(timeout=5)
    append_thread = Thread(target=append_after_barrier)
    append_thread.start()
    assert append_started.wait(timeout=5)
    release_backfill.set()
    subscribe_thread.join(timeout=5)
    append_thread.join(timeout=5)

    assert not subscribe_thread.is_alive()
    assert not append_thread.is_alive()
    assert errors == []
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.sync.watermarks == PlayerReplicationWatermarks(
        source_event_cursor=1,
        observation_cursor=1,
        presentation_cursor=0,
        combat_log_cursor=1,
    )
    assert [
        frame.watermarks.observation_cursor
        for frame in snapshot.observation_backfill.frames
    ] == [1]
    assert snapshot.observation_backfill.captured_watermarks == snapshot.sync.watermarks
    assert [
        frame.combat_log_cursor for frame in snapshot.combat_log_backfill.frames
    ] == [1]
    assert snapshot.combat_log_backfill.total == 1

    queued_sync = asyncio.run(_next(snapshot.subscription))
    queued_frame = asyncio.run(_next(snapshot.subscription))
    queued_log = asyncio.run(_next(snapshot.subscription))
    assert queued_sync == snapshot.sync
    assert isinstance(queued_frame, SubjectiveFrameDelivery)
    assert queued_frame.frame.watermarks.observation_cursor == 2
    assert isinstance(queued_log, SubjectiveCombatLogDelivery)
    assert queued_log.frame.combat_log_cursor == 2


def test_subscribe_backfill_preserves_exact_cross_channel_delivery_order() -> None:
    """Reconnect catch-up retains the watermarks seen at each original commit."""

    journal = _journal()
    journal.append_frame(_frame(observation=1, source=1))
    journal.append_combat_log(_log_frame(1, event_cursor=1, entry=_entry("log 1")))
    journal.append_frame(_frame(observation=2, source=2, combat_log=1))
    journal.append_combat_log(_log_frame(2, event_cursor=2, entry=_entry("log 2")))

    snapshot = journal.subscribe_with_backfill(
        from_observation_cursor=0,
        from_combat_log_cursor=0,
    )

    assert [delivery.kind for delivery in snapshot.backfill_deliveries] == [
        "frame",
        "combat_log",
        "frame",
        "combat_log",
    ]
    assert [
        delivery.frame.watermarks.observation_cursor
        if isinstance(delivery, SubjectiveFrameDelivery)
        else delivery.watermarks.observation_cursor
        for delivery in snapshot.backfill_deliveries
    ] == [1, 1, 2, 2]
    assert [
        delivery.frame.watermarks.combat_log_cursor
        if isinstance(delivery, SubjectiveFrameDelivery)
        else delivery.watermarks.combat_log_cursor
        for delivery in snapshot.backfill_deliveries
    ] == [0, 1, 1, 2]
