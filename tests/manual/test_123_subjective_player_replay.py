"""Focused cold replay tests for exact canonical player reducer inputs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import Event, EventQueue, EventType
from dnd.core.gridmap import GridMap, get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from tests.manual.live_replication_support import create_stream_scene, execute_stream_attack
from server.player_replay import (
    PLAYER_REPLAY_CONTRACT_HASH,
    PLAYER_REPLAY_CONTRACT_VERSION,
    SubjectivePlayerReplayArchive,
    SubjectivePlayerReplayBundle,
    SubjectiveReplaySegmentEnd,
    player_replay_contract_summary,
)
from server.player_replay_capture import (
    SubjectiveReplayCaptureError,
    SubjectiveReplayCaptureKey,
    SubjectiveReplayCaptureStore,
)
from server.player_replication.journal import SubjectiveJournalStore
from server.player_replication.journal import (
    SubjectiveFrameProjectionContext,
    SubjectiveProjectionError,
)
from server.player_replication.mapper import CausalEventBatch
from server.player_replication.runtime import CanonicalSubjectiveReplicationRuntime
from server.player_replication_contract import (
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveReplicationFrame,
    SubjectiveSyncDelivery,
)
from server.replication_perspective import PerspectiveEpochRegistry, PerspectiveScope
from server.session import PlayerSession, PlayerType
from server.subjective_authority import (
    ResolvedSubjectiveAuthority,
    resolve_subjective_authority,
)
from server.timeline_contracts import CombatLogProjection


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    yield
    event_stream.stop()
    reset_engine_runtime()


def _authority(
    entity: Entity,
    *,
    epoch: str,
) -> ResolvedSubjectiveAuthority:
    entity_uuid = str(entity.uuid)
    return ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id="replay-session",
            membership_id="replay-membership",
            authority_epoch=1,
            projection=CombatLogProjection.SUBJECTIVE,
            controlled_entity_uuids=(entity_uuid,),
            observer_entity_uuids=(entity_uuid,),
            active_observer_uuid=entity_uuid,
        ),
        perspective_epoch_id=epoch,
    )


async def _read_deliveries(subscription: object, count: int) -> tuple[object, ...]:
    get = getattr(subscription, "get")
    return tuple([await get() for _ in range(count)])


class _FailingFrameProjector:
    def project_frame(
        self,
        source: CausalEventBatch,
        context: SubjectiveFrameProjectionContext,
    ) -> SubjectiveReplicationFrame:
        del source, context
        raise RuntimeError("intentional replay projection failure")


def _record_new_deliveries(
    *,
    context: object,
    subscription: object,
    opening_observation_cursor: int,
    opening_combat_log_cursor: int,
) -> tuple[object, ...]:
    journal = getattr(context, "journal")
    watermarks = journal.watermarks
    count = (
        watermarks.observation_cursor
        - opening_observation_cursor
        + watermarks.combat_log_cursor
        - opening_combat_log_cursor
    )
    deliveries = asyncio.run(_read_deliveries(subscription, count))
    return deliveries


def _completed_bundle() -> SubjectivePlayerReplayBundle:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    try:
        context = runtime.bind(
            _authority(scene.hero, epoch="replay-epoch-1"),
            encounter=scene.encounter,
        )
        opening = context.bootstrap()
        subscription = context.subscribe()
        assert isinstance(asyncio.run(subscription.get()), SubjectiveSyncDelivery)

        hidden_uuid = uuid4()
        EventQueue.push_combat_log(
            CombatLogEntry(
                entry_type=CombatLogEntryType.ACTION,
                source_name="Hidden source",
                source_uuid=str(hidden_uuid),
                compact="Hidden source acts",
                verbose="Hidden source acts",
                detailed="Hidden source acts",
            ),
            hidden_uuid,
        )
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        scene.encounter.end_encounter("subjective replay contract")
        deliveries = _record_new_deliveries(
            context=context,
            subscription=subscription,
            opening_observation_cursor=opening.watermarks.observation_cursor,
            opening_combat_log_cursor=opening.watermarks.combat_log_cursor,
        )
        bundle = capture_store.build_bundle(
            game_id="subjective-replay-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert bundle.segments[0].bootstrap == opening
        assert bundle.segments[0].deliveries == deliveries
        return bundle
    finally:
        runtime.clear_all()
        runtime.stop()


def test_player_replay_round_trips_only_exact_subjective_reducer_inputs() -> None:
    bundle = _completed_bundle()

    restored = SubjectivePlayerReplayBundle.model_validate_json(
        bundle.model_dump_json()
    )
    assert restored == bundle
    assert restored.replay_contract_version == PLAYER_REPLAY_CONTRACT_VERSION
    assert restored.replay_contract_hash == PLAYER_REPLAY_CONTRACT_HASH
    assert player_replay_contract_summary() == {
        "player_replay_contract_version": PLAYER_REPLAY_CONTRACT_VERSION,
        "player_replay_contract_hash": PLAYER_REPLAY_CONTRACT_HASH,
        "player_replication_contract_hash": (
            restored.segments[0]
            .bootstrap.protocol.player_replication_contract_hash
        ),
    }

    segment = restored.segments[0]
    assert segment.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
    assert any(isinstance(value, SubjectiveFrameDelivery) for value in segment.deliveries)
    assert any(
        isinstance(value, SubjectiveCombatLogDelivery)
        for value in segment.deliveries
    )
    assert any(
        isinstance(value, SubjectiveCombatLogDelivery)
        and value.frame.entry is None
        for value in segment.deliveries
    )
    assert segment.through_watermarks.source_event_cursor == (
        restored.terminal_source_event_cursor
    )
    assert segment.through_watermarks.combat_log_cursor == (
        restored.terminal_combat_log_cursor
    )
    serialized = restored.model_dump_json()
    assert '"wire_type"' not in serialized
    assert '"objective"' not in serialized
    assert '"command_result"' not in serialized
    assert '"sync"' not in serialized


def test_player_replay_rejects_objective_logs_and_causal_reordering() -> None:
    bundle = _completed_bundle()
    payload = bundle.model_dump(mode="json")
    deliveries = payload["segments"][0]["deliveries"]
    log_index = next(
        index
        for index, delivery in enumerate(deliveries)
        if delivery["kind"] == "combat_log"
    )
    objective_payload = bundle.model_dump(mode="json")
    objective_payload["segments"][0]["deliveries"][log_index]["frame"][
        "projection"
    ] = "objective"
    with pytest.raises(ValidationError, match="projection"):
        SubjectivePlayerReplayBundle.model_validate(objective_payload)

    frame_index = next(
        index
        for index, delivery in enumerate(deliveries)
        if delivery["kind"] == "frame"
    )
    following_log_index = next(
        index
        for index, delivery in enumerate(deliveries)
        if index > frame_index and delivery["kind"] == "combat_log"
    )
    reordered_payload = bundle.model_dump(mode="json")
    reordered = reordered_payload["segments"][0]["deliveries"]
    reordered[frame_index], reordered[following_log_index] = (
        reordered[following_log_index],
        reordered[frame_index],
    )
    with pytest.raises(ValidationError, match="barrier|contiguous|watermark"):
        SubjectivePlayerReplayBundle.model_validate(reordered_payload)


def test_authority_epoch_rotation_is_preserved_as_an_explicit_bootstrap_reset() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    try:
        first = runtime.bind(
            _authority(scene.hero, epoch="replay-epoch-1"),
            encounter=scene.encounter,
        )
        first_opening = first.bootstrap()
        first_subscription = first.subscribe()
        asyncio.run(first_subscription.get())
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        _record_new_deliveries(
            context=first,
            subscription=first_subscription,
            opening_observation_cursor=first_opening.watermarks.observation_cursor,
            opening_combat_log_cursor=first_opening.watermarks.combat_log_cursor,
        )

        second = runtime.bind(
            _authority(scene.hero, epoch="replay-epoch-2"),
            encounter=scene.encounter,
        )
        second_opening = second.bootstrap()
        second_subscription = second.subscribe()
        asyncio.run(second_subscription.get())
        scene.encounter.end_encounter("rotated subjective replay")
        _record_new_deliveries(
            context=second,
            subscription=second_subscription,
            opening_observation_cursor=second_opening.watermarks.observation_cursor,
            opening_combat_log_cursor=second_opening.watermarks.combat_log_cursor,
        )

        bundle = capture_store.build_bundle(
            game_id="rotated-replay-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert tuple(segment.segment_index for segment in bundle.segments) == (0, 1)
        assert tuple(segment.end_reason for segment in bundle.segments) == (
            SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED,
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
        )
        assert bundle.segments[0].bootstrap.perspective.perspective_epoch_id == (
            "replay-epoch-1"
        )
        assert bundle.segments[1].bootstrap.perspective.perspective_epoch_id == (
            "replay-epoch-2"
        )
        assert bundle.segments[1].bootstrap.watermarks.combat_log_cursor >= (
            bundle.segments[0].through_watermarks.combat_log_cursor
        )
    finally:
        runtime.clear_all()
        runtime.stop()


def test_standalone_player_and_spectator_replays_are_session_scoped() -> None:
    """Independent standalone views freeze as distinct terminal replay bundles."""
    scene = create_stream_scene()
    player_session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.HUMAN,
        name="Standalone player",
        controlled_entities={scene.hero.uuid},
    )
    player_session.synchronize_controlled_observers()
    spectator_session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.OBSERVER,
        name="Standalone spectator",
    )
    spectator_session.configure_subjective_observers(
        {scene.monster.uuid},
        active_observer_uuid=scene.monster.uuid,
    )
    registry = PerspectiveEpochRegistry()
    player_authority = resolve_subjective_authority(
        player_session,
        None,
        allow_standalone=True,
        registry=registry,
    )
    spectator_authority = resolve_subjective_authority(
        spectator_session,
        None,
        allow_standalone=True,
        registry=registry,
    )
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    try:
        player = runtime.bind(player_authority, encounter=scene.encounter)
        spectator = runtime.bind(spectator_authority, encounter=scene.encounter)
        player_bootstrap = player.bootstrap()
        spectator_bootstrap = spectator.bootstrap()

        assert player.partition_key != spectator.partition_key
        assert player_authority.scope.membership_id == (
            f"standalone:{player_session.session_id}"
        )
        assert spectator_authority.scope.membership_id == (
            f"standalone:{spectator_session.session_id}"
        )
        assert (
            player_authority.scope.membership_id
            != spectator_authority.scope.membership_id
        )
        assert player_bootstrap.perspective.kind.value == "controlled_knowledge_union"
        assert spectator_bootstrap.perspective.kind.value == (
            "spectator_knowledge_union"
        )
        assert set(player_bootstrap.world.visibility.root) == {str(scene.hero.uuid)}
        assert set(spectator_bootstrap.world.visibility.root) == {
            str(scene.monster.uuid)
        }
        assert set(player_bootstrap.world.equipment_by_entity) == {
            str(scene.hero.uuid)
        }
        assert spectator_bootstrap.world.equipment_by_entity == {}

        scene.encounter.end_encounter("standalone replay identity regression")
        archive = capture_store.build_archive(
            game_id="standalone-replay-game",
            encounter_uuid=str(scene.encounter.uuid),
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        restored = SubjectivePlayerReplayArchive.model_validate_json(
            archive.model_dump_json()
        )

        assert restored == archive
        assert restored.opened_partition_count == 2
        assert {bundle.membership_id for bundle in restored.membership_replays} == {
            player_authority.scope.membership_id,
            spectator_authority.scope.membership_id,
        }
        replay_by_membership = {
            bundle.membership_id: bundle
            for bundle in restored.membership_replays
        }
        assert (
            replay_by_membership[player_authority.scope.membership_id]
            .segments[-1]
            .runtime_session_id
            == str(player_session.session_id)
        )
        assert (
            replay_by_membership[spectator_authority.scope.membership_id]
            .segments[-1]
            .runtime_session_id
            == str(spectator_session.session_id)
        )
        assert all(
            bundle.segments[-1].end_reason
            is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
            for bundle in restored.membership_replays
        )
    finally:
        runtime.clear_all()
        runtime.stop()


def test_transient_open_failure_creates_no_ghost_replay_segment() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    attempts = 0

    def flaky_grid_provider() -> GridMap:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient replay seed failure")
        return get_map()

    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=flaky_grid_provider,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    authority = _authority(scene.hero, epoch="retry-replay-epoch")
    try:
        with pytest.raises(SubjectiveProjectionError, match="transient replay seed"):
            runtime.bind(authority, encounter=scene.encounter)
        assert capture_store.memberships(encounter_uuid=str(scene.encounter.uuid)) == ()

        context = runtime.bind(authority, encounter=scene.encounter)
        assert context.healthy is True
        scene.encounter.end_encounter("replay retry succeeded")
        bundle = capture_store.build_bundle(
            game_id="retry-replay-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert len(bundle.segments) == 1
        assert bundle.segments[0].segment_index == 0
        assert bundle.segments[0].end_reason is (
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
        )
    finally:
        runtime.clear_all()
        runtime.stop()


def test_terminal_capture_waits_for_every_finalized_nullable_log_slot() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    closed_sources: list[str] = []
    capture_store.add_source_closed_listener(closed_sources.append)
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    try:
        context = runtime.bind(
            _authority(scene.hero, epoch="delayed-terminal-log-epoch"),
            encounter=scene.encounter,
        )
        recorder = capture_store.get(
            SubjectiveReplayCaptureKey(
                source_stream_id=context.protocol.source_stream_id,
                generation_id=context.protocol.generation_id,
                perspective_epoch_id=context.perspective.perspective_epoch_id,
            )
        )
        opening_log_cursor = context.journal.watermarks.combat_log_cursor
        event_stream.remove_finalized_combat_log_source_listener(
            runtime._on_finalized_combat_log_source
        )
        hidden_uuid = uuid4()
        EventQueue.push_combat_log(
            CombatLogEntry(
                entry_type=CombatLogEntryType.ACTION,
                source_name="Delayed hidden source",
                source_uuid=str(hidden_uuid),
                compact="Delayed hidden source acts",
                verbose="Delayed hidden source acts",
                detailed="Delayed hidden source acts",
            ),
            hidden_uuid,
        )
        assert len(scene.encounter.combat_log) == opening_log_cursor + 1
        assert context.journal.watermarks.combat_log_cursor == opening_log_cursor

        scene.encounter.end_encounter("wait for finalized replay log")
        assert recorder.encounter_ended is True
        assert recorder.closed is False
        assert closed_sources == []

        source_window = event_stream.capture_combat_log_source_window(
            scene.encounter,
            from_cursor=opening_log_cursor,
            through_cursor=len(scene.encounter.combat_log),
            expected_generation_id=context.protocol.generation_id,
        )
        for slot in source_window.slots[:-1]:
            context._note_finalized_combat_log(slot)
            assert recorder.closed is False
            assert closed_sources == []
        context._note_finalized_combat_log(source_window.slots[-1])
        assert recorder.closed is True
        assert closed_sources == [str(scene.encounter.uuid)]
        capture_store.close(
            recorder.key,
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
        )
        assert closed_sources == [str(scene.encounter.uuid)]
        bundle = capture_store.build_bundle(
            game_id="delayed-terminal-log-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        final_delivery = bundle.segments[-1].deliveries[-1]
        assert isinstance(final_delivery, SubjectiveCombatLogDelivery)
        assert final_delivery.frame.combat_log_cursor == len(scene.encounter.combat_log)
        delayed_logs = tuple(
            delivery
            for delivery in bundle.segments[-1].deliveries
            if isinstance(delivery, SubjectiveCombatLogDelivery)
            and delivery.frame.combat_log_cursor > opening_log_cursor
        )
        assert any(delivery.frame.entry is None for delivery in delayed_logs)
    finally:
        runtime.clear_all()
        runtime.stop()


def test_failed_live_context_discards_partial_replay_instead_of_publishing_it() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        frame_projector=_FailingFrameProjector(),
        replay_capture_store=capture_store,
    )
    try:
        context = runtime.bind(
            _authority(scene.hero, epoch="failed-replay-epoch"),
            encounter=scene.encounter,
        )
        Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=scene.hero.uuid,
        )
        assert context.healthy is False
        assert capture_store.memberships(encounter_uuid=str(scene.encounter.uuid)) == ()
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="no subjective replay segments",
        ):
            capture_store.build_bundle(
                game_id="failed-replay-game",
                encounter_uuid=str(scene.encounter.uuid),
                membership_id="replay-membership",
                terminal_source_event_cursor=EventQueue.event_cursor(),
                terminal_combat_log_cursor=len(scene.encounter.combat_log),
            )
        with pytest.raises(
            SubjectiveReplayCaptureError,
                match=(
                    "failed and cannot be replayed exactly: causal batch projection "
                    "failed: SubjectiveProjectionError: frame projection failed: "
                    "RuntimeError: intentional replay projection failure"
                ),
            ):
            capture_store.build_archive(
                game_id="failed-replay-game",
                encounter_uuid=str(scene.encounter.uuid),
                terminal_source_event_cursor=EventQueue.event_cursor(),
                terminal_combat_log_cursor=len(scene.encounter.combat_log),
            )
    finally:
        runtime.clear_all()
        runtime.stop()
