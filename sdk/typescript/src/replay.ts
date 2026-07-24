import {
  OBJECTIVE_REPLAY_CONTRACT_HASH,
  OBJECTIVE_REPLAY_CONTRACT_VERSION,
  PLAYER_REPLAY_CONTRACT_HASH,
  PLAYER_REPLAY_CONTRACT_VERSION,
  type ObjectiveReplayBundle,
  type PlayerReplicationWatermarks,
  type SubjectivePlayerReplayBundle,
  type SubjectiveReplaySegment,
} from "./generated/contracts.generated.js";
import {
  assertObjectiveCombatLogWindow,
} from "./objectiveDiagnostics.js";
import {
  assertObjectiveGameEventFrame,
  assertObjectiveProtocolIdentity,
} from "./objectiveSse.js";
import {
  assertSubjectiveReplicationBootstrap,
} from "./subjectiveJournal.js";
import {
  assertDominates,
  assertSubjectiveCombatLogDelivery,
  assertSubjectiveFrame,
} from "./subjectiveSse.js";
import { ContractValidationError, decodeModel } from "./validation.js";

/** Decode and semantically authenticate one ended objective replay. */
export function decodeObjectiveReplay(value: unknown): ObjectiveReplayBundle {
  const replay = decodeModel("ObjectiveReplayBundle", value);
  assertObjectiveReplay(replay);
  return replay;
}

/** Decode one membership-scoped replay; objective/raw event payloads are not in its schema. */
export function decodeSubjectivePlayerReplay(value: unknown): SubjectivePlayerReplayBundle {
  const replay = decodeModel("SubjectivePlayerReplayBundle", value);
  assertSubjectivePlayerReplay(replay);
  return replay;
}

export function assertObjectiveReplay(replay: ObjectiveReplayBundle): void {
  if (replay.replay_contract_version !== OBJECTIVE_REPLAY_CONTRACT_VERSION) {
    fail("$objective_replay.replay_contract_version", "unsupported objective replay contract version");
  }
  if (replay.replay_contract_hash !== OBJECTIVE_REPLAY_CONTRACT_HASH) {
    fail("$objective_replay.replay_contract_hash", "objective replay contract hash mismatch");
  }
  assertObjectiveProtocolIdentity(replay.protocol, "$objective_replay.protocol");
  const encounter = replay.seed.world.state.encounter;
  if (encounter === null || encounter.uuid !== replay.encounter_uuid) {
    fail("$objective_replay.seed.world.state.encounter", "seed does not describe the replay encounter");
  }
  if (replay.source_stream_id !== replay.encounter_uuid) {
    fail("$objective_replay.source_stream_id", "source stream must equal the encounter UUID");
  }
  assertObjectiveWorld(replay);
  if (replay.seed.event_cursor >= replay.terminal_event_cursor) {
    fail("$objective_replay.seed.event_cursor", "seed must precede the terminal event cursor");
  }
  if (replay.seed.combat_log_cursor > replay.terminal_combat_log_cursor) {
    fail("$objective_replay.seed.combat_log_cursor", "seed exceeds the terminal log cursor");
  }

  const logs = replay.combat_log_frames;
  assertObjectiveCombatLogWindow(logs);
  if (logs.source_stream_id !== replay.source_stream_id) {
    fail("$objective_replay.combat_log_frames.source_stream_id", "source stream differs from replay");
  }
  if (logs.generation_id !== replay.generation_id) {
    fail("$objective_replay.combat_log_frames.generation_id", "generation differs from replay");
  }
  if (logs.retained_from_cursor !== 0 || logs.from_cursor !== 0) {
    fail("$objective_replay.combat_log_frames", "replay logs must be retained from cursor zero");
  }
  if (logs.through_cursor !== logs.total || logs.total !== replay.terminal_combat_log_cursor) {
    fail("$objective_replay.combat_log_frames", "replay log window is not terminal and complete");
  }
  if (replay.seed.combat_log_cursor > logs.total) {
    fail("$objective_replay.seed.combat_log_cursor", "seed log cursor exceeds retained replay logs");
  }
  if (
    logs.frames
      .slice(0, replay.seed.combat_log_cursor)
      .some((frame) => frame.event_cursor > replay.seed.event_cursor)
  ) {
    fail("$objective_replay.seed", "seed includes a log beyond its event barrier");
  }

  const logEventCursors = logs.frames.map((frame) => frame.event_cursor);
  let previousEventCursor = replay.seed.event_cursor;
  let previousLogCursor = replay.seed.combat_log_cursor;
  replay.events.forEach((frame, index) => {
    const path = `$objective_replay.events[${index}]`;
    assertObjectiveGameEventFrame(frame, path);
    if (frame.source_stream_id !== replay.source_stream_id) {
      fail(`${path}.source_stream_id`, "source stream differs from replay");
    }
    if (frame.generation_id !== replay.generation_id) {
      fail(`${path}.generation_id`, "generation differs from replay");
    }
    if (frame.event_cursor <= previousEventCursor) {
      fail(`${path}.event_cursor`, "completion events must be strictly ordered");
    }
    if (frame.event_cursor > replay.terminal_event_cursor) {
      fail(`${path}.event_cursor`, "event exceeds terminal cursor");
    }
    if (frame.event.phase !== "completion") {
      fail(`${path}.event.phase`, "replay may contain only completion events");
    }
    const exactLogCursor = upperBound(logEventCursors, frame.event_cursor);
    if (frame.combat_log_cursor !== exactLogCursor) {
      fail(`${path}.combat_log_cursor`, "event does not carry its exact combat-log barrier");
    }
    if (frame.combat_log_cursor < previousLogCursor) {
      fail(`${path}.combat_log_cursor`, "event log barriers moved backwards");
    }
    previousEventCursor = frame.event_cursor;
    previousLogCursor = frame.combat_log_cursor;
  });

  const terminal = replay.events.at(-1);
  if (terminal === undefined) {
    fail("$objective_replay.events", "ended replay requires a terminal completion event");
  }
  if (terminal.event_cursor !== replay.terminal_event_cursor) {
    fail("$objective_replay.events", "last completion is not the terminal event cursor");
  }
  if (terminal.event.event_type !== "encounter_end") {
    fail("$objective_replay.events", "last completion must end the encounter");
  }
  if (logs.frames.some((frame) => frame.event_cursor > replay.terminal_event_cursor)) {
    fail("$objective_replay.combat_log_frames", "combat log exceeds terminal event cursor");
  }
}

export function assertSubjectivePlayerReplay(replay: SubjectivePlayerReplayBundle): void {
  if (replay.replay_contract_version !== PLAYER_REPLAY_CONTRACT_VERSION) {
    fail("$subjective_replay.replay_contract_version", "unsupported player replay contract version");
  }
  if (replay.replay_contract_hash !== PLAYER_REPLAY_CONTRACT_HASH) {
    fail("$subjective_replay.replay_contract_hash", "player replay contract hash mismatch");
  }

  const partitions = new Set<string>();
  const ended: number[] = [];
  let previousOpeningSourceCursor = -1;
  replay.segments.forEach((segment, index) => {
    const path = `$subjective_replay.segments[${index}]`;
    if (segment.segment_index !== index) {
      fail(`${path}.segment_index`, "segments must be contiguous and ordered");
    }
    if (segment.membership_id !== replay.membership_id) {
      fail(`${path}.membership_id`, "segment belongs to another membership");
    }
    assertSubjectiveReplaySegment(segment, path);
    const { protocol } = segment.bootstrap;
    const { perspective } = segment.bootstrap;
    if (protocol.source_stream_id !== replay.encounter_uuid) {
      fail(`${path}.bootstrap.protocol.source_stream_id`, "segment belongs to another encounter stream");
    }
    const encounter = segment.bootstrap.world.state.encounter;
    if (encounter === null || encounter.uuid !== replay.encounter_uuid) {
      fail(`${path}.bootstrap.world.state.encounter`, "segment does not describe the replay encounter");
    }
    const partition = JSON.stringify([
      protocol.generation_id,
      perspective.perspective_epoch_id,
    ]);
    if (partitions.has(partition)) {
      fail(path, "generation-and-perspective partition is repeated");
    }
    partitions.add(partition);
    const opening = segment.bootstrap.watermarks.source_event_cursor;
    if (opening < previousOpeningSourceCursor) {
      fail(`${path}.bootstrap.watermarks.source_event_cursor`, "segment openings moved backwards");
    }
    previousOpeningSourceCursor = opening;
    if (segment.through_watermarks.source_event_cursor > replay.terminal_source_event_cursor) {
      fail(`${path}.through_watermarks.source_event_cursor`, "segment exceeds terminal source cursor");
    }
    if (segment.through_watermarks.combat_log_cursor > replay.terminal_combat_log_cursor) {
      fail(`${path}.through_watermarks.combat_log_cursor`, "segment exceeds terminal log cursor");
    }
    if (segment.end_reason === "encounter_ended") ended.push(index);
  });

  if (ended.length !== 1 || ended[0] !== replay.segments.length - 1) {
    fail("$subjective_replay.segments", "exactly the final segment must end the encounter");
  }
  const terminal = replay.segments.at(-1)?.through_watermarks;
  if (terminal === undefined) {
    fail("$subjective_replay.segments", "ended replay requires at least one segment");
  }
  if (terminal.source_event_cursor !== replay.terminal_source_event_cursor) {
    fail("$subjective_replay.terminal_source_event_cursor", "terminal source cursor is incomplete");
  }
  if (terminal.combat_log_cursor !== replay.terminal_combat_log_cursor) {
    fail("$subjective_replay.terminal_combat_log_cursor", "terminal log cursor is incomplete");
  }
}

export function assertSubjectiveReplaySegment(
  segment: SubjectiveReplaySegment,
  path = "$subjective_replay.segment",
): void {
  assertSubjectiveReplicationBootstrap(segment.bootstrap);
  const { protocol, perspective } = segment.bootstrap;
  let previous = segment.bootstrap.watermarks;
  const presentationIds = new Set<string>();
  let encounterEndSeen = segment.bootstrap.world.state.encounter?.state === "ended";

  segment.deliveries.forEach((delivery, index) => {
    const deliveryPath = `${path}.deliveries[${index}]`;
    if (delivery.kind === "frame") {
      if (encounterEndSeen) {
        fail(deliveryPath, "observation frame follows encounter end");
      }
      const frame = delivery.frame;
      assertSubjectiveFrame(frame);
      assertSubjectiveIdentity(frame, protocol.source_stream_id, protocol.generation_id, perspective.perspective_epoch_id, deliveryPath);
      if (frame.watermarks.observation_cursor !== previous.observation_cursor + 1) {
        fail(`${deliveryPath}.frame.watermarks.observation_cursor`, "observation frames are not contiguous");
      }
      if (frame.presentation_from_cursor !== previous.presentation_cursor) {
        fail(`${deliveryPath}.frame.presentation_from_cursor`, "presentation windows are not contiguous");
      }
      if (frame.watermarks.combat_log_cursor !== previous.combat_log_cursor) {
        fail(`${deliveryPath}.frame.watermarks.combat_log_cursor`, "frame advanced the log cursor");
      }
      assertDominates(frame.watermarks, previous, `${deliveryPath}.frame.watermarks`);
      for (const cue of frame.presentation) {
        if (presentationIds.has(cue.presentation_id)) {
          fail(deliveryPath, "presentation ID is reused across replay frames");
        }
        presentationIds.add(cue.presentation_id);
      }
      const terminalCues = frame.presentation.filter(
        (cue) => cue.kind === "encounter" && cue.transition === "end",
      );
      if (terminalCues.length > 1) {
        fail(deliveryPath, "one frame cannot end the encounter twice");
      }
      if (terminalCues.length === 1) encounterEndSeen = true;
      previous = frame.watermarks;
      return;
    }

    assertSubjectiveCombatLogDelivery(delivery);
    const frame = delivery.frame;
    assertSubjectiveIdentity(frame, protocol.source_stream_id, protocol.generation_id, perspective.perspective_epoch_id, deliveryPath);
    if (frame.combat_log_cursor !== previous.combat_log_cursor + 1) {
      fail(`${deliveryPath}.frame.combat_log_cursor`, "combat-log frames are not contiguous");
    }
    if (frame.event_cursor > previous.source_event_cursor) {
      fail(`${deliveryPath}.frame.event_cursor`, "combat-log barrier exceeds consumed source events");
    }
    const expected = { ...previous, combat_log_cursor: frame.combat_log_cursor };
    if (!equalWatermarks(delivery.watermarks, expected)) {
      fail(`${deliveryPath}.watermarks`, "combat-log delivery does not match its exact slot");
    }
    previous = delivery.watermarks;
  });

  if (!equalWatermarks(previous, segment.through_watermarks)) {
    fail(`${path}.through_watermarks`, "through watermarks differ from delivery stream");
  }
  if (segment.end_reason === "encounter_ended" && !encounterEndSeen) {
    fail(`${path}.end_reason`, "encounter-ended segment has no terminal bootstrap or cue");
  }
  if (segment.end_reason === "perspective_retired" && encounterEndSeen) {
    fail(`${path}.end_reason`, "terminal segment is labeled perspective-retired");
  }
}

function assertObjectiveWorld(replay: ObjectiveReplayBundle): void {
  const entities = new Set(replay.seed.world.state.entities.map((entity) => entity.uuid));
  for (const entityUuid of Object.keys(replay.seed.world.equipment_by_entity)) {
    if (!entities.has(entityUuid)) {
      fail("$objective_replay.seed.world.equipment_by_entity", "equipment references an absent entity");
    }
  }
}

function assertSubjectiveIdentity(
  value: { readonly source_stream_id: string; readonly generation_id: string; readonly perspective_epoch_id: string },
  sourceStreamId: string,
  generationId: string,
  perspectiveEpochId: string,
  path: string,
): void {
  if (
    value.source_stream_id !== sourceStreamId
    || value.generation_id !== generationId
    || value.perspective_epoch_id !== perspectiveEpochId
  ) {
    fail(path, "delivery identity differs from segment bootstrap");
  }
}

function equalWatermarks(
  left: PlayerReplicationWatermarks,
  right: PlayerReplicationWatermarks,
): boolean {
  return left.source_event_cursor === right.source_event_cursor
    && left.observation_cursor === right.observation_cursor
    && left.presentation_cursor === right.presentation_cursor
    && left.combat_log_cursor === right.combat_log_cursor;
}

function upperBound(sorted: ReadonlyArray<number>, value: number): number {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if ((sorted[middle] ?? Number.POSITIVE_INFINITY) <= value) low = middle + 1;
    else high = middle;
  }
  return low;
}

function fail(path: string, message: string): never {
  throw new ContractValidationError(path, message);
}
