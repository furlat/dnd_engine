"""Cold player replay made only from canonical subjective reducer inputs.

Unlike objective replay, a player replay is never reconstructed from engine
events after the game.  Each segment is the exact bootstrap reset delivered
for one authority epoch followed by the canonical frame and combat-log
deliveries accepted by that epoch's live journal.  Perspective rotation starts
a new segment instead of merging knowledge across authority boundaries.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Annotated, Final, Tuple, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from server.player_replication_contract import (
    EncounterPresentationCue,
    EncounterTransition,
    PLAYER_REPLICATION_CONTRACT_HASH,
    PlayerReplicationWatermarks,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveReplicationBootstrap,
)


PLAYER_REPLAY_CONTRACT_VERSION: Final[int] = 1
PLAYER_REPLAY_CONTRACT_HASH: Final[str]


class PlayerReplayModel(BaseModel):
    """Immutable, closed base for durable player replay values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SubjectiveReplaySegmentEnd(str, Enum):
    """Why the live reducer stopped consuming one perspective epoch."""

    PERSPECTIVE_RETIRED = "perspective_retired"
    ENCOUNTER_ENDED = "encounter_ended"


SubjectiveReplayDelivery: TypeAlias = Annotated[
    Union[SubjectiveFrameDelivery, SubjectiveCombatLogDelivery],
    Field(discriminator="kind"),
]
_SUBJECTIVE_REPLAY_DELIVERY_ADAPTER: Final[TypeAdapter[SubjectiveReplayDelivery]] = (
    TypeAdapter(SubjectiveReplayDelivery)
)


def subjective_bootstrap_encounter_ended(
    bootstrap: SubjectiveReplicationBootstrap,
) -> bool:
    """Return whether one canonical replay seed is already terminal."""
    encounter = bootstrap.world.state.encounter
    return encounter is not None and encounter.state == "ended"


class SubjectiveReplaySegment(PlayerReplayModel):
    """Exact reducer input stream for one generation-and-perspective epoch."""

    segment_index: int = Field(
        ge=0,
        description="Contiguous membership-local reset-segment index.",
    )
    membership_id: str = Field(
        min_length=1,
        description="Durable hosted membership, or the explicit standalone identity.",
    )
    runtime_session_id: str = Field(
        min_length=1,
        description="Worker session that consumed this exact perspective epoch.",
    )
    bootstrap: SubjectiveReplicationBootstrap = Field(
        description="Exact atomic world/log reducer reset used at segment opening.",
    )
    deliveries: Tuple[SubjectiveReplayDelivery, ...] = Field(
        default_factory=tuple,
        description=(
            "Canonical frame and nullable combat-log deliveries in original live order; "
            "sync and command receipts are deliberately excluded."
        ),
    )
    through_watermarks: PlayerReplicationWatermarks = Field(
        description="Exact independent reducer boundaries after the last delivery.",
    )
    end_reason: SubjectiveReplaySegmentEnd

    @model_validator(mode="after")
    def validate_exact_reducer_stream(self) -> "SubjectiveReplaySegment":
        protocol = self.bootstrap.protocol
        perspective = self.bootstrap.perspective
        previous = self.bootstrap.watermarks
        presentation_ids: set[str] = set()
        encounter_end_seen = subjective_bootstrap_encounter_ended(
            self.bootstrap,
        )

        for delivery in self.deliveries:
            if isinstance(delivery, SubjectiveFrameDelivery):
                frame = delivery.frame
                if encounter_end_seen:
                    raise ValueError(
                        "a replay segment cannot contain an observation frame after encounter end"
                    )
                if (
                    frame.source_stream_id != protocol.source_stream_id
                    or frame.generation_id != protocol.generation_id
                    or frame.perspective_epoch_id != perspective.perspective_epoch_id
                ):
                    raise ValueError("replay observation frame identity does not match bootstrap")
                if frame.watermarks.observation_cursor != previous.observation_cursor + 1:
                    raise ValueError("replay observation frames must be contiguous")
                if frame.presentation_from_cursor != previous.presentation_cursor:
                    raise ValueError("replay presentation windows must be contiguous")
                if frame.watermarks.combat_log_cursor != previous.combat_log_cursor:
                    raise ValueError(
                        "replay observation frame cannot advance the combat-log cursor"
                    )
                if not frame.watermarks.dominates(previous):
                    raise ValueError("replay observation watermarks moved backwards")
                frame_ids = {cue.presentation_id for cue in frame.presentation}
                if presentation_ids & frame_ids:
                    raise ValueError(
                        "presentation IDs must remain unique across the replay segment"
                    )
                presentation_ids.update(frame_ids)
                terminal_cues = tuple(
                    cue
                    for cue in frame.presentation
                    if isinstance(cue, EncounterPresentationCue)
                    and cue.transition is EncounterTransition.END
                )
                if len(terminal_cues) > 1:
                    raise ValueError("one replay frame cannot end the encounter twice")
                if terminal_cues:
                    encounter_end_seen = True
                previous = frame.watermarks
                continue

            frame = delivery.frame
            if (
                frame.source_stream_id != protocol.source_stream_id
                or frame.generation_id != protocol.generation_id
                or frame.perspective_epoch_id != perspective.perspective_epoch_id
            ):
                raise ValueError("replay combat-log frame identity does not match bootstrap")
            if frame.combat_log_cursor != previous.combat_log_cursor + 1:
                raise ValueError("replay combat-log frames must be contiguous")
            if frame.event_cursor > previous.source_event_cursor:
                raise ValueError("replay combat-log barrier exceeds consumed source events")
            expected = previous.model_copy(
                update={"combat_log_cursor": frame.combat_log_cursor}
            )
            if delivery.watermarks != expected:
                raise ValueError(
                    "replay combat-log delivery watermarks do not match its exact slot"
                )
            previous = delivery.watermarks

        if previous != self.through_watermarks:
            raise ValueError("replay through watermarks do not match the delivery stream")
        if self.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED:
            if not encounter_end_seen:
                raise ValueError(
                    "encounter-ended replay segment requires a terminal bootstrap or cue"
                )
        elif encounter_end_seen:
            raise ValueError(
                "a segment containing encounter end cannot be labeled perspective-retired"
            )
        return self

class SubjectivePlayerReplayBundle(PlayerReplayModel):
    """All exact live reducer segments retained for one game membership."""

    replay_contract_version: int = Field(
        default=PLAYER_REPLAY_CONTRACT_VERSION,
        ge=1,
    )
    replay_contract_hash: str = Field(
        default_factory=lambda: PLAYER_REPLAY_CONTRACT_HASH,
        min_length=1,
    )
    game_id: str = Field(min_length=1)
    encounter_uuid: str = Field(min_length=1)
    membership_id: str = Field(min_length=1)
    terminal_source_event_cursor: int = Field(ge=1)
    terminal_combat_log_cursor: int = Field(ge=0)
    segments: Tuple[SubjectiveReplaySegment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ended_game_replay(self) -> "SubjectivePlayerReplayBundle":
        if self.replay_contract_version != PLAYER_REPLAY_CONTRACT_VERSION:
            raise ValueError("unsupported player replay contract version")
        if self.replay_contract_hash != PLAYER_REPLAY_CONTRACT_HASH:
            raise ValueError("player replay contract hash mismatch")

        expected_indices = tuple(range(len(self.segments)))
        if tuple(segment.segment_index for segment in self.segments) != expected_indices:
            raise ValueError("player replay segments must be contiguous and ordered")

        partition_ids: set[tuple[str, str]] = set()
        ended_indices: list[int] = []
        previous_opening_source_cursor = -1
        for segment in self.segments:
            bootstrap = segment.bootstrap
            protocol = bootstrap.protocol
            perspective = bootstrap.perspective
            if segment.membership_id != self.membership_id:
                raise ValueError("replay segment belongs to another membership")
            if protocol.source_stream_id != self.encounter_uuid:
                raise ValueError("replay segment belongs to another encounter stream")
            encounter = bootstrap.world.state.encounter
            if encounter is None or encounter.uuid != self.encounter_uuid:
                raise ValueError("replay bootstrap does not describe the declared encounter")
            partition_id = (
                protocol.generation_id,
                perspective.perspective_epoch_id,
            )
            if partition_id in partition_ids:
                raise ValueError("replay cannot repeat a generation-and-perspective partition")
            partition_ids.add(partition_id)
            opening_cursor = bootstrap.watermarks.source_event_cursor
            if opening_cursor < previous_opening_source_cursor:
                raise ValueError("replay segment openings must not move backwards")
            previous_opening_source_cursor = opening_cursor
            if segment.through_watermarks.source_event_cursor > self.terminal_source_event_cursor:
                raise ValueError("replay segment exceeds the terminal source cursor")
            if segment.through_watermarks.combat_log_cursor > self.terminal_combat_log_cursor:
                raise ValueError("replay segment exceeds the terminal combat-log cursor")
            if segment.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED:
                ended_indices.append(segment.segment_index)

        if len(ended_indices) != 1:
            raise ValueError(
                "ended-game player replay requires exactly one encounter-ended segment"
            )
        if ended_indices[0] != len(self.segments) - 1:
            raise ValueError("encounter end must terminate the final replay segment")
        terminal = self.segments[-1].through_watermarks
        if terminal.source_event_cursor != self.terminal_source_event_cursor:
            raise ValueError("terminal replay segment source cursor is incomplete")
        if terminal.combat_log_cursor != self.terminal_combat_log_cursor:
            raise ValueError("terminal replay segment combat-log cursor is incomplete")
        return self


class SubjectivePlayerReplayArchive(PlayerReplayModel):
    """One immutable ended-game artifact containing every recorded membership."""

    replay_contract_version: int = Field(
        default=PLAYER_REPLAY_CONTRACT_VERSION,
        ge=1,
    )
    replay_contract_hash: str = Field(
        default_factory=lambda: PLAYER_REPLAY_CONTRACT_HASH,
        min_length=1,
    )
    game_id: str = Field(min_length=1)
    encounter_uuid: str = Field(min_length=1)
    terminal_source_event_cursor: int = Field(ge=1)
    terminal_combat_log_cursor: int = Field(ge=0)
    opened_partition_count: int = Field(
        ge=0,
        description="Canonical player partitions successfully opened during play.",
    )
    membership_replays: Tuple[SubjectivePlayerReplayBundle, ...] = Field(
        default_factory=tuple,
    )

    @model_validator(mode="after")
    def validate_complete_membership_archive(self) -> "SubjectivePlayerReplayArchive":
        if self.replay_contract_version != PLAYER_REPLAY_CONTRACT_VERSION:
            raise ValueError("unsupported player replay contract version")
        if self.replay_contract_hash != PLAYER_REPLAY_CONTRACT_HASH:
            raise ValueError("player replay contract hash mismatch")
        if self.opened_partition_count == 0:
            if self.membership_replays:
                raise ValueError(
                    "archive cannot contain replay bundles when no partition opened"
                )
            return self
        if not self.membership_replays:
            raise ValueError(
                "opened canonical player partitions require durable replay bundles"
            )

        membership_ids = tuple(
            bundle.membership_id for bundle in self.membership_replays
        )
        if membership_ids != tuple(sorted(membership_ids)):
            raise ValueError("membership replay bundles must use stable sorted order")
        if len(membership_ids) != len(set(membership_ids)):
            raise ValueError("membership replay bundles must be unique")
        segment_count = 0
        for bundle in self.membership_replays:
            if bundle.game_id != self.game_id:
                raise ValueError("membership replay belongs to another game")
            if bundle.encounter_uuid != self.encounter_uuid:
                raise ValueError("membership replay belongs to another encounter")
            if bundle.terminal_source_event_cursor != self.terminal_source_event_cursor:
                raise ValueError("membership replay terminal source cursor disagrees")
            if bundle.terminal_combat_log_cursor != self.terminal_combat_log_cursor:
                raise ValueError("membership replay terminal combat-log cursor disagrees")
            segment_count += len(bundle.segments)
        if segment_count != self.opened_partition_count:
            raise ValueError(
                "archive must retain one replay segment for every opened partition"
            )
        return self


def player_replay_wire_schema() -> dict[str, object]:
    """Return the complete transitive durable player-replay schema."""

    return {
        "contract_version": PLAYER_REPLAY_CONTRACT_VERSION,
        "player_replication_contract_hash": PLAYER_REPLICATION_CONTRACT_HASH,
        "semantics": {
            "source": "recorded canonical subjective reducer inputs",
            "raw_events": "forbidden",
            "objective_state": "forbidden",
            "segment_reset": "exact SubjectiveReplicationBootstrap",
            "delivery_order": "original frame/combat-log journal commit order",
            "excluded": ("sync", "command_result"),
        },
        "bundle": SubjectivePlayerReplayBundle.model_json_schema(
            mode="serialization"
        ),
        "archive": SubjectivePlayerReplayArchive.model_json_schema(
            mode="serialization"
        ),
        "delivery": _SUBJECTIVE_REPLAY_DELIVERY_ADAPTER.json_schema(
            mode="serialization"
        ),
    }


PLAYER_REPLAY_CONTRACT_HASH = hashlib.sha256(
    json.dumps(
        player_replay_wire_schema(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def player_replay_contract_summary() -> dict[str, object]:
    """Return the durable player replay decoder identity."""

    return {
        "player_replay_contract_version": PLAYER_REPLAY_CONTRACT_VERSION,
        "player_replay_contract_hash": PLAYER_REPLAY_CONTRACT_HASH,
        "player_replication_contract_hash": PLAYER_REPLICATION_CONTRACT_HASH,
    }


__all__ = [
    "PLAYER_REPLAY_CONTRACT_HASH",
    "PLAYER_REPLAY_CONTRACT_VERSION",
    "SubjectivePlayerReplayBundle",
    "SubjectivePlayerReplayArchive",
    "SubjectiveReplayDelivery",
    "SubjectiveReplaySegment",
    "SubjectiveReplaySegmentEnd",
    "player_replay_contract_summary",
    "player_replay_wire_schema",
]
