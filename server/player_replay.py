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
    EncounterTerminalPresentationFact,
    PLAYER_REPLICATION_CONTRACT_HASH,
    PlayerReplicationWatermarks,
    SubjectiveCombatLogDelivery,
    SubjectiveFrameDelivery,
    SubjectiveReplicationBootstrap,
    validate_ordinary_encounter_terminal_authority,
    validate_reset_encounter_terminal_authority,
)


PLAYER_REPLAY_CONTRACT_VERSION: Final[int] = 2
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
        previous_combat_log_event_cursor = (
            self.bootstrap.combat_log_frames.frames[-1].event_cursor
            if self.bootstrap.combat_log_frames.frames
            else 0
        )
        presentation_ids: set[str] = set()
        encounter_end_seen = subjective_bootstrap_encounter_ended(
            self.bootstrap,
        )
        terminal_source_event_cursor = (
            previous.source_event_cursor if encounter_end_seen else None
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
                terminal_cue = validate_ordinary_encounter_terminal_authority(frame)
                reset_terminal = validate_reset_encounter_terminal_authority(frame)
                if terminal_cue is not None and reset_terminal is not None:
                    raise ValueError(
                        "one replay frame cannot carry both terminal authority branches"
                    )
                if terminal_cue is not None:
                    if not (
                        previous.source_event_cursor
                        < terminal_cue.source_event_cursor
                        == frame.watermarks.source_event_cursor
                    ):
                        raise ValueError(
                            "terminal cue must belong to the newly consumed source interval"
                        )
                    encounter_end_seen = True
                    terminal_source_event_cursor = terminal_cue.source_event_cursor
                elif isinstance(reset_terminal, EncounterTerminalPresentationFact):
                    if not (
                        previous.source_event_cursor
                        < reset_terminal.source_event_cursor
                        == frame.watermarks.source_event_cursor
                    ):
                        raise ValueError(
                            "reset terminal fact must belong to the newly consumed source interval"
                        )
                    encounter_end_seen = True
                    terminal_source_event_cursor = reset_terminal.source_event_cursor
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
            event_barrier = (
                terminal_source_event_cursor
                if terminal_source_event_cursor is not None
                else previous.source_event_cursor
            )
            if frame.event_cursor > event_barrier:
                raise ValueError("replay combat-log barrier exceeds consumed source events")
            if frame.event_cursor < previous_combat_log_event_cursor:
                raise ValueError("replay combat-log event barriers moved backwards")
            expected = previous.model_copy(
                update={"combat_log_cursor": frame.combat_log_cursor}
            )
            if delivery.watermarks != expected:
                raise ValueError(
                    "replay combat-log delivery watermarks do not match its exact slot"
                )
            previous = delivery.watermarks
            previous_combat_log_event_cursor = frame.event_cursor

        if previous != self.through_watermarks:
            raise ValueError("replay through watermarks do not match the delivery stream")
        if self.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED:
            if not encounter_end_seen:
                raise ValueError(
                    "encounter-ended replay segment requires a terminal bootstrap, cue, or reset fact"
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
        previous_through_by_branch: dict[
            tuple[str, str],
            PlayerReplicationWatermarks,
        ] = {}
        combat_log_event_barriers_by_generation: dict[
            str,
            dict[int, int],
        ] = {}
        combat_log_frontier_cursor_by_generation: dict[str, int] = {}
        combat_log_frontier_event_cursor_by_generation: dict[str, int] = {}
        terminal_generation_ids = {
            segment.bootstrap.protocol.generation_id
            for segment in self.segments
            if segment.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
        }
        if not terminal_generation_ids:
            raise ValueError(
                "ended-game player replay requires at least one encounter-ended branch"
            )
        if len(terminal_generation_ids) != 1:
            raise ValueError(
                "all encounter-ended replay branches must use one terminal generation"
            )
        terminal_generation_id = next(iter(terminal_generation_ids))
        ended_branches: set[tuple[str, str]] = set()
        terminal_generation_started = False
        active_generation_id: str | None = None
        departed_generation_ids: set[str] = set()
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
            opening = bootstrap.watermarks
            generation_id = protocol.generation_id
            if generation_id != active_generation_id:
                if generation_id in departed_generation_ids:
                    raise ValueError(
                        "replay generations must form contiguous segment runs"
                    )
                if active_generation_id is not None:
                    departed_generation_ids.add(active_generation_id)
                active_generation_id = generation_id
            if generation_id == terminal_generation_id:
                terminal_generation_started = True
            elif terminal_generation_started:
                raise ValueError(
                    "no replay generation may follow the terminal generation"
                )
            branch_id = (generation_id, segment.runtime_session_id)
            if branch_id in ended_branches:
                raise ValueError("replay branch continued after encounter end")
            previous_through = previous_through_by_branch.get(branch_id)
            if (
                previous_through is not None
                and opening.source_event_cursor
                < previous_through.source_event_cursor
            ):
                raise ValueError("replay segment source history must not regress")
            if (
                previous_through is not None
                and opening.combat_log_cursor
                < previous_through.combat_log_cursor
            ):
                raise ValueError(
                    "replay segment combat-log history must not regress"
                )
            combat_log_event_barrier_by_cursor = (
                combat_log_event_barriers_by_generation.setdefault(
                    generation_id,
                    {},
                )
            )
            combat_log_frontier_cursor = (
                combat_log_frontier_cursor_by_generation.get(generation_id, -1)
            )
            combat_log_frontier_event_cursor = (
                combat_log_frontier_event_cursor_by_generation.get(
                    generation_id,
                    0,
                )
            )
            for frame in bootstrap.combat_log_frames.frames:
                (
                    combat_log_frontier_cursor,
                    combat_log_frontier_event_cursor,
                ) = _remember_combat_log_event_barrier(
                    combat_log_event_barrier_by_cursor,
                    combat_log_cursor=frame.combat_log_cursor,
                    event_cursor=frame.event_cursor,
                    frontier_cursor=combat_log_frontier_cursor,
                    frontier_event_cursor=combat_log_frontier_event_cursor,
                )
            for delivery in segment.deliveries:
                if isinstance(delivery, SubjectiveCombatLogDelivery):
                    (
                        combat_log_frontier_cursor,
                        combat_log_frontier_event_cursor,
                    ) = _remember_combat_log_event_barrier(
                        combat_log_event_barrier_by_cursor,
                        combat_log_cursor=delivery.frame.combat_log_cursor,
                        event_cursor=delivery.frame.event_cursor,
                        frontier_cursor=combat_log_frontier_cursor,
                        frontier_event_cursor=combat_log_frontier_event_cursor,
                    )
            previous_through_by_branch[branch_id] = (
                segment.through_watermarks
            )
            combat_log_frontier_cursor_by_generation[generation_id] = (
                combat_log_frontier_cursor
            )
            combat_log_frontier_event_cursor_by_generation[generation_id] = (
                combat_log_frontier_event_cursor
            )
            if (
                generation_id == terminal_generation_id
                and segment.through_watermarks.source_event_cursor
                > self.terminal_source_event_cursor
            ):
                raise ValueError("replay segment exceeds the terminal source cursor")
            if (
                generation_id == terminal_generation_id
                and segment.through_watermarks.combat_log_cursor
                > self.terminal_combat_log_cursor
            ):
                raise ValueError("replay segment exceeds the terminal combat-log cursor")
            if segment.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED:
                ended_indices.append(segment.segment_index)
                ended_branches.add(branch_id)

        for ended_index in ended_indices:
            terminal = self.segments[ended_index].through_watermarks
            if terminal.source_event_cursor != self.terminal_source_event_cursor:
                raise ValueError("terminal replay branch source cursor is incomplete")
            if terminal.combat_log_cursor != self.terminal_combat_log_cursor:
                raise ValueError("terminal replay branch combat-log cursor is incomplete")
        terminal_identities = tuple(
            _segment_terminal_event_identity(self.segments[index])
            for index in ended_indices
        )
        if any(
            identity is not None and identity[2] != self.encounter_uuid
            for identity in terminal_identities
        ):
            raise ValueError(
                "terminal replay branch belongs to another encounter"
            )
        if len(ended_indices) > 1:
            if (
                any(identity is None for identity in terminal_identities)
                or len(set(terminal_identities)) != 1
            ):
                raise ValueError(
                    "terminal replay branches disagree on terminal event identity"
                )
        return self


def _segment_terminal_event_identity(
    segment: SubjectiveReplaySegment,
) -> tuple[str, str, str, str | None] | None:
    """Return the branch-neutral terminal fact shared by sibling perspectives."""
    for delivery in segment.deliveries:
        if not isinstance(delivery, SubjectiveFrameDelivery):
            continue
        frame = delivery.frame
        ordinary = validate_ordinary_encounter_terminal_authority(frame)
        reset = validate_reset_encounter_terminal_authority(frame)
        authority = ordinary if ordinary is not None else reset
        if authority is not None:
            return (
                "ordinary" if ordinary is not None else "reset",
                str(authority.source_event_uuid),
                authority.encounter_uuid,
                authority.reason,
            )
    return None


def _remember_combat_log_event_barrier(
    known: dict[int, int],
    *,
    combat_log_cursor: int,
    event_cursor: int,
    frontier_cursor: int,
    frontier_event_cursor: int,
) -> tuple[int, int]:
    previous = known.get(combat_log_cursor)
    if previous is not None and previous != event_cursor:
        raise ValueError(
            "retained combat-log cursor changed its canonical event barrier"
        )
    known[combat_log_cursor] = event_cursor
    if combat_log_cursor > frontier_cursor:
        if (
            frontier_cursor >= 0
            and event_cursor < frontier_event_cursor
        ):
            raise ValueError(
                "combat-log event barriers moved backwards across replay segments"
            )
        return combat_log_cursor, event_cursor
    return frontier_cursor, frontier_event_cursor


def validate_subjective_replay_segment_transition(
    previous_segments: Tuple[SubjectiveReplaySegment, ...],
    bootstrap: SubjectiveReplicationBootstrap,
) -> int:
    """Validate one live perspective reset against every retained prior segment."""
    current_generation_id = bootstrap.protocol.generation_id
    generation_segments = tuple(
        segment
        for segment in previous_segments
        if segment.bootstrap.protocol.generation_id == current_generation_id
    )
    if any(
        segment.end_reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
        for segment in generation_segments
    ):
        raise ValueError("replay branch continued after encounter end")
    if generation_segments:
        previous_through = generation_segments[-1].through_watermarks
        opening = bootstrap.watermarks
        if opening.source_event_cursor < previous_through.source_event_cursor:
            raise ValueError("replay segment source history must not regress")
        if opening.combat_log_cursor < previous_through.combat_log_cursor:
            raise ValueError("replay segment combat-log history must not regress")
    known: dict[int, int] = {}
    frontier_cursor = -1
    frontier_event_cursor = 0
    for segment in generation_segments:
        for frame in segment.bootstrap.combat_log_frames.frames:
            frontier_cursor, frontier_event_cursor = (
                _remember_combat_log_event_barrier(
                known,
                combat_log_cursor=frame.combat_log_cursor,
                event_cursor=frame.event_cursor,
                frontier_cursor=frontier_cursor,
                frontier_event_cursor=frontier_event_cursor,
                )
            )
        for delivery in segment.deliveries:
            if isinstance(delivery, SubjectiveCombatLogDelivery):
                frontier_cursor, frontier_event_cursor = (
                    _remember_combat_log_event_barrier(
                    known,
                    combat_log_cursor=delivery.frame.combat_log_cursor,
                    event_cursor=delivery.frame.event_cursor,
                    frontier_cursor=frontier_cursor,
                    frontier_event_cursor=frontier_event_cursor,
                    )
                )
    for frame in bootstrap.combat_log_frames.frames:
        frontier_cursor, frontier_event_cursor = _remember_combat_log_event_barrier(
            known,
            combat_log_cursor=frame.combat_log_cursor,
            event_cursor=frame.event_cursor,
            frontier_cursor=frontier_cursor,
            frontier_event_cursor=frontier_event_cursor,
        )
    return frontier_event_cursor


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
            "segment_history": (
                "within one exact source generation and runtime-session branch each "
                "reset source/log watermark dominates its prior segment through; "
                "simultaneous runtime-session branches remain siblings; overlapping "
                "combat-log cursors "
                "preserve canonical event barriers, and new log cursors keep "
                "nondecreasing event barriers; a new generation starts fresh "
                "cursor and event-barrier authority and occupies one contiguous "
                "segment run which cannot later reappear; an ended runtime-session "
                "branch cannot reopen, every live terminal branch ends independently "
                "at the shared exact terminal watermarks and preserves one shared "
                "ordinary-vs-reset authority mode, source-event UUID, encounter "
                "UUID, and reason across perspective-specific presentation IDs and "
                "projected combatants, and every terminal authority names the "
                "bundle encounter; that terminal generation is "
                "globally final in the archive"
            ),
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
