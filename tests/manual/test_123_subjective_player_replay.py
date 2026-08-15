"""Focused cold replay tests for exact canonical player reducer inputs."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from collections.abc import Iterator
from typing import Any, Callable, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import Event, EventQueue, EventType
from dnd.core.gridmap import GridMap, get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from tests.manual.live_replication_support import (
    create_stream_scene,
    execute_stream_attack,
    start_stream_encounter,
)
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
    SubjectiveReplayRecorder,
)
from server.player_replication.journal import SubjectiveJournalStore
from server.player_replication.journal import (
    SubjectiveFrameProjectionContext,
    SubjectiveProjectionError,
)
from server.player_replication.mapper import CausalEventBatch
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationRuntime,
    SubjectiveRuntimeIdentityError,
)
from server.player_replication_contract import (
    EncounterReplacePatch,
    EncounterPresentationCue,
    EncounterTransition,
    PresentationDeliveryMode,
    PresentationResetReason,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveReplicationFrame,
    SubjectiveReplicationBootstrap,
    SubjectiveSyncDelivery,
    reset_terminal_authority_id,
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
    session_id: str = "replay-session",
    membership_id: str = "replay-membership",
) -> ResolvedSubjectiveAuthority:
    entity_uuid = str(entity.uuid)
    return ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id=session_id,
            membership_id=membership_id,
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


def _reset_terminal_bundle_payload() -> dict[str, Any]:
    bundle = _completed_bundle()
    payload = bundle.model_dump(mode="python")
    segment = payload["segments"][0]
    deliveries = list(segment["deliveries"])
    segment["deliveries"] = deliveries
    terminal_index = next(
        index
        for index, delivery in enumerate(deliveries)
        if delivery["kind"] == "frame"
        and any(
            cue["kind"] == "encounter" and cue["transition"] == "end"
            for cue in delivery["frame"]["presentation"]
        )
    )
    terminal_delivery = deliveries[terminal_index]
    terminal_frame = terminal_delivery["frame"]
    terminal_cues = tuple(
        cue
        for cue in terminal_frame["presentation"]
        if cue["kind"] == "encounter" and cue["transition"] == "end"
    )
    assert len(terminal_cues) == 1
    assert len(terminal_frame["presentation"]) == 1
    cue = terminal_cues[0]
    ended_patches = tuple(
        patch
        for patch in terminal_frame["patches"]
        if patch["kind"] == "encounter_replace"
        and patch["encounter"] is not None
        and patch["encounter"]["state"] == "ended"
    )
    assert len(ended_patches) == 1
    encounter = ended_patches[0]["encounter"]
    observation_cursor = terminal_frame["watermarks"]["observation_cursor"]
    source_event_uuid = cue["source_event_uuid"]
    terminal_frame["presentation"] = []
    terminal_frame["watermarks"]["presentation_cursor"] -= 1
    terminal_frame["presentation_delivery"] = (
        PresentationDeliveryMode.RESET_REQUIRED.value
    )
    terminal_frame["presentation_reset_reason"] = (
        PresentationResetReason.SOURCE_PRESENTATION_DISCONTINUITY.value
    )
    terminal_frame["encounter_terminal"] = {
        "encounter_uuid": encounter["uuid"],
        "source_event_uuid": source_event_uuid,
        "source_event_cursor": cue["source_event_cursor"],
        "terminal_authority_id": reset_terminal_authority_id(
            terminal_frame["perspective_epoch_id"],
            observation_cursor,
            source_event_uuid,
        ),
        "reason": cue["reason"],
        "projected_combatant_uuids": cue["projected_combatant_uuids"],
        "terminal_barrier": True,
    }
    for delivery in deliveries[terminal_index + 1 :]:
        assert delivery["kind"] == "combat_log"
        delivery["watermarks"]["presentation_cursor"] -= 1
    segment["through_watermarks"]["presentation_cursor"] -= 1
    trailing_watermarks = dict(segment["through_watermarks"])
    trailing_watermarks["combat_log_cursor"] += 1
    deliveries.append(
        {
            "kind": "combat_log",
            "watermarks": trailing_watermarks,
            "frame": {
                "source_stream_id": terminal_frame["source_stream_id"],
                "generation_id": terminal_frame["generation_id"],
                "perspective_epoch_id": terminal_frame["perspective_epoch_id"],
                "projection": "subjective",
                "combat_log_cursor": trailing_watermarks["combat_log_cursor"],
                "event_cursor": cue["source_event_cursor"],
                "entry": None,
            },
        }
    )
    segment["through_watermarks"] = trailing_watermarks
    payload["terminal_combat_log_cursor"] += 1
    return payload


def test_reset_terminal_fact_closes_capture_and_replay_with_trailing_logs() -> None:
    payload = _reset_terminal_bundle_payload()
    bundle = SubjectivePlayerReplayBundle.model_validate(payload)
    segment = bundle.segments[0]
    reset_index = next(
        index
        for index, delivery in enumerate(segment.deliveries)
        if isinstance(delivery, SubjectiveFrameDelivery)
        and delivery.frame.presentation_delivery
        is PresentationDeliveryMode.RESET_REQUIRED
    )
    reset_delivery = segment.deliveries[reset_index]
    assert isinstance(reset_delivery, SubjectiveFrameDelivery)
    fact = reset_delivery.frame.encounter_terminal
    assert fact is not None
    assert reset_delivery.frame.presentation == ()
    assert any(
        isinstance(delivery, SubjectiveCombatLogDelivery)
        for delivery in segment.deliveries[reset_index + 1 :]
    )

    recorder = SubjectiveReplayRecorder(
        segment_index=segment.segment_index,
        membership_id=segment.membership_id,
        runtime_session_id=segment.runtime_session_id,
        bootstrap=segment.bootstrap,
    )
    for delivery in segment.deliveries:
        if isinstance(delivery, SubjectiveFrameDelivery):
            recorder.append_frame(delivery.frame)
        else:
            recorder.append_combat_log(
                delivery.frame,
                watermarks=delivery.watermarks,
            )
    assert recorder.encounter_ended is True
    assert recorder.close(SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED).end_reason is (
        SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
    )
    restored = SubjectivePlayerReplayBundle.model_validate_json(
        bundle.model_dump_json()
    )
    restored_fact = next(
        delivery.frame.encounter_terminal
        for delivery in restored.segments[0].deliveries
        if isinstance(delivery, SubjectiveFrameDelivery)
        and delivery.frame.encounter_terminal is not None
    )
    assert restored_fact == fact


def test_replay_rejects_cross_branch_terminal_delivery_after_reset_fact() -> None:
    payload = _reset_terminal_bundle_payload()
    deliveries = payload["segments"][0]["deliveries"]
    reset_index = next(
        index
        for index, delivery in enumerate(deliveries)
        if delivery["kind"] == "frame"
        and delivery["frame"]["presentation_delivery"]
        == PresentationDeliveryMode.RESET_REQUIRED.value
    )
    reset_frame = deliveries[reset_index]["frame"]
    fact = reset_frame["encounter_terminal"]
    presentation_cursor = reset_frame["watermarks"]["presentation_cursor"]
    duplicate_cue = EncounterPresentationCue(
        presentation_id=f"{fact['source_event_cursor']}:1",
        presentation_cursor=presentation_cursor + 1,
        source_event_uuid=fact["source_event_uuid"],
        source_event_cursor=fact["source_event_cursor"],
        encounter_uuid=fact["encounter_uuid"],
        transition=EncounterTransition.END,
        round_number=0,
        reason=fact["reason"],
        terminal_barrier=True,
        projected_combatant_uuids=tuple(fact["projected_combatant_uuids"]),
    )
    later_watermarks = dict(reset_frame["watermarks"])
    later_watermarks["observation_cursor"] += 1
    later_watermarks["presentation_cursor"] += 1
    later = {
        "kind": "frame",
        "frame": {
            "source_stream_id": reset_frame["source_stream_id"],
            "generation_id": reset_frame["generation_id"],
            "perspective_epoch_id": reset_frame["perspective_epoch_id"],
            "watermarks": later_watermarks,
            "presentation_from_cursor": presentation_cursor,
            "patches": list(reset_frame["patches"]),
            "presentation": [duplicate_cue.model_dump(mode="python")],
        },
    }
    deliveries.insert(reset_index + 1, later)
    for delivery in deliveries[reset_index + 2 :]:
        assert delivery["kind"] == "combat_log"
        delivery["watermarks"]["observation_cursor"] += 1
        delivery["watermarks"]["presentation_cursor"] += 1
    through = payload["segments"][0]["through_watermarks"]
    through["observation_cursor"] += 1
    through["presentation_cursor"] += 1
    with pytest.raises(ValidationError, match="after encounter end"):
        SubjectivePlayerReplayBundle.model_validate(payload)


@pytest.mark.parametrize("terminal_branch", ("cue", "reset_fact"))
def test_terminal_authority_must_be_in_its_new_source_interval(
    terminal_branch: str,
) -> None:
    payload = (
        _completed_bundle().model_dump(mode="python")
        if terminal_branch == "cue"
        else _reset_terminal_bundle_payload()
    )
    segment = payload["segments"][0]
    previous_source = segment["bootstrap"]["watermarks"]["source_event_cursor"]
    for delivery in segment["deliveries"]:
        if delivery["kind"] == "frame":
            frame = delivery["frame"]
            if terminal_branch == "cue":
                terminal_cues = tuple(
                    cue
                    for cue in frame["presentation"]
                    if cue["kind"] == "encounter" and cue["transition"] == "end"
                )
                if terminal_cues:
                    terminal_cues[0]["source_event_cursor"] = previous_source
                    break
            elif frame["encounter_terminal"] is not None:
                frame["encounter_terminal"]["source_event_cursor"] = previous_source
                break
            previous_source = frame["watermarks"]["source_event_cursor"]
        else:
            previous_source = delivery["watermarks"]["source_event_cursor"]
    else:
        raise AssertionError("terminal authority delivery not found")

    with pytest.raises(
        ValidationError,
        match="newly consumed source interval|final source event slot",
    ):
        SubjectivePlayerReplayBundle.model_validate(payload)


def test_replay_rejects_a_fresh_generation_after_the_terminal_generation() -> None:
    bundle = _completed_bundle()
    payload = bundle.model_dump(mode="python")
    terminal = payload["segments"][0]
    successor = deepcopy(terminal)
    successor["segment_index"] = 1
    successor["runtime_session_id"] = "post-terminal-runtime"
    successor["end_reason"] = SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED.value
    successor["deliveries"] = []
    bootstrap = successor["bootstrap"]
    bootstrap["protocol"]["generation_id"] = "post-terminal-generation"
    bootstrap["perspective"]["perspective_epoch_id"] = "post-terminal-epoch"
    bootstrap["combat_log_frames"]["generation_id"] = (
        "post-terminal-generation"
    )
    bootstrap["combat_log_frames"]["perspective_epoch_id"] = (
        "post-terminal-epoch"
    )
    for frame in bootstrap["combat_log_frames"]["frames"]:
        frame["generation_id"] = "post-terminal-generation"
        frame["perspective_epoch_id"] = "post-terminal-epoch"
    successor["through_watermarks"] = deepcopy(bootstrap["watermarks"])
    payload["segments"] = (*payload["segments"], successor)

    with pytest.raises(ValidationError, match="terminal generation"):
        SubjectivePlayerReplayBundle.model_validate(payload)


def test_replay_generations_are_contiguous_while_parallel_siblings_remain_lawful() -> None:
    payload = _completed_bundle().model_dump(mode="python")
    template = payload["segments"][0]

    def identified_segment(
        *,
        generation_id: str,
        perspective_epoch_id: str,
        runtime_session_id: str,
        terminal: bool,
    ) -> dict[str, Any]:
        segment = deepcopy(template)
        segment["runtime_session_id"] = runtime_session_id
        bootstrap = segment["bootstrap"]
        bootstrap["protocol"]["generation_id"] = generation_id
        bootstrap["perspective"]["perspective_epoch_id"] = (
            perspective_epoch_id
        )
        bootstrap["combat_log_frames"]["generation_id"] = generation_id
        bootstrap["combat_log_frames"]["perspective_epoch_id"] = (
            perspective_epoch_id
        )
        for frame in bootstrap["combat_log_frames"]["frames"]:
            frame["generation_id"] = generation_id
            frame["perspective_epoch_id"] = perspective_epoch_id
        for delivery in segment["deliveries"]:
            delivery["frame"]["generation_id"] = generation_id
            delivery["frame"]["perspective_epoch_id"] = perspective_epoch_id
        if not terminal:
            segment["deliveries"] = []
            segment["through_watermarks"] = deepcopy(bootstrap["watermarks"])
            segment["end_reason"] = (
                SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED.value
            )
        return segment

    generation_a = tuple(
        identified_segment(
            generation_id="generation-a",
            perspective_epoch_id=f"generation-a-epoch-{index}",
            runtime_session_id=f"generation-a-runtime-{index}",
            terminal=False,
        )
        for index in range(2)
    )
    generation_b = tuple(
        identified_segment(
            generation_id="generation-b",
            perspective_epoch_id=f"generation-b-epoch-{index}",
            runtime_session_id=f"generation-b-runtime-{index}",
            terminal=True,
        )
        for index in range(2)
    )
    lawful_segments = (*generation_a, *generation_b)
    for index, segment in enumerate(lawful_segments):
        segment["segment_index"] = index
    payload["segments"] = lawful_segments
    assert SubjectivePlayerReplayBundle.model_validate(payload)

    resurrected = deepcopy(payload)
    resurrected_segments = (
        resurrected["segments"][0],
        resurrected["segments"][2],
        resurrected["segments"][1],
        resurrected["segments"][3],
    )
    for index, segment in enumerate(resurrected_segments):
        segment["segment_index"] = index
    resurrected["segments"] = resurrected_segments
    with pytest.raises(ValidationError, match="contiguous segment runs"):
        SubjectivePlayerReplayBundle.model_validate(resurrected)

    for field, value in (
        ("source_event_uuid", str(uuid4())),
        ("reason", "conflicting terminal reason"),
    ):
        conflicting = deepcopy(payload)
        sibling = conflicting["segments"][3]
        terminal_cue = next(
            cue
            for delivery in sibling["deliveries"]
            if delivery["kind"] == "frame"
            for cue in delivery["frame"]["presentation"]
            if cue["kind"] == "encounter" and cue["transition"] == "end"
        )
        terminal_cue[field] = value
        with pytest.raises(ValidationError, match="terminal event identity"):
            SubjectivePlayerReplayBundle.model_validate(conflicting)

    mixed_mode = deepcopy(payload)
    sibling = mixed_mode["segments"][3]
    terminal_delivery = next(
        delivery
        for delivery in sibling["deliveries"]
        if delivery["kind"] == "frame"
        and any(
            cue["kind"] == "encounter" and cue["transition"] == "end"
            for cue in delivery["frame"]["presentation"]
        )
    )
    frame = terminal_delivery["frame"]
    cue = next(
        cue
        for cue in frame["presentation"]
        if cue["kind"] == "encounter" and cue["transition"] == "end"
    )
    frame["presentation"] = []
    frame["watermarks"]["presentation_cursor"] = frame[
        "presentation_from_cursor"
    ]
    frame["presentation_delivery"] = PresentationDeliveryMode.RESET_REQUIRED.value
    frame["presentation_reset_reason"] = (
        PresentationResetReason.SOURCE_PRESENTATION_DISCONTINUITY.value
    )
    frame["encounter_terminal"] = {
        "encounter_uuid": cue["encounter_uuid"],
        "source_event_uuid": cue["source_event_uuid"],
        "source_event_cursor": cue["source_event_cursor"],
        "terminal_authority_id": reset_terminal_authority_id(
            sibling["bootstrap"]["perspective"]["perspective_epoch_id"],
            frame["watermarks"]["observation_cursor"],
            UUID(cue["source_event_uuid"]),
        ),
        "reason": cue["reason"],
        "projected_combatant_uuids": cue["projected_combatant_uuids"],
        "terminal_barrier": True,
    }
    sibling["through_watermarks"] = deepcopy(frame["watermarks"])
    with pytest.raises(ValidationError, match="terminal event identity"):
        SubjectivePlayerReplayBundle.model_validate(mixed_mode)

    for foreign in (
        _completed_bundle().model_dump(mode="python"),
        deepcopy(payload),
    ):
        for segment in foreign["segments"]:
            if segment["end_reason"] != (
                SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED.value
            ):
                continue
            for delivery in segment["deliveries"]:
                if delivery["kind"] != "frame":
                    continue
                terminal_frame = delivery["frame"]
                for terminal_cue in terminal_frame["presentation"]:
                    if (
                        terminal_cue["kind"] == "encounter"
                        and terminal_cue["transition"] == "end"
                    ):
                        terminal_cue["encounter_uuid"] = "foreign-encounter"
                if terminal_frame["encounter_terminal"] is not None:
                    terminal_frame["encounter_terminal"]["encounter_uuid"] = (
                        "foreign-encounter"
                    )
                for patch in terminal_frame["patches"]:
                    if (
                        patch["kind"] == "encounter_replace"
                        and patch["encounter"] is not None
                        and patch["encounter"]["state"] == "ended"
                    ):
                        patch["encounter"]["uuid"] = "foreign-encounter"
        with pytest.raises(ValidationError, match="another encounter"):
            SubjectivePlayerReplayBundle.model_validate(foreign)


@pytest.mark.parametrize("mutation", ("missing_patch", "later_source"))
def test_ordinary_terminal_cue_requires_exact_final_ended_patch_authority(
    mutation: str,
) -> None:
    """Live frame, cold replay, and recorder repeat the same terminal proof."""
    bundle = _completed_bundle()
    segment = bundle.segments[0]
    terminal_index = next(
        index
        for index, delivery in enumerate(segment.deliveries)
        if isinstance(delivery, SubjectiveFrameDelivery)
        and any(
            isinstance(cue, EncounterPresentationCue)
            and cue.transition is EncounterTransition.END
            for cue in delivery.frame.presentation
        )
    )
    terminal_delivery = segment.deliveries[terminal_index]
    assert isinstance(terminal_delivery, SubjectiveFrameDelivery)
    terminal_frame = terminal_delivery.frame
    if mutation == "missing_patch":
        forged_frame = terminal_frame.model_copy(update={"patches": ()})
        error_pattern = "ended encounter patch"
    else:
        forged_frame = terminal_frame.model_copy(
            update={
                "watermarks": terminal_frame.watermarks.model_copy(
                    update={
                        "source_event_cursor": (
                            terminal_frame.watermarks.source_event_cursor + 1
                        )
                    }
                )
            }
        )
        error_pattern = "final source event slot"

    with pytest.raises(ValidationError, match=error_pattern):
        SubjectiveReplicationFrame.model_validate(
            forged_frame.model_dump(mode="python")
        )

    payload = bundle.model_dump(mode="python")
    payload["segments"][0]["deliveries"][terminal_index]["frame"] = (
        forged_frame.model_dump(mode="python")
    )
    with pytest.raises(ValidationError, match=error_pattern):
        SubjectivePlayerReplayBundle.model_validate(payload)

    recorder = SubjectiveReplayRecorder(
        segment_index=segment.segment_index,
        membership_id=segment.membership_id,
        runtime_session_id=segment.runtime_session_id,
        bootstrap=segment.bootstrap,
    )
    for delivery in segment.deliveries[:terminal_index]:
        if isinstance(delivery, SubjectiveFrameDelivery):
            recorder.append_frame(delivery.frame)
        else:
            recorder.append_combat_log(
                delivery.frame,
                watermarks=delivery.watermarks,
            )
    with pytest.raises(SubjectiveReplayCaptureError, match=error_pattern):
        recorder.append_frame(forged_frame)


@pytest.mark.parametrize("terminal_branch", ("ordinary", "reset"))
@pytest.mark.parametrize("override_state", ("active", "null"))
def test_terminal_authority_requires_final_reduced_encounter_to_remain_ended(
    terminal_branch: str,
    override_state: str,
) -> None:
    """Later patches cannot overwrite the ended state authenticated by either branch."""
    bundle = (
        _completed_bundle()
        if terminal_branch == "ordinary"
        else SubjectivePlayerReplayBundle.model_validate(
            _reset_terminal_bundle_payload()
        )
    )
    segment = bundle.segments[0]
    terminal_index = next(
        index
        for index, delivery in enumerate(segment.deliveries)
        if isinstance(delivery, SubjectiveFrameDelivery)
        and (
            delivery.frame.encounter_terminal is not None
            or any(
                isinstance(cue, EncounterPresentationCue)
                and cue.transition is EncounterTransition.END
                for cue in delivery.frame.presentation
            )
        )
    )
    terminal_delivery = segment.deliveries[terminal_index]
    assert isinstance(terminal_delivery, SubjectiveFrameDelivery)
    ended_patch = next(
        patch
        for patch in terminal_delivery.frame.patches
        if isinstance(patch, EncounterReplacePatch)
        and patch.encounter is not None
        and patch.encounter.state == "ended"
    )
    assert ended_patch.encounter is not None
    final_encounter = (
        ended_patch.encounter.model_copy(update={"state": "active"})
        if override_state == "active"
        else None
    )
    forged_frame = terminal_delivery.frame.model_copy(
        update={
            "patches": (
                *terminal_delivery.frame.patches,
                EncounterReplacePatch(encounter=final_encounter),
            )
        }
    )

    payload = bundle.model_dump(mode="python")
    payload["segments"][0]["deliveries"][terminal_index]["frame"] = (
        forged_frame.model_dump(mode="python")
    )
    with pytest.raises(ValidationError, match="final replacement"):
        SubjectivePlayerReplayBundle.model_validate(payload)

    recorder = SubjectiveReplayRecorder(
        segment_index=segment.segment_index,
        membership_id=segment.membership_id,
        runtime_session_id=segment.runtime_session_id,
        bootstrap=segment.bootstrap,
    )
    for delivery in segment.deliveries[:terminal_index]:
        if isinstance(delivery, SubjectiveFrameDelivery):
            recorder.append_frame(delivery.frame)
        else:
            recorder.append_combat_log(
                delivery.frame,
                watermarks=delivery.watermarks,
            )
    with pytest.raises(SubjectiveReplayCaptureError, match="final replacement"):
        recorder.append_frame(forged_frame)


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

    retired = restored.model_dump(mode="python")
    retired["replay_contract_version"] = 1
    with pytest.raises(ValidationError, match="unsupported player replay"):
        SubjectivePlayerReplayBundle.model_validate(retired)


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
        assert bundle.segments[1].bootstrap.watermarks.source_event_cursor >= (
            bundle.segments[0].through_watermarks.source_event_cursor
        )

        first_segment, second_segment = bundle.segments

        def cold_bundle_with_bootstrap(
            next_bootstrap: SubjectiveReplicationBootstrap,
        ) -> SubjectivePlayerReplayBundle:
            candidate = bundle.model_copy(
                update={
                    "segments": (
                    first_segment,
                    second_segment.model_copy(
                        update={"bootstrap": next_bootstrap}
                    ),
                    )
                }
            )
            validate = cast(
                Callable[[], SubjectivePlayerReplayBundle],
                candidate.validate_ended_game_replay,
            )
            return validate()

        def capture_after_first() -> SubjectiveReplayCaptureStore:
            candidate_store = SubjectiveReplayCaptureStore()
            first_recorder = candidate_store.open(
                membership_id=first_segment.membership_id,
                runtime_session_id=first_segment.runtime_session_id,
                bootstrap=first_segment.bootstrap,
            )
            for delivery in first_segment.deliveries:
                if isinstance(delivery, SubjectiveFrameDelivery):
                    first_recorder.append_frame(delivery.frame)
                else:
                    first_recorder.append_combat_log(
                        delivery.frame,
                        watermarks=delivery.watermarks,
                    )
            candidate_store.close(
                first_recorder.key,
                SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED,
            )
            return candidate_store

        second_payload = second_segment.bootstrap.model_dump(mode="python")
        prior_source = first_segment.through_watermarks.source_event_cursor
        assert prior_source > 0
        source_regression = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "watermarks": {
                    **second_payload["watermarks"],
                    "source_event_cursor": prior_source - 1,
                },
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "frames": [
                        {
                            **frame,
                            "event_cursor": min(
                                frame["event_cursor"],
                                prior_source - 1,
                            ),
                        }
                        for frame in second_payload["combat_log_frames"]["frames"]
                    ],
                },
            }
        )
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="source history",
        ):
            capture_after_first().open(
                membership_id=second_segment.membership_id,
                runtime_session_id=first_segment.runtime_session_id,
                bootstrap=source_regression,
            )
        with pytest.raises(ValueError, match="source history"):
            cold_bundle_with_bootstrap(source_regression)

        prior_log = first_segment.through_watermarks.combat_log_cursor
        assert prior_log > 0
        retained_frames = second_payload["combat_log_frames"]["frames"]
        regressed_log = prior_log - 1
        log_regression = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "watermarks": {
                    **second_payload["watermarks"],
                    "combat_log_cursor": regressed_log,
                },
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "through_cursor": regressed_log,
                    "total": regressed_log,
                    "frames": retained_frames[:regressed_log],
                },
            }
        )
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="combat-log history",
        ):
            capture_after_first().open(
                membership_id=second_segment.membership_id,
                runtime_session_id=first_segment.runtime_session_id,
                bootstrap=log_regression,
            )
        with pytest.raises(ValueError, match="combat-log history"):
            cold_bundle_with_bootstrap(log_regression)

        assert retained_frames
        changed_barriers = [
            {
                **frame,
                "event_cursor": max(0, frame["event_cursor"] - 1),
            }
            for frame in retained_frames
        ]
        barrier_regression = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "frames": changed_barriers,
                },
            }
        )
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="canonical event barrier",
        ):
            capture_after_first().open(
                membership_id=second_segment.membership_id,
                runtime_session_id=first_segment.runtime_session_id,
                bootstrap=barrier_regression,
            )
        with pytest.raises(ValueError, match="canonical event barrier"):
            cold_bundle_with_bootstrap(barrier_regression)

        prior_log_rows = {
            frame.combat_log_cursor: frame
            for frame in first_segment.bootstrap.combat_log_frames.frames
        }
        prior_log_rows.update(
            {
                delivery.frame.combat_log_cursor: delivery.frame
                for delivery in first_segment.deliveries
                if isinstance(delivery, SubjectiveCombatLogDelivery)
            }
        )
        prior_frontier = prior_log_rows[max(prior_log_rows)]
        assert prior_frontier.event_cursor > 0
        next_log_cursor = prior_log + 1
        gap_frame = prior_frontier.model_copy(
            update={
                "source_stream_id": (
                    second_segment.bootstrap.protocol.source_stream_id
                ),
                "generation_id": second_segment.bootstrap.protocol.generation_id,
                "perspective_epoch_id": (
                    second_segment.bootstrap.perspective.perspective_epoch_id
                ),
                "combat_log_cursor": next_log_cursor,
                "event_cursor": prior_frontier.event_cursor - 1,
                "entry": None,
            }
        )
        frontier_regression = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "watermarks": {
                    **second_payload["watermarks"],
                    "combat_log_cursor": next_log_cursor,
                },
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "retained_from_cursor": prior_log,
                    "from_cursor": prior_log,
                    "through_cursor": next_log_cursor,
                    "total": next_log_cursor,
                    "frames": [gap_frame.model_dump(mode="python")],
                },
            }
        )
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="across replay segments",
        ):
            capture_after_first().open(
                membership_id=second_segment.membership_id,
                runtime_session_id=first_segment.runtime_session_id,
                bootstrap=frontier_regression,
            )
        with pytest.raises(ValueError, match="across replay segments"):
            cold_bundle_with_bootstrap(frontier_regression)

        empty_retained = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "watermarks": {
                    **second_payload["watermarks"],
                    "combat_log_cursor": prior_log,
                },
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "retained_from_cursor": prior_log,
                    "from_cursor": prior_log,
                    "through_cursor": prior_log,
                    "total": prior_log,
                    "frames": [],
                },
            }
        )
        empty_store = capture_after_first()
        empty_recorder = empty_store.open(
            membership_id=second_segment.membership_id,
            runtime_session_id=first_segment.runtime_session_id,
            bootstrap=empty_retained,
        )
        with pytest.raises(
            SubjectiveReplayCaptureError,
            match="event barriers moved backwards",
        ):
            empty_recorder.append_combat_log(
                gap_frame,
                watermarks=empty_retained.watermarks.model_copy(
                    update={"combat_log_cursor": next_log_cursor}
                ),
            )

        perspective_specific_payload = second_segment.bootstrap.model_validate(
            {
                **second_payload,
                "combat_log_frames": {
                    **second_payload["combat_log_frames"],
                    "frames": [
                        {**frame, "entry": None}
                        for frame in retained_frames
                    ],
                },
            }
        )
        capture_after_first().open(
            membership_id=second_segment.membership_id,
            runtime_session_id=first_segment.runtime_session_id,
            bootstrap=perspective_specific_payload,
        )
        cold_bundle_with_bootstrap(perspective_specific_payload)
    finally:
        runtime.clear_all()
        runtime.stop()


def test_capture_allows_new_generation_cursor_reset_after_closed_segment() -> None:
    bundle = _completed_bundle()
    first_segment = bundle.segments[0]
    assert first_segment.through_watermarks.source_event_cursor > (
        first_segment.bootstrap.watermarks.source_event_cursor
    )
    store = SubjectiveReplayCaptureStore()
    first = store.open(
        membership_id=first_segment.membership_id,
        runtime_session_id=first_segment.runtime_session_id,
        bootstrap=first_segment.bootstrap,
    )
    for delivery in first_segment.deliveries:
        if isinstance(delivery, SubjectiveCombatLogDelivery):
            first.append_combat_log(
                delivery.frame,
                watermarks=delivery.watermarks,
            )
            continue
        if delivery.frame.encounter_terminal is None:
            first.append_frame(delivery.frame)
            break
    closed_first = store.close(
        first.key,
        SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED,
    )

    fresh_generation = "fresh-source-generation"
    fresh_epoch = "fresh-generation-epoch"
    bootstrap_payload = first_segment.bootstrap.model_dump(mode="python")
    next_bootstrap = first_segment.bootstrap.model_validate(
        {
            **bootstrap_payload,
            "protocol": {
                **bootstrap_payload["protocol"],
                "generation_id": fresh_generation,
            },
            "perspective": {
                **bootstrap_payload["perspective"],
                "perspective_epoch_id": fresh_epoch,
            },
            "watermarks": {
                "source_event_cursor": 1,
                "observation_cursor": 0,
                "presentation_cursor": 0,
                "combat_log_cursor": 0,
            },
            "world": {
                **bootstrap_payload["world"],
                "state": {
                    **bootstrap_payload["world"]["state"],
                    "encounter": {
                        **bootstrap_payload["world"]["state"]["encounter"],
                        "state": "ended",
                    },
                },
            },
            "combat_log_frames": {
                **bootstrap_payload["combat_log_frames"],
                "generation_id": fresh_generation,
                "perspective_epoch_id": fresh_epoch,
                "retained_from_cursor": 0,
                "from_cursor": 0,
                "through_cursor": 0,
                "frames": [],
                "total": 0,
            },
        }
    )
    second = store.open(
        membership_id=first_segment.membership_id,
        runtime_session_id=first_segment.runtime_session_id,
        bootstrap=next_bootstrap,
    )
    assert second.segment_index == 1
    assert second.through_watermarks == next_bootstrap.watermarks
    closed_second = store.close(
        second.key,
        SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
    )
    frozen = store.build_bundle(
        game_id="generation-reset-game",
        encounter_uuid=first_segment.bootstrap.protocol.source_stream_id,
        membership_id=first_segment.membership_id,
        terminal_source_event_cursor=1,
        terminal_combat_log_cursor=0,
    )
    assert frozen.segments == (closed_first, closed_second)
    assert closed_first.through_watermarks.source_event_cursor > 1


def test_capture_opens_parallel_perspectives_without_sealing_active_sibling() -> None:
    completed_segment = _completed_bundle().segments[0]
    bootstrap = completed_segment.bootstrap
    store = SubjectiveReplayCaptureStore()
    first = store.open(
        membership_id="parallel-membership",
        runtime_session_id="parallel-session-a",
        bootstrap=bootstrap,
    )
    parallel_epoch = "parallel-perspective-b"
    bootstrap_payload = bootstrap.model_dump(mode="python")
    parallel_bootstrap = bootstrap.model_validate(
        {
            **bootstrap_payload,
            "perspective": {
                **bootstrap_payload["perspective"],
                "perspective_epoch_id": parallel_epoch,
            },
            "combat_log_frames": {
                **bootstrap_payload["combat_log_frames"],
                "perspective_epoch_id": parallel_epoch,
                "frames": [
                    {**frame, "perspective_epoch_id": parallel_epoch}
                    for frame in bootstrap_payload["combat_log_frames"]["frames"]
                ],
            },
        }
    )
    second = store.open(
        membership_id="parallel-membership",
        runtime_session_id="parallel-session-b",
        bootstrap=parallel_bootstrap,
    )

    assert first.closed is False
    assert second.closed is False
    assert (first.segment_index, second.segment_index) == (0, 1)
    assert store.get(first.key) is first
    assert store.get(second.key) is second

    terminal_index = next(
        index
        for index, delivery in enumerate(completed_segment.deliveries)
        if isinstance(delivery, SubjectiveFrameDelivery)
        and (
            delivery.frame.encounter_terminal is not None
            or any(
                isinstance(cue, EncounterPresentationCue)
                and cue.transition is EncounterTransition.END
                for cue in delivery.frame.presentation
            )
        )
    )
    for delivery in completed_segment.deliveries[:terminal_index]:
        if isinstance(delivery, SubjectiveFrameDelivery):
            first.append_frame(delivery.frame)
        else:
            first.append_combat_log(
                delivery.frame,
                watermarks=delivery.watermarks,
            )
    closed_first = store.close(
        first.key,
        SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED,
    )
    assert (
        closed_first.through_watermarks.source_event_cursor
        > parallel_bootstrap.watermarks.source_event_cursor
    )

    for delivery in completed_segment.deliveries:
        if isinstance(delivery, SubjectiveFrameDelivery):
            second.append_frame(
                delivery.frame.model_copy(
                    update={"perspective_epoch_id": parallel_epoch}
                )
            )
        else:
            second.append_combat_log(
                delivery.frame.model_copy(
                    update={"perspective_epoch_id": parallel_epoch}
                ),
                watermarks=delivery.watermarks,
            )
    closed_second = store.close(
        second.key,
        SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
    )
    frozen = store.build_bundle(
        game_id="parallel-replay-game",
        encounter_uuid=bootstrap.protocol.source_stream_id,
        membership_id="parallel-membership",
        terminal_source_event_cursor=(
            closed_second.through_watermarks.source_event_cursor
        ),
        terminal_combat_log_cursor=(
            closed_second.through_watermarks.combat_log_cursor
        ),
    )
    assert frozen.segments == (closed_first, closed_second)
    serialized = frozen.model_dump(mode="python")
    serialized["segments"][1]["runtime_session_id"] = (
        closed_first.runtime_session_id
    )
    with pytest.raises(ValidationError, match="source history"):
        SubjectivePlayerReplayBundle.model_validate(serialized)


def test_parallel_live_perspectives_close_as_exact_terminal_sibling_branches() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        replay_capture_store=capture_store,
    )
    try:
        first = runtime.bind(
            _authority(
                scene.hero,
                epoch="terminal-sibling-a",
                session_id="terminal-session-a",
            ),
            encounter=scene.encounter,
        )
        second = runtime.bind(
            _authority(
                scene.hero,
                epoch="terminal-sibling-b",
                session_id="terminal-session-b",
            ),
            encounter=scene.encounter,
        )
        first_opening = first.bootstrap()
        second_opening = second.bootstrap()
        first_subscription = first.subscribe()
        second_subscription = second.subscribe()
        assert isinstance(
            asyncio.run(first_subscription.get()),
            SubjectiveSyncDelivery,
        )
        assert isinstance(
            asyncio.run(second_subscription.get()),
            SubjectiveSyncDelivery,
        )

        scene.encounter.end_encounter("parallel terminal replay")
        _record_new_deliveries(
            context=first,
            subscription=first_subscription,
            opening_observation_cursor=(
                first_opening.watermarks.observation_cursor
            ),
            opening_combat_log_cursor=(
                first_opening.watermarks.combat_log_cursor
            ),
        )
        _record_new_deliveries(
            context=second,
            subscription=second_subscription,
            opening_observation_cursor=(
                second_opening.watermarks.observation_cursor
            ),
            opening_combat_log_cursor=(
                second_opening.watermarks.combat_log_cursor
            ),
        )

        bundle = capture_store.build_bundle(
            game_id="parallel-terminal-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert tuple(segment.end_reason for segment in bundle.segments) == (
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
        )
        assert {
            segment.runtime_session_id for segment in bundle.segments
        } == {"terminal-session-a", "terminal-session-b"}
        assert all(
            segment.through_watermarks.source_event_cursor
            == bundle.terminal_source_event_cursor
            and segment.through_watermarks.combat_log_cursor
            == bundle.terminal_combat_log_cursor
            for segment in bundle.segments
        )
        assert (
            SubjectivePlayerReplayBundle.model_validate_json(
                bundle.model_dump_json()
            )
            == bundle
        )
    finally:
        runtime.clear_all()
        runtime.stop()


def test_terminal_bootstrap_opens_no_same_or_different_session_capture_successor() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        replay_capture_store=capture_store,
    )
    try:
        first = runtime.bind(
            _authority(
                scene.hero,
                epoch="terminal-successor-a",
                session_id="terminal-successor-session",
            ),
            encounter=scene.encounter,
        )
        opening = first.bootstrap()
        subscription = first.subscribe()
        assert isinstance(asyncio.run(subscription.get()), SubjectiveSyncDelivery)
        scene.encounter.end_encounter("terminal successor capture fence")
        _record_new_deliveries(
            context=first,
            subscription=subscription,
            opening_observation_cursor=opening.watermarks.observation_cursor,
            opening_combat_log_cursor=opening.watermarks.combat_log_cursor,
        )

        successors = (
            runtime.bind(
                _authority(
                    scene.hero,
                    epoch="terminal-successor-b",
                    session_id="terminal-successor-session",
                ),
                encounter=scene.encounter,
            ),
            runtime.bind(
                _authority(
                    scene.hero,
                    epoch="terminal-successor-c",
                    session_id="different-terminal-session",
                ),
                encounter=scene.encounter,
            ),
        )
        for successor in successors:
            encounter_state = successor.bootstrap().world.state.encounter
            assert encounter_state is not None
            assert encounter_state.state == "ended"

        foreign = Encounter(
            name="Foreign post-terminal encounter",
            source_entity_uuid=scene.hero.uuid,
        )
        with pytest.raises(
            SubjectiveRuntimeIdentityError,
            match="runtime subscribed source",
        ):
            runtime.bind(
                _authority(
                    scene.hero,
                    epoch="terminal-successor-foreign",
                    session_id="foreign-terminal-session",
                ),
                encounter=foreign,
            )

        bundle = capture_store.build_bundle(
            game_id="terminal-successor-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert len(bundle.segments) == 1
        assert bundle.segments[0].end_reason is (
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
        )
        assert SubjectivePlayerReplayBundle.model_validate_json(
            bundle.model_dump_json()
        ) == bundle

        runtime.clear_all()
        next_encounter = start_stream_encounter(scene.hero, scene.monster)
        next_context = runtime.bind(
            _authority(
                scene.hero,
                epoch="next-source-epoch",
                session_id="next-source-session",
            ),
            encounter=next_encounter,
        )
        assert next_context.encounter is next_encounter
    finally:
        runtime.clear_all()
        runtime.stop()


def test_lazy_default_runtime_captures_ended_source_before_any_partition_bind() -> None:
    scene = create_stream_scene()
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        replay_capture_store=capture_store,
    )
    try:
        scene.encounter.end_encounter("lazy terminal bootstrap")
        assert Encounter.get_active() is None
        assert event_stream.source_encounter is scene.encounter

        foreign = Encounter(
            name="Foreign lazy terminal encounter",
            source_entity_uuid=scene.hero.uuid,
        )
        with pytest.raises(
            SubjectiveRuntimeIdentityError,
            match="runtime subscribed source",
        ):
            runtime.bind(
                _authority(
                    scene.hero,
                    epoch="lazy-foreign-epoch",
                    session_id="lazy-foreign-session",
                ),
                encounter=foreign,
            )

        context = runtime.bind(
            _authority(
                scene.hero,
                epoch="lazy-terminal-epoch",
                session_id="lazy-terminal-session",
            ),
            encounter=scene.encounter,
        )
        encounter_state = context.bootstrap().world.state.encounter
        assert encounter_state is not None
        assert encounter_state.state == "ended"
        bundle = capture_store.build_bundle(
            game_id="lazy-terminal-game",
            encounter_uuid=str(scene.encounter.uuid),
            membership_id="replay-membership",
            terminal_source_event_cursor=EventQueue.event_cursor(),
            terminal_combat_log_cursor=len(scene.encounter.combat_log),
        )
        assert len(bundle.segments) == 1
        assert bundle.segments[0].deliveries == ()
        assert bundle.segments[0].end_reason is (
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
        )
        assert SubjectivePlayerReplayBundle.model_validate_json(
            bundle.model_dump_json()
        ) == bundle

        runtime.clear_all()
        next_encounter = start_stream_encounter(scene.hero, scene.monster)
        next_context = runtime.bind(
            _authority(
                scene.hero,
                epoch="lazy-next-source-epoch",
                session_id="lazy-next-source-session",
            ),
            encounter=next_encounter,
        )
        assert next_context.encounter is next_encounter
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
        registry=registry,
    )
    spectator_authority = resolve_subjective_authority(
        spectator_session,
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
            f"game:{player_session.session_id}"
        )
        assert spectator_authority.scope.membership_id == (
            f"game:{spectator_session.session_id}"
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
